"""Multi-timeframe scan orchestrator.

scan -> per instrument: availability check -> 14 independent timeframe analyses (cached by content signature) ->
per trading style: candidate setups on the style's timeframes -> analogues + evidence score + validation lookup ->
headline opportunity (or an explicit WAIT) -> deduplicated persistence + status lifecycle.

Principles: database reads only unless `refresh_data` is requested (provider quotas are never spent implicitly);
unchanged data is never re-analysed (signature cache, then style-level cache); nothing is invented when data is missing.
"""
import hashlib
import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError, UnsupportedError
from app.core.jsonutil import to_jsonable
from app.database.base import utcnow
from app.database.models import Candle as CandleRow
from app.database.models import (
    DataProvider,
    Instrument,
    MarketScan,
    OpportunityStatusHistory,
    ProviderInstrument,
    TimeframeAnalysis,
    TradeOpportunity,
)
from app.market_data.ingestion.service import get_instrument, resolve_mapping
from app.opportunities.analogue import build_context, setup_analogues
from app.opportunities.analysis import TF, build_bias, prepare_tf, provider_configured, tf_features, tf_result
from app.opportunities.config import (
    ALL_TIMEFRAMES,
    BIAS_TFS,
    CONFIG_VERSION,
    PROFILES,
    STYLE_ORDER,
    VALIDATION_RANK,
    StyleProfile,
    profile_config,
    round_trip_cost,
)
from app.opportunities.evidence import build_evidence
from app.opportunities.scoring import ScoreInputs, score_setup
from app.opportunities.setup import Bias, Setup, SetupOutcome, generate_setup
from app.opportunities.validation import load_validation, strategy_validation
from app.research.experiments import code_version

log = logging.getLogger(__name__)
OPEN = ("watchlist", "waiting_for_confirmation", "entry_triggered")
MAX_EXTRA_CANDIDATES = 3
REFRESH_ORDER = ("1D", "4H", "1H", "15m", "5m", "1W", "30m", "2H", "1m", "3m")


# ------------------------------------------------------------------------------------------ scan lifecycle
def create_scan(session: Session, user_id: int | None, params: dict, trigger: str = "manual") -> tuple[MarketScan, bool]:
    """Returns (scan, deduplicated). A scan that is already queued/running (started in the last 30 min) is reused, so repeated
    clicks / overlapping schedules never stack duplicate work."""
    cutoff = utcnow() - timedelta(minutes=30)
    live = session.scalar(select(MarketScan).where(MarketScan.status.in_(("queued", "running")), MarketScan.created_at >= cutoff)
                          .order_by(MarketScan.id.desc()).limit(1))
    if live:
        return live, True
    scan = MarketScan(user_id=user_id, status="queued", trigger=trigger, params=to_jsonable(params), config_version=CONFIG_VERSION)
    session.add(scan)
    session.commit()
    return scan, False


def run_scan_job(scan_id: int) -> None:
    from app.database.session import session_scope

    with session_scope() as session:
        scan = session.get(MarketScan, scan_id)
        if scan is None:
            return
        try:
            execute_scan(session, scan)
        except Exception as exc:  # noqa: BLE001
            log.exception("scan %s crashed", scan_id)
            session.rollback()
            scan = session.get(MarketScan, scan_id)
            scan.status, scan.error, scan.finished_at = "failed", f"internal error ({exc.__class__.__name__})", utcnow()
            session.commit()


