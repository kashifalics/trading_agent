"""Experiment 7 Gann-only rules J1-J6 (spec 4.5)."""
from types import SimpleNamespace

import numpy as np
import pytest

from app.feature_engineering.indicators import atr as atr_fn
from app.gann import state as G
from app.gann.anchors import cut
from app.gann.params import GannParams
from app.gold_research.exp7 import rules as J
from app.gold_research.exp7 import timing as T
from app.market_data.bars import Bars


def walk(n=1500, seed=12):
    rng = np.random.default_rng(seed)
    c = 2000 + np.cumsum(rng.normal(0, 4, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 3, n)
    l = np.minimum(o, c) - rng.uniform(0, 3, n)  # noqa: E741
    return Bars(t=1_104_537_600 + 3600 * np.arange(n, dtype=np.int64), o=o, h=h, l=l, c=c, v=np.ones(n), step=3600)


def sigs(b):
    p = GannParams()
    atr = atr_fn(b.h, b.l, b.c, p.atr_n)
    return J.signals(b, atr, G.panel(b, p, daily=False), p, T.line_sets(b, p))


def test_rejection_support_and_resistance():
    # support at 100: came from above, wick to 99.95, closed 0.5 above (>= 0.25 ATR of 1.0)
    assert J.rejection(100.8, 101.0, 99.95, 100.5, 100.0, 0.1, 1.0) == 1
    # resistance at 100: came from below, wick to 100.05, closed 0.4 below
    assert J.rejection(99.2, 100.05, 99.3, 99.6, 100.0, 0.1, 1.0) == -1
    # closed too close to the level: no rejection
    assert J.rejection(100.8, 101.0, 99.95, 100.1, 100.0, 0.1, 1.0) == 0


def test_zone_families_count_once():
    vals = {"square9": np.array([100.0, 100.02, 150.0]), "division": np.array([100.05]), "angle_swing": np.array([90.0])}
    assert J.zone_families(vals, 100.0, 0.1) == {"square9", "divisions"}
    assert J.zone_families(vals, 150.0, 0.1) == {"square9"}


def test_retest_after_1x1_break():
    line = np.full(12, 100.0)
    lid = np.zeros(12, dtype=np.int64)
    c = np.array([101, 101, 101, 98, 97, 99.5, 97, 96, 96, 96, 96, 96], dtype=float)
    h, l = c + 0.6, c - 0.6  # noqa: E741
    # break below at 3; candle 5 touches 100 (high 100.1) and closes back below: short retest
    assert J.retest_signals(c, h, l, line, lid, np.full(12, 0.2)) == [(5, -1)]
    lid2 = lid.copy()
    lid2[3:] = 1  # the latest anchor changed at 3: that is not a break
    assert J.retest_signals(c, h, l, line, lid2, np.full(12, 0.2)) == []


def test_gate_events_by_window():
    ev = [SimpleNamespace(idx=2), SimpleNamespace(idx=5), SimpleNamespace(idx=9)]
    mask = np.zeros(10, bool)
    mask[4:7] = True
    assert [e.idx for e in J.gate_events(ev, mask)] == [5]


def test_rules_prefix_equality():
    b = walk()
    full = sigs(b)
    for j in (700, 1100, 1499):
        part = sigs(cut(b, j + 1))
        for r in full:
            a = full[r].filter(full[r]["idx"] <= j)
            assert a.equals(part[r].filter(part[r]["idx"] <= j)), (r, j)


def test_stop_beyond_trigger_side():
    b = walk(seed=13)
    for r, s in sigs(b).items():
        for idx, d, stop in zip(s["idx"].to_list(), s["d"].to_list(), s["stop"].to_list()):
            assert (stop < b.c[idx]) if d > 0 else (stop > b.c[idx]), r


def test_targets_tp1_at_least_1r():
    tp1, tp3, from_gann = J.targets(100.0, 2.0, 1, np.array([101.0, 103.0, 107.0, 95.0]))
    assert tp1 == pytest.approx(1.5) and tp3 == pytest.approx(3.5) and from_gann
    tp1, tp3, from_gann = J.targets(100.0, 2.0, -1, np.array([99.0, 101.0]))
    assert (tp1, tp3, from_gann) == (1.0, 3.0, False)
