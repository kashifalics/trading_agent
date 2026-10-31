"""Audit tests for the backtester: timing, accounting, costs, sizing, duplicate counting, look-ahead."""
from datetime import datetime, timezone

import numpy as np
import pytest

from app.backtesting.engine import BacktestConfig, run_backtest
from app.backtesting.strategies import (
    DecisionEngineStrategy,
    MACrossStrategy,
    RandomEntryStrategy,
    Signal,
)
from app.market_data.bars import Bars
from tests.test_backtest_policy import LONG, Scripted, flat
from tests.test_ml_analogues import walk

COSTS = dict(spread=0.3, slippage=0.1, commission_pct=0.05, spread_pct=0.002, slippage_pct=0.01)


def iso(t) -> str:
    return datetime.fromtimestamp(int(t), tz=timezone.utc).isoformat()


def test_costs_target_pays_entry_half_spread_stop_pays_both_halves():
    tgt = run_backtest(flat(edits={62: (100, 102.6, 99.5, 102)}), Scripted(60, LONG), BacktestConfig(spread=0.4)).trades[0]
    stp = run_backtest(flat(edits={62: (100, 100.5, 98, 98.5)}), Scripted(60, LONG), BacktestConfig(spread=0.4)).trades[0]
    u = tgt["units"]
    assert tgt["exit_reason"] == "target" and tgt["costs"] == pytest.approx(0.2 * u)
    assert stp["exit_reason"] == "stop" and stp["costs"] == pytest.approx(0.4 * stp["units"])


def test_percentage_costs_scale_with_price():
    def entry_offset(price):
        b = Bars.from_arrays(*(np.full(100, v) for v in (price, price * 1.005, price * 0.995, price)))
        t = run_backtest(b, Scripted(60, Signal("BUY", price * 0.99, price * 1.05)),
                         BacktestConfig(spread_pct=0.02, slippage_pct=0.01)).trades[0]
        return (t["entry_price"] - price) / price
    assert entry_offset(100.0) == pytest.approx(entry_offset(10_000.0))
    assert entry_offset(100.0) == pytest.approx(0.0001 + 0.0001)  # half of 0.02% + 0.01% slippage


def test_entry_fills_at_next_open_plus_costs_never_signal_close():
    b = flat(edits={61: (101.0, 101.5, 100.5, 101.2)})
    t = run_backtest(b, Scripted(60, Signal("BUY", 99.0, 110.0)), BacktestConfig(spread=0.2, slippage=0.05)).trades[0]
    assert t["entry_price"] == pytest.approx(101.0 + 0.1 + 0.05)
    assert t["entry_ts"] == iso(b.t[61]) and t["signal_ts"] == iso(b.t[60])


def invariants(trades, bars, cfg):
    t_index = {iso(t): i for i, t in enumerate(bars.t)}
    last_exit = -1
    seen_signals = set()
    for t in trades:
        s, e, x = t_index[t["signal_ts"]], t_index[t["entry_ts"]], t_index[t["exit_ts"]]
        assert e == s + 1, "entry must be exactly the bar after the signal"
        assert x >= e and e > last_exit, "trades overlap or exit precedes entry"
        assert t["signal_ts"] not in seen_signals, "a signal produced two trades"
        seen_signals.add(t["signal_ts"])
        last_exit = x
        half = cfg.spread / 2 + cfg.spread_pct / 100 * bars.o[e] / 2
        slip = cfg.slippage + cfg.slippage_pct / 100 * bars.o[e]
        d = 1 if t["direction"] == "BUY" else -1
        assert t["entry_price"] == pytest.approx(bars.o[e] + d * (half + slip))
        if t["exit_reason"] == "target":
            assert t["exit_price"] == pytest.approx(t["take_profit"])
        if t["exit_reason"] == "stop":  # a stop never fills better than the stop level
            assert d * (t["exit_price"] - t["stop_loss"]) <= 1e-9
        assert t["costs"] >= 0 and t["units"] > 0


@pytest.mark.parametrize("strategy", [MACrossStrategy(), RandomEntryStrategy(p=0.05, seed=3)], ids=["ma_cross", "random"])
def test_accounting_identity_no_overlap_no_duplicates(strategy):
    bars = walk(1500, seed=33, vol=1.5)
    cfg = BacktestConfig(**COSTS, max_bars_in_trade=40)
    r = run_backtest(bars, strategy, cfg)
    assert len(r.trades) > 20
    invariants(r.trades, bars, cfg)
    # equity bookkeeping: final equity == initial + sum of per-trade P&L (commissions and spreads included)
    assert r.equity_curve[-1][1] == pytest.approx(cfg.initial_equity + sum(t["pnl"] for t in r.trades), rel=1e-9)


def test_position_size_risks_exactly_risk_pct_of_equity_at_entry():
    bars = walk(1200, seed=9, vol=1.2)
    cfg = BacktestConfig(risk_pct=1.0, max_leverage=1e9)  # no costs, no leverage cap: pure sizing
    r = run_backtest(bars, MACrossStrategy(), cfg)
    equity = cfg.initial_equity
    for t in r.trades:
        assert abs(t["entry_price"] - t["stop_loss"]) * t["units"] == pytest.approx(equity * 0.01, rel=1e-9)
        equity += t["pnl"]


def test_leverage_cap_limits_units_and_r_uses_actual_risk():
    b = flat(edits={62: (100, 100.5, 98, 98.5)})
    t = run_backtest(b, Scripted(60, Signal("BUY", 99.9, 110.0)), BacktestConfig(max_leverage=2.0)).trades[0]
    assert t["units"] * 100 <= 2.0 * 10_000 + 1e-6  # capped, would otherwise be 10x larger
    assert t["r_multiple"] == pytest.approx(-1.0)  # R is relative to the risk actually taken ...
    assert -100 < t["pnl"] < -10  # ... which the cap made smaller than the planned 1% (-100)


def test_decision_engine_strategy_has_no_lookahead():
    a = walk(900, seed=21, drift=0.1)
    b = Bars(a.t.copy(), a.o.copy(), a.h.copy(), a.l.copy(), a.c.copy(), a.v.copy(), a.step)
    cut = 600
    for arr in (b.o, b.h, b.l, b.c):
        arr[cut:] = arr[cut:] * 0.5 + 77  # rewrite the future completely
    cfg = BacktestConfig(eval_every=3, **COSTS)
    r1, r2 = (run_backtest(x, DecisionEngineStrategy(), cfg) for x in (a, b))
    limit = iso(a.t[cut - 1])
    t1 = [t for t in r1.trades if t["exit_ts"] < limit]
    t2 = [t for t in r2.trades if t["exit_ts"] < limit]
    assert t1 and t1 == t2


def test_zero_cost_breakeven_symmetry_on_random_entries():
    """Sanity: with no costs and fair coin entries, expectancy in R is near zero (no hidden edge or bias in fills)."""
    bars = walk(8000, seed=44, vol=1.0)
    rs = []
    for seed in range(4):
        rs += [t["r_multiple"] for t in run_backtest(bars, RandomEntryStrategy(p=0.05, seed=seed), BacktestConfig(max_leverage=1e9)).trades]
    rs = np.array(rs)
    assert len(rs) > 300
    assert abs(rs.mean()) < 3 * rs.std(ddof=1) / np.sqrt(len(rs)) + 0.05
