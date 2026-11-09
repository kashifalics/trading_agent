"""Combinations and multi-timeframe flags (TEST FIXTURES ONLY: hand-made events and states)."""
import numpy as np
import polars as pl

from app.gold_research import combos


def test_combination_needs_a_same_direction_or_neutral_A_inside_the_window():
    events = pl.DataFrame({"pattern": ["liquidity_sweep", "liquidity_sweep", "compression", "liquidity_sweep"],
                           "direction": [1, -1, 0, 1], "idx": [100, 200, 295, 400]})
    trades = pl.DataFrame({"pattern": ["CHoCH", "CHoCH", "CHoCH", "CHoCH", "liquidity_sweep"],
                           "direction": [1, 1, -1, 1, 1], "idx": [105, 125, 205, 400, 300]})
    f = combos.combo_flags(trades, events)
    assert f["combo:sweep+choch"].to_list() == [True, False, True, True, False]  # 20 candles late: no; opposite sweep: no
    assert f["combo:compression+sweep"].to_list() == [False, False, False, False, True]  # neutral A pairs with either direction


def test_mtf_flags_use_only_higher_timeframe_candles_closed_at_the_signal():
    h = 3600
    trades = pl.DataFrame({"signal_ts": np.array([10 * h, 10 * h]), "direction": [1, -1]})
    bias = {"close": np.array([5 * h, 9 * h, 11 * h]), "trend": np.array([-1, 1, -1], np.int8), "regime": np.array([0, 1, -1]),
            "break_dir": np.zeros(3, np.int8), "break_close": np.full(3, -1)}
    ctx = {"close": np.array([0, 8 * h, 12 * h]), "trend": np.array([0, 1, 1], np.int8), "regime": np.array([0, 1, -1]),
           "break_dir": np.zeros(3, np.int8), "break_close": np.full(3, -1)}
    conf = {"close": np.array([9 * h + 2700, 9 * h + 3600, 10 * h + 900]), "trend": np.zeros(3, np.int8), "regime": np.zeros(3),
            "break_dir": np.array([0, 1, -1], np.int8), "break_close": np.array([-1, 9 * h + 3600, 10 * h + 900])}
    f = combos.mtf_flags(trades, "H1", {"H4": bias, "D1": ctx, "M15": conf})
    # signal candle (H1) closes at 11h: bias candle closing at 11h is usable (trend -1); the D1 one closing at 12h is not (regime 1)
    assert f["mtf:intraday:bias"].to_list() == [False, True]
    assert f["mtf:intraday:counter"].to_list() == [True, False]
    assert f["mtf:intraday:bias+context"].to_list() == [False, False]
    assert not f["mtf:scalp:bias"].any() and len(combos.extra_tests("H1")) == len(combos.PAIRS) + len(combos.MTF_PATTERNS) * 4
