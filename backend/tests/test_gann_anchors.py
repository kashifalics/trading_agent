"""Gann anchors: causal, known only from their confirmation candle (docs/gann/GANN_METHODOLOGY.md section 3)."""
import numpy as np

from app.feature_engineering.indicators import atr as atr_fn
from app.gann.anchors import (
    Anchor,
    active_spans,
    cut,
    major_anchors,
    minor_anchors,
    swing_chart,
)
from app.market_data.bars import Bars


def mk(h, l, c=None, step=3600):  # noqa: E741
    h, l = np.asarray(h, float), np.asarray(l, float)  # noqa: E741
    c = (h + l) / 2 if c is None else np.asarray(c, float)
    return Bars(t=np.arange(len(h), dtype=np.int64) * step, o=c.copy(), h=h, l=l, c=c, v=np.ones(len(h)), step=step)


def walk(n=3000, seed=3):
    rng = np.random.default_rng(seed)
    c = 1000 + np.cumsum(rng.normal(0, 2, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 1.5, n)
    l = np.minimum(o, c) - rng.uniform(0, 1.5, n)  # noqa: E741
    return Bars(t=np.arange(n, dtype=np.int64) * 3600, o=o, h=h, l=l, c=c, v=np.ones(n), step=3600)


def test_major_anchor_known_path():
    p = [*range(0, 11), 9, 8, 7, 6, 5, 4, 5, 6, 7, 6, 5, 4, 3, 2, 1, 0, 1, 2, 3, 4, 5, 6]
    b = mk(p, p)
    got = major_anchors(b, np.ones(len(p)), k=5.0)
    assert got == [Anchor(0, 5, 0.0, "low", "major"), Anchor(10, 15, 10.0, "high", "major"), Anchor(26, 31, 0.0, "low", "major")]


def test_major_prefix_equality():
    b = walk()
    full = major_anchors(b, atr_fn(b.h, b.l, b.c), k=5.0)
    assert len(full) > 10
    for j in (500, 1200, 2999):
        part = cut(b, j)
        assert major_anchors(part, atr_fn(part.h, part.l, part.c), k=5.0) == [a for a in full if a.tc < j]


def test_major_never_confirms_on_its_own_candle():
    b = walk(seed=11)
    assert all(a.tc > a.idx for a in major_anchors(b, atr_fn(b.h, b.l, b.c)))


def test_minor_tc_is_idx_plus_3():
    b = walk(400)
    an = minor_anchors(b)
    assert an and all(a.tc == a.idx + 3 and a.tier == "minor" for a in an)


def test_swing_chart_two_bar():
    # falls to a low at index 4, then two consecutive higher highs (5, 6): the line turns up at 6 with the low at 4;
    # then two consecutive lower lows (9, 10) turn it down at 10 with the high at 8
    h = [10, 9, 8, 7, 6, 7, 8, 9, 10, 9, 8]
    l = [9, 8, 7, 6, 5, 6, 7, 8, 9, 8, 7]  # noqa: E741
    got = swing_chart(mk(h, l), 2)
    assert got == [Anchor(4, 6, 5.0, "low", "chart2"), Anchor(8, 10, 10.0, "high", "chart2")]


def test_active_spans_latest_two():
    lows = [Anchor(i, i, 1.0, "low", "major") for i in (10, 20, 30, 40)]
    spans = active_spans(lows, 100, per_kind=2)
    assert [(a.tc, s, e) for a, s, e in spans] == [(10, 10, 30), (20, 20, 40), (30, 30, 100), (40, 40, 100)]


def test_active_spans_kinds_independent():
    an = [Anchor(1, 2, 1.0, "low", "major"), Anchor(3, 5, 2.0, "high", "major"), Anchor(6, 8, 1.5, "low", "major"),
          Anchor(9, 11, 1.2, "low", "major")]
    spans = {(a.kind, a.tc): (s, e) for a, s, e in active_spans(an, 50)}
    assert spans[("low", 2)] == (2, 11) and spans[("high", 5)] == (5, 50)
