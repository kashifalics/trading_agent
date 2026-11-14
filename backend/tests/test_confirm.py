"""The confirmation matrix (docs/engine_v2/CONFIRMATION_DESIGN.md sections 6-8): worked examples for every rule."""
from dataclasses import replace

import numpy as np
import pytest

from app.market_data.bars import Bars
from app.strategy_engine import confirm
from app.strategy_engine.config import COMBOS, CONFIRM, GATES, validate_gates
from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies.base import Candidate
from app.strategy_engine.vsa import VsaEvent

N = 300
LAST = N - 1  # the view candle


def base_t(vtype: str = "tick", seed: int = 2) -> TFData:
    """300 hourly candles of a mild uptrend with healthy volume; arrays are overridden per test."""
    rng = np.random.default_rng(seed)
    c = 100 + np.cumsum(rng.normal(0.05, 0.4, N))
    o = np.r_[c[0], c[:-1]]
    h, lo = np.maximum(o, c) + 0.3, np.minimum(o, c) - 0.3
    b = Bars.from_arrays(o, h, lo, c, v=rng.uniform(80, 120, N).round(0) + np.arange(N) % 5, t0=1_704_067_200, step=3600)
    return TFData.build("1H", b, calendar="continuous", vtype=vtype)


def put(t: TFData, name: str, last_values: list[float], fill: float = np.nan) -> TFData:
    """A copy of t whose array `name` ends with last_values (the rest = fill)."""
    a = np.full(N, fill)
    a[N - len(last_values):] = last_values
    return replace(t, **{name: a})


def bars_with(t: TFData, rows: dict[int, tuple[float, float, float, float]]) -> TFData:
    o, h, lo, c = (x.astype(float).copy() for x in (t.bars.o, t.bars.h, t.bars.l, t.bars.c))
    for k, (oo, hh, ll, cc) in rows.items():
        o[k], h[k], lo[k], c[k] = oo, hh, ll, cc
    b = Bars(t.bars.t, o, h, lo, c, t.bars.v, t.bars.step, t.bars.vtype, t.bars.tb)
    return replace(t, bars=b)


# ---- trend (all strategies) -------------------------------------------------------------------------------------------------------
def _trend(t, close_vs_ema200: float, di_spread: float, d: int = 1) -> tuple:
    c = float(t.bars.c[LAST])
    t = put(t, "ema200", [c - close_vs_ema200])
    t = put(put(t, "pdi", [20 + di_spread / 2]), "mdi", [20 - di_spread / 2])
    t = put(t, "vwap", [np.nan])  # VWAP not available in these cases
    return confirm.trend_verdict(t, d)


def test_trend_pass_fail_neutral_unavailable():
    t = base_t()
    assert _trend(t, 1.0, 8.0)[0] == "PASS"  # above EMA200 and +DI leads by 8
    assert _trend(t, -1.0, -8.0)[0] == "FAIL"
    assert _trend(t, 1.0, -8.0)[0] == "NEUTRAL"  # one for, one against
    assert _trend(t, 1.0, 2.0)[0] == "NEUTRAL"  # DI spread inside +-5: flat
    assert _trend(t, -1.0, -8.0, d=-1)[0] == "PASS"  # a SELL below EMA200 with -DI leading
    t2 = put(put(t, "ema200", [np.nan]), "pdi", [np.nan])
    v, reason, _ = confirm.trend_verdict(put(t2, "vwap", [np.nan]), 1)
    assert v == "UNAVAILABLE" and "2" in reason


def test_trend_uses_vwap_on_intraday_with_reliable_volume():
    t = base_t()
    c = float(t.bars.c[LAST])
    t = put(put(put(t, "ema200", [c - 1]), "pdi", [20]), "mdi", [20])  # EMA200 for, DI flat
    assert confirm.trend_verdict(put(t, "vwap", [c - 0.5]), 1)[0] == "PASS"  # VWAP for: two for, none against
    assert confirm.trend_verdict(put(t, "vwap", [c + 0.5]), 1)[0] == "NEUTRAL"


