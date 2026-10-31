from datetime import datetime, timedelta

from app.market_data.calendars import get_calendar
from app.market_data.timeframes import (
    UTC_ANCHOR,
    SessionAnchor,
    bucket_end,
    get_timeframe,
)


def find_gaps(
    timestamps: list[datetime],
    timeframe: str,
    calendar: str = "continuous",
    anchor: SessionAnchor = UTC_ANCHOR,
    max_gaps: int = 500,
) -> list[dict]:
    """Missing candle ranges between consecutive stored timestamps.

    Expected open times inside calendar closures (e.g. FX weekend) are not counted as missing.
    Returns [{start, end, missing}] where start/end are the first/last missing candle open times.
    """
    tf = get_timeframe(timeframe)
    cal = get_calendar(calendar)
    ts = sorted(set(timestamps))
    gaps: list[dict] = []
    for prev, cur in zip(ts, ts[1:]):
        nxt = bucket_end(prev, tf, anchor)
        if nxt >= cur:
            continue
        missing: list[datetime] = []
        probe = nxt
        while probe < cur and len(missing) < 100_000:
            if cal.is_open(probe):
                missing.append(probe)
            probe = bucket_end(probe, tf, anchor)
        if missing:
            gaps.append({"start": missing[0].isoformat(), "end": missing[-1].isoformat(), "missing": len(missing)})
            if len(gaps) >= max_gaps:
                break
    return gaps


def staleness(last_ts: datetime | None, timeframe: str, now: datetime, calendar: str = "continuous",
              anchor: SessionAnchor = UTC_ANCHOR) -> float | None:
    """Number of expected-but-unavailable completed candles after last_ts (0 = fresh)."""
    if last_ts is None:
        return None
    tf = get_timeframe(timeframe)
    cal = get_calendar(calendar)
    n, cur = 0, bucket_end(last_ts, tf, anchor)
    while bucket_end(cur, tf, anchor) <= now and n < 100_000:
        if cal.is_open(cur):
            n += 1
        cur = bucket_end(cur, tf, anchor)
    return float(n)


__all__ = ["find_gaps", "staleness", "timedelta"]