def execute_scan(session: Session, scan: MarketScan) -> MarketScan:
    s = get_settings()
    params = scan.params or {}
    symbols = [x.upper() for x in (params.get("symbols") or s.opportunity_list)]
    scan.status, scan.started_at, scan.code_version = "running", utcnow(), {**code_version(), "config_version": CONFIG_VERSION}
    session.commit()
    infos, errors = [], 0
    for sym in symbols:
        try:
            info = scan_instrument(session, scan, sym, bool(params.get("refresh_data")), params.get("refresh_providers"))
        except Exception as exc:  # noqa: BLE001 - one instrument must not abort the others
            log.exception("scan %s: instrument %s failed", scan.id, sym)
            session.rollback()
            info = {"symbol": sym, "status": "failed", "reason": f"{exc.__class__.__name__}: {exc}"[:300]}
        errors += info["status"] == "failed"
        infos.append(info)
    scan = session.get(MarketScan, scan.id)
    done = [i for i in infos if i["status"] == "scanned"]
    tf_total = sum(len(i.get("timeframes", [])) for i in done)
    tf_ok = sum(1 for i in done for t in i["timeframes"] if t["status"] == "completed")
    opps = session.scalars(select(TradeOpportunity).where(TradeOpportunity.last_scan_id == scan.id, TradeOpportunity.is_headline.is_(True))).all()
    stale = [t["stale_bars"] for i in done for t in i["timeframes"] if t.get("stale_bars") is not None and t["status"] == "completed"]
    scan.instruments = to_jsonable(infos)
    scan.summary = to_jsonable({
        "instruments_requested": len(symbols), "instruments_scanned": len(done),
        "instruments_unavailable": [i["symbol"] for i in infos if i["status"] in ("unavailable", "unsupported")],
        "timeframes_completed": tf_ok, "timeframes_total": tf_total,
        "opportunities_actionable": sum(1 for o in opps if o.direction in ("BUY", "SELL")),
        "opportunities_watchlist": sum(1 for o in opps if o.status == "watchlist"),
        "wait": sum(1 for o in opps if o.direction == "WAIT"),
        "data_freshness": {"max_stale_bars": max(stale) if stale else None, "median_stale_bars": float(np.median(stale)) if stale else None},
        "latest_candle_ts": max((t["last_ts"] for i in done for t in i["timeframes"] if t.get("last_ts")), default=None)})
    scan.status = "failed" if (errors and not done) else "completed_with_errors" if errors else "completed"
    scan.finished_at = utcnow()
    session.commit()
    return scan


# ------------------------------------------------------------------------------------------ one instrument
VIEW_KEYS = ("trend", "bias", "last_break", "last_break_bars_ago", "zone", "range_position", "summary", "last_close", "atr")


def _tf_info(t: TF, reused: bool, res: dict | None = None) -> dict:
    """Per-timeframe status for the page. `view` is the descriptive market read (trend, last break, premium/discount) so a scan that finds no
    setup still shows what every timeframe is doing."""
    info = {"timeframe": t.tf, "status": t.status, "n_bars": t.n_bars, "last_ts": int(t.bars.t[-1]) if t.bars is not None and len(t.bars) else None,
            "stale_bars": t.stale_bars, "derived_from": t.derived_from, "reason": t.reason or t.error, "reused": reused}
    if res and t.ok:
        info["view"] = {k: res.get(k) for k in VIEW_KEYS}
    return info


def _refresh(session: Session, inst: Instrument, prov: DataProvider, pi: ProviderInstrument) -> list[str]:
    from app.services.data_service import ensure_data

    notes = []
    for tf in REFRESH_ORDER[: get_settings().opportunity_max_sync_tfs]:
        notes += ensure_data(session, inst, prov, pi, tf, 1500, True)
    return notes


def _has_candles(session: Session, inst: Instrument, prov: DataProvider) -> bool:
    return session.scalar(select(CandleRow.id).where(CandleRow.instrument_id == inst.id, CandleRow.provider_id == prov.id).limit(1)) is not None