def test_trend_ignores_signals_the_regime_already_uses():
    t = base_t()
    v0 = confirm.trend_verdict(t, 1)
    t2 = replace(t, ema20=t.ema20 * 0.5, ema50=t.ema50 * 2.0, adx=t.adx * 0 + 99)
    assert confirm.trend_verdict(t2, 1) == v0


# ---- momentum (one primary indicator per strategy) ----------------------------------------------------------------------------------
@pytest.mark.parametrize("strategy", ["trend_pullback", "sweep_reversal"])
def test_momentum_macd_rising_two_candles(strategy):
    t = base_t()
    assert confirm.momentum_verdict(strategy, put(t, "macd_hist", [0.1, 0.2, 0.3]), 1)[0] == "PASS"
    assert confirm.momentum_verdict(strategy, put(t, "macd_hist", [0.3, 0.2, 0.1]), 1)[0] == "FAIL"
    assert confirm.momentum_verdict(strategy, put(t, "macd_hist", [0.1, 0.3, 0.2]), 1)[0] == "NEUTRAL"
    assert confirm.momentum_verdict(strategy, put(t, "macd_hist", [0.3, 0.2, 0.1]), -1)[0] == "PASS"  # falling: for a SELL
    assert confirm.momentum_verdict(strategy, put(t, "macd_hist", [0.1, np.nan, 0.3]), 1)[0] == "UNAVAILABLE"


def test_momentum_continuation_needs_a_histogram_for_the_trade_and_not_shrinking():
    t = base_t()
    assert confirm.momentum_verdict("momentum_continuation", put(t, "macd_hist", [0.2, 0.1, 0.1, 0.25]), 1)[0] == "PASS"
    assert confirm.momentum_verdict("momentum_continuation", put(t, "macd_hist", [0.2, 0.1, 0.1, -0.05]), 1)[0] == "FAIL"
    assert confirm.momentum_verdict("momentum_continuation", put(t, "macd_hist", [0.4, 0.3, 0.2, 0.1]), 1)[0] == "NEUTRAL"


@pytest.mark.parametrize("strategy", ["breakout_retest", "volatility_expansion"])
def test_momentum_roc_with_a_dead_zone(strategy):
    t = base_t()
    a = float(t.atr[LAST])
    c = t.bars.c.astype(float).copy()

    def with_change(x):
        cc = c.copy()
        cc[LAST - 10] = cc[LAST] - x
        return replace(t, bars=Bars(t.bars.t, t.bars.o, t.bars.h, t.bars.l, cc, t.bars.v, t.bars.step, t.bars.vtype),
                       roc10=np.r_[np.full(N - 1, np.nan), cc[LAST] / cc[LAST - 10] - 1])

    assert confirm.momentum_verdict(strategy, with_change(1.0 * a), 1)[0] == "PASS"
    assert confirm.momentum_verdict(strategy, with_change(-1.0 * a), 1)[0] == "FAIL"
    assert confirm.momentum_verdict(strategy, with_change(0.1 * a), 1)[0] == "NEUTRAL"  # within 0.25 ATR


def test_momentum_range_reversion_uses_a_stoch_rsi_cross_from_the_extreme():
    t = base_t()
    up = put(put(t, "stoch_k", [10.0, 15.0, 30.0]), "stoch_d", [12.0, 16.0, 20.0])  # %K crosses %D from below 20
    assert confirm.momentum_verdict("range_reversion", up, 1)[0] == "PASS"
    hot = put(put(t, "stoch_k", [70.0, 80.0, 90.0]), "stoch_d", [70.0, 75.0, 85.0])
    assert confirm.momentum_verdict("range_reversion", hot, 1)[0] == "FAIL"  # %K beyond 80 for a BUY
    mid = put(put(t, "stoch_k", [40.0, 45.0, 55.0]), "stoch_d", [42.0, 46.0, 50.0])  # a cross, but not from the extreme
    assert confirm.momentum_verdict("range_reversion", mid, 1)[0] == "NEUTRAL"
    down = put(put(t, "stoch_k", [90.0, 85.0, 70.0]), "stoch_d", [88.0, 84.0, 80.0])
    assert confirm.momentum_verdict("range_reversion", down, -1)[0] == "PASS"


