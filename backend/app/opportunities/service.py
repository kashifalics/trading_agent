"""Read-side helpers: serialisation, ranking, correlation clustering and the page summary."""
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.jsonutil import to_jsonable
from app.database.base import utcnow
from app.database.models import (
    BacktestRun,
    Instrument,
    MarketScan,
    OpportunityStatusHistory,
    TimeframeAnalysis,
    TradeOpportunity,
)
from app.opportunities.config import (
    PROFILES,
    SCORE_LABEL,
    STYLE_ORDER,
    VALIDATION_RANK,
    profile_config,
)
from app.opportunities.validation import load_validation, validation_overview

OPPORTUNITY_COLUMNS = ("direction", "status", "setup_timeframe", "setup_type", "risk_reward", "evidence_score", "validation_status",
                       "expected_holding_seconds")


def latest_scan(session: Session, finished_only: bool = True) -> MarketScan | None:
    q = select(MarketScan).order_by(MarketScan.id.desc())
    if finished_only:
        q = q.where(MarketScan.status.in_(("completed", "completed_with_errors")))
    return session.scalar(q.limit(1))


def opp_out(o: TradeOpportunity, symbol: str, detail: bool = False) -> dict:
    ev = o.evidence or {}
    setup = ev.get("setup") or {}
    out: dict[str, Any] = {
        "id": o.id, "symbol": symbol, "style": o.style, "is_headline": o.is_headline, "scan_id": o.scan_id, "last_scan_id": o.last_scan_id,
        **{k: getattr(o, k) for k in OPPORTUNITY_COLUMNS},
        "entry_low": o.entry_low, "entry_high": o.entry_high, "stop_loss": o.stop_loss, "take_profit_1": o.take_profit_1,
        "take_profit_2": o.take_profit_2, "take_profit_3": o.take_profit_3, "invalidation": o.invalidation,
        "side": setup.get("direction"),  # BUY/SELL of the underlying setup, also for non-actionable watchlist rows
        "actionable": bool(ev.get("actionable")), "score_label": SCORE_LABEL,
        "signal_ts": o.signal_ts, "expires_at": o.expires_at, "created_at": o.created_at, "last_seen_at": o.last_seen_at,
        "provider": ev.get("provider"), "lean": ev.get("lean"), "wait_reasons": (ev.get("wait_reasons") or [])[:6],
        "thesis": ev.get("thesis"), "conditions": setup.get("conditions"),
    }
    if detail:
        out["evidence"] = ev
    return to_jsonable(out)


def rank_key(r: dict) -> tuple:
    live = r["direction"] in ("BUY", "SELL")
    tier = 2 if live else 1 if r["status"] == "watchlist" else 0
    return (tier, VALIDATION_RANK.get(r["validation_status"] or "untested", 2), r["evidence_score"] or 0.0, r["risk_reward"] or 0.0)


def rank_rows(rows: list[dict]) -> list[dict]:
    """Highest tier first: actionable, then watchlist, then WAIT. Within a tier a validated setup outranks an unvalidated one
    whatever its technical score. Same-instrument same-direction setups are flagged as ONE exposure, not independent ideas."""
    ordered = sorted(rows, key=rank_key, reverse=True)
    seen: dict[tuple, int] = {}
    n = 0
    for r in ordered:
        if r["direction"] == "WAIT" and r["status"] != "watchlist":
            r["rank"], r["correlated_with_rank"] = None, None
            continue
        n += 1
        r["rank"] = n
        side = r["side"] or r["direction"]
        k = (r["symbol"], side)
        r["correlated_with_rank"] = seen.get(k)
        seen.setdefault(k, n)
    return ordered


def headline_rows(session: Session, scan: MarketScan) -> list[dict]:
    rows = session.execute(select(TradeOpportunity, Instrument.canonical_symbol).join(Instrument, Instrument.id == TradeOpportunity.instrument_id)
                           .where(TradeOpportunity.last_scan_id == scan.id, TradeOpportunity.is_headline.is_(True))).all()
    return [opp_out(o, sym) for o, sym in rows]


