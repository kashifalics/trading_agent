"""Volume type, reliability and session-normalised relative volume (design section 3), and VSA (section 5)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np

from app.market_data.bars import Bars
from app.market_data.binance.provider import BinanceProvider
from app.market_data.types import Candle
from app.strategy_engine.config import VOLUME_LABELS
from app.strategy_engine.volume import hour_of_week, quality, rvol, session_ids

UTC = timezone.utc


def _hours(start: datetime, n: int) -> np.ndarray:
    return np.array([int((start + timedelta(hours=k)).timestamp()) for k in range(n)], dtype=np.int64)


# ---- volume -------------------------------------------------------------------------------------------------------------------------
def test_volume_labels_are_the_customer_copy():
    assert VOLUME_LABELS == {"base": "Exchange volume (Binance only)", "tick": "Tick volume (broker)",
                             "venue": "Venue volume (Dukascopy)", "none": "No volume"}


def test_rvol_compares_a_candle_with_the_same_hour_of_week_only():
    t = _hours(datetime(2024, 1, 1, tzinfo=UTC), 24 * 7 * 30)  # 30 weeks of hourly candles
    hod = (t // 3600) % 24
    v = np.where(hod == 8, 3.0, 1.0)  # the 08:00 candle is always three times busier
    v[-24 + 8] = 6.0  # the last day's 08:00 candle is twice its usual
    rv, n = rvol(v, t, 3600, "continuous")
    assert np.isclose(rv[-24 + 9], 1.0)  # an ordinary 09:00 candle
    assert np.isclose(rv[-24 * 2 + 8], 1.0)  # an ordinary 08:00 candle: compared with 08:00s, not with the whole day
    assert np.isclose(rv[-24 + 8], 2.0)
    assert n[-1] == 20 and n[0] == 0 and np.isnan(rv[0])


def test_rvol_falls_back_to_the_same_hour_of_day_with_under_four_weeks():
    t = _hours(datetime(2024, 1, 1, tzinfo=UTC), 24 * 10)  # 10 days: the same hour of the week has < 4 samples
    v = np.ones(len(t))
    rv, n = rvol(v, t, 3600, "continuous")
    assert n[-1] == 9 and np.isclose(rv[-1], 1.0)  # 9 earlier days at this hour (weekdays and weekends: 24/7 market)


def test_rvol_on_8h_and_above_uses_the_previous_20_candles():
    t = np.arange(40, dtype=np.int64) * 28800 + 1_700_000_000
    v = np.r_[np.ones(39), 4.0]
    rv, n = rvol(v, t, 28800, "fx_weekly")
    assert np.isclose(rv[-1], 4.0) and n[-1] == 20
    assert np.isnan(rv[3]) and n[3] == 3 and np.isfinite(rv[5])  # fewer than 4 earlier candles: no baseline yet


def test_rvol_is_causal():
    rng = np.random.default_rng(3)
    t = _hours(datetime(2024, 1, 1, tzinfo=UTC), 24 * 7 * 25)
    v = rng.uniform(1, 5, len(t))
    full, nf = rvol(v, t, 3600, "fx_weekly")
    for k in (100, 1000, 2500, len(t) - 1):
        part, npart = rvol(v[:k], t[:k], 3600, "fx_weekly")
        assert np.allclose(part, full[:k], equal_nan=True) and (npart == nf[:k]).all()


def test_hour_of_week_follows_new_york_dst_for_fx_and_utc_for_continuous():
    winter = int(datetime(2024, 3, 8, 21, tzinfo=UTC).timestamp())  # Friday 16:00 New York (EST)
    summer = int(datetime(2024, 3, 15, 20, tzinfo=UTC).timestamp())  # Friday 16:00 New York (EDT)
    fx = hour_of_week(np.array([winter, summer]), "fx_weekly")
    utc = hour_of_week(np.array([winter, summer]), "continuous")
    assert fx[0] == fx[1] and utc[0] != utc[1]


def test_session_ids_reset_at_17_new_york_in_both_seasons_and_at_utc_midnight_for_crypto():
    jan = _hours(datetime(2024, 1, 10, 18, tzinfo=UTC), 8)  # 18:00 .. 01:00 UTC
    s = session_ids(jan, "fx_weekly")
    assert (np.diff(s) != 0).nonzero()[0].tolist() == [3]  # new session at 22:00 UTC = 17:00 EST
    jul = _hours(datetime(2024, 7, 10, 18, tzinfo=UTC), 8)
    s = session_ids(jul, "fx_weekly")
    assert (np.diff(s) != 0).nonzero()[0].tolist() == [2]  # 21:00 UTC = 17:00 EDT
    s = session_ids(jan, "continuous")
    assert (np.diff(s) != 0).nonzero()[0].tolist() == [5]  # 00:00 UTC


def _healthy(n: int = 3000) -> np.ndarray:
    return np.random.default_rng(1).uniform(50, 150, n).round(0) + np.arange(n) % 7


def test_quality_reliable_for_a_healthy_tick_series():
    v = _healthy()
    q = quality(v, "tick", len(v) - 1, np.full(len(v), 20))
    assert q.reliable and q.type == "tick" and q.label == "Tick volume (broker)" and q.reason == ""


def test_quality_unavailable_for_mixed_zero_constant_or_missing_volume():
    n20 = np.full(3000, 20)
    v = _healthy()
    v[::10] = 0.0  # 10% zeros (a provider fallback without volume)
    q = quality(v, "tick", 2999, n20)
    assert not q.reliable and "zero" in q.reason
    v = _healthy()
    v[-12:] = 77.0  # a stuck feed
    q = quality(v, "tick", 2999, n20)
    assert not q.reliable and "constant" in q.reason
    v = _healthy()
    v[-200:] = np.nan
    assert not quality(v, "tick", 2999, n20).reliable
    q = quality(_healthy(), "none", 2999, n20)
    assert not q.reliable and q.label == "No volume" and "no volume" in q.reason


def test_quality_unavailable_when_history_is_shorter_than_four_samples():
    v = _healthy(50)
    q = quality(v, "tick", 49, np.full(50, 3))
    assert not q.reliable and "baseline" in q.reason


# ---- Bars carry the volume type and Binance taker-buy volume ------------------------------------------------------------------------
def _candle(k: int, vt: str = "base", tb: float | None = 1.0) -> Candle:
    return Candle(ts=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=k), open=Decimal(1), high=Decimal(2), low=Decimal(1),
                  close=Decimal(2), volume=Decimal(3), volume_type=vt, complete=True,
                  meta={} if tb is None else {"taker_buy_base": str(tb)})


def test_binance_candles_keep_taker_buy_and_bars_carry_it():
    c = BinanceProvider._parse([1704067200000, "1", "2", "0.5", "1.5", "10", 1704067259999, "15", 7, "6", "9", "0"],
                               now_ms=1704067300000)
    assert c.meta["taker_buy_base"] == "6"
    b = Bars.from_candles([_candle(k, tb=0.5 * k) for k in range(4)], 3600)
    assert b.vtype == "base" and b.tb.tolist() == [0.0, 0.5, 1.0, 1.5]
    s = b.slice(1, 3)
    assert s.vtype == "base" and s.tb.tolist() == [0.5, 1.0]
    b = Bars.from_candles([_candle(0, tb=None), _candle(1)], 3600)
    assert b.tb is None  # taker-buy only when every candle has it
    b = Bars.from_candles([_candle(0, "tick"), _candle(1, "tick"), _candle(2, "none")], 3600)
    assert b.vtype == "tick"  # the most common type; quality() then catches the gap in the volumes