def scan_instrument(session: Session, scan: MarketScan, symbol: str, refresh: bool, refresh_providers: list[str] | None) -> dict:
    try:
        inst = get_instrument(session, symbol)
        inst, prov, pi = resolve_mapping(session, symbol)
    except (NotFoundError, UnsupportedError) as exc:
        return {"symbol": symbol, "status": "unsupported", "reason": exc.message}
    configured, why = provider_configured(prov.code)
    base = {"symbol": inst.canonical_symbol, "provider": prov.code, "provider_status": pi.status, "provider_symbol": pi.provider_symbol,
            "mapping_notes": pi.notes}
    stored = _has_candles(session, inst, prov)
    notes: list[str] = []
    if refresh and configured and (refresh_providers is None or prov.code in refresh_providers):
        notes += _refresh(session, inst, prov, pi)
        stored = _has_candles(session, inst, prov)
    if not stored:
        reason = why or "no stored candles yet: run a sync for this instrument first"
        return {**base, "status": "unavailable", "reason": reason + (" - no verified data source" if why else ""), "notes": notes}

    now = utcnow()
    tfs: dict[str, TF] = {}
    infos = []
    for code in ALL_TIMEFRAMES:
        t = prepare_tf(session, inst, prov, pi, code, now)
        tfs[code] = t
        reused, res = False, None
        row = TimeframeAnalysis(scan_id=scan.id, instrument_id=inst.id, provider_id=prov.id, timeframe=code, status=t.status,
                                signature=t.signature, n_bars=t.n_bars, first_ts=t.first_ts(), last_ts=t.last_ts(),
                                derived_from=t.derived_from, error=t.error)
        if t.ok:
            prev = session.scalar(select(TimeframeAnalysis).where(
                TimeframeAnalysis.instrument_id == inst.id, TimeframeAnalysis.timeframe == code, TimeframeAnalysis.status == "completed",
                TimeframeAnalysis.signature == t.signature).order_by(TimeframeAnalysis.id.desc()).limit(1))
            if prev is not None:
                row.reused_from_id, reused = prev.reused_from_id or prev.id, True
                root = session.get(TimeframeAnalysis, row.reused_from_id)
                res = root.result if root is not None else None
            else:
                try:
                    row.result = res = to_jsonable(tf_result(t))
                except Exception as exc:  # noqa: BLE001
                    t.status, t.error = "failed", f"{exc.__class__.__name__}: {exc}"[:300]
                    row.status, row.error = "failed", t.error
        else:
            row.result = {"reason": t.reason or t.error}
        session.add(row)
        infos.append(_tf_info(t, reused, res))
    session.commit()

    reconcile(session, scan, inst, tfs)
    style_out = {}
    for style in STYLE_ORDER:
        style_out[style] = scan_style(session, scan, inst, prov, PROFILES[style], tfs)
    return {**base, "status": "scanned", "timeframes": infos, "styles": style_out, "notes": notes}


# ------------------------------------------------------------------------------------------ style level
def _used_tfs(prof: StyleProfile) -> set[str]:
    used = set(prof.setup_tfs)
    for c in prof.setup_tfs:
        used |= set(BIAS_TFS.get(c, ()))
    return used


def _style_key(prof: StyleProfile, symbol: str, tfs: dict[str, TF]) -> str:
    sigs = "|".join(f"{c}:{tfs[c].signature or tfs[c].status}" for c in sorted(_used_tfs(prof)) if c in tfs)
    val = load_validation().get("meta", {}).get("generated_at", "none")
    return hashlib.sha256(f"{CONFIG_VERSION}|{symbol}|{prof.key}|{val}|{sigs}".encode()).hexdigest()[:32]


def _zone_position(t: TF, poi: dict) -> float | None:
    pdz = t.pa.premium_discount
    if not pdz or pdz.high <= pdz.low:
        return None
    return float((((poi["low"] + poi["high"]) / 2) - pdz.low) / (pdz.high - pdz.low))