def test_momentum_uses_one_primary_indicator_and_agreement_adds_nothing():
    t = put(base_t(), "macd_hist", [0.1, 0.2, 0.3])
    v1 = confirm.momentum_verdict("trend_pullback", t, 1)
    other = replace(t, rsi=t.rsi * 0 + 10, stoch_k=t.stoch_k * 0 + 5, roc10=t.roc10 * 0 - 0.5)  # every secondary disagrees
    v2 = confirm.momentum_verdict("trend_pullback", other, 1)
    assert v1[0] == v2[0] == "PASS"
    assert set(v1[2]) >= {"macd_hist", "rsi", "stoch_k", "roc10"}  # all shown as evidence


# ---- volatility ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("pct,verdict", [(0.5, "PASS"), (0.2, "PASS"), (0.9, "PASS"), (0.97, "FAIL"), (0.05, "FAIL"), (0.15, "NEUTRAL"),
                                         (0.93, "NEUTRAL"), (np.nan, "UNAVAILABLE")])
def test_volatility_atr_percentile(pct, verdict):
    assert confirm.volatility_verdict("trend_pullback", put(base_t(), "atr_pct", [pct]), 1, {})[0] == verdict


def test_volatility_expansion_uses_the_keltner_band():
    t = put(put(put(base_t(), "kc_up", [101.0]), "kc_mid", [100.0]), "kc_lo", [99.0])
    def at_close(x):
        return bars_with(t, {LAST: (100.0, max(x, 100.0) + 0.1, min(x, 100.0) - 0.1, x)})
    anchors = {"expansion": LAST, "box_hi": 100.5, "box_lo": 99.5}
    assert confirm.volatility_verdict("volatility_expansion", at_close(101.5), 1, anchors)[0] == "PASS"
    assert confirm.volatility_verdict("volatility_expansion", at_close(99.5), 1, anchors)[0] == "FAIL"
    assert confirm.volatility_verdict("volatility_expansion", at_close(100.5), 1, anchors)[0] == "NEUTRAL"
    assert confirm.volatility_verdict("volatility_expansion", at_close(101.5), 1, {})[0] == "UNAVAILABLE"


# ---- VSA ------------------------------------------------------------------------------------------------------------------------------
def rv(t: TFData, values: dict[int, float], base: float = 1.0) -> TFData:
    a = np.full(N, base)
    for k, x in values.items():
        a[k] = x
    return replace(t, rv=a, vsa_m=replace(t.vsa_m, rvol=a), vsa_events=[])


def test_vsa_unavailable_with_the_reason_when_volume_is_unreliable():
    t = base_t()
    v = t.bars.v.copy()
    v[::5] = 0.0
    t = replace(t, bars=Bars(t.bars.t, t.bars.o, t.bars.h, t.bars.l, t.bars.c, v, t.bars.step, "tick"))
    out = confirm.vsa_verdict("volatility_expansion", t, 1, {"expansion": LAST, "box_hi": 1.0, "box_lo": 0.0})
    assert out[0] == "UNAVAILABLE" and "zero" in out[1]
    assert confirm.vsa_verdict("volatility_expansion", base_t(vtype="none"), 1, {"expansion": LAST})[0] == "UNAVAILABLE"


