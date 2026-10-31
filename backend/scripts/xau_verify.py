"""Live verification of the Twelve Data / XAUUSD integration. REAL API calls only - no mocks, no substitute provider.

Run from backend/:   python scripts/xau_verify.py
Writes docs/reports/XAUUSD_COVERAGE.md. The API key is read from the environment/.env and never printed or written
(all output is passed through `redact`). Uses its own SQLite file so it cannot disturb other databases.
"""
import json
import logging
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8")
os.environ["DATABASE_URL"] = "sqlite:///./xau_verify.db"
for name in ("httpx", "httpcore"):  # their INFO lines contain full request URLs (which include the key)
    logging.getLogger(name).setLevel(logging.WARNING)

from sqlalchemy import func, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.database.init_db import init_db  # noqa: E402
from app.database.models import Candle as CandleRow  # noqa: E402
from app.database.models import IngestionRun  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.market_data.aggregation.aggregate import aggregate_candles  # noqa: E402
from app.market_data.calendars import get_calendar  # noqa: E402
from app.market_data.coverage.gaps import find_gaps  # noqa: E402
from app.market_data.ingestion.backfill import backfill_candles  # noqa: E402
from app.market_data.ingestion.service import (  # noqa: E402
    anchor_for,
    load_candles,
    resolve_mapping,
)
from app.market_data.registry import get_provider  # noqa: E402
from app.market_data.timeframes import (  # noqa: E402
    bucket_end,
    bucket_start,
    get_timeframe,
)
from app.market_data.twelve_data.provider import TwelveDataProvider  # noqa: E402

SYMBOL, PROVIDER, TD_SYMBOL = "XAUUSD", "twelve_data", "XAU/USD"
TFS = ["1H", "4H", "1D"]
KEY = get_settings().twelve_data_api_key or ""
OUT = Path(__file__).resolve().parents[2] / "docs" / "reports" / "XAUUSD_COVERAGE.md"


def redact(x) -> str:
    s = x if isinstance(x, str) else json.dumps(x, default=str, indent=2)
    return s.replace(KEY, "***") if KEY else s


def say(title: str, obj=None) -> None:
    print(f"\n== {title}")
    if obj is not None:
        print(redact(obj), flush=True)


def alignment_diagnostic(provider) -> dict:
    """Hour-of-day (UTC) of native 4H candles in different DST periods: shows whether the provider's 4H grid is stable."""
    out = {}
    for label, a, b in [("2023-08 (US summer time)", datetime(2023, 8, 1, tzinfo=timezone.utc), datetime(2023, 8, 31, tzinfo=timezone.utc)),
                        ("2023-12 (US winter time)", datetime(2023, 12, 1, tzinfo=timezone.utc), datetime(2023, 12, 31, tzinfo=timezone.utc)),
                        ("2025-06 (US summer time)", datetime(2025, 6, 1, tzinfo=timezone.utc), datetime(2025, 6, 30, tzinfo=timezone.utc)),
                        ("2026-01 (US winter time)", datetime(2026, 1, 5, tzinfo=timezone.utc), datetime(2026, 2, 5, tzinfo=timezone.utc))]:
        c = provider.get_candles(TD_SYMBOL, "4H", start=a, end=b)
        out[label] = {"candles": len(c), "hours_utc": dict(sorted(Counter(x.ts.hour for x in c).items())),
                      "epoch_aligned_share": round(sum(x.ts.hour % 4 == 0 for x in c) / max(1, len(c)), 3)}
    return out


