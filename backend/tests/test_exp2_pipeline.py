"""Experiment 2 end to end on a synthetic Brownian world (TEST FIXTURES ONLY): no candidates may come out of a world without memory,
controls share the strategy's mechanics, and nothing outside the (synthetic) training period is touched."""
from datetime import datetime, timezone

import numpy as np
import polars as pl
import pytest

from app.gold_research import nulls


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    from app.gold_research.exp2 import data as D
    from app.gold_research.exp2 import financing as F
    from app.gold_research.exp2 import run as R
    from app.historical import split as Sp
    from app.historical import store as Sto
    from app.historical.build import build_timeframes, resample
    tmp = tmp_path_factory.mktemp("exp2")
    mp = pytest.MonkeyPatch()
    for mod, names in ((Sto, ("CLEAN", "DATA_ROOT", "SPLIT_DIR")), (Sp, ("CLEAN", "SPLIT_DIR", "REPORTS")), (D, ("CLEAN", "SPLIT_DIR")),
                       (R, ("DATA_ROOT", "SPLIT_DIR", "REPO_ROOT"))):
        for nm in names:
            mp.setattr(mod, nm, tmp / {"SPLIT_DIR": "docs", "CLEAN": "clean", "REPORTS": "reports", "REPO_ROOT": "repo"}.get(nm, "root"))
    mp.setattr(F, "FRED_FILE", tmp / "no_fred.csv")
    mp.setattr(D, "DEV_END", "2023-06-03T00:00:00+00:00")
    mp.setattr(R, "MIN_TRADES", 40)
    (tmp / "repo" / "docs" / "reports").mkdir(parents=True)
    m1df = nulls.brownian_m1(datetime(2021, 1, 4, tzinfo=timezone.utc), 1100, seed=31, vol=0.25)
    (tmp / "clean" / "XAUUSD" / "M1").mkdir(parents=True)
    m1df.write_parquet(tmp / "clean" / "XAUUSD" / "M1" / "all.parquet")
    for tf, df in build_timeframes(resample(m1df, "5m")).items():
        (tmp / "clean" / "XAUUSD" / tf).mkdir(parents=True)
        df.write_parquet(tmp / "clean" / "XAUUSD" / tf / "all.parquet")
    pl.DataFrame(schema={"start": pl.Datetime("us", "UTC"), "minutes": pl.Int64, "holiday": pl.Boolean, "material": pl.Boolean}).write_parquet(
        tmp / "clean" / "XAUUSD" / "gaps.parquet")
    Sp.freeze_split("XAUUSD", log=lambda m: None)
    Sto.build_m1_store("XAUUSD", log=lambda m: None)
    for tf in R.TFS:
        R.run_tf("XAUUSD", tf, log=lambda m: None)
    yield R
    mp.undo()


def test_controls_use_the_strategy_mechanics(world):
    R = world
    tr = pl.read_parquet(R.out_dir("XAUUSD") / "trades_H4.parquet")
    pool = pl.read_parquet(R.out_dir("XAUUSD") / "pool_H4.parquet")
    assert tr.height > 100 and pool.height > 1000
    assert set(tr.columns) >= set(pool.columns) - {"setup"}  # the same simulated quantities for both
    for c in ("r_2R_60", "exit_2R_60", "gap_2R_60", "fin_fixed_0.10_2R_60", "fin_none_2R_60", "spread_signal"):
        assert c in tr.columns and c in pool.columns
    assert "fin_fred_proxy_2R_60" not in tr.columns  # no FRED file: the scenario is absent, never estimated
    k = tr.filter(pl.col("r_2R_60").is_not_nan())
    assert (k["exit_2R_60"] > k["fill_ts"]).all() and (k["fin_none_2R_60"] == 0).all() and (k["fin_fixed_0.10_2R_60"] >= 0).all()


def test_development_finds_nothing_in_a_world_without_memory(world):
    R = world
    s = R.develop("XAUUSD", log=lambda m: None)
    assert s["pre_registered_tests"] == 36 and s["trials_counted_for_deflated_sharpe"] >= 36
    assert len(s["candidates"]) == 0, s["candidates"]
    edges = [r["main"]["edge"] for r in s["rows"] if r.get("main") and r["trades"] >= R.MIN_TRADES]
    assert edges and abs(np.median(edges)) < 0.15
    sc = R.screen("XAUUSD", log=lambda m: None)
    assert sc["rows"] == []
    from app.gold_research.exp2 import report
    md = report.render("XAUUSD")
    assert "NOT independent" in md and "FRED data:** NOT available" in md and "sealed final test" in md
    scope = R.verify_scope("XAUUSD")
    assert all(v.get("all_exits_before_training_end", True) for k, v in scope.items() if isinstance(v, dict))


def test_signal_scarcity_diagnostics_are_consistent_counts(world):
    """The read-only diagnostic reproduces the experiment's own counts and never increases along a funnel."""
    R = world
    from app.gold_research.exp2 import diagnostics as G
    dev = R.develop("XAUUSD", log=lambda m: None)
    res = G.run("XAUUSD", log=lambda m: None)
    by_test = {(r["tf"], r["setup"], r["direction"]): r["trades"] for r in dev["rows"]}
    for tf in R.TFS:
        for k, v in res["fills"][tf]["setups"].items():
            setup, dn = k.split("|")
            assert v["development_trades"] == by_test[(tf, setup, dn)]
            assert v["orders_dev"] >= v["reasons_dev"]["touched"] >= v["fills_dev"]["conservative (open spread, as run)"]
            assert v["dev_fill_in_period"] >= v["dev_exit_before_boundary"] >= v["dev_no_gap"] >= v["development_trades"]
        for s in ("S1", "S2", "S3", "S6"):
            counts = [c for name, c in res["funnels"][tf][s]["conditions"] if not name.startswith(("zones emitted", "order blocks emitted",
                                                                                                  "emitted by"))]
            assert all(a >= b for a, b in zip(counts, counts[1:])), (tf, s, counts)
        assert res["s4_refresh"][tf]["refresh_every_200_candles"]["breakouts_dev_unique"] == res["extras"][tf]["S4_dedup"]["unique_candle_direction"]
    md = G.render("XAUUSD")
    assert "Counts only" in md and "sealed final test was not read" in md