def _evaluate_candidate(symbol: str, prof: StyleProfile, code: str, t: TF, out: SetupOutcome, bias: Bias) -> dict:
    s = out.setup
    ctx = t.actx.get(prof.key)
    if ctx is None:
        ctx = t.actx[prof.key] = build_context(t.bars, t.pa, prof) or False
    an = setup_analogues(t.bars, t.pa, ctx or None, prof, s.direction, symbol, code)
    d = 1 if s.direction == "BUY" else -1
    sd = "bullish" if d == 1 else "bearish"
    last = len(t.bars) - 1
    feats = tf_features(t)
    val = strategy_validation(symbol, prof.key, code)
    sc = score_setup(ScoreInputs(
        setup=s, bias=bias, profile=prof, trend=int(t.pa.trend[last]),
        recent_break_same_dir=any(e.direction == sd and last - e.idx <= 20 for e in t.pa.breaks),
        zone_position=_zone_position(t, s.poi), poi_touches=s.poi.get("touches"), feats=feats, analogue=an, quality=t.quality, validation=val))
    return {"code": code, "outcome": out, "bias": bias, "analogue": an, "score": sc, "validation": val, "tf": t}


def _lean_tf(prof: StyleProfile, tfs: dict[str, TF]) -> str | None:
    ok = [c for c in prof.setup_tfs if tfs[c].ok and tfs[c].n_bars >= prof.min_bars and not (prof.needs_native_resolution and tfs[c].derived_from)]
    ok = ok or [c for c in prof.setup_tfs if tfs[c].ok]
    if not ok:
        return None
    return next((c for c in ok if int(tfs[c].pa.trend[-1]) != 0), ok[0])


def scan_style(session: Session, scan: MarketScan, inst: Instrument, prov: DataProvider, prof: StyleProfile, tfs: dict[str, TF]) -> dict:
    symbol = inst.canonical_symbol
    key = _style_key(prof, symbol, tfs)
    latest = session.scalar(select(func.max(TradeOpportunity.last_scan_id)).where(TradeOpportunity.instrument_id == inst.id,
                                                                                 TradeOpportunity.style == prof.key))
    if latest is not None:
        prev = session.scalars(select(TradeOpportunity).where(TradeOpportunity.instrument_id == inst.id, TradeOpportunity.style == prof.key,
                                                             TradeOpportunity.last_scan_id == latest)).all()
        if prev and all(o.style_key == key for o in prev) and not any(o.status in ("invalidated", "expired") for o in prev if o.is_headline):
            now = utcnow()
            for o in prev:
                o.last_scan_id, o.last_seen_at = scan.id, now
            session.commit()
            head = next((o for o in prev if o.is_headline), prev[0])
            return {"cache": "unchanged_data_reused", "headline": head.id, "direction": head.direction, "status": head.status}

    cost = round_trip_cost(symbol)
    cands, notes, leans = [], {}, []
    for code in prof.setup_tfs:
        t = tfs[code]
        if not t.ok:
            notes[code] = t.reason or t.error or t.status
            continue
        if t.n_bars < prof.min_bars:
            notes[code] = f"only {t.n_bars} complete candles ({prof.label} needs >= {prof.min_bars})"
            continue
        if prof.needs_native_resolution and t.derived_from:
            notes[code] = f"built from {t.derived_from} candles; {prof.label.lower()} requires native-resolution data"
            continue
        if prof.key == "scalping" and t.stale_bars is not None and t.stale_bars > prof.max_stale_bars:
            notes[code] = f"latest candle is {t.stale_bars:.0f} bars old; too stale to scalp"
            continue
        bias = build_bias(tfs, code)
        out = generate_setup(t.bars, t.pa, t.cx, bias, prof, cost)
        notes[code] = out.wait_reasons
        leans.append((code, out.lean, bias))
        if out.setup:
            cands.append(_evaluate_candidate(symbol, prof, code, t, out, bias))

    cands.sort(key=lambda c: (VALIDATION_RANK[c["validation"]["status"]], c["score"]["score"]), reverse=True)
    persisted = []
    if cands:
        for i, c in enumerate(cands[: 1 + MAX_EXTRA_CANDIDATES]):
            persisted.append(_persist_candidate(session, scan, inst, prov, prof, key, tfs, c, headline=(i == 0)))
        head = persisted[0]
    else:
        code = _lean_tf(prof, tfs)
        bias = build_bias(tfs, code) if code else Bias()
        lean = next((ln for c, ln, _ in leans if c == code), 0) or bias.direction
        reasons = []
        for c, n in notes.items():
            reasons += [f"{c}: {r}" for r in (n if isinstance(n, list) else [n])]
        validation = strategy_validation(symbol, prof.key, code or prof.setup_tfs[0])
        analogue = {"available": False, "reason": "no candidate setup, so no direction-specific analogue search was run"}
        ev = build_evidence(symbol=symbol, provider=prov.code, prof=prof, tfs=tfs, setup_tf=code, setup=None, lean=lean,
                            wait_reasons=reasons[:14] or ["no timeframe for this style has enough usable data"], bias=bias,
                            analogue=analogue, score=None, validation=validation, actionable=False)
        head = _upsert(session, scan, inst, prov, prof, key, f"{symbol}:{prof.key}:WAIT", dict(
            direction="WAIT", status="none", setup_timeframe=code, setup_type=None, validation_status=validation["status"], evidence=ev,
            signal_ts=tfs[code].last_ts() if code else None), headline=True)
        persisted = [head]
    session.commit()
    return {"cache": "recomputed", "headline": head.id, "direction": head.direction, "status": head.status,
            "candidates": len(cands), "score": head.evidence_score}


