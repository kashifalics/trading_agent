"""Gann price maths and the Squares (docs/gann/GANN_METHODOLOGY.md sections 4.2, 4.6-4.8)."""
import math

import numpy as np
import pytest

from app.gann.price import divisions, round_tick, swing_ratios, twelfths
from app.gann.squares import cross, cross_levels, spiral, sq9_levels


def test_sq9_worked_example():
    lv = dict(sq9_levels(2000.0, 0.01))
    assert lv[90.0] == 2044.97 and lv[-180.0] == 1911.56
    assert abs(lv[45.0] - 2000.0 - 22.42) < 0.01


def test_sq9_full_turn_adds_two_to_root():
    assert abs(math.sqrt(dict(sq9_levels(1234.5, 0.01))[360.0]) - (math.sqrt(1234.5) + 2)) < 1e-3


def test_sq9_skips_non_positive_roots():
    lv = sq9_levels(4.0, 0.01, steps=8)  # sqrt 2: -360 gives 0, -720 negative
    assert all(p > 0 for _, p in lv) and -360.0 not in dict(lv) and -315.0 in dict(lv)


def test_cross_formulas_match_spiral():
    sp = spiral(2000)
    card = sorted(n for n, (x, y) in sp.items() if n > 1 and (x == 0 or y == 0))
    diag = sorted(n for n, (x, y) in sp.items() if n > 1 and abs(x) == abs(y))
    assert cross("cardinal", 2000) == card
    assert cross("diagonal", 2000) == diag
    assert cross("cardinal", 50)[:12] == [2, 4, 6, 8, 11, 15, 19, 23, 28, 34, 40, 46]


def test_spiral_odd_squares_on_one_diagonal():
    sp = spiral(500)
    assert {sp[(2 * k + 1) ** 2] for k in range(1, 10)} == {(k, -k) for k in range(1, 10)}


def test_sq4_even_squares_on_diagonal():
    assert {4, 16, 36, 64, 100} <= set(cross("diagonal", 200, square=4))
    sp = spiral(200, core=4)
    assert sp[1] == (0, 0) and sp[2] == (1, 0) and sp[3] == (1, 1) and sp[4] == (0, 1)
    with pytest.raises(ValueError):
        cross("cardinal", 200, square=4)


def test_cross_levels_in_range():
    assert cross_levels([2, 4, 6, 8, 11, 15], 5.0, 11.0) == [6.0, 8.0, 11.0]
    assert cross_levels([10850, 10900, 10950], 1.08, 1.09, norm=10_000) == [1.085, 1.09]


def test_divisions_eighths_thirds():
    assert [p for _, p in divisions(100, 200, 0.01, ext=False)] == [112.5, 125.0, 133.33, 137.5, 150.0, 162.5, 166.67, 175.0, 187.5]
    ext = dict(divisions(100, 200, 0.01))
    assert ext[2.0] == 300.0 and ext[1.125] == 212.5


def test_twelfths():
    assert [p for _, p in twelfths(0, 120, 0.01)] == [10.0 * j for j in range(1, 12)]


def test_swing_ratios():
    pr, tr = swing_ratios(np.array([100., 110, 105, 125]), np.array([0, 10, 15, 35]))
    assert np.allclose(pr, [0.5, 4.0]) and np.allclose(tr, [0.5, 4.0])


def test_round_tick():
    assert round_tick(2044.9712, 0.01) == 2044.97
    assert np.allclose(round_tick(np.array([1.23456, 2.0]), 0.001), [1.235, 2.0])
