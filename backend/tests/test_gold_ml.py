"""Gold research ML pipeline on a synthetic Brownian world (TEST FIXTURES ONLY)."""
from datetime import datetime, timezone

import numpy as np
import polars as pl
import pytest

from app.gold_research import ml, nulls


def test_purged_folds_never_train_on_outcomes_that_reach_the_test_block():
    rng = np.random.default_rng(0)
    ts = np.sort(rng.integers(0, 10_000_000, 5000))
    hold = 50_000
    n = 0
    for train, test, (t0, t1) in ml.purged_folds(ts, hold):
        assert (ts[train] + hold < t0).all() and (ts[test] >= t0).all()
        n += 1
    assert n == ml.N_FOLDS
    roll = [len(tr) for tr, _, _ in ml.purged_folds(ts, hold, rolling=True)]
    assert max(roll) == min(roll)  # rolling window keeps the first block's length


def test_pattern_prior_uses_only_trades_that_had_finished():
    t = pl.DataFrame({"pattern": ["pin_bar_bull"] * 40, "direction": [1] * 40, "entry_ts": np.arange(40) * 100,
                      "stop_r": [-1.0] * 40, "mfe_48": [3.0] * 20 + [0.0] * 20, "mfe_opt_48": [3.0] * 20 + [0.0] * 20,
                      "stopped_48": [False] * 20 + [True] * 20, "end_r_48": [0.0] * 40})
    pr = ml.pattern_prior(t, None, "M5")  # hold = 48 * 300 s = 14,400 s: no trade finishes inside this 4,000 s window
    assert np.isnan(pr).all()
    t2 = t.with_columns(entry_ts=pl.Series(np.arange(40) * 20_000))
    pr2 = ml.pattern_prior(t2, None, "M5")
    assert np.isnan(pr2[:30]).all()  # needs 30 finished trades
    assert pr2[-1] == pytest.approx((20 * 2.0 - 1 * (39 - 1 - 20 + 1 - 1)) / 38, abs=0.2) or pr2[-1] < 2.0


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    from app.gold_research import study
    from app.historical import split as Sp
    from app.historical import store as Sto
    from app.historical.build import build_timeframes, resample
    tmp = tmp_path_factory.mktemp("ml")
    mp = pytest.MonkeyPatch()
    for mod, names in ((Sto, ("CLEAN", "DATA_ROOT", "SPLIT_DIR")), (Sp, ("CLEAN", "SPLIT_DIR", "REPORTS")), (study, ("CLEAN", "DATA_ROOT", "SPLIT_DIR"))):
        for nm in names:
            mp.setattr(mod, nm, tmp / ("docs" if nm == "SPLIT_DIR" else "clean" if nm == "CLEAN" else "reports" if nm == "REPORTS" else ""))
    m1df = nulls.brownian_m1(datetime(2021, 1, 4, tzinfo=timezone.utc), 400, seed=9)
    (tmp / "clean" / "XAUUSD" / "M1").mkdir(parents=True)
    m1df.write_parquet(tmp / "clean" / "XAUUSD" / "M1" / "2021.parquet")
    for tf, df in build_timeframes(resample(m1df, "5m")).items():
        (tmp / "clean" / "XAUUSD" / tf).mkdir(parents=True)
        df.write_parquet(tmp / "clean" / "XAUUSD" / tf / "all.parquet")
    Sp.freeze_split("XAUUSD", log=lambda m: None)
    Sto.build_m1_store("XAUUSD", log=lambda m: None)
    study.run_timeframe("XAUUSD", "H1", "train")
    yield tmp
    mp.undo()


def test_training_registers_a_challenger_and_shuffled_labels_show_no_skill(world):
    s = ml.train("XAUUSD", tfs=("H1",), kinds=("logistic", "lgbm"), log=lambda m: None)
    r = s["tfs"]["H1"]
    assert r["rows"] > 1000 and "pattern_prior_r" in r["features"] and "htf_bias_trend" in r["features"]
    for kind in ("logistic", "lgbm"):
        assert len(r["models"][kind]["folds"]) == ml.N_FOLDS
    assert abs(r["shuffled_label_check"]["roc_auc"] - 0.5) < 0.05
    assert abs(r["models"]["lgbm"]["oof"]["roc_auc"] - 0.5) < 0.1  # Brownian world: nothing to learn about direction
    v = r["challenger"]
    res = ml.promote("XAUUSD", v, approve=True)
    assert not res["promoted"] and any("validation" in p for p in res["problems"])
    assert not ml.promote("XAUUSD", v, approve=False)["promoted"]
