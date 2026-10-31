"""Data-quality audit of a stored candle series, computed from the database (never from a request's success)."""
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Candle as CandleRow
from app.database.models import IngestionRun
from app.market_data.ingestion.backfill import expected_open_times
from app.market_data.ingestion.service import anchor_for
from app.market_data.timeframes import bucket_start, get_timeframe

JUMP_THRESHOLD = 0.15  # |close/prev_close - 1| flagged as an anomaly (informational, never "fixed")


def _ranges(missing: list[datetime], tf_seconds: int) -> list[dict]:
    out: list[dict] = []
    for t in missing:
        if out and (t - out[-1]["_last"]).total_seconds() == tf_seconds:
            out[-1]["end"], out[-1]["_last"] = t, t
            out[-1]["missing"] += 1
        else:
            out.append({"start": t, "end": t, "_last": t, "missing": 1})
    for r in out:
        r.pop("_last")
    return out


def compute_quality(session: Session, inst, prov, timeframe: str, now: datetime | None = None) -> dict:
    tf = get_timeframe(timeframe)
    anchor = anchor_for(inst)
    now = now or datetime.now(timezone.utc)
    step = tf.seconds
    rows = session.execute(
        select(CandleRow.ts, CandleRow.open, CandleRow.high, CandleRow.low, CandleRow.close, CandleRow.volume,
               CandleRow.is_complete).where(CandleRow.instrument_id == inst.id, CandleRow.provider_id == prov.id,
                                            CandleRow.timeframe == timeframe).order_by(CandleRow.ts)).all()
    total = len(rows)
    distinct = session.scalar(select(func.count(func.distinct(CandleRow.ts))).where(
        CandleRow.instrument_id == inst.id, CandleRow.provider_id == prov.id, CandleRow.timeframe == timeframe)) or 0
    runs = session.scalars(select(IngestionRun).where(
        IngestionRun.instrument_id == inst.id, IngestionRun.provider_id == prov.id,
        IngestionRun.timeframe == timeframe).order_by(IngestionRun.id)).all()
    q: dict = {
        "symbol": inst.canonical_symbol, "provider": prov.code, "timeframe": timeframe, "generated_at": now.isoformat(),
        "total_rows": total, "db_duplicate_timestamps": total - distinct,
        "provider_duplicates_seen": sum(r.duplicates for r in runs), "ingestion_runs": len(runs),
        "rejected_at_ingestion": sum(r.rejected for r in runs), "misaligned_at_ingestion": sum(r.misaligned for r in runs),
    }
    if not total:
        q.update(status="no data", complete_count=0, missing_count=0, coverage_pct=0.0, gaps=[])
        return q

    complete = [r for r in rows if r.is_complete]
    incomplete = total - len(complete)
    first = rows[0].ts
    last_complete = complete[-1].ts if complete else None
    q.update(first_candle=first.isoformat(), last_completed_candle=last_complete.isoformat() if last_complete else None,
             complete_count=len(complete), incomplete_count=incomplete)

    # Re-validate stored values (independent of ingestion-time validation)
    invalid = misaligned = zero_vol = flat = 0
    jumps: list[dict] = []
    prev_close = None
    non_monotonic = 0
    prev_ts = None
    diffs: Counter = Counter()
    for r in rows:
        o, h, lo, c = float(r.open), float(r.high), float(r.low), float(r.close)
        if min(o, h, lo, c) <= 0 or h < max(o, c, lo) - 1e-9 or lo > min(o, c, h) + 1e-9:
            invalid += 1
        if bucket_start(r.ts, tf, anchor) != r.ts:
            misaligned += 1
        if r.volume is not None and float(r.volume) == 0:
            zero_vol += 1
        if h == lo:
            flat += 1
        if prev_ts is not None:
            if r.ts <= prev_ts:
                non_monotonic += 1
            diffs[int((r.ts - prev_ts).total_seconds())] += 1
        if prev_close and abs(c / prev_close - 1) > JUMP_THRESHOLD and len(jumps) < 10:
            jumps.append({"time": r.ts.isoformat(), "move_pct": round((c / prev_close - 1) * 100, 2)})
        prev_close, prev_ts = c, r.ts
    q.update(invalid_stored=invalid, misaligned_stored=misaligned, zero_volume=zero_vol, flat_candles=flat,
             non_monotonic=non_monotonic, spacing_histogram={str(k): v for k, v in diffs.most_common(6)},
             large_jumps=jumps, large_jump_threshold_pct=JUMP_THRESHOLD * 100,
             timestamps_all_utc=all(r.ts.tzinfo is not None and r.ts.utcoffset() == timedelta(0) for r in rows))

    # Expected vs stored over [first, last completed]
    if last_complete is not None:
        expected = expected_open_times(tf, first, last_complete + timedelta(seconds=step), anchor)
        have = {r.ts for r in complete}
        missing = [t for t in expected if t not in have]
        gaps = _ranges(missing, step)
        by_date: Counter = Counter(t.date().isoformat() for t in missing)
        q.update(expected_count=len(expected), missing_count=len(missing),
                 coverage_pct=round(100 * (len(expected) - len(missing)) / len(expected), 4),
                 gaps=[{"start": g["start"].isoformat(), "end": g["end"].isoformat(), "missing": g["missing"]} for g in gaps],
                 gap_count=len(gaps), largest_gap=max((g["missing"] for g in gaps), default=0),
                 missing_by_date=dict(sorted(by_date.items())))
        q["span_days"] = round((last_complete - first).total_seconds() / 86400, 1)
    latest = runs[-1] if runs else None
    q["runs"] = [{"id": r.id, "kind": r.kind, "status": r.status, "requests": r.requests, "fetched": r.fetched,
                  "stored": r.stored, "missing_before": r.missing_before, "missing_after": r.missing_after,
                  "started_at": r.started_at.isoformat()} for r in runs[-20:]]
    if last_complete is not None:  # independent of the grid walk above: count by arithmetic on first/last
        arithmetic = int((last_complete - first).total_seconds() // step) + 1
        q["independent_count_check"] = {"arithmetic_expected": arithmetic, "complete_rows": len(complete),
                                        "agree": arithmetic == len(complete)}
    q["latest_run"] = None if latest is None else {
        "id": latest.id, "status": latest.status, "kind": latest.kind, "started_at": latest.started_at.isoformat(),
        "finished_at": latest.finished_at.isoformat() if latest.finished_at else None,
        "range_start": latest.range_start.isoformat() if latest.range_start else None,
        "range_end": latest.range_end.isoformat() if latest.range_end else None,
        "requests": latest.requests, "stored": latest.stored, "missing_before": latest.missing_before,
        "missing_after": latest.missing_after, "error": latest.error, "meta": latest.meta,
    }
    clean = (q.get("missing_count", 1) == 0 and not invalid and not misaligned and not non_monotonic
             and not q["db_duplicate_timestamps"])
    q["status"] = "clean" if clean else "issues found"
    return q


def render_markdown(reports: list[dict], requested_start: datetime | None = None) -> str:
    ts = reports[0]["generated_at"] if reports else ""
    out = ["# BTCUSDT data quality report", "",
           f"_Generated {ts} by `python -m app.research.run_milestone` from the stored database; provider: Binance spot "
           "public klines. Values below are recomputed from stored candles, not copied from API responses._", ""]
    if requested_start:
        out += [f"Requested history start: **{requested_start.date()}** (target ≥ 3 years).", ""]
    out += ["## Summary", "", "| Metric | " + " | ".join(r["timeframe"] for r in reports) + " |",
            "|---|" + "---|" * len(reports)]

    def row(label, key, fmt=lambda v: v):
        out.append(f"| {label} | " + " | ".join(str(fmt(r.get(key, "—"))) for r in reports) + " |")

    row("Ingestion status (latest run)", "latest_run", lambda v: v["status"] if isinstance(v, dict) else "never run")
    row("Dataset status", "status")
    row("First available candle (UTC)", "first_candle")
    row("Last completed candle (UTC)", "last_completed_candle")
    row("Span (days)", "span_days")
    row("Stored rows", "total_rows")
    row("Complete candles", "complete_count")
    row("Incomplete candles stored", "incomplete_count")
    row("Expected candles (first→last)", "expected_count")
    row("**Missing candles**", "missing_count")
    row("**Coverage %**", "coverage_pct")
    row("Gap ranges", "gap_count")
    row("Largest gap (candles)", "largest_gap")
    row("Duplicate timestamps in DB", "db_duplicate_timestamps")
    row("Duplicates returned by provider (all runs)", "provider_duplicates_seen")
    row("Invalid OHLC (re-validated, stored)", "invalid_stored")
    row("Rejected at ingestion (all runs)", "rejected_at_ingestion")
    row("Misaligned timestamps (stored)", "misaligned_stored")
    row("Non-monotonic timestamps", "non_monotonic")
    row("All timestamps UTC", "timestamps_all_utc")
    row("Zero-volume candles", "zero_volume")
    row("Flat (high = low) candles", "flat_candles")
    out.append("")
    for r in reports:
        out += [f"## {r['timeframe']}", ""]
        lr = r.get("latest_run")
        if lr and lr.get("error"):
            out.append(f"* Latest run error: `{lr['error']}`")
        ic = r.get("independent_count_check")
        if ic:
            out.append(f"* Independent check: (last − first) ÷ step + 1 = {ic['arithmetic_expected']:,} vs {ic['complete_rows']:,} complete rows → "
                       f"**{'agree' if ic['agree'] else 'DISAGREE'}**.")
        if r.get("runs"):
            out += ["", "Ingestion run history (idempotence: later runs find nothing to fetch):", "",
                    "| Run | Kind | Status | Requests | Fetched | Stored | Missing before → after | Started (UTC) |", "|---|---|---|---|---|---|---|---|"]
            out += [f"| #{x['id']} | {x['kind']} | {x['status']} | {x['requests']} | {x['fetched']} | {x['stored']} | "
                    f"{x['missing_before']} → {x['missing_after']} | {x['started_at'][:19]} |" for x in r["runs"]]
            out.append("")
        out.append(f"* Spacing histogram (seconds → count): `{r.get('spacing_histogram')}`")
        gaps = r.get("gaps") or []
        out += ["", "### Gaps by date", ""]
        if not gaps:
            out.append("No missing candles between the first and last completed candle.")
        else:
            out += ["| From | To | Missing candles |", "|---|---|---|"]
            out += [f"| {g['start']} | {g['end']} | {g['missing']} |" for g in gaps[:60]]
            if len(gaps) > 60:
                out.append(f"\n…and {len(gaps) - 60} more ranges.")
            byd = r.get("missing_by_date") or {}
            out += ["", f"Dates with missing candles: {len(byd)} (e.g. " + ", ".join(f"{d}: {n}" for d, n in list(byd.items())[:8]) + ")"]
        jumps = r.get("large_jumps") or []
        out += ["", f"### Large single-candle moves (> {r.get('large_jump_threshold_pct')}%; informational, kept as-is)", ""]
        out += [f"* {j['time']}: {j['move_pct']}%" for j in jumps] or ["None."]
        out.append("")
    out += ["## Interpretation notes", "",
            "* A candle is *expected* when its open time falls on the timeframe grid between the first and last completed "
            "candle (BTCUSDT trades 24/7, so every grid slot should exist). Anything absent is reported as missing, never filled.",
            "* The still-forming candle is never stored as history. Open times before Binance's first BTCUSDT candle are "
            "not counted as gaps.",
            "* Anomalous moves are listed, not removed: removing real volatility would bias every downstream test.", ""]
    return "\n".join(out)