def next_scan_info(session: Session) -> dict:
    s = get_settings()
    last = session.scalar(select(MarketScan).where(MarketScan.trigger == "scheduled").order_by(MarketScan.id.desc()).limit(1))
    nxt = (last.created_at + timedelta(minutes=s.opportunity_scan_interval_minutes)) if (last and s.opportunity_scan_interval_minutes) else None
    return {"enabled": s.opportunity_scan_interval_minutes > 0, "interval_minutes": s.opportunity_scan_interval_minutes,
            "next_run_estimate": nxt, "last_scheduled_status": last.status if last else None,
            "note": "Scheduled scans only sync providers listed in OPPORTUNITY_REFRESH_PROVIDERS; others are scanned from stored candles."}


def summary(session: Session) -> dict:
    scan = latest_scan(session)
    running = session.scalar(select(MarketScan).where(MarketScan.status.in_(("queued", "running"))).order_by(MarketScan.id.desc()).limit(1))
    base = {"scan": None, "running_scan": to_jsonable({"id": running.id, "status": running.status, "started_at": running.started_at}) if running else None,
            "next_scan": to_jsonable(next_scan_info(session)), "score_label": SCORE_LABEL, "styles": [], "ranking": [], "instruments": []}
    if scan is None:
        return base
    rows = headline_rows(session, scan)
    ranked = rank_rows(rows)
    styles = []
    for key in STYLE_ORDER:
        best = next((r for r in ranked if r["style"] == key and r["rank"] is not None), None)
        wait = next((r for r in ranked if r["style"] == key), None)
        styles.append({"style": key, "label": PROFILES[key].label, "scope": PROFILES[key].scope, "best": best, "fallback_wait": None if best else wait,
                       "setup_timeframes": list(PROFILES[key].setup_tfs)})
    base.update({"scan": to_jsonable({"id": scan.id, "status": scan.status, "trigger": scan.trigger, "started_at": scan.started_at,
                                      "finished_at": scan.finished_at, "summary": scan.summary, "config_version": scan.config_version,
                                      "code_version": scan.code_version}),
                 "styles": styles, "ranking": ranked, "instruments": scan.instruments or []})
    return base


def timeframe_rows(session: Session, symbol: str, scan_id: int) -> list[dict]:
    inst = session.scalar(select(Instrument).where(Instrument.canonical_symbol == symbol.upper()))
    if not inst:
        return []
    rows = session.scalars(select(TimeframeAnalysis).where(TimeframeAnalysis.scan_id == scan_id, TimeframeAnalysis.instrument_id == inst.id)).all()
    out = []
    for r in rows:
        res = r.result
        if res is None and r.reused_from_id:
            src = session.get(TimeframeAnalysis, r.reused_from_id)
            res = src.result if src else None
        out.append(to_jsonable({"timeframe": r.timeframe, "status": r.status, "n_bars": r.n_bars, "first_ts": r.first_ts, "last_ts": r.last_ts,
                                "derived_from": r.derived_from, "reused_from_analysis_id": r.reused_from_id, "error": r.error, "analysis": res}))
    return out


def status_history(session: Session, opp_id: int) -> list[dict]:
    rows = session.scalars(select(OpportunityStatusHistory).where(OpportunityStatusHistory.opportunity_id == opp_id)
                           .order_by(OpportunityStatusHistory.id)).all()
    return to_jsonable([{"status": r.status, "at": r.at, "note": r.note} for r in rows])


def validation_payload(session: Session, user_id: int) -> dict:
    store = load_validation()
    refs = session.execute(select(BacktestRun, Instrument.canonical_symbol).join(Instrument, Instrument.id == BacktestRun.instrument_id)
                           .where(BacktestRun.user_id == user_id, BacktestRun.status == "completed").order_by(BacktestRun.id.desc()).limit(25)).all()
    keep = ("total_return_pct", "profit_factor", "win_rate", "n_trades", "expectancy_r", "max_drawdown_pct", "sharpe_annualized")
    return to_jsonable({
        "meta": store.get("meta", {}), "results": validation_overview(),
        "reference_backtests": [{"id": b.id, "symbol": sym, "strategy": b.strategy, "timeframe": b.timeframe,
                                 "metrics": {k: (b.metrics or {}).get(k) for k in keep}, "created_at": b.created_at} for b, sym in refs],
        "config": profile_config(), "note": "Reference backtests are shown exactly as stored; nothing is hidden, re-tuned or overwritten."})


__all__ = ["utcnow"]