# ------------------------------------------------------------------------------------------ persistence
def _dec(x):
    return None if x is None else float(x)


def _upsert(session: Session, scan: MarketScan, inst: Instrument, prov: DataProvider, prof: StyleProfile, style_key: str, dedupe_key: str,
            fields: dict, headline: bool) -> TradeOpportunity:
    now = utcnow()
    existing = session.scalar(select(TradeOpportunity).where(
        TradeOpportunity.instrument_id == inst.id, TradeOpportunity.dedupe_key == dedupe_key,
        TradeOpportunity.status.in_(OPEN + ("none",))).order_by(TradeOpportunity.id.desc()).limit(1))
    if headline:
        for o in session.scalars(select(TradeOpportunity).where(TradeOpportunity.instrument_id == inst.id, TradeOpportunity.style == prof.key,
                                                               TradeOpportunity.is_headline.is_(True))):
            o.is_headline = False
    if existing is not None:
        old = existing.status
        if old == "entry_triggered" and fields.get("status") in ("waiting_for_confirmation", "watchlist"):
            fields = {**fields, "status": old, "direction": existing.direction}  # a trigger that happened is never un-happened
        keep = {"entry_low", "entry_high", "stop_loss", "take_profit_1", "take_profit_2", "take_profit_3", "invalidation", "risk_reward",
                "setup_timeframe", "setup_type", "expected_holding_seconds"}
        for k, v in fields.items():
            if k in keep and existing.entry_low is not None:
                continue  # an existing plan's levels never drift between scans
            setattr(existing, k, v)
        existing.last_scan_id, existing.last_seen_at, existing.style_key, existing.is_headline = scan.id, now, style_key, headline
        if existing.status != old:
            session.add(OpportunityStatusHistory(opportunity_id=existing.id, status=existing.status, at=now, note={"scan_id": scan.id}))
        session.flush()
        return existing
    o = TradeOpportunity(scan_id=scan.id, last_scan_id=scan.id, instrument_id=inst.id, provider_id=prov.id, style=prof.key,
                         dedupe_key=dedupe_key, style_key=style_key, is_headline=headline, created_at=now, last_seen_at=now, **fields)
    session.add(o)
    session.flush()
    session.add(OpportunityStatusHistory(opportunity_id=o.id, status=o.status, at=now, note={"scan_id": scan.id, "created": True}))
    return o


