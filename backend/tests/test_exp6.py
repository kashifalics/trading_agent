"""Experiment 6 harness (docs/engine_v2/EXPERIMENT_6_PLAN.md) on synthetic data only: statistics, counts-only pre-registration,
integrity guards, signal re-scoring checks and cost scenarios."""
import numpy as np
import polars as pl
import pytest

from app.gold_research.exp6 import run, stats
from app.gold_research.exp6.rescore import RescoreMismatch, check_signal


# ---- statistics ---------------------------------------------------------------------------------------------------------------------
def test_random_filter_p_finds_a_planted_edge_and_rejects_noise():
    rng = np.random.default_rng(0)
    n = 2000
    r = rng.normal(-0.1, 1.0, n)
    strata = rng.integers(0, 10, n)
    keep = rng.random(n) < 0.5
    planted = r.copy()
    planted[keep] += 0.3
    assert stats.random_filter_p(planted, keep, strata, draws=2000, seed=1) < 0.001
    quiet = 0
    for s in range(20):
        k = np.random.default_rng(100 + s).random(n) < 0.5
        quiet += stats.random_filter_p(r, k, strata, draws=1000, seed=s) > 0.05
    assert quiet >= 17  # a random filter is no better than random filters (about 19 of 20 expected)


def test_random_filter_respects_strata():
    r = np.r_[np.ones(50), np.zeros(50)]
    strata = np.r_[np.zeros(50, int), np.ones(50, int)]
    keep = np.r_[np.arange(50) % 2 == 0, np.zeros(50, bool)]  # half of stratum 0 (all r = 1), none of stratum 1
    nulls = stats.null_means(r, keep, strata, draws=500, seed=3)
    assert np.allclose(nulls, 1.0)  # every random filter also takes 25 trades from stratum 0 only
    assert stats.random_filter_p(r, keep, strata, draws=500, seed=3) == 1.0


def test_holm_matches_reference():
    out = stats.holm_dict({"a": 0.01, "b": 0.04, "c": 0.03})
    assert out == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})