def test_vsa_trend_pullback():
    t = base_t()
    pb = {"pullback": [LAST - 3, LAST - 2, LAST - 1], "trigger": LAST}
    assert confirm.vsa_verdict("trend_pullback", rv(t, {LAST - 3: 0.6, LAST - 2: 0.7, LAST - 1: 0.8}), 1, pb)[0] == "PASS"
    assert confirm.vsa_verdict("trend_pullback", rv(t, {LAST - 3: 1.4, LAST - 2: 1.3, LAST - 1: 1.5}), 1, pb)[0] == "FAIL"
    assert confirm.vsa_verdict("trend_pullback", rv(t, {LAST - 3: 1.0, LAST - 2: 1.0, LAST - 1: 1.0}), 1, pb)[0] == "NEUTRAL"
    heavy = bars_with(rv(t, {LAST - 3: 0.5, LAST - 2: 2.0, LAST - 1: 0.5}), {LAST - 2: (100.0, 100.1, 98.0, 98.1)})  # a wide, heavy down candle
    heavy = replace(heavy, atr=np.full(N, 1.0))
    assert confirm.vsa_verdict("trend_pullback", heavy, 1, pb)[0] == "FAIL"
    assert confirm.vsa_verdict("trend_pullback", t, 1, {})[0] == "UNAVAILABLE"  # no key candles


def test_vsa_breakout_retest():
    t = base_t()
    a = {"breakout": LAST - 3, "retest": [LAST - 1, LAST], "level": 100.0}
    assert confirm.vsa_verdict("breakout_retest", rv(t, {LAST - 3: 1.8, LAST - 1: 0.8, LAST: 0.9}), 1, a)[0] == "PASS"
    assert confirm.vsa_verdict("breakout_retest", rv(t, {LAST - 3: 0.9}), 1, a)[0] == "FAIL"
    assert confirm.vsa_verdict("breakout_retest", rv(t, {LAST - 3: 1.8, LAST - 1: 1.3, LAST: 1.4}), 1, a)[0] == "NEUTRAL"
    fresh = {"breakout": LAST, "retest": [], "level": 100.0}  # the breakout is the last candle: no retest candles yet
    assert confirm.vsa_verdict("breakout_retest", rv(t, {LAST: 1.8}), 1, fresh)[0] == "PASS"


def test_vsa_momentum_continuation():
    t = base_t()
    a = {"displacement": LAST - 3, "pullback": [LAST - 2, LAST - 1, LAST]}
    assert confirm.vsa_verdict("momentum_continuation", rv(t, {LAST - 3: 2.0, LAST - 2: 0.8, LAST - 1: 0.9, LAST: 1.0}), 1, a)[0] == "PASS"
    assert confirm.vsa_verdict("momentum_continuation", rv(t, {LAST - 3: 0.8}), 1, a)[0] == "FAIL"
    assert confirm.vsa_verdict("momentum_continuation", rv(t, {LAST - 3: 2.0, LAST - 2: 1.5, LAST - 1: 1.5, LAST: 1.5}), 1, a)[0] == "NEUTRAL"
    climax = replace(rv(t, {LAST - 3: 2.0, LAST - 2: 0.8, LAST - 1: 0.9, LAST: 1.0}),
                     vsa_events=[VsaEvent("climactic", LAST - 1, 1, 0, "climactic volume")])
    assert confirm.vsa_verdict("momentum_continuation", climax, 1, a)[0] == "FAIL"  # exhaustion in the trade's direction


def test_vsa_range_reversion_and_unconfirmed_events_cannot_pass():
    t = rv(base_t(), {})
    a = {"touch": [LAST - 2, LAST - 1, LAST], "boundary": 100.0}
    no_demand = replace(t, vsa_events=[VsaEvent("no_demand", LAST - 1, -1, 0, "no demand")])
    assert confirm.vsa_verdict("range_reversion", no_demand, -1, a)[0] == "PASS"  # SELL at the top
    spring_only = replace(t, vsa_events=[VsaEvent("spring", LAST - 1, 1, 3, "spring", ref=99.0, atr=1.0)])
    assert confirm.vsa_verdict("range_reversion", spring_only, 1, a)[0] == "NEUTRAL"  # still unconfirmed: cannot pass
    assert confirm.vsa_verdict("range_reversion", t, 1, a)[0] == "NEUTRAL"
    against = bars_with(replace(rv(base_t(), {LAST: 2.0}), atr=np.full(N, 1.0)), {LAST: (100.0, 100.1, 98.0, 98.1)})
    assert confirm.vsa_verdict("range_reversion", against, 1, a)[0] == "FAIL"  # heavy wide candle closing down for a BUY


