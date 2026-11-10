"""Experiment 3: the fixes F1-F5 (unit tests) and the whole pipeline on a synthetic Brownian world (TEST FIXTURES ONLY): the power
gate comes before any outcome, nothing is found in a world without memory, and nothing outside the (synthetic) training period is used."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import polars as pl
import pytest

from app.gold_research import nulls
from app.gold_research.exp3 import data as D
from app.gold_research.exp3 import setups as SU


def test_f1_daily_break_gaps_are_scheduled_but_other_gaps_are_not():
    day = 86400 * 20000
    starts = np.array([day + 21 * 3600, day + 22 * 3600 + 120, day + 22 * 3600, day + 13 * 3600, day + 21 * 3600 + 900])
    minutes = np.array([60, 45, 180, 60, 60])
    assert D.is_break_gap(starts, minutes).tolist() == [True, True, False, False, False]  # too long / mid-day / 15 min late: real gaps


def test_f3_one_breakout_per_candle_uses_the_band_nearest_the_close():
    close = np.array([0.0, 0.0, 105.0])
    ev = [SimpleNamespace(idx=2, direction="bullish", low=90.0, high=95.0),
          SimpleNamespace(idx=2, direction="bullish", low=99.0, high=103.0),
          SimpleNamespace(idx=2, direction="bearish", low=110.0, high=112.0)]
    out = SU.nearest_band(ev, close)
    assert len(out) == 2 and [e.high for e in out if e.direction == "bullish"] == [103.0]


def test_f2_levels_are_refreshed_every_trading_week_from_earlier_swings(monkeypatch):
    week_id = np.repeat(np.arange(10), 30)
    calls = []

    def fake_levels(b, swings, atr, as_of):
        calls.append(as_of)
        return []

    class FakeBars:  # minimal Bars stand-in: length, closes, prefix
        def __init__(self, n):
            self.c, self._n = np.zeros(n), n

        def __len__(self):
            return self._n

        def upto(self, k):
            return FakeBars(k)

    monkeypatch.setattr(SU, "detect_levels", fake_levels)
    SU.weekly_breakouts(FakeBars(300), [], np.ones(300), week_id)
    assert calls == [w - 1 for w in range(60, 300, 30)]  # one refresh per week, as of the candle before it (after MIN_HISTORY)


def test_f5_previous_day_sweep_needs_a_reclaim_inside_the_same_day():
    day_id = np.array([0] * 4 + [1] * 4 + [2] * 4)
    pdl = np.array([np.nan] * 4 + [100.0] * 4 + [100.0] * 4)
    pdh = np.array([np.nan] * 4 + [120.0] * 4 + [120.0] * 4)
    lo = np.array([101, 101, 101, 101, 101, 99, 98.5, 100.5, 101, 99, 99, 99], float)
    h = np.full(12, 110.0)
    c = np.array([105, 105, 105, 105, 101, 99.5, 99, 101, 102, 99.5, 99.4, 99.2], float)
    out = SU.prev_day_sweep_reclaim(h, lo, c, pdh, pdl, day_id)
    assert out == [(1, 7, 100.0, 98.5)]  # day 1: swept at 5, reclaimed by candle 7 (not the first one); day 2: never reclaimed


def test_e2_uses_a_1p5_atr_displacement_candle():
    assert SU.DISPLACEMENT_ATR == 1.5 and SU.DISPLACEMENT_BODY == 0.7
    assert len(SU.TESTS) == 9 and ("E5_prev_day_sweep_reclaim", "H4") not in SU.TESTS


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    from app.gold_research.exp2 import data as D2
    from app.gold_research.exp2 import financing as F
    from app.gold_research.exp2 import run as R2
    from app.gold_research.exp3 import run as R
    from app.historical import split as Sp
    from app.historical import store as Sto
    from app.historical.build import build_timeframes, resample
    tmp = tmp_path_factory.mktemp("exp3")
    mp = pytest.MonkeyPatch()
    names = {"SPLIT_DIR": "docs", "CLEAN": "clean", "REPORTS": "reports", "REPO_ROOT": "repo"}
    for mod, attrs in ((Sto, ("CLEAN", "DATA_ROOT", "SPLIT_DIR")), (Sp, ("CLEAN", "SPLIT_DIR", "REPORTS")), (D2, ("CLEAN", "SPLIT_DIR")),
                       (D, ("SPLIT_DIR",)), (R2, ("DATA_ROOT", "SPLIT_DIR", "REPO_ROOT")), (R, ("DATA_ROOT", "SPLIT_DIR", "REPO_ROOT"))):
        for nm in attrs:
            mp.setattr(mod, nm, tmp / names.get(nm, "root"))
    mp.setattr(F, "FRED_FILE", tmp / "no_fred.csv")
    mp.setattr(R, "N_MIN", 40)
    mp.setattr(R, "CONTROL_BARS", 2_000)
    (tmp / "repo" / "docs" / "reports").mkdir(parents=True)
    m1df = nulls.brownian_m1(datetime(2021, 1, 4, tzinfo=timezone.utc), 1100, seed=37, vol=0.25)
    (tmp / "clean" / "XAUUSD" / "M1").mkdir(parents=True)
    m1df.write_parquet(tmp / "clean" / "XAUUSD" / "M1" / "all.parquet")
    for tf, df in build_timeframes(resample(m1df, "5m")).items():
        (tmp / "clean" / "XAUUSD" / tf).mkdir(parents=True)
        df.write_parquet(tmp / "clean" / "XAUUSD" / tf / "all.parquet")
    pl.DataFrame(schema={"start": pl.Datetime("us", "UTC"), "minutes": pl.Int64, "holiday": pl.Boolean, "material": pl.Boolean}).write_parquet(
        tmp / "clean" / "XAUUSD" / "gaps.parquet")
    Sp.freeze_split("XAUUSD", log=lambda m: None)
    Sto.build_m1_store("XAUUSD", log=lambda m: None)
    yield R, tmp
    mp.undo()


def test_outcomes_need_the_preregistration_first_and_it_cannot_be_edited(world):
    R, tmp = world
    with pytest.raises(RuntimeError, match="pre-registration"):
        R.run_tf("XAUUSD", "H4", log=lambda m: None)
    inputs = {tf: R.load_inputs("XAUUSD", tf) for tf in R.TFS}
    pre = R.gate("XAUUSD", log=lambda m: None, inputs=inputs)
    assert len(pre["tests"]) == 9 and all(t["est_fills"] <= t["orders"] for t in pre["tests"])
    assert {t["status"] for t in pre["tests"]} <= {"run", "not testable (fewer fills than N_MIN)"}
    assert R.gate("XAUUSD", log=lambda m: None)["sha256"] == pre["sha256"]  # never overwritten
    p = R.preregistration_path("XAUUSD")
    doc = json.loads(p.read_text())
    doc["n_min"] = 1
    p.write_text(json.dumps(doc))
    with pytest.raises(RuntimeError, match="edited"):
        R.load_preregistration("XAUUSD")
    p.write_text(json.dumps(pre))
    for tf in R.TFS:
        R.run_tf("XAUUSD", tf, log=lambda m: None, inputs=inputs[tf])


def test_development_finds_nothing_in_a_world_without_memory(world):
    R, tmp = world
    s = R.develop("XAUUSD", log=lambda m: None)
    assert s["tests_run"] >= 1, s["not_testable"]
    assert s["candidates"] == [], [(r["tf"], r["setup"], r["status"]) for r in s["rows"]]
    assert s["trials_counted_for_deflated_sharpe"] >= s["tests_run"]
    for r in s["rows"]:
        if r.get("main"):
            assert r["long"] + r["short"] == r["trades"] and set(r["halves"]) <= {"2003-2011", "2012-2020"}
    tr = pl.read_parquet(R.out_dir("XAUUSD") / "trades_H1.parquet")
    pool = pl.read_parquet(R.out_dir("XAUUSD") / "pool_H1.parquet")
    assert set(tr.columns) >= set(pool.columns) - {"setup"}  # strategy and controls share every simulated quantity
    assert all(v["max_fill_before_training_end"] for v in R.verify_scope("XAUUSD").values())
    from app.gold_research.exp3 import report
    md = report.render("XAUUSD")
    assert "Power gate" in md and "sealed final test" in md and "Frozen candidates:** 0" in md