def test_cluster_ci_brackets_the_difference_of_means():
    rng = np.random.default_rng(4)
    rk, rd = rng.normal(0.2, 1, 800), rng.normal(0.0, 1, 800)
    lo, hi = stats.cluster_ci(rk, np.arange(800) // 10, rd, np.arange(800) // 10)
    assert lo < rk.mean() - rd.mean() < hi and hi - lo < 0.5


def test_double_cost_and_fee_adjustments():
    c = stats.cost_scenarios(np.array([1.0]), np.array([0.3]), np.array([3.0]), np.array([2000.0]))
    assert c["r_2x"] == pytest.approx([0.9])
    f = stats.cost_scenarios(np.array([1.0]), np.array([2.0]), np.array([500.0]), np.array([50_000.0]))
    assert f["r_fee"] == pytest.approx([0.8])  # Binance taker fee 0.1% per side: 2 x 50 / 500


# ---- arms and the counts-only pre-registration -------------------------------------------------------------------------------------
def _verdicts(n: int = 2000, seed: int = 7) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    v = lambda: rng.choice(["PASS", "FAIL", "NEUTRAL", "UNAVAILABLE"], n, p=[0.5, 0.2, 0.2, 0.1])  # noqa: E731
    return pl.DataFrame({"symbol": "BTCUSDT", "tf": rng.choice(["M5", "H1"], n), "idx": np.arange(n), "strategy": "trend_pullback",
                         "direction": rng.choice([1, -1], n), "signal_ts": np.arange(n) * 3600 + 1_600_000_000,
                         "compatible": rng.random(n) < 0.9, "tested": True, "vsa": v(), "momentum": v(), "trend": v(), "volatility": v()})


def test_arms_keep_only_pass_and_a_combination_needs_every_category():
    f = run.with_combo(_verdicts())
    assert set(run.ARMS) == {"vsa", "momentum", "trend", "volatility", "combo"}
    row = f.filter((pl.col("trend") == "PASS") & (pl.col("momentum") == "PASS") & (pl.col("vsa") == "PASS"))
    assert (row["combo"] == "PASS").all()  # trend_pullback's combination = trend + momentum + vsa
    assert (f.filter(pl.col("vsa") == "UNAVAILABLE")["combo"] != "PASS").all()  # UNAVAILABLE never passes


def test_prereg_counts_signals_only_and_refuses_overwrite(tmp_path):
    f = _verdicts()  # no outcome column exists: counting cannot read one
    train_end = 1_600_000_000 + 1500 * 3600
    rows = run.arm_counts(f, train_end)
    dev = f.filter(pl.col("compatible") & pl.col("tested") & (pl.col("signal_ts") < train_end))
    vsa = next(x for x in rows if x["arm"] == "vsa")
    assert vsa["signals"] == dev.height and vsa["kept"] == dev.filter(pl.col("vsa") == "PASS").height
    assert vsa["in_family"] == (vsa["kept"] >= 300 and vsa["dropped"] >= 0.1 * vsa["signals"])
    small = next(x for x in run.arm_counts(f.head(300), train_end) if x["arm"] == "vsa")
    assert small["in_family"] is False  # fewer than 300 kept signals: out of the family, decided from counts only
    p = tmp_path / "prereg.json"
    run.write_once(p, {"a": 1})
    with pytest.raises(RuntimeError, match="exists"):
        run.write_once(p, {"a": 2})


def test_develop_refuses_without_committed_prereg(tmp_path):
    p = tmp_path / "EXP6_preregistration.json"
    p.write_text("{}")
    with pytest.raises(RuntimeError, match="committed"):
        run.require_committed(p)


def test_confirm_runs_once(tmp_path):
    p = tmp_path / "EXP6_confirmation.json"
    run.guard_once(p)
    p.write_text("{}")
    with pytest.raises(RuntimeError, match="once"):
        run.guard_once(p)


def test_arm_checks_pass_a_real_improvement_and_fail_a_mere_filter():
    rng = np.random.default_rng(11)
    n = 6000
    years = rng.integers(2010, 2020, n)
    ts = ((years - 1970) * 365.25 * 86400 + rng.integers(0, 300 * 86400, n)).astype(np.int64)
    r = rng.normal(-0.1, 1.0, n)
    keep = rng.random(n) < 0.4
    good = r.copy()
    good[keep] += 0.25
    common = dict(strata=years * 10, ts=ts, spread_r=np.full(n, 0.02), stopped=r < -0.9, draws=2000, seed=2)
    real = run.evaluate_arm(good, keep, **common)
    assert real["checks"]["kept_beats_baseline"] and real["p_random"] < 0.001 and real["checks"]["pf_sharpe_not_worse"]
    assert real["checks"]["positive_years_60pct"] and real["checks"]["positive_at_2x_costs"] and real["checks"]["at_least_300_trades"]
    mere = run.evaluate_arm(r, keep, **common)  # fewer trades, no better expectancy
    assert mere["p_random"] > 0.05 or not mere["checks"]["kept_beats_baseline"]
    assert {"kept", "dropped", "baseline", "false_entry", "improvement_r"} <= set(real)


# ---- report ---------------------------------------------------------------------------------------------------------------------------
def test_report_states_every_arm_result_with_its_sample_and_never_hides_failures(tmp_path, monkeypatch):
    import json

    from app.gold_research.exp6 import report
    arm = lambda sym, strat, a, passed, imp, n: {  # noqa: E731
        "symbol": sym, "strategy": strat, "arm": a, "trades": n, "passed": passed, "promotable": passed, "p_random": 0.0005 if passed else 0.4,
        "p_holm": 0.01 if passed else 1.0, "improvement_r": imp, "improvement_r_2x_costs": imp, "positive_year_share": 0.7,
        "kept": {"trades": n // 2, "expectancy_r": -0.05 + imp, "win_rate": 0.4, "profit_factor": 0.9},
        "baseline": {"trades": n, "expectancy_r": -0.05, "win_rate": 0.38, "profit_factor": 0.85},
        "false_entry": {"stop_share_kept": 0.5, "stop_share_dropped": 0.6}, "checks": {"kept_beats_baseline": imp > 0}}
    pre = {"total_trials": 2120, "family": ["BTCUSDT|trend_pullback|momentum", "XAUUSD|trend_pullback|vsa"], "arms": [
        {"symbol": "BTCUSDT", "strategy": "trend_pullback", "arm": "momentum", "signals": 900, "kept": 400, "dropped": 500, "in_family": True},
        {"symbol": "XAUUSD", "strategy": "range_reversion", "arm": "vsa", "signals": 50, "kept": 10, "dropped": 40, "in_family": False}],
        "sha256": "x"}
    dev = {"arms": [arm("BTCUSDT", "trend_pullback", "momentum", True, 0.08, 900), arm("XAUUSD", "trend_pullback", "vsa", False, -0.01, 5000)],
           "passed": ["BTCUSDT|trend_pullback|momentum"], "sha256": "y"}
    conf = {"status": "run once", "arms": [arm("BTCUSDT", "trend_pullback", "momentum", False, 0.01, 200)], "passed": [], "sha256": "z"}
    for name, doc in (("p.json", pre), ("d.json", dev), ("c.json", conf)):
        (tmp_path / name).write_text(json.dumps(doc))
    monkeypatch.setattr(run, "PREREG", tmp_path / "p.json")
    monkeypatch.setattr(run, "DEV", tmp_path / "d.json")
    monkeypatch.setattr(run, "CONF", tmp_path / "c.json")
    md = report.render()
    assert "| BTCUSDT | Trend-following pullback | momentum | 900 |" in md and "| XAUUSD | Trend-following pullback | vsa | 5,000 |" in md
    assert "passed development" in md and "did not pass" in md
    assert "Range mean reversion" in md and "below the count rule" in md  # out-of-family arms are listed, not dropped silently
    assert "No confirmation was promoted to a gate" in md  # the carried arm failed the confirmation segment
    assert "2,120" in md
    assert "## By confirmation" in md
    assert "| Momentum | 1 | 1 | 1 | 0 |" in md and "| VSA | 1 | 0 | 0 | 0 |" in md  # tested, improved, passed dev, confirmed


def test_exp5_report_for_btcusdt_uses_its_own_split_costs_and_all_trials():
    from app.gold_research.exp5 import report as R5report
    from app.gold_research.exp5 import run as R5
    if not R5.dev_path("BTCUSDT").exists() or not run.PREREG.exists():
        pytest.skip("BTCUSDT Experiment 5 results not on this machine")
    md = R5report.render("BTCUSDT")
    assert "2017-08-17" in md and "2024-01-29" in md and "2003-05" not in md  # BTCUSDT's own segments
    assert "gold rose" not in md and "$2 round-trip" in md
    assert "2,115 trials" in md and "fewer than 12 development years" in md  # the Experiment 6 trial count and the PBO limit


def test_confirm_status_and_gates_match_the_frozen_experiment_6_results():
    import json

    from app.strategy_engine.config import CONFIRM_STATUS, GATES
    if not (run.DEV.exists() and run.CONF.exists()):
        pytest.skip("Experiment 6 results not on this machine")
    dev, conf = json.loads(run.DEV.read_text()), json.loads(run.CONF.read_text())
    confirmed = {(r["symbol"], r["strategy"], r["arm"]) for r in conf["arms"] if r.get("passed") and r.get("promotable")}
    expected: dict = {}
    for r in dev["arms"]:
        if r["arm"] in run.CATS and r.get("trades"):
            key = (r["symbol"], r["strategy"], r["arm"])
            expected.setdefault(r["symbol"], {}).setdefault(r["strategy"], {})[r["arm"]] = "gate" if key in confirmed else "not passed"
    assert CONFIRM_STATUS == expected
    gates: dict = {}
    for sym, strat, arm in confirmed:
        if arm in run.CATS:
            gates.setdefault(sym, {}).setdefault(strat, ()).__add__((arm,))
    assert GATES == gates == {}  # Experiment 6 confirmed nothing: no gate


# ---- re-scoring must reproduce the stored signal -------------------------------------------------------------------------------------
def test_rescore_raises_on_signal_mismatch():
    ev = {"direction": 1, "entry_mode": "market", "limit": 100.0, "stop": 99.0, "idx": 5, "strategy": "trend_pullback"}
    check_signal(ev, "ready", {"entry_mode": "market", "entry": 100.0, "stop_loss": 99.0}, 1)
    with pytest.raises(RescoreMismatch):
        check_signal(ev, "ready", {"entry_mode": "market", "entry": 100.0, "stop_loss": 98.5}, 1)
    with pytest.raises(RescoreMismatch):
        check_signal(ev, "forming", None, 1)
    with pytest.raises(RescoreMismatch):
        check_signal(ev, "ready", {"entry_mode": "market", "entry": 100.0, "stop_loss": 99.0}, -1)
