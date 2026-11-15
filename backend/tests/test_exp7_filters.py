"""Experiment 7 filter track B-I (spec 4.4)."""
import numpy as np
import polars as pl

from app.gold_research.exp6 import run as R6
from app.gold_research.exp7 import filters as F
from app.gold_research.exp7 import stats as S


def frame():
    return pl.DataFrame({
        "direction": [1, 1, -1, -1, 1],
        "t_cycle_bars": [True, False, True, False, False],
        "t_balance_swing": [False, True, False, False, True],
        "t_balance_atr": [False, False, True, False, False],
        "side_swing": [1.0, -1.0, -1.0, 1.0, 0.0],
        "side_atr": [-1.0, 1.0, 1.0, -1.0, 1.0],
        "div_ok": [True, False, False, True, False],
        "sq9_ok": [False, False, True, True, True],
        "families": [2, 1, 3, 0, 2],
        "vsa": ["PASS", "PASS", "FAIL", "PASS", "NEUTRAL"],
        "trend": ["FAIL", "PASS", "PASS", "PASS", "PASS"],
    })


def test_arm_definitions():
    k = F.arm_keep(frame())
    assert set(k) == set(F.ARMS)
    assert k["B"].tolist() == [True, False, True, False, False]
    assert k["C"].tolist() == [True, False, False, True, False]
    assert k["D-swing"].tolist() == [False, True, False, False, True]
    assert k["D-atr"].tolist() == [False, False, True, False, False]
    assert k["F"].tolist() == [False, False, True, True, True]
    assert k["G"].tolist() == [True, False, True, False, True]
    assert k["H"].tolist() == [True, False, False, False, False]
    assert k["I"].tolist() == [False, False, True, False, True]


def test_E_side_rule():
    k = F.arm_keep(frame())
    assert k["E-swing"].tolist() == [True, False, True, False, False]  # long needs +1, short needs -1; 0 never
    assert k["E-atr"].tolist() == [False, True, False, True, True]


def test_support_side_and_tolerance():
    v = np.array([99.0, 100.0, 100.5, 103.0])
    assert F.support_ok(v, 100.2, 1, 0.3)  # 100.0 is at/below the long entry within 0.3
    assert not F.support_ok(v, 100.2, -1, 0.2)  # nothing at/above within 0.2 (100.5 is 0.3 away)
    assert F.support_ok(v, 100.2, -1, 0.3)
    assert not F.support_ok(np.array([]), 100.0, 1, 1.0)


def test_lines_lookup_by_candle():
    ls = S.LineSet.static(np.array([0, 10]), np.array([10, 20]), [np.array([1.0, 2.0]), np.array([5.0])])
    ix = F.LineIndex(ls)
    assert sorted(ix.values_at(3).tolist()) == [1.0, 2.0] and ix.values_at(15).tolist() == [5.0]
    assert ix.values_at(25).tolist() == []


def test_planted_filter_edge():
    rng = np.random.default_rng(8)
    n = 4000
    f = rng.random(n) < 0.3
    r = np.where(f, 1.0, -0.2) + rng.normal(0, 0.3, n)
    ts = (1_104_537_600 + 3600 * np.arange(n)).astype(np.int64)
    strata = (np.arange(n) % 4).astype(np.int64)
    res = R6.evaluate_arm(r, f, strata=strata, ts=ts, spread_r=np.full(n, 0.01), stopped=np.zeros(n, bool), draws=2000)
    assert res["p_random"] < 0.01 and res["checks"]["kept_beats_baseline"]