def _persist_candidate(session: Session, scan: MarketScan, inst: Instrument, prov: DataProvider, prof: StyleProfile, style_key: str,
                       tfs: dict[str, TF], c: dict, headline: bool) -> TradeOpportunity:
    s: Setup = c["outcome"].setup
    t: TF = c["tf"]
    code = c["code"]
    sc = c["score"]
    actionable = sc["score"] >= prof.min_evidence
    step = t.bars.step
    as_of = datetime.fromtimestamp(int(t.bars.t[-1]) + step, tz=timezone.utc)
    reasons = list(c["outcome"].wait_reasons)
    if not actionable:
        reasons.append(f"evidence score {sc['score']:.0f} is below the {prof.min_evidence:.0f} needed to publish an actionable {prof.label.lower()} setup"
                       + (f" ({sc['cap']['reason']})" if sc["cap"]["applied"] else ""))
    ev = build_evidence(symbol=inst.canonical_symbol, provider=prov.code, prof=prof, tfs=tfs, setup_tf=code, setup=s, lean=1 if s.direction == "BUY" else -1,
                        wait_reasons=reasons, bias=c["bias"], analogue=c["analogue"], score=sc, validation=c["validation"], actionable=actionable,
                        note=None if actionable else "Reference levels only: the evidence does not justify an actionable trade.")
    tg = [x["price"] for x in s.targets] + [None, None, None]
    fields = dict(
        direction=s.direction if actionable else "WAIT", status=s.status if actionable else "watchlist", setup_timeframe=code, setup_type=s.setup_type,
        entry_low=s.entry_low, entry_high=s.entry_high, stop_loss=s.stop_loss, take_profit_1=tg[0], take_profit_2=tg[1], take_profit_3=tg[2],
        invalidation=s.invalidation, risk_reward=s.risk_reward, evidence_score=sc["score"], validation_status=c["validation"]["status"],
        expected_holding_seconds=prof.horizon_bars * step, signal_ts=as_of, expires_at=as_of + timedelta(seconds=prof.expiry_bars * step),
        evidence=to_jsonable(ev))
    key = f"{inst.canonical_symbol}:{prof.key}:{s.direction}:{code}:{s.setup_type}:{s.anchor_ts}"
    return _upsert(session, scan, inst, prov, prof, style_key, key, fields, headline)


# ------------------------------------------------------------------------------------------ lifecycle
def reconcile(session: Session, scan: MarketScan, inst: Instrument, tfs: dict[str, TF]) -> None:
    """Close open opportunities whose invalidation was breached, whose first target was reached, or that ran out of time."""
    now = utcnow()
    rows = session.scalars(select(TradeOpportunity).where(TradeOpportunity.instrument_id == inst.id, TradeOpportunity.status.in_(OPEN))).all()
    for o in rows:
        t = tfs.get(o.setup_timeframe or "")
        sd = ((o.evidence or {}).get("setup") or {}).get("direction")
        if not t or not t.ok or sd not in ("BUY", "SELL") or o.invalidation is None or o.signal_ts is None:
            continue
        b = t.bars
        after = b.t >= int(o.signal_ts.timestamp())
        new, why = None, None
        if after.any():
            c, h, lo = b.c[after], b.h[after], b.l[after]
            inv, tp1 = float(o.invalidation), _dec(o.take_profit_1)
            if (sd == "BUY" and (c < inv).any()) or (sd == "SELL" and (c > inv).any()):
                new, why = "invalidated", "a candle closed beyond the invalidation level"
            elif tp1 is not None and ((sd == "BUY" and (h >= tp1).any()) or (sd == "SELL" and (lo <= tp1).any())):
                new, why = "expired", "first target was reached (setup has played out)"
        if new is None and o.expires_at is not None and now > o.expires_at:
            new, why = "expired", "setup lifetime elapsed without a valid trigger"
        if new:
            o.status, o.last_seen_at = new, now
            session.add(OpportunityStatusHistory(opportunity_id=o.id, status=new, at=now, note={"scan_id": scan.id, "reason": why}))
    session.commit()


__all__ = ["create_scan", "execute_scan", "run_scan_job", "profile_config", "AppError"]
