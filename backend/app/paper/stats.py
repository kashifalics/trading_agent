"""Performance of paper trades (docs/PAPER_TRADING.md).

Forward test = every recorded signal, whether or not the account took it (the honest measure of the engine). Account = the trades the
paper account's risk rules let it take, in account currency. Verdicts use the same rule as the backtest (app.opportunities.validation
.classify: >= 100 trades, bootstrap CI > 0, p < 0.05, >= 2/3 positive thirds); below 100 closed trades no conclusion is drawn.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jsonutil import to_jsonable
from app.database.models import PaperShadowTrade, PaperTrade
from app.ml_engine.evaluation import trade_metrics
from app.opportunities.validation import classify
from app.paper.service import (
    LIVE,
    SHADOW_TARGET_R,
    SHADOW_VARIANT,
    account_out,
    active_account,
    trade_out,
    worker_status,
)
from app.research.strategy_eval import significance
from app.signals import track_record
from app.signals.track_record import bucket_of

MIN_TRADES = 100
STATUSES = ("pending", "open", "closed", "cancelled", "missed", "expired", "skipped")
DISCLAIMER = ("Paper trading: simulated orders on live candles, no broker and no real money. Fills assume the spread you configured and no "
              "slippage beyond gaps; real fills can be worse. Results are only evidence once enough trades have closed.")
METHOD = [
    "Every technically complete setup is recorded when the backend first sees it (immediate entry -> market order, limit plan -> "
    "limit order), whatever the customer decision: this is the forward test of the unvalidated rules; nothing is backfilled.",
    "Market orders fill at the open of the first candle after the signal was seen; skipped if price is already past the stop/TP1 or "
    "more than 0.3R beyond the planned entry.",
    "Limit orders rest until the plan expires; cancelled on a setup-candle close beyond the invalidation level, missed if TP1 trades first.",
    "Exit at the stop or TP1 on 1-minute candles; a candle touching both counts as a loss; a gap through the stop exits at the open.",
    "There is no time stop, as in the backtest: a trade stays open until its stop or TP1. TP1 is the first chart level at least 2R "
    "away, so on short timeframes it can be far (10R or more) and the trade can stay open for days.",
    "The configured round-trip spread is charged on every trade (R net = R gross - spread / risk).",
    "One trade per instrument x timeframe at a time, as in the backtest. The account applies its own risk limits on top.",
]


def metrics(r: list[float]) -> dict:
    return trade_metrics(np.asarray(r, dtype=float)) if r else {"n_trades": 0}


def verdict(r: list[float]) -> dict:
    n = len(r)
    if n < MIN_TRADES:
        return {"status": "collecting", "n": n, "needed": MIN_TRADES,
                "summary": f"{n} of {MIN_TRADES} closed trades: too few to tell an edge from luck, no conclusion yet"}
    arr = np.asarray(r, dtype=float)
    sig = significance(arr)
    share = float(np.mean([part.mean() > 0 for part in np.array_split(arr, 3)]))
    status, text = classify({"n_trades": n, "expectancy_r": float(arr.mean())}, sig, share, None)
    return {"status": status, "n": n, "needed": MIN_TRADES, "summary": text, "ci95": sig.get("boot_ci95"), "p_value": sig.get("p_edge_gt_0"),
            "positive_thirds": share}


def _group(trades: list[PaperTrade], key) -> list[dict]:
    groups: dict[str, list[float]] = {}
    for t in trades:
        groups.setdefault(key(t), []).append(t.r_net)
    out = []
    for k, rs in groups.items():
        arr = np.asarray(rs, dtype=float)
        out.append({"key": k, "n": len(rs), "win_rate": float((arr > 0).mean()), "expectancy_r": float(arr.mean()), "total_r": float(arr.sum())})
    return sorted(out, key=lambda g: (-g["n"], g["key"]))


def breakdowns(closed: list[PaperTrade]) -> dict:
    series = _group(closed, lambda t: f"{t.symbol} {t.timeframe}")
    for g in series:
        sym, tf = g["key"].split(" ", 1)
        tr = track_record.lookup(sym, tf)
        g["backtest"] = {"status": tr.get("status"), "expectancy_r": (tr.get("oos") or {}).get("expectancy_r"),
                         "n_trades": (tr.get("oos") or {}).get("n_trades")} if tr.get("available") else None
    return {"series": series, "symbol": _group(closed, lambda t: t.symbol), "timeframe": _group(closed, lambda t: t.timeframe),
            "setup_type": _group(closed, lambda t: (t.setup_type or "unknown").replace("_", " ")),
            "score_band": _group(closed, lambda t: bucket_of(t.score) or "below 60"), "direction": _group(closed, lambda t: t.direction),
            "order_type": _group(closed, lambda t: t.order_type), "session": _group(closed, lambda t: t.session or "unknown")}


def backtest_reference() -> dict:
    """Pooled out-of-sample expectancy of the historical replay, to compare the live record against."""
    n_all, total = 0, 0.0
    for per_tf in (track_record.load().get("results") or {}).values():
        for r in per_tf.values():
            oos = r.get("oos") or {}
            n, e = oos.get("n_trades") or 0, oos.get("expectancy_r")
            if n and e is not None:
                n_all += n
                total += n * e
    return {"n_trades": n_all, "expectancy_r": total / n_all if n_all else None,
            "note": "historical replay of the same rules, out-of-sample part only (docs/reports/SIGNAL_TRACK_RECORD.md)"}


def _drawdown(values: list[float]) -> float:
    peak, dd = -np.inf, 0.0
    for v in values:
        peak = max(peak, v)
        dd = max(dd, peak - v)
    return float(dd)


def _performance_window(trades: list[PaperTrade], start: datetime | None = None, end: datetime | None = None) -> dict:
    """Metrics for a chronologically ordered set of closed forward-test trades."""
    returns = [float(t.r_net) for t in trades if t.r_net is not None]
    target_hits = sum(t.exit_reason == "target" for t in trades)
    stop_exits = sum(t.exit_reason == "stop" for t in trades)
    current_loss_streak = longest_loss_streak = 0
    for r in returns:
        current_loss_streak = current_loss_streak + 1 if r <= 0 else 0
        longest_loss_streak = max(longest_loss_streak, current_loss_streak)
    mfe = [float(t.mfe_r) for t in trades if t.mfe_r is not None]
    mae = [float(t.mae_r) for t in trades if t.mae_r is not None]
    stop_mfe = [float(t.mfe_r) for t in trades if t.exit_reason == "stop" and t.mfe_r is not None]
    first, last = (trades[0], trades[-1]) if trades else (None, None)
    return {
        **metrics(returns),
        "start_at": first.closed_at if first else None,
        "end_at": last.closed_at if last else None,
        "range_start": start,
        "range_end": end,
        "target_hits": target_hits,
        "stop_exits": stop_exits,
        "tp1_hit_rate": target_hits / len(trades) if trades else None,
        "stop_rate": stop_exits / len(trades) if trades else None,
        "longest_losing_streak": longest_loss_streak,
        "average_mfe_r": float(np.mean(mfe)) if mfe else None,
        "average_mae_r": float(np.mean(mae)) if mae else None,
        "excursion_sample_count": len(mfe),
        "stopped_trade_count": len(stop_mfe),
        "stopped_mfe_at_least_1r": sum(value >= 1.0 for value in stop_mfe),
        "stopped_mfe_at_least_2r": sum(value >= 2.0 for value in stop_mfe),
    }


def performance_windows(closed: list[PaperTrade], now: datetime) -> dict:
    """Lifetime, rolling-count and UTC date windows from the full closed-trade set."""
    ordered = sorted(closed, key=lambda t: (t.closed_at, t.id))
    return {
        "lifetime": _performance_window(ordered),
        "last_100": _performance_window(ordered[-100:]),
        "last_50": _performance_window(ordered[-50:]),
        "last_30_days": _performance_window(
            [t for t in ordered if now - timedelta(days=30) <= t.closed_at <= now],
            now - timedelta(days=30), now,
        ),
        "last_7_days": _performance_window(
            [t for t in ordered if now - timedelta(days=7) <= t.closed_at <= now],
            now - timedelta(days=7), now,
        ),
    }


def shadow_experiment(session: Session, now: datetime) -> dict:
    """Paired, prospective comparison; unfilled terminal signals count as zero R."""
    pairs = session.execute(
        select(PaperTrade, PaperShadowTrade)
        .join(PaperShadowTrade, PaperShadowTrade.trade_id == PaperTrade.id)
        .order_by(PaperShadowTrade.created_at, PaperTrade.id)
    ).all()
    complete = [(trade, shadow) for trade, shadow in pairs
                if trade.status not in LIVE and shadow.status not in LIVE]
    baseline_r = [float(trade.r_net) if trade.status == "closed" and trade.r_net is not None else 0.0
                  for trade, _ in complete]
    candidate_r = [float(shadow.r_net) if shadow.status == "closed" and shadow.r_net is not None else 0.0
                   for _, shadow in complete]

    def signal_metrics(values: list[float]) -> dict:
        n = len(values)
        return {
            "n_signals": n,
            "total_r": float(sum(values)) if n else None,
            "expectancy_r": float(np.mean(values)) if n else None,
            "win_rate": float(np.mean(np.asarray(values) > 0)) if n else None,
        }

    baseline, candidate = signal_metrics(baseline_r), signal_metrics(candidate_r)
    capped = sum(float(shadow.take_profit) != float(trade.take_profit) for trade, shadow in pairs)
    return {
        "variant": SHADOW_VARIANT,
        "rule": f"Cap planned TP1 at {SHADOW_TARGET_R:g}R when its planned reward/risk is greater; keep entry, stop, and configured spread.",
        "generated_at": now,
        "cohort_started_at": min((shadow.created_at for _, shadow in pairs), default=None),
        "n_recorded": len(pairs),
        "n_complete": len(complete),
        "n_waiting": len(pairs) - len(complete),
        "n_targets_capped": capped,
        "baseline": baseline,
        "candidate": candidate,
        "delta_expectancy_r": candidate["expectancy_r"] - baseline["expectancy_r"]
        if candidate["expectancy_r"] is not None and baseline["expectancy_r"] is not None else None,
        "note": ("Exploratory paired shadow test only; existing baseline/account results are unchanged. "
                 "Unfilled terminal signals count as zero R. No validation claim is made."),
    }


def summary(session: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    acc = active_account(session)
    trades = session.scalars(select(PaperTrade).order_by(PaperTrade.id)).all()
    closed = sorted((t for t in trades if t.status == "closed" and t.r_net is not None), key=lambda t: (t.closed_at, t.id))
    r = [t.r_net for t in closed]
    counts = {s: sum(t.status == s for t in trades) for s in STATUSES}
    limits = [t for t in trades if t.order_type == "limit" and t.status != "pending"]
    filled = [t for t in limits if t.fill_price is not None]
    cum, curve = 0.0, []
    for t in closed:
        cum += t.r_net
        curve.append({"t": t.closed_at, "r": round(cum, 4), "id": t.id})
    taken = [t for t in closed if t.account_id == acc.id and t.account_taken]
    bal, acc_curve = acc.start_balance, [{"t": acc.created_at, "balance": acc.start_balance}]
    for t in taken:
        bal += t.pnl or 0.0
        acc_curve.append({"t": t.closed_at, "balance": round(bal, 2), "id": t.id})
    account = account_out(session, acc, now)
    account.update(metrics=metrics([t.r_net for t in taken]), max_drawdown=round(_drawdown([p["balance"] for p in acc_curve]), 2),
                   equity_curve=acc_curve, skipped_signals=sum(1 for t in trades if t.account_id == acc.id and not t.account_taken))
    live = [t for t in trades if t.status in LIVE]
    finished = sorted((t for t in trades if t.status not in LIVE), key=lambda t: (t.closed_at or t.detected_at, t.id), reverse=True)
    return to_jsonable({
        "generated_at": now, "account": account,
        "forward": {**metrics(r), "verdict": verdict(r), "counts": counts, "signals_recorded": len(trades),
                    "limit_fill_rate": (len(filled) / len(limits)) if limits else None,
                    "since": min((t.detected_at for t in trades), default=None), "equity_curve": curve,
                    "performance_windows": performance_windows(closed, now),
                    "shadow_experiment": shadow_experiment(session, now)},
        "backtest": backtest_reference(), "breakdowns": breakdowns(closed),
        "open": [trade_out(t) for t in live if t.status == "open"], "pending": [trade_out(t) for t in live if t.status == "pending"],
        "recent": [trade_out(t) for t in finished[:25]], "worker": worker_status(), "method": METHOD, "disclaimer": DISCLAIMER})
