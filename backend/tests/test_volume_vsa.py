"""Volume type, reliability and session-normalised relative volume (design section 3), and VSA (section 5)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np

from app.market_data.bars import Bars
from app.market_data.binance.provider import BinanceProvider
from app.market_data.types import Candle
from app.strategy_engine import vsa
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


# ---- VSA (design section 5) ---------------------------------------------------------------------------------------------------------
def _bars(o, h, lo, c, tb=None) -> Bars:
    b = Bars.from_arrays(o, h, lo, c, v=np.full(len(c), 100.0))
    if tb is not None:
        b.tb = np.asarray(tb, float)
    return b


def _series(n=70):
    """n quiet candles around 100 (range about 1 ATR with ATR = 1), RVOL = 1 everywhere."""
    o = np.full(n, 100.0)
    c = 100.0 + np.where(np.arange(n) % 2 == 0, 0.2, -0.2)
    h = np.maximum(o, c) + 0.4
    lo = np.minimum(o, c) - 0.4
    return o, h, lo, c, np.ones(n), np.ones(n)


def _events_at(b, atr_, rv, i):
    m = vsa.measures(b, atr_, rv)
    hi, lo = vsa.levels(b)
    return [e for e in vsa.detect(b, m, hi, lo) if e.idx == i]


def _decline(o, h, lo, c, end: int, size: float = 3.0):
    """Closes fall by `size` ATR over the 8 candles before `end` (a prior decline)."""
    for k, j in enumerate(range(end - 8, end)):
        p = 100 - size * (k + 1) / 8
        o[j], c[j], h[j], lo[j] = p + 0.1, p, p + 0.3, p - 0.3
    return o, h, lo, c


def test_vsa_thresholds_are_the_design_values():
    from app.strategy_engine.config import VSA_T
    assert (VSA_T["wide"], VSA_T["narrow"], VSA_T["top"], VSA_T["bottom"]) == (1.2, 0.6, 0.67, 0.33)
    assert (VSA_T["low"], VSA_T["high"], VSA_T["ultra"], VSA_T["prior_n"], VSA_T["prior_atr"]) == (0.7, 1.5, 2.5, 8, 2.0)
    assert (VSA_T["confirm_n"], VSA_T["test_n"], VSA_T["test_atr"], VSA_T["absorb_n"], VSA_T["absorb_atr"], VSA_T["level_n"]) == \
        (3, 10, 0.3, 5, 1.0, 50)


def test_high_volume_alone_is_never_an_event():
    o, h, lo, c, a, rv = _series()
    i = 60
    o[i], h[i], lo[i], c[i] = 100.0, 100.5, 99.5, 100.0  # spread 1 ATR, close mid-range, no prior move, inside the range
    rv[i] = 3.0  # ultra volume
    assert _events_at(_bars(o, h, lo, c), a, rv, i) == []


def test_stopping_volume_needs_a_prior_decline_and_a_close_off_the_low():
    o, h, lo, c, a, rv = _series()
    i = 60
    o, h, lo, c = _decline(o, h, lo, c, i)
    o[i], h[i], lo[i], c[i] = 97.0, 97.1, 96.0, 96.6  # down bar, close at 0.55 of its range
    rv[i] = 2.0
    ev = [e for e in _events_at(_bars(o, h, lo, c), a, rv, i) if e.kind == "stopping"]
    assert len(ev) == 1 and ev[0].direction == 1 and ev[0].confirm_n == 3
    c2 = c.copy()
    c2[i] = 96.1  # close in the bottom third: selling not stopped
    assert "stopping" not in [e.kind for e in _events_at(_bars(o, h, lo, c2), a, rv, i)]
    o3, h3, lo3, c3, a3, rv3 = _series()  # the same kind of bar without the prior decline
    o3[i], h3[i], lo3[i], c3[i] = 100.4, 100.5, 99.4, 100.0
    rv3[i] = 2.0
    assert "stopping" not in [e.kind for e in _events_at(_bars(o3, h3, lo3, c3), a3, rv3, i)]


def test_stopping_volume_is_unconfirmed_until_three_candles_then_confirmed_or_failed():
    o, h, lo, c, a, rv = _series()
    i = 60
    o, h, lo, c = _decline(o, h, lo, c, i)
    o[i], h[i], lo[i], c[i] = 97.0, 97.1, 96.0, 96.6
    rv[i] = 2.0
    for j in range(i + 1, 70):
        o[j], h[j], lo[j], c[j] = 96.6, 97.2, 96.3, 96.9  # holds above the stopping candle's low
    b = _bars(o, h, lo, c)
    e = next(e for e in _events_at(b, a, rv, i) if e.kind == "stopping")
    assert vsa.state(e, b, i + 1) == "unconfirmed" and vsa.state(e, b, i + 2) == "unconfirmed"
    assert vsa.state(e, b, i + 3) == "confirmed" and vsa.state(e, b, 69) == "confirmed"
    c[i + 2] = 95.5  # a close below the low inside the window
    b = _bars(o, h, lo, c)
    assert vsa.state(e, b, i + 1) == "unconfirmed" and vsa.state(e, b, i + 2) == "failed" and vsa.state(e, b, i + 5) == "failed"


def _spring_series(test_at: int | None = 65, test_rv: float = 0.5):
    o, h, lo, c, a, rv = _series(80)
    i = 60
    o[i], h[i], lo[i], c[i] = 99.5, 100.6, 98.5, 100.4  # undercuts the 50-candle low (99.4), closes back above in the top third
    rv[i] = 1.2
    if test_at is not None:
        j = test_at
        o[j], h[j], lo[j], c[j] = 99.6, 100.0, 98.6, 99.9  # back to the spring low on low volume, close in the top half
        rv[j] = test_rv
    return o, h, lo, c, a, rv


def test_spring_needs_a_meaningful_level_undercut_and_a_close_back_above():
    o, h, lo, c, a, rv = _spring_series(None)
    assert [e.kind for e in _events_at(_bars(o, h, lo, c), a, rv, 60)] == ["spring"]
    c2 = c.copy()
    c2[60] = 98.7  # closes below the level: a breakdown, not a spring
    assert "spring" not in [e.kind for e in _events_at(_bars(o, h, lo, c2), a, rv, 60)]
    lo3 = lo.copy()
    lo3[60] = 99.5  # does not undercut the level
    assert "spring" not in [e.kind for e in _events_at(_bars(o, h, lo3, c), a, rv, 60)]


def test_test_bar_must_follow_a_spring_within_ten_candles_on_low_volume():
    o, h, lo, c, a, rv = _spring_series(65)
    assert "test" in [e.kind for e in _events_at(_bars(o, h, lo, c), a, rv, 65)]
    o, h, lo, c, a, rv = _spring_series(65, test_rv=1.0)  # not low volume
    assert "test" not in [e.kind for e in _events_at(_bars(o, h, lo, c), a, rv, 65)]
    o, h, lo, c, a, rv = _spring_series(72)  # 12 candles after the spring
    assert "test" not in [e.kind for e in _events_at(_bars(o, h, lo, c), a, rv, 72)]


def test_absorption_requires_effort_without_result_at_a_level_and_a_move_away():
    o, h, lo, c, a, rv = _series(80)
    i = 60
    o, h, lo, c = _decline(o, h, lo, c, i, size=2.5)
    lo[30] = 97.2  # the 50-candle low: a support level at 97.2
    o[i], h[i], lo[i], c[i] = 97.45, 97.6, 97.1, 97.4  # narrow spread (0.5 ATR) on high volume at the support
    rv[i] = 2.0
    for j in range(i + 1, i + 4):
        o[j], h[j], lo[j], c[j] = 97.6 + 0.4 * (j - i), 98.2 + 0.4 * (j - i), 97.5 + 0.4 * (j - i), 98.0 + 0.4 * (j - i)
    b = _bars(o, h, lo, c)
    ev = {e.kind: e for e in _events_at(b, a, rv, i)}
    assert "effort_no_result" in ev and "absorption" in ev and ev["absorption"].direction == 1
    assert vsa.state(ev["absorption"], b, i + 2) == "confirmed"  # closed >= 1 ATR above the level within 5 candles
    c2 = c.copy()
    c2[i + 1:] = 97.5  # never moves away
    b2 = _bars(o, h, lo, c2)
    assert vsa.state(ev["absorption"], b2, i + 3) == "unconfirmed" and vsa.state(ev["absorption"], b2, i + 5) == "failed"


def test_zero_range_or_zero_atr_candle_produces_no_measure_and_no_event():
    o, h, lo, c, a, rv = _series()
    i = 60
    o[i] = h[i] = lo[i] = c[i] = 100.0  # a flat filler candle
    rv[i] = 3.0
    b = _bars(o, h, lo, c)
    m = vsa.measures(b, a, rv)
    assert np.isnan(m.spread[i]) and np.isnan(m.close_pos[i]) and _events_at(b, a, rv, i) == []
    a2 = a.copy()
    a2[i + 1] = 0.0
    m2 = vsa.measures(_bars(*_series()[:4]), a2, rv)
    assert np.isnan(m2.spread[i + 1])


def test_detect_is_causal():
    from app.feature_engineering.indicators import atr
    rng = np.random.default_rng(5)
    n = 600
    c = 100 + np.cumsum(rng.normal(0, 0.5, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 0.6, n)
    lo = np.minimum(o, c) - rng.uniform(0, 0.6, n)
    rv = rng.uniform(0.3, 3.0, n)
    full_b = _bars(o, h, lo, c)
    hi_l, lo_l = vsa.levels(full_b)
    full = [(e.kind, e.idx, e.direction) for e in vsa.detect(full_b, vsa.measures(full_b, atr(h, lo, c, 14), rv), hi_l, lo_l)]
    assert full  # the random walk produces events
    for k in (120, 333, 599):
        b = full_b.slice(0, k)
        hk, lk = vsa.levels(b)
        part = [(e.kind, e.idx, e.direction) for e in vsa.detect(b, vsa.measures(b, atr(h[:k], lo[:k], c[:k], 14), rv[:k]), hk, lk)]
        assert part == [x for x in full if x[1] < k]


def test_until_keeps_events_up_to_the_view_candle():
    evs = [vsa.VsaEvent("spring", 5, 1, 3, "x", 1.0, 1.0), vsa.VsaEvent("test", 9, 1, 0, "y", 1.0, 1.0)]
    assert [e.idx for e in vsa.until(evs, 8)] == [5]


def test_pressure_uses_taker_share_on_binance_and_says_inferred_elsewhere():
    o, h, lo, c, _, _ = _series(5)
    b = _bars(o, h, lo, c, tb=[60, 50, 40, 70, 30])  # volume 100 per candle
    assert vsa.pressure(b, 0) == {"source": "taker-buy share (Binance)", "value": 0.6, "side": "buying"}
    assert vsa.pressure(b, 2)["side"] == "selling" and vsa.pressure(b, 1)["side"] == "balanced"
    b2 = _bars(np.array([1.0]), np.array([2.0]), np.array([1.0]), np.array([1.9]))
    p2 = vsa.pressure(b2, 0)
    assert p2["source"] == "inferred from price" and p2["side"] == "buying" and np.isclose(p2["value"], 0.9)


def test_accumulation_label_needs_a_range_spring_and_test():
    o, h, lo, c, a, rv = _spring_series(65)
    b = _bars(o, h, lo, c)
    evs = vsa.detect(b, vsa.measures(b, a, rv), *vsa.levels(b))
    assert vsa.context_label(evs, (98.4, 101.0, 0), b, 70) == "potential accumulation"
    o, h, lo, c, a, rv = _spring_series(None)
    b = _bars(o, h, lo, c)
    evs = vsa.detect(b, vsa.measures(b, a, rv), *vsa.levels(b))
    assert vsa.context_label(evs, (98.4, 101.0, 0), b, 70) is None
    assert vsa.context_label(evs, None, b, 70) is None
