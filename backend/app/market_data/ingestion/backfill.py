"""Resumable historical backfill.

Idea: never trust "the request succeeded". Compute the set of candle open-times that SHOULD exist for the
requested range, subtract what is already stored as complete, and fetch only the missing windows. Every
window is validated, committed and recorded, so an interrupted run resumes where it stopped and a repeated
run is a no-op (idempotent). Holes the provider genuinely cannot fill remain reported as missing.
"""
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, UnsupportedError
from app.database.base import utcnow
from app.database.models import Candle as CandleRow
from app.database.models import (
    DataProvider,
    IngestionRun,
    Instrument,
    ProviderInstrument,
)
from app.market_data.base import MarketDataProvider
from app.market_data.calendars import get_calendar
from app.market_data.ingestion.service import (
    anchor_for,
    refresh_coverage,
    store_candles,
)
from app.market_data.normalization.normalize import normalize_candles
from app.market_data.timeframes import (
    SessionAnchor,
    Timeframe,
    bucket_end,
    bucket_start,
    get_timeframe,
)


def expected_open_times(tf: Timeframe, start: datetime, end_exclusive: datetime, anchor: SessionAnchor,
                        calendar: str = "continuous") -> list[datetime]:
    """Candle open times in [start, end_exclusive) the market calendar says must exist (weekend closures excluded;
    holidays and maintenance breaks are NOT modelled, so they surface as missing - conservative)."""
    cal = get_calendar(calendar)
    out: list[datetime] = []
    cur = bucket_start(start, tf, anchor)
    if cur < start:
        cur = bucket_end(cur, tf, anchor)
    while cur < end_exclusive:
        if cal.is_open(cur):
            out.append(cur)
        cur = bucket_end(cur, tf, anchor)
    return out


def _stored_complete(session: Session, inst_id: int, prov_id: int, timeframe: str, lo: datetime, hi: datetime) -> set[datetime]:
    rows = session.scalars(select(CandleRow.ts).where(
        CandleRow.instrument_id == inst_id, CandleRow.provider_id == prov_id, CandleRow.timeframe == timeframe,
        CandleRow.is_complete.is_(True), CandleRow.ts >= lo, CandleRow.ts < hi))
    return set(rows)


def _windows(missing: list[datetime], expected_index: dict[datetime, int], size: int) -> list[tuple[int, int]]:
    """Cover the missing open-times with windows of at most `size` expected slots, starting at the first missing one.

    Windows are SPAN-based, not run-based: hundreds of tiny holes that a provider can never fill (maintenance breaks,
    holidays) are re-requested inside a few wide windows instead of one request each. That keeps a resumed run cheap on
    credit-limited plans; re-fetching candles that are already stored is harmless (idempotent upsert)."""
    runs: list[tuple[int, int]] = []
    for t in missing:
        i = expected_index[t]
        if runs and i - runs[-1][0] < size:
            runs[-1] = (runs[-1][0], i)
        else:
            runs.append((i, i))
    return runs


def backfill_candles(
    session: Session, provider: MarketDataProvider, inst: Instrument, prov: DataProvider, pi: ProviderInstrument,
    timeframe: str, start: datetime, end: datetime | None = None, window_candles: int = 1000,
    now: datetime | None = None, progress: Callable[[dict], None] | None = None,
) -> IngestionRun:
    tf = get_timeframe(timeframe)
    if tf.seconds is None:
        raise UnsupportedError("backfill supports fixed-length timeframes only; aggregate calendar timeframes from 1D")
    if timeframe not in provider.native_timeframes:
        raise UnsupportedError(f"{prov.code} has no native {timeframe}; backfill only uses native series")
    now = now or datetime.now(timezone.utc)
    anchor = anchor_for(inst)
    end_excl = bucket_start(now, tf, anchor)  # open time of the still-forming candle: never ingested as history
    if end is not None:
        end_excl = min(end_excl, bucket_start(end, tf, anchor))
    expected = expected_open_times(tf, start, end_excl, anchor, inst.calendar)
    run = IngestionRun(provider_id=prov.id, instrument_id=inst.id, timeframe=timeframe, kind="backfill", status="running",
                       range_start=expected[0] if expected else start, range_end=end_excl, started_at=utcnow(), meta={})
    session.add(run)
    session.commit()
    if not expected:
        run.status, run.finished_at = "completed", utcnow()
        session.commit()
        return run

    index = {t: i for i, t in enumerate(expected)}
    stored = _stored_complete(session, inst.id, prov.id, timeframe, expected[0], end_excl)
    missing = [t for t in expected if t not in stored]
    run.missing_before = len(missing)
    session.commit()
    step = timedelta(seconds=tf.seconds)  # type: ignore[arg-type]
    meta = {"windows": 0, "empty_windows": 0, "incomplete_skipped": 0}

    try:
        for a, b in _windows(missing, index, window_candles):
            lo, hi = expected[a], expected[b]
            raw = provider.get_candles(pi.provider_symbol, timeframe, start=lo, end=hi + step - timedelta(seconds=1))
            clean, rep = normalize_candles(raw)
            good = []
            for c in clean:
                if bucket_start(c.ts, tf, anchor) != c.ts:
                    run.misaligned += 1
                elif not c.complete or c.ts >= end_excl:
                    meta["incomplete_skipped"] += 1
                elif c.ts < lo or c.ts > hi:
                    continue  # outside the requested window (provider returned extra rows)
                else:
                    good.append(c)
            run.requests += max(1, -(-(b - a + 1) // 1000))
            run.fetched += len(raw)
            run.rejected += len(rep.rejected)
            run.duplicates += rep.duplicates
            run.stored += store_candles(session, inst.id, prov.id, timeframe, good)
            meta["windows"] += 1
            meta["empty_windows"] += 0 if good else 1
            run.meta = dict(meta)
            session.commit()  # checkpoint: a crash after this line loses nothing
            if progress:
                progress({"window": meta["windows"], "from": lo.isoformat(), "stored": run.stored})
    except AppError as exc:
        run.status, run.error, run.finished_at = "partial", exc.message, utcnow()
        session.commit()
        raise
    except Exception as exc:  # pragma: no cover - defensive
        run.status, run.error, run.finished_at = "failed", f"{exc.__class__.__name__}: {exc}", utcnow()
        session.commit()
        raise

    after = _stored_complete(session, inst.id, prov.id, timeframe, expected[0], end_excl)
    first_stored = min(after) if after else None
    still = [t for t in expected if t not in after]
    # Open-times before the provider's first candle are history that does not exist, not gaps.
    pre_history = [t for t in still if first_stored is not None and t < first_stored]
    run.missing_after = len(still) - len(pre_history)
    meta["pre_history_unavailable"] = len(pre_history)
    meta["first_stored"] = first_stored.isoformat() if first_stored else None
    run.meta = dict(meta)
    run.status = "completed" if run.missing_after == 0 else "partial"
    run.finished_at = utcnow()
    session.commit()
    refresh_coverage(session, inst, prov, timeframe, status="ok")
    return run
