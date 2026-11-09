"""Family G (classical chart patterns): exact events on hand-built paths, causality and speed (TEST FIXTURES ONLY: synthetic candles).

The hand-built paths have closes that move at most 0.5 per candle, with high = close + 0.5 and low = close - 0.5, so every true range
is exactly 1 and ATR = 1 from candle 13 on. The waypoints are therefore the swing pivots and the expected indices can be worked out
by hand (swing prices are highs / lows, i.e. waypoint close +/- 0.5).
"""
import time

import numpy as np
import pytest

from app.feature_engineering.indicators import atr as atr_fn
from app.market_data.bars import Bars
from app.market_structure.swings import find_swings
from app.patterns import chart
from app.patterns.ctx import ChunkCtx
from app.patterns.registry import REGISTRY


def candles(c):
    c = np.asarray(c, dtype=float)
    h, lo = c + 0.5, c - 0.5
    return np.clip(np.r_[c[0], c[:-1]], lo, h), h, lo, c


def path(*wps):
    """Closes interpolated linearly through (index, close) waypoints."""
    x, y = zip(*wps)
    return np.interp(np.arange(x[-1] + 1), x, y)


def make_ctx(o, h, lo, c, step=900):
    b = Bars.from_arrays(o, h, lo, c, v=np.ones(len(c)), step=step)
    return ChunkCtx(t=b.t, o=b.o, h=b.h, l=b.l, c=b.c, v=b.v, atr=atr_fn(b.h, b.l, b.c, 14), step=step,
                    swings=find_swings(b, 3, 3), swings_int=find_swings(b, 2, 2), swings_ext=find_swings(b, 5, 5),
                    levels=None, events={})


def rows(ctx):
    pats, idx, d, s, _, _ = chart.detect(ctx).rows()
    return [(p, int(i), int(k), round(float(x), 4)) for p, i, k, x in zip(pats, idx, d, s)]


def events(c, pid):
    return [r[1:] for r in rows(make_ctx(*candles(c))) if r[0] == pid]


def walk(n, seed=7):
    rng = np.random.default_rng(seed)
    c = 1800 + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[c[0], c[:-1]] + rng.normal(0, 0.2, n)
    return o, np.maximum(o, c) + rng.exponential(0.6, n), np.minimum(o, c) - rng.exponential(0.6, n), c


def bowl(tail):
    """Rise 100 -> 106 over candles 0..20 (external swing high rim at 20, high 106.5), then a parabolic cup to its bottom at 50."""
    t = np.arange(21, 51)
    return np.r_[np.linspace(100, 106, 21), 100 + 6 * ((t - 50) / 30) ** 2, tail]


def test_double_top_breaks_its_neckline():
    # L0 low 89.5 @12, tops 96.5 @24 and 96.7 @41, trough (neckline) 91.5 @32; first close below 91.5 is candle 51
    c = path((0, 95), (12, 90), (24, 96), (32, 92), (41, 96.2), (61, 86.2))
    assert events(c, "double_top") == [(51, -1, 96.7)]


def test_double_bottom_mirror():
    c = 200 - path((0, 95), (12, 90), (24, 96), (32, 92), (41, 96.2), (61, 86.2))
    assert events(c, "double_bottom") == [(51, 1, 103.3)]


def test_head_and_shoulders_breaks_a_sloping_neckline():
    # external pivots: L0 87.5 @10, LS 95.5 @24, N1 90.5 @32, head 97.5 @44, N2 90.7 @56, RS 95.6 @64 (confirmed @69)
    c = path((0, 93), (10, 88), (24, 95), (32, 91), (44, 97), (56, 91.2), (64, 95.1), (90, 82.1))
    assert events(c, "head_and_shoulders") == [(73, -1, 97.5)]
    assert events(200 - c, "inverse_head_and_shoulders") == [(73, 1, 102.5)]


def test_ascending_triangle_breakout():
    # highs 98.5 @24 and 98.6 @41 (flat), lows 93.5 @32 and 95.5 @47 (rising, confirmed @50); close 99.0 @53 clears the line
    c = path((0, 94), (8, 90), (24, 98), (32, 94), (41, 98.1), (47, 96), (66, 105.5))
    assert events(c, "asc_triangle_breakout") == [(53, 1, 95.5)]
    assert events(200 - c, "desc_triangle_breakdown") == [(53, -1, 104.5)]


def test_symmetrical_triangle_breaks_down():
    # lows 91.5 @12 and 93.5 @32 (rising), highs 98.5 @24 and 97.1 @38 (falling, confirmed @41); stop = last pivot high
    c = path((0, 98), (12, 92), (24, 98), (32, 94), (38, 96.6), (60, 85.6))
    assert events(c, "sym_triangle_breakout") == [(43, -1, 97.1)]