def test_vsa_sweep_reversal():
    t = base_t()
    a = {"sweep": LAST - 2, "level": 99.0}
    assert confirm.vsa_verdict("sweep_reversal", rv(t, {LAST - 2: 1.3}), 1, a)[0] == "PASS"
    tested = replace(rv(t, {LAST - 2: 0.8}), vsa_events=[VsaEvent("test", LAST, 1, 0, "test")])
    assert confirm.vsa_verdict("sweep_reversal", tested, 1, a)[0] == "PASS"
    assert confirm.vsa_verdict("sweep_reversal", rv(t, {LAST - 2: 0.8}), 1, a)[0] == "NEUTRAL"
    effort = bars_with(replace(rv(t, {LAST - 2: 1.3, LAST - 1: 2.0}), atr=np.full(N, 1.0)), {LAST - 1: (100.0, 100.1, 98.0, 98.1)})
    assert confirm.vsa_verdict("sweep_reversal", effort, 1, a)[0] == "FAIL"  # heavy selling continues after the sweep


def test_vsa_volatility_expansion():
    t = base_t()
    a = {"expansion": LAST, "box_hi": 100.0, "box_lo": 99.0}
    assert confirm.vsa_verdict("volatility_expansion", rv(t, {LAST: 1.6}), 1, a)[0] == "PASS"
    assert confirm.vsa_verdict("volatility_expansion", rv(t, {LAST: 0.9}), 1, a)[0] == "FAIL"
    assert confirm.vsa_verdict("volatility_expansion", rv(t, {LAST: 1.2}), 1, a)[0] == "NEUTRAL"


# ---- the matrix, combinations and gates ----------------------------------------------------------------------------------------------
def _cand(status: str = "ready", strategy: str = "trend_pullback") -> Candidate:
    c = Candidate(strategy, 1, status, "market", 100.0, None, 99.0, LAST, "continuation close", ["uptrend", "pullback to EMA20"])
    return c.tag(["regime", "structure"], {"pullback": [LAST - 2, LAST - 1], "trigger": LAST})


def test_score_returns_ten_components_in_design_order():
    t = base_t()
    comps = confirm.score(_cand(), t, Regime("TRENDING", 1, None, "uptrend"), None, {"risk_reward": 2.4}, blocked=[], stale=False,
                          symbol="BTCUSDT")
    assert [c.key for c in comps] == ["regime", "htf", "entry", "structure", "vsa", "momentum", "trend", "volatility", "execution", "rr"]
    by = {c.key: c for c in comps}
    assert [c.key for c in comps if c.mandatory] == ["regime", "htf", "entry", "structure", "execution", "rr"]
    assert by["regime"].verdict == "PASS" and by["entry"].verdict == "PASS" and by["structure"].verdict == "PASS"
    assert by["htf"].verdict == "NEUTRAL" and by["execution"].verdict == "PASS" and by["rr"].verdict == "PASS"
    assert all(by[k].note == "evidence only — not tested" and not by[k].gating for k in ("vsa", "momentum", "trend", "volatility"))
    pending = {c.key: c for c in confirm.score(_cand("pending"), t, Regime("TRENDING", 1), None, {"risk_reward": 2.0}, blocked=["the market is closed"],
                                               stale=False, symbol="BTCUSDT")}
    assert pending["entry"].verdict == "NEUTRAL" and pending["execution"].verdict == "FAIL"
    hv = {c.key: c for c in confirm.score(_cand(), t, Regime("HIGH_VOLATILITY"), None, None, blocked=[], stale=True, symbol="BTCUSDT")}
    assert hv["regime"].verdict == "FAIL" and hv["rr"].verdict == "FAIL" and hv["execution"].verdict == "FAIL"