def validate(session, inst, prov, tf: str) -> dict:
    rows = session.execute(select(CandleRow.ts, CandleRow.open, CandleRow.high, CandleRow.low, CandleRow.close,
                                  CandleRow.volume, CandleRow.is_complete).where(
        CandleRow.instrument_id == inst.id, CandleRow.provider_id == prov.id, CandleRow.timeframe == tf)
        .order_by(CandleRow.ts)).all()
    distinct = session.scalar(select(func.count(func.distinct(CandleRow.ts))).where(
        CandleRow.instrument_id == inst.id, CandleRow.provider_id == prov.id, CandleRow.timeframe == tf)) or 0
    tfo, anchor, cal = get_timeframe(tf), anchor_for(inst), get_calendar(inst.calendar)
    invalid = misaligned = non_utc = 0
    for r in rows:
        o, h, lo, c = (float(v) for v in (r.open, r.high, r.low, r.close))
        invalid += min(o, h, lo, c) <= 0 or h < max(o, c, lo) - 1e-9 or lo > min(o, c, h) + 1e-9
        misaligned += bucket_start(r.ts, tfo, anchor) != r.ts
        non_utc += r.ts.utcoffset() != timedelta(0)
    ts = [r.ts for r in rows]
    gaps = find_gaps(ts, tf, inst.calendar, anchor, max_gaps=100_000)
    missing = []
    for g in gaps:
        cur, n = datetime.fromisoformat(g["start"]), 0
        while n < g["missing"]:
            if cal.is_open(cur):
                missing.append(cur)
                n += 1
            cur = bucket_end(cur, tfo, anchor)
    closes = [float(r.close) for r in rows]
    closed_rows = [r for r in rows if not cal.is_open(r.ts)]
    open_rows = [r for r in rows if cal.is_open(r.ts)]
    med = lambda rs: round(sorted(float(r.high) - float(r.low) for r in rs)[len(rs) // 2], 3) if rs else None  # noqa: E731
    by_hour = Counter(t.hour for t in missing)
    by_day = Counter(t.date().isoformat() for t in missing)
    return {
        "timeframe": tf, "rows": len(rows), "distinct_timestamps": distinct, "duplicates": len(rows) - distinct,
        "first": ts[0].isoformat() if ts else None, "last": ts[-1].isoformat() if ts else None,
        "span_days": round((ts[-1] - ts[0]).total_seconds() / 86400, 1) if ts else 0,
        "invalid_ohlc": int(invalid), "misaligned": int(misaligned), "non_utc": int(non_utc),
        "with_volume": sum(r.volume is not None for r in rows), "incomplete_stored": sum(not r.is_complete for r in rows),
        "close_min": min(closes) if closes else None, "close_max": max(closes) if closes else None,
        "stamped_in_calendar_closed_time": len(closed_rows),
        "closed_time_pct_of_rows": round(100 * len(closed_rows) / len(rows), 2) if rows else 0,
        "closed_time_flat_candles": sum(float(r.high) == float(r.low) for r in closed_rows),
        "closed_time_median_range": med(closed_rows), "open_time_median_range": med(open_rows),
        "closed_time_by_weekday": dict(Counter(r.ts.strftime("%a") for r in closed_rows)),
        "missing_open_slots": len(missing), "gap_ranges": len(gaps),
        "coverage_pct_vs_weekly_calendar": round(100 * len(rows) / (len(rows) + len(missing)), 3) if rows else 0,
        "missing_by_utc_hour": dict(sorted(by_hour.items())),
        "days_with_most_missing": dict(by_day.most_common(8)),
        "largest_gap_slots": max((g["missing"] for g in gaps), default=0),
    }


def main() -> int:
    say("1. configuration (secret never printed)", {"key_loaded": bool(KEY), "key_length": len(KEY),
                                                      "key_in_settings_repr": bool(KEY) and KEY in repr(get_settings())})
    if not KEY:
        say("ABORT", "TWELVE_DATA_API_KEY is not set (root .env or backend/.env).")
        return 2
    init_db()
    provider = get_provider(PROVIDER)
    assert isinstance(provider, TwelveDataProvider) and provider.is_configured()
    report: dict = {"generated_at": datetime.now(timezone.utc).isoformat()}

    try:
        report["quota_before"] = provider.get_quota()
    except AppError as exc:
        report["quota_before"] = {"error": exc.message}
    say("2. quota before (provider's own numbers)", report["quota_before"])

    try:
        found = provider.get_instruments([TD_SYMBOL])
        report["discovery"] = [{"symbol": i.symbol, "name": i.name, **{k: (i.raw or {}).get(k) for k in
                               ("instrument_type", "exchange", "currency_base", "currency_quote", "country")}} for i in found]
    except AppError as exc:
        report["discovery"] = {"error": exc.message}
    say("3. instrument discovery (symbol_search)", report["discovery"])

    report["probe"] = {}
    for tf in TFS:
        report["probe"][tf] = provider.check_data_coverage(TD_SYMBOL, tf, max_pages=8)
    say("4. coverage probe (what the plan actually serves)", report["probe"])

    now = datetime.now(timezone.utc)
    report["alignment_4h"] = alignment_diagnostic(provider)
    say("4b. native 4H alignment across DST periods", report["alignment_4h"])
    report["ingestion"], report["validation"] = {}, {}
    with session_scope() as s:
        inst, prov, pi = resolve_mapping(s, SYMBOL, PROVIDER)
        report["mapping"] = {"instrument": inst.canonical_symbol, "provider": prov.code, "provider_symbol": pi.provider_symbol,
                             "market_kind": pi.market_kind, "status_in_registry": pi.status, "calendar": inst.calendar,
                             "session_anchor": f"{inst.session_tz} {inst.session_open}"}
        for tf in TFS:
            pr = report["probe"][tf]
            if not pr.get("available"):
                report["ingestion"][tf] = {"skipped": pr.get("error", "probe unavailable")}
                continue
            earliest = datetime.fromisoformat(pr["earliest"]) if pr.get("earliest") else now - timedelta(days=1200)
            want = now - timedelta(days=3650 if tf == "1D" else 1200)
            start = max(earliest, want)
            t0 = time.perf_counter()
            try:
                run = backfill_candles(s, provider, inst, prov, pi, tf, start, now=now, window_candles=3500)
                report["ingestion"][tf] = {"requested_from": start.isoformat(), "status": run.status, "requests": run.requests,
                                           "fetched": run.fetched, "stored": run.stored, "rejected": run.rejected,
                                           "provider_duplicates": run.duplicates, "misaligned": run.misaligned,
                                           "missing_before": run.missing_before, "missing_after_calendar_model": run.missing_after,
                                           "seconds": round(time.perf_counter() - t0, 1)}
            except AppError as exc:
                report["ingestion"][tf] = {"error": exc.message}
            say(f"5. backfill {tf}", report["ingestion"][tf])
        for tf in TFS:
            report["validation"][tf] = validate(s, inst, prov, tf)
            say(f"6. validation {tf}", report["validation"][tf])
        # internal consistency of ONE provider: our 1H->4H aggregation vs the provider's own 4H candles
        c1 = load_candles(s, inst.id, prov.id, "1H")
        c4 = {c.ts: c for c in load_candles(s, inst.id, prov.id, "4H")}
        agg = [a for a in aggregate_candles(c1, "1H", "4H", anchor_for(inst), inst.calendar) if a.complete and a.ts in c4]
        if agg:
            tol = lambda a, b: abs(float(a) - float(b)) <= 0.02 + 1e-6 * float(b)  # noqa: E731
            both = [(a, c4[a.ts]) for a in agg]
            report["consistency_1h_vs_4h"] = {
                "complete_buckets_compared": len(both),
                "open_match": sum(tol(a.open, b.open) for a, b in both), "high_match": sum(tol(a.high, b.high) for a, b in both),
                "low_match": sum(tol(a.low, b.low) for a, b in both), "close_match": sum(tol(a.close, b.close) for a, b in both)}
        else:
            report["consistency_1h_vs_4h"] = {"note": "no complete 1H-aggregated bucket aligned with a stored 4H candle"}
        say("7. 1H to 4H internal consistency (same provider)", report["consistency_1h_vs_4h"])
        report["runs"] = [{"id": r.id, "tf": r.timeframe, "status": r.status, "requests": r.requests}
                          for r in s.scalars(select(IngestionRun).order_by(IngestionRun.id))]

    try:
        report["quota_after"] = provider.get_quota()
    except AppError as exc:
        report["quota_after"] = {"error": exc.message}
    say("8. quota after backfill", report["quota_after"])
    report["last_credit_headers"] = provider.last_quota

    # Rate-limit behaviour: 10 back-to-back cheap requests with pacing disabled, adapter retry logic left on.
    sleeps: list[float] = []
    burst = TwelveDataProvider(KEY, get_settings().twelve_data_base_url, min_interval_s=0)
    burst._sleep = lambda sec: (sleeps.append(sec), time.sleep(sec))[1]
    events = []
    for i in range(10):
        t0 = time.perf_counter()
        try:
            q = burst.get_latest_quote(TD_SYMBOL)
            events.append({"n": i + 1, "result": "ok", "price_present": q.price > 0, "seconds": round(time.perf_counter() - t0, 1)})
        except AppError as exc:
            events.append({"n": i + 1, "result": "error", "code": exc.code, "message": exc.message, "details": exc.details,
                           "seconds": round(time.perf_counter() - t0, 1)})
    report["rate_limit_burst"] = {"requests": 10, "events": events, "adapter_waits_seconds": sleeps,
                                  "credit_headers_after": burst.last_quota}
    say("9. rate-limit burst (10 unpaced requests)", report["rate_limit_burst"])

    write_report(report)
    text = OUT.read_text(encoding="utf8")
    assert not KEY or KEY not in text, "key leaked into report"
    say("DONE", f"report written to {OUT}")
    return 0


def write_report(r: dict) -> None:
    pr, ing, val = r["probe"], r["ingestion"], r["validation"]
    qa, qb = r.get("quota_after", {}), r.get("quota_before", {})
    o = ["# XAUUSD / Twelve Data — live integration verification", "",
         f"_Generated {r['generated_at']} by `python scripts/xau_verify.py` against the real Twelve Data API (no mocks, no substitute provider). "
         "The API key is never printed or stored in this report._", "",
         "## Mapping", "", "```json", redact(r["mapping"]), "```", "",
         "## Instrument discovery (`/symbol_search`)", "", "```json", redact(r["discovery"]), "```", "",
         "## Plan / quota (provider-reported, verbatim)", "", "Before:", "```json", redact(qb), "```", "After backfill:", "```json", redact(qa), "```",
         f"Last credit headers seen: `{redact(r.get('last_credit_headers', {}))}`", "",
         "## Coverage probe (what the current plan serves)", "",
         "| Timeframe | Available | Earliest candle | Earliest is only a lower bound | Latest candle | Volume |", "|---|---|---|---|---|---|"]
    for tf, p in pr.items():
        o.append(f"| {tf} | {p.get('available')} | {p.get('earliest') or p.get('error', '—')} | {p.get('earliest_is_lower_bound')} | {p.get('latest')} | {p.get('has_volume')} |")
    o += ["", "## Retrieval and validation", "",
          "| Timeframe | Requested from | Requests | Stored | Rows | Distinct ts | Duplicates | Invalid OHLC | Misaligned | Non-UTC | First | Last | Close min–max |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for tf in TFS:
        v, i = val.get(tf, {}), ing.get(tf, {})
        o.append(f"| {tf} | {str(i.get('requested_from', '—'))[:10]} | {i.get('requests', '—')} | {i.get('stored', '—')} | {v.get('rows')} | {v.get('distinct_timestamps')} | "
                 f"{v.get('duplicates')} | {v.get('invalid_ohlc')} | {v.get('misaligned')} | {v.get('non_utc')} | {str(v.get('first'))[:16]} | {str(v.get('last'))[:16]} | "
                 f"{v.get('close_min')}–{v.get('close_max')} |")
    o += ["", "## Ingestion (this run; backfill windows are span-based, so re-runs are cheap)", "",
          "| Timeframe | Status | Requests | Fetched | Stored | Rejected misaligned (off our grid) | Rejected invalid | Provider duplicates | Missing before → after |",
          "|---|---|---|---|---|---|---|---|---|"]
    for tf in TFS:
        i = ing.get(tf, {})
        o.append(f"| {tf} | {i.get('status', i.get('skipped', i.get('error')))} | {i.get('requests')} | {i.get('fetched')} | {i.get('stored')} | "
                 f"{i.get('misaligned')} | {i.get('rejected')} | {i.get('provider_duplicates')} | {i.get('missing_before')} → {i.get('missing_after_calendar_model')} |")
    o += ["", "## Missing intervals (against the FX weekly calendar: closed Fri 17:00 → Sun 17:00 New York)", "",
          "| Timeframe | Missing open slots | Gap ranges | Largest gap (slots) | Coverage vs calendar | Missing by UTC hour | Days with most missing |", "|---|---|---|---|---|---|---|"]
    for tf in TFS:
        v = val.get(tf, {})
        o.append(f"| {tf} | {v.get('missing_open_slots')} | {v.get('gap_ranges')} | {v.get('largest_gap_slots')} | {v.get('coverage_pct_vs_weekly_calendar')}% | "
                 f"`{v.get('missing_by_utc_hour')}` | `{v.get('days_with_most_missing')}` |")
    o += ["", "Holidays and the spot-gold daily maintenance break are **not** in the calendar model, so they appear above as missing; "
          "a concentration in one UTC hour indicates a systematic daily break rather than data loss.", "",
          "## Weekend / closed-time candles (feed vs. assumed FX weekly closure)", "",
          "| Timeframe | Rows stamped inside closure | % of rows | Flat (H=L) | Median range in closure | Median range when open | By weekday |", "|---|---|---|---|---|---|---|"]
    for tf in TFS:
        v = val.get(tf, {})
        o.append(f"| {tf} | {v.get('stamped_in_calendar_closed_time')} | {v.get('closed_time_pct_of_rows')}% | {v.get('closed_time_flat_candles')} | "
                 f"{v.get('closed_time_median_range')} | {v.get('open_time_median_range')} | `{v.get('closed_time_by_weekday')}` |")
    o += ["", "## Native 4H alignment by DST period (hours are UTC)", "", "```json", redact(r.get("alignment_4h")), "```", "",
          "## 1H to 4H internal consistency (one provider)", "", "```json", redact(r.get("consistency_1h_vs_4h")), "```", "",
          "## Rate-limit behaviour (10 unpaced requests)", "", "```json", redact(r.get("rate_limit_burst")), "```", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(redact("\n".join(o)), encoding="utf8")


if __name__ == "__main__":
    sys.exit(main())