def test_rising_wedge_breaks_down():
    # lows 89.5 @10 and 93.5 @30, highs 97.5 @24 and 98.5 @38: both rising, width ratio 3.4 / 7.0 < 0.75
    c = path((0, 95), (10, 90), (24, 97), (30, 94), (38, 98), (60, 87))
    assert events(c, "rising_wedge_breakdown") == [(43, -1, 98.5)]
    assert events(200 - c, "falling_wedge_breakout") == [(43, 1, 101.5)]


def test_bull_flag_breaks_its_upper_line():
    # pole 85.5 @10 -> 94.5 @26; flag highs 94.5, 94.1 and lows 91.5, 91.1 falling in parallel; last flag low confirmed @41
    c = path((0, 91), (10, 86), (26, 94), (30, 92), (34, 93.6), (38, 91.6), (55, 100.1))
    assert events(c, "bull_flag") == [(43, 1, 91.1)]
    assert events(200 - c, "bear_flag") == [(43, -1, 108.9)]


def test_rounding_bottom_needs_a_u_not_a_v():
    rise = 106 + 0.4 * np.arange(1, 21)
    t = np.arange(51, 81)
    u = bowl(np.r_[100 + 6 * ((t - 50) / 30) ** 2, rise])
    # first close above the rim (106.5) is candle 82; stop = the 3/3 swing low at the bottom (99.5)
    assert events(u, "rounding_bottom") == [(82, 1, 99.5)]
    assert events(200 - u, "rounding_top") == [(82, -1, 100.5)]
    v = np.r_[np.linspace(100, 106, 21), np.linspace(106, 100, 31)[1:], np.linspace(100, 106, 31)[1:], rise]
    assert v[82] > 106.5 >= v[81]
    assert events(v, "rounding_bottom") == []  # only 31% of closes in the lower third of the depth


def test_cup_and_handle_breaks_the_right_rim():
    t = np.arange(51, 79)
    right = 100 + 6 * ((t - 50) / 30) ** 2  # right rim @78: close 105.227, high 105.727
    handle = right[-1] - 0.2 * np.arange(1, 9)  # handle low @86: close 103.627, low 103.127
    up = handle[-1] + 0.4 * np.arange(1, 16)
    c = bowl(np.r_[right, handle, up])
    assert events(c, "cup_and_handle") == [(92, 1, round(right[-1] - 1.6 - 0.5, 4))]
    assert events(200 - c, "inverse_cup_and_handle") == [(92, -1, round(200 - (right[-1] - 1.6 - 0.5), 4))]


def test_events_are_causal():
    """Events confirmed before the cut must be identical when 1,500 later candles are appended."""
    o, h, lo, c = walk(4000)
    full = rows(make_ctx(o, h, lo, c))
    part = rows(make_ctx(o[:2500], h[:2500], lo[:2500], c[:2500]))
    early = lambda r: {x for x in r if x[1] < 2475}  # noqa: E731
    assert len(early(full)) > 50
    assert early(full) == early(part)


def test_random_walk_events_are_registered_and_stops_on_the_right_side():
    o, h, lo, c = walk(21000, seed=3)
    r = rows(make_ctx(o, h, lo, c))
    implemented = {k for k, s in REGISTRY.items() if s.family == "G" and s.status == "implemented"}
    fired = {p for p, *_ in r}
    assert fired <= implemented
    assert len(fired) >= 20, sorted(implemented - fired)
    for p, i, d, s in r:
        assert d != 0 and REGISTRY[p].entry == "next_open"
        assert (s < h[i] + 1e-9) if d > 0 else (s > lo[i] - 1e-9), (p, i, d, s)
    assert len(r) == len(set(r))


def test_scoped_out_items_have_reasons():
    g = {k: s for k, s in REGISTRY.items() if s.family == "G"}
    assert {"contracting_triangle", "expanding_triangle", "rectangle_directional", "diamond_top", "diamond_bottom"} <= {
        k for k, s in g.items() if s.status == "scoped_out"}
    assert all(s.reason for s in g.values() if s.status == "scoped_out")
    assert all(s.definition and s.invalidation for s in g.values() if s.status == "implemented")


@pytest.mark.parametrize("n", [21000])
def test_detect_is_fast(n):
    ctx = make_ctx(*walk(n, seed=11))
    t0 = time.perf_counter()
    chart.detect(ctx)
    assert time.perf_counter() - t0 < 5.0