def test_unavailable_never_passes_a_combination():
    comps = [confirm.Component(k, k, "PASS", "", {}, False) for k in ("trend", "momentum")] + \
            [confirm.Component("vsa", "VSA", "UNAVAILABLE", "no volume", {}, False)]
    assert not confirm.combo_pass(comps, "trend_pullback")
    comps[-1] = confirm.Component("vsa", "VSA", "PASS", "", {}, False)
    assert confirm.combo_pass(comps, "trend_pullback")
    assert COMBOS["momentum_continuation"] == ("trend", "momentum", "volatility")


def test_gates_reject_gold_vsa_and_unknown_names():
    assert GATES == {}  # empty until Experiment 6 promotes a category
    validate_gates({"BTCUSDT": {"trend_pullback": ("vsa", "momentum")}, "XAUUSD": {"momentum_continuation": ("trend",)}})
    for bad in ({"XAUUSD": {"trend_pullback": ("vsa",)}}, {"XAUUSD": {"trend_pullback": ("momentum", "vsa")}},
                {"BTCUSDT": {"nope": ("trend",)}}, {"BTCUSDT": {"trend_pullback": ("rsi",)}}, {"DOGE": {"trend_pullback": ("trend",)}}):
        with pytest.raises(ValueError):
            validate_gates(bad)


def test_gate_failures_only_for_promoted_categories(monkeypatch):
    comps = [confirm.Component("momentum", "Momentum", "FAIL", "MACD falling", {}, False),
             confirm.Component("trend", "Trend", "NEUTRAL", "mixed", {}, False)]
    assert confirm.gate_failures(comps, "BTCUSDT", "trend_pullback") == []
    monkeypatch.setitem(GATES, "BTCUSDT", {"trend_pullback": ("momentum",)})
    assert [c.key for c in confirm.gate_failures(comps, "BTCUSDT", "trend_pullback")] == ["momentum"]
    assert confirm.gate_failures(comps, "XAUUSD", "trend_pullback") == []  # a gate applies only to its instrument


def test_thresholds_are_the_design_values():
    assert CONFIRM["di_for"] == 5.0 and CONFIRM["atr_pct_pass"] == (20, 90) and CONFIRM["atr_pct_fail"] == (10, 95)
    assert CONFIRM["roc_dead_atr"] == 0.25 and (CONFIRM["stoch_lo"], CONFIRM["stoch_hi"]) == (20, 80)
    assert (CONFIRM["pullback_rvol_pass"], CONFIRM["pullback_rvol_fail"], CONFIRM["breakout_rvol"], CONFIRM["retest_rvol"]) == (0.8, 1.3, 1.5, 1.0)
    assert (CONFIRM["weak_rvol"], CONFIRM["disp_rvol"], CONFIRM["disp_pullback_ratio"], CONFIRM["sweep_rvol"], CONFIRM["expansion_rvol"]) == \
        (1.0, 1.5, 0.6, 1.2, 1.5)


def test_tfdata_carries_the_new_arrays_and_volume_quality():
    t = base_t()
    for name in ("ema200", "macd_hist", "stoch_k", "stoch_d", "roc10", "kc_mid", "kc_up", "kc_lo", "hv20", "hv_pct", "vwap", "rv", "rv_n"):
        assert len(getattr(t, name)) == N, name
    assert t.vtype == "tick" and t.calendar == "continuous" and t.volume.reliable
    assert np.isnan(t.ema200[:199]).all() and np.isfinite(t.ema200[199])
    v = t.at(150)
    assert v.last == 150 and v.volume.type == "tick"  # a replay view keeps every array
    daily = TFData.build("1D", Bars.from_arrays(t.bars.o, t.bars.h, t.bars.l, t.bars.c, v=t.bars.v, step=86400), calendar="continuous", vtype="tick")
    assert np.isnan(daily.vwap).all()  # VWAP only on timeframes up to 1H
