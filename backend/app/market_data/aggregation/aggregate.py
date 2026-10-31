"""Aggregate lower-timeframe candles into a higher timeframe.

Rules:
  * Only COMPLETE base candles are used.
  * A bucket is complete iff its end <= end of the last complete base candle AND every expected
    base candle (per the market calendar) is present. Otherwise it is emitted with complete=False
    so downstream analysis can exclude it. Missing OHLC values are never invented.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from app.market_data.calendars import MarketCalendar, get_calendar
from app.market_data.timeframes import (
    UTC_ANCHOR,
    SessionAnchor,
    Timeframe,
    bucket_end,
    bucket_start,
    get_timeframe,
)
from app.market_data.types import Candle


def _expected_count(start: datetime, end: datetime, base: Timeframe, cal: MarketCalendar,
                    anchor: SessionAnchor) -> int:
    if base.seconds is None:  # month-based base (e.g. 1M -> 3M)
        n, cur = 0, start
        while cur < end:
            n += 1
            cur = bucket_end(cur, base, anchor)
        return n
    step = timedelta(seconds=base.seconds)
    if cal.name == "continuous":
        return int((end - start) / step)
    n, cur = 0, start
    while cur < end:
        if cal.is_open(cur):
            n += 1
        cur += step
    return n


def aggregate_candles(
    candles: list[Candle],
    base_tf: str,
    target_tf: str,
    anchor: SessionAnchor = UTC_ANCHOR,
    calendar: str = "continuous",
) -> list[Candle]:
    base, target = get_timeframe(base_tf), get_timeframe(target_tf)
    cal = get_calendar(calendar)
    usable = sorted((c for c in candles if c.complete), key=lambda c: c.ts)
    if not usable:
        return []
    last = usable[-1]
    last_end = bucket_end(last.ts, base, anchor) if base.seconds is None else last.ts + timedelta(seconds=base.seconds)

    groups: dict[datetime, list[Candle]] = defaultdict(list)
    for c in usable:
        groups[bucket_start(c.ts, target, anchor)].append(c)

    out: list[Candle] = []
    for start in sorted(groups):
        rows = groups[start]
        end = bucket_end(start, target, anchor)
        expected = _expected_count(start, end, base, cal, anchor)
        has_volume = all(r.volume is not None for r in rows)
        complete = end <= last_end and len(rows) >= expected
        out.append(
            Candle(
                ts=start,
                open=rows[0].open,
                high=max(r.high for r in rows),
                low=min(r.low for r in rows),
                close=rows[-1].close,
                volume=sum((r.volume for r in rows), Decimal(0)) if has_volume else None,
                complete=complete,
                volume_type=rows[0].volume_type if has_volume else "none",
                origin="aggregated",
                meta={"base_tf": base_tf, "n_base": len(rows), "expected_base": expected},
            )
        )
    return out
