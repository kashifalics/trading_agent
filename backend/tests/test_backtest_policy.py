import numpy as np
import pytest

from app.backtesting.engine import BacktestConfig, run_backtest
from app.backtesting.metrics import backtest_metrics
from app.backtesting.strategies import MACrossStrategy, Signal
from app.historical_engine.analogues import AnalogueResult
from app.market_data.bars import Bars
from app.prediction.decision_engine import DecisionInputs, decide
from app.price_action.engine import analyze_price_action
from tests.test_ml_analogues import walk

# ---------------------------------------------------------------- backtest mechanics


class Scripted:
    name, warmup = "scripted", 0

    def __init__(self, at: int, sig: Signal):
        self.at, self.sig = at, sig

    def signal(self, bars):
        return self.sig if len(bars) == self.at + 1 else None


def flat(n=100, edits=None):
    o = np.full(n, 100.0)
    h = np.full(n, 100.5)
    lo = np.full(n, 99.5)
    c = np.full(n, 100.0)
    for i, (a, b, d, e) in (edits or {}).items():
        o[i], h[i], lo[i], c[i] = a, b, d, e
    return Bars.from_arrays(o, h, lo, c)


LONG = Signal("BUY", 99.0, 102.0)


def bt(bars, strat, **kw):
    return run_backtest(bars, strat, BacktestConfig(**kw))


def test_long_target_hit_pnl_and_sizing():
    r = bt(flat(edits={62: (100, 102.5, 99.5, 102.4)}), Scripted(60, LONG))
    t = r.trades[0]
    assert t["exit_reason"] == "target" and t["units"] == pytest.approx(100.0)  # 1% of 10k / 1.0 risk
    assert t["pnl"] == pytest.approx(200.0) and t["r_multiple"] == pytest.approx(2.0)
    assert r.metrics["final_equity"] == pytest.approx(10_200.0)


def test_same_bar_stop_and_target_resolves_to_stop():
    r = bt(flat(edits={62: (100, 103, 98, 100)}), Scripted(60, LONG))
    t = r.trades[0]
    assert t["exit_reason"] == "stop" and t["pnl"] == pytest.approx(-100.0)  # exactly 1% risk lost
    assert r.metrics["final_equity"] == pytest.approx(9_900.0)


def test_gap_through_stop_fills_at_the_open_not_the_stop():
    r = bt(flat(edits={62: (97, 97.5, 96.5, 97)}), Scripted(60, LONG))
    t = r.trades[0]
    assert t["exit_price"] == pytest.approx(97.0) and t["r_multiple"] == pytest.approx(-3.0)


def test_spread_raises_entry_and_raises_the_bar_for_targets():
    bars = flat(edits={62: (100, 102.1, 99.5, 102), 63: (102, 102.3, 101.5, 102)})
    r = bt(bars, Scripted(60, LONG), spread=0.4)
    t = r.trades[0]
    assert t["entry_price"] == pytest.approx(100.2)  # buys the ask
    assert t["exit_ts"] == r.trades[0]["exit_ts"] and t["exit_reason"] == "target"
    assert t["entry_ts"] != t["exit_ts"]  # 102.1 high did not reach 102 + half spread on bar 62
    assert t["pnl"] == pytest.approx((102 - 100.2) * (100 / 1.2), rel=1e-6)
    # target exit: only the entry half-spread is paid (the exit half is implicit in needing TP + half to trade)
    assert t["costs"] == pytest.approx(0.2 * 100 / 1.2, rel=1e-6)


def test_short_target():
    r = bt(flat(edits={62: (100, 100.4, 97.9, 98.1)}), Scripted(60, Signal("SELL", 101.0, 98.0)))
    assert r.trades[0]["pnl"] == pytest.approx(200.0)


def test_entry_is_next_bar_open_not_signal_close():
    r = bt(flat(edits={61: (100.7, 101, 100.5, 100.8)}), Scripted(60, LONG))
    assert r.trades[0]["entry_price"] == pytest.approx(100.7)


def test_signal_with_stop_on_wrong_side_after_gap_is_skipped():
    r = bt(flat(edits={61: (98.5, 99, 98, 98.6)}), Scripted(60, LONG))
    assert r.skipped_signals == 1 and not r.trades


def test_time_stop_and_session_filter_and_commission():
    r = bt(flat(), Scripted(60, LONG), max_bars_in_trade=5, commission_pct=0.1)
    assert r.trades[0]["exit_reason"] == "time" and r.trades[0]["costs"] > 0 and r.trades[0]["pnl"] < 0
    assert not bt(flat(), Scripted(60, LONG), allowed_hours_utc=[99]).trades


def test_backtest_has_no_lookahead():
    a = walk(900, seed=21)
    b = Bars(a.t.copy(), a.o.copy(), a.h.copy(), a.l.copy(), a.c.copy(), a.v.copy(), a.step)
    cut = 500
    for arr in (b.o, b.h, b.l, b.c):
        arr[cut:] = arr[cut:] * 1.5 + 40  # rewrite the future
    r1 = bt(a, MACrossStrategy(), spread=0.1)
    r2 = bt(b, MACrossStrategy(), spread=0.1)
    cut_iso = __import__("datetime").datetime.fromtimestamp(int(a.t[cut - 1]), tz=__import__("datetime").timezone.utc).isoformat()
    t1 = [t for t in r1.trades if t["exit_ts"] < cut_iso]
    t2 = [t for t in r2.trades if t["exit_ts"] < cut_iso]
    assert t1 and t1 == t2


