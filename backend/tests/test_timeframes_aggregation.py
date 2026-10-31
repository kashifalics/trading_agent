from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.market_data.aggregation.aggregate import aggregate_candles
from app.market_data.coverage.gaps import find_gaps
from app.market_data.normalization.normalize import normalize_candles
from app.market_data.timeframes import (
    NY_17_ANCHOR,
    TIMEFRAME_ORDER,
    bucket_end,
    bucket_start,
    get_timeframe,
    plan_timeframe,
)
from app.market_data.types import Candle
from tests.conftest import UTC0, make_candles

UTC = timezone.utc


def dt(*a):
    return datetime(*a, tzinfo=UTC)


def test_registry_has_all_required_timeframes():
    assert TIMEFRAME_ORDER == ["1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "1D", "1W", "1M", "3M", "6M", "12M"]


def test_intraday_buckets_epoch_aligned():
    assert bucket_start(dt(2024, 3, 5, 13, 47), get_timeframe("4H")) == dt(2024, 3, 5, 12)
    assert bucket_start(dt(2024, 3, 5, 13, 47), get_timeframe("15m")) == dt(2024, 3, 5, 13, 45)


def test_week_starts_monday_and_month_quarter_year():
    assert bucket_start(dt(2024, 3, 7, 5), get_timeframe("1W")) == dt(2024, 3, 4)  # Thursday -> Monday
    assert bucket_start(dt(2024, 5, 20), get_timeframe("3M")) == dt(2024, 4, 1)
    assert bucket_start(dt(2024, 11, 20), get_timeframe("6M")) == dt(2024, 7, 1)
    assert bucket_start(dt(2024, 11, 20), get_timeframe("12M")) == dt(2024, 1, 1)
    assert bucket_end(dt(2024, 1, 1), get_timeframe("3M")) == dt(2024, 4, 1)
    assert bucket_end(dt(2024, 12, 1), get_timeframe("1M")) == dt(2025, 1, 1)


def test_ny_17_daily_anchor_handles_dst():
    tf = get_timeframe("1D")
    # Winter: 17:00 EST = 22:00 UTC. Summer: 17:00 EDT = 21:00 UTC.
    assert bucket_start(dt(2024, 1, 10, 23), tf, NY_17_ANCHOR) == dt(2024, 1, 10, 22)
    assert bucket_start(dt(2024, 7, 10, 22), tf, NY_17_ANCHOR) == dt(2024, 7, 10, 21)
    # Bucket spanning the spring-forward change (2024-03-10) is 23h long, not 24h.
    start = bucket_start(dt(2024, 3, 10, 12), tf, NY_17_ANCHOR)
    assert start == dt(2024, 3, 9, 22)
    assert bucket_end(start, tf, NY_17_ANCHOR) - start == timedelta(hours=23)
    # FX week opens Sunday 17:00 NY
    assert bucket_start(dt(2024, 1, 10, 12), get_timeframe("1W"), NY_17_ANCHOR) == dt(2024, 1, 7, 22)


def test_plan_timeframe():
    native = {"1m", "5m", "1H", "1D", "1M"}
    assert plan_timeframe("1H", native) == ("native", "1H")
    assert plan_timeframe("4H", native) == ("aggregate", "1H")
    assert plan_timeframe("3m", {"5m", "1H"}) is None  # no native divisor
    assert plan_timeframe("12M", native) == ("aggregate", "1M")
    assert plan_timeframe("1W", native) == ("aggregate", "1D")


def test_plan_3m_from_1m():
    assert plan_timeframe("3m", {"1m", "5m"}) == ("aggregate", "1m")


def test_aggregation_ohlcv_and_completeness():
    base = make_candles(10, UTC0, 3600)  # 00:00..09:00
    agg = aggregate_candles(base, "1H", "4H")
    assert [a.ts.hour for a in agg] == [0, 4, 8]
    first = agg[0]
    assert first.open == base[0].open and first.close == base[3].close
    assert first.high == max(b.high for b in base[:4]) and first.low == min(b.low for b in base[:4])
    assert first.volume == Decimal("40")
    assert first.complete and agg[1].complete
    assert not agg[2].complete  # 08:00-12:00 bucket only has 2 of 4 base candles -> never leaks as complete


def test_incomplete_base_candle_is_excluded():
    base = make_candles(8, UTC0, 3600)
    last = base[-1]
    base[-1] = Candle(last.ts, last.open, last.high, last.low, last.close, last.volume, complete=False)
    agg = aggregate_candles(base, "1H", "4H")
    assert agg[1].complete is False and agg[1].meta["n_base"] == 3


def test_missing_base_candle_prevents_completion_without_fabrication():
    base = make_candles(12, UTC0, 3600)
    del base[5]
    agg = aggregate_candles(base, "1H", "4H")
    assert agg[1].complete is False
    assert agg[1].meta["n_base"] == 3 and agg[1].meta["expected_base"] == 4


def test_monthly_to_quarter():
    months = []
    for m in range(1, 7):
        months.append(Candle(dt(2024, m, 1), Decimal(m), Decimal(m + 2), Decimal(m - 0.5), Decimal(m + 1)))
    agg = aggregate_candles(months, "1M", "3M")
    assert [a.ts.month for a in agg] == [1, 4]
    assert agg[0].complete and agg[1].complete
    partial = aggregate_candles(months[:5], "1M", "3M")  # May is the last month -> Q2 unfinished
    assert partial[0].complete and not partial[1].complete


def test_gap_detection_continuous():
    c = make_candles(10, UTC0, 3600)
    del c[4:6]
    gaps = find_gaps([x.ts for x in c], "1H")
    assert gaps == [{"start": dt(2024, 1, 1, 4).isoformat(), "end": dt(2024, 1, 1, 5).isoformat(), "missing": 2}]


def test_gap_detection_ignores_fx_weekend():
    fri = dt(2024, 1, 5, 20)  # Fri 15:00 NY (open)
    mon = dt(2024, 1, 8, 1)  # Sun 20:00 NY (open again)
    ts = [fri, fri + timedelta(hours=1), fri + timedelta(hours=2), mon, mon + timedelta(hours=1)]
    # 22:00 UTC Fri = 17:00 NY closes; reopening Sun 22:00 UTC. Expect only hours Sun 22:00..Mon 00:00 missing.
    gaps = find_gaps(ts, "1H", "fx_weekly")
    assert gaps and gaps[0]["missing"] == 3
    assert gaps[0]["start"] == dt(2024, 1, 7, 22).isoformat()


def test_normalization_rejects_invalid_and_dedupes():
    good = make_candles(3, UTC0)
    bad = Candle(UTC0 + timedelta(hours=9), Decimal(10), Decimal(9), Decimal(8), Decimal(9))  # high < open
    dup = good[1]
    out, rep = normalize_candles([good[2], bad, good[0], dup, good[1]])
    assert [c.ts for c in out] == [c.ts for c in good]
    assert rep.duplicates == 1 and len(rep.rejected) == 1