def test_metrics_math():
    trades = [{"pnl": p, "r_multiple": r, "costs": 1.0, "bars_held": 3, "exit_reason": "target" if p > 0 else "stop"}
              for p, r in [(200, 2), (-100, -1), (-100, -1), (300, 3)]]
    eq = np.array([10000, 10200, 10100, 10000, 10300.0])
    m = backtest_metrics(trades, eq, 10000, 3600, 100)
    assert m["win_rate"] == 0.5 and m["profit_factor"] == pytest.approx(2.5) and m["expectancy_cash"] == pytest.approx(75)
    assert m["longest_losing_streak"] == 2 and m["max_drawdown_pct"] == pytest.approx(2 / 102 * 100, rel=1e-3)
    assert backtest_metrics([], eq, 10000, 3600, 100)["n_trades"] == 0


# ---------------------------------------------------------------- decision policy


def _inputs(b, quality=1.0, **kw):
    return DecisionInputs("TEST", "1H", b, analyze_price_action(b), {"score": quality, "issues": []}, **kw)


def find_signal():
    for seed in range(8):
        base = walk(900, seed=seed, drift=0.15 if seed % 2 == 0 else -0.15)
        for k in range(300, 900, 10):
            inp = _inputs(base.upto(k))
            d = decide(inp)
            if d.decision != "WAIT":
                return inp, d
    raise AssertionError("no BUY/SELL found in trending synthetic data")


def test_every_non_wait_decision_has_a_valid_plan():
    n_signals = 0
    for seed in range(4):
        base = walk(800, seed=seed, drift=0.12 * (-1) ** seed)
        for k in range(300, 800, 25):
            d = decide(_inputs(base.upto(k)))
            if d.decision == "WAIT":
                assert d.plan is None and d.wait_reasons
                continue
            n_signals += 1
            p = d.plan
            assert p.risk_reward >= 1.5 and p.invalidation and p.targets
            if d.decision == "BUY":
                assert p.stop_loss < p.entry_ref < p.targets[0]
            else:
                assert p.stop_loss > p.entry_ref > p.targets[0]
            assert abs(d.confluence) >= 0.35
    assert n_signals > 0


def test_wait_when_data_is_poor_uncalibrated_or_short():
    inp, d = find_signal()
    assert d.decision in ("BUY", "SELL")
    low = decide(DecisionInputs(**{**inp.__dict__, "quality": {"score": 0.3, "issues": ["stale"]}}))
    assert low.decision == "WAIT" and any("data quality" in r for r in low.wait_reasons)
    unc = decide(DecisionInputs(**{**inp.__dict__, "price_calibrated": False}))
    assert unc.decision == "WAIT" and any("calibrated" in r for r in unc.wait_reasons)
    assert decide(_inputs(walk(30))).decision == "WAIT"


def test_wait_on_multi_timeframe_conflict_or_opposition():
    inp, d = find_signal()
    sign = 1 if d.decision == "BUY" else -1
    view = lambda role, tf, direction: {"role": role, "timeframe": tf, "direction": direction, "note": "x"}  # noqa: E731
    conflict = {"available": True, "score": 0.0, "conflict": True, "views": [view("higher", "4H", -sign), view("entry", "1H", sign)]}
    r = decide(DecisionInputs(**{**inp.__dict__, "mtf": conflict}))
    assert r.decision == "WAIT" and any("disagree" in x for x in r.wait_reasons)


def test_wait_when_history_says_setup_is_worse_than_base_rate():
    inp, d = find_signal()
    fav = "long_tp_before_sl" if d.decision == "BUY" else "short_tp_before_sl"
    f = lambda fr, hi=None: {"frequency": fr, "ci_low": 0.0, "ci_high": hi if hi is not None else fr, "k": 1, "n": 50}  # noqa: E731
    stats = {"horizon_bars": 24, "long_tp_before_sl": f(0.3), "short_tp_before_sl": f(0.3),
             "base_rate_long": f(0.3), "base_rate_short": f(0.3)}
    stats[fav] = f(0.04, 0.12)
    an = AnalogueResult(0, 1000, 50, True, None, [], stats)
    r = decide(DecisionInputs(**{**inp.__dict__, "analogues": an}))
    assert r.decision == "WAIT" and any("base rate" in x for x in r.wait_reasons)


def test_research_only_model_never_drives_decision_or_probabilities():
    inp, d = find_signal()
    ml = {"p_long_tp_first": 0.9, "p_short_tp_first": 0.02, "p_neither": 0.08, "algorithm": "lightgbm",
          "validation_status": "research_only", "is_calibrated": True, "model_version_id": 3}
    r = decide(DecisionInputs(**{**inp.__dict__, "ml": ml}))
    ev = next(e for e in r.evidence if e["category"] == "ml_model")
    assert ev["weight"] == 0.0
    assert r.panel["model_probability"] is None and r.panel["research_only_model_output"]["p_long_tp_first"] == 0.9
    assert r.decision == d.decision and r.confluence == pytest.approx(d.confluence)
    ok = decide(DecisionInputs(**{**inp.__dict__, "ml": {**ml, "validation_status": "passed_minimum_checks"}}))
    assert ok.panel["model_probability"]["p_long_tp_first"] == 0.9 and ok.panel["research_only_model_output"] is None


def test_confidence_components_are_kept_separate():
    _, d = find_signal()
    assert {"model_probability", "historical_frequency", "analytical_confluence", "data_quality", "uncertainty"} <= set(d.panel)
    assert "scale" in d.panel["analytical_confluence"]
