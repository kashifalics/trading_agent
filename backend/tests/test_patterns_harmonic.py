"""Family I (Fibonacci and harmonic) detectors: hand-built swing paths, causality and speed (TEST FIXTURES ONLY: synthetic candles)."""
import time

import numpy as np
import pytest

from app.feature_engineering.indicators import atr as atr_fn
from app.market_data.bars import Bars
from app.market_structure.swings import find_swings
from app.patterns import harmonic
from app.patterns.ctx import ChunkCtx
from app.patterns.registry import REGISTRY

LEAD, LEG, W = 10, 8, 0.05
SHAPES = ("abcd", "three_drives", "elliott_impulse", "elliott_wave5", *harmonic.HARMONICS)
FIBS = ("fib_retracement", "golden_pullback", "deep_retracement", "fib_extension")


def make_ctx(o, h, l, c, v=None) -> ChunkCtx:  # noqa: E741
    b = Bars.from_arrays(o, h, l, c, v, step=900)
    return ChunkCtx(t=b.t, o=b.o, h=b.h, l=b.l, c=b.c, v=b.v, atr=atr_fn(b.h, b.l, b.c, 14), step=b.step, swings=find_swings(b),
                    swings_int=find_swings(b, 2, 2), swings_ext=find_swings(b, 5, 5), levels=None, events={})


def events(hits, pids=None) -> list[tuple]:
    pats, idx, d, stop, _, _ = hits.rows()
    return sorted((p, int(i), int(k), None if s != s else round(float(s), 6))
                  for p, i, k, s in zip(pats, idx, d, stop) if pids is None or p in pids)


def path(points, leg=LEG, w=W, lead=LEAD):
    """Candles whose highs / lows run in straight legs through the turning prices points[1:-1] (points[0] and points[-1] are the ends
    of the path, not swings). A turning high's candle high (a turning low's candle low) is exactly that price, so it is the 3/3 swing
    price. Returns (o, h, l, c) and the candle index of every point."""
    pts = np.asarray(points, dtype=float)
    kind = np.r_[0.0, [1.0 if pts[j] > pts[j - 1] else -1.0 for j in range(1, len(pts) - 1)], 0.0]
    at = np.r_[0, lead + leg * np.arange(len(pts) - 1)]
    m = np.interp(np.arange(at[-1] + 1), at, pts - kind * w)
    s = np.sign(np.diff(m, prepend=2 * m[0] - m[1]))
    o, c, h, lo = m - 0.5 * w * s, m + 0.5 * w * s, m + w, m - w
    for j in range(1, len(pts) - 1):
        (h if kind[j] > 0 else lo)[at[j]] = pts[j]
    return (o, h, lo, c), at


def run(points, **kw):
    arrs, at = path(points, **kw)
    return harmonic.detect(make_ctx(*arrs)), at, arrs


# (points, {pattern: [(index of the point whose swing completes it, direction, stop)]}); the candle of the event is that swing's
# confirmation, 3 candles after it
X, A = 100.0, 110.0
CASES = {
    "gartley_bull": ([103, X, A, 103.82, 107.63924, 102.14, 108], {"gartley": [(5, 1, X)]}),
    "bat_bear": ([197, 200, 190, 194.5, 191.8, 198.86, 193], {"bat": [(5, -1, 200.0)]}),
    "butterfly_bull": ([103, X, A, 102.14, 108.31796, 97.3, 104], {"butterfly": [(5, 1, 97.3 - 2.5)]}),
    "crab_bear": ([197, 200, 190, 195, 190.57, 206.18, 199], {"crab": [(5, -1, 206.18 + 2.5)]}),
    "deep_crab_bull": ([103, X, A, 101.14, 106.61548, 93.82, 100], {"deep_crab": [(5, 1, 93.82 - 2.5)]}),
    "cypher_bull": ([103, X, A, 105, 111.36, 102.43104, 108], {"cypher": [(5, 1, X)]}),
    "shark_bear": ([197, 200, 190, 195, 188.65, 199.5, 194], {"shark": [(5, -1, 199.5 + 2.5)]}),
    "abcd_bull": ([104, A, 100, 106.18, 96.18, 101], {"abcd": [(4, 1, 96.18 - 2.5)]}),
    "three_drives_bear": ([104, 100, 110, 103, 114.2, 106.36, 118.904, 112], {"three_drives": [(6, -1, 118.904 + 0.25 * 12.544)]}),
    "elliott_up": ([103, 100, 110, 104, 120, 114, 124, 118], {"elliott_wave5": [(5, 1, 110.0)], "elliott_impulse": [(6, -1, 124.0)]}),
}


def expected(case, at, mirror_k=None):
    out = []
    for pid, rows in case.items():
        for j, d, stop in rows:
            if mirror_k is not None:
                d, stop = -d, mirror_k - stop
            out.append((pid, int(at[j]) + 3, d, round(stop, 6)))
    return sorted(out)


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("name", sorted(CASES))
def test_hand_built_harmonic_paths_give_exactly_their_patterns(name, mirror):
    points, case = CASES[name]
    k = 400.0
    hits, at, _ = run([k - p for p in points] if mirror else points)
    assert events(hits, SHAPES) == expected(case, at, k if mirror else None)


def test_golden_pullback_after_an_up_impulse():
    hits, at, _ = run([103, 100, 110, 103.82, 109])  # 0.618 retracement, the rally stops short of the 1.272 extension
    assert events(hits, FIBS) == [("golden_pullback", int(at[3]) + 3, 1, 103.82)]


def test_fib_retracement_then_extension_close():
    hits, at, (_, _, _, c) = run([103, 100, 110, 105.5, 114])  # 0.45 retracement, then a close above 100 + 1.272 x 10
    conf = int(at[3]) + 3
    first = conf + int(np.flatnonzero(c[conf:] > 112.72)[0])
    assert first < at[4]
    assert events(hits, FIBS) == sorted([("fib_retracement", conf, 1, 105.5), ("fib_extension", first, 1, 105.5)])


def test_deep_retracement_after_a_down_impulse():
    hits, at, _ = run([107, 110, 100, 108.5, 102])  # 0.85 retracement of a down leg
    assert events(hits, FIBS) == [("deep_retracement", int(at[3]) + 3, -1, 108.5)]


def test_no_fibonacci_event_when_the_impulse_is_under_3_atr():
    hits, _, _ = run([103, 100, 102, 100.764, 101.8], w=1.0)  # 0.618 retracement, but wide candles: the 2-point leg is < 3 ATR
    assert events(hits, FIBS) == []


def test_extension_is_cancelled_by_a_close_below_the_pullback():
    hits, _, _ = run([103, 100, 110, 105.5, 108, 104, 116])  # pullback low lost before the 1.272 level is reached
    assert [e for e in events(hits, ("fib_extension",)) if e[3] == 105.5] == []


def random_walk(n, seed=7):
    rng = np.random.default_rng(seed)
    c = 1800 + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[c[0], c[:-1]] + rng.normal(0, 0.2, n)
    h = np.maximum(o, c) + rng.exponential(0.6, n)
    lo = np.minimum(o, c) - rng.exponential(0.6, n)
    return o, h, lo, c, rng.lognormal(5, 0.6, n)


def test_detect_is_causal_and_stops_sit_on_the_right_side():
    o, h, lo, c, v = random_walk(4000)
    full = harmonic.detect(make_ctx(o, h, lo, c, v))
    part = harmonic.detect(make_ctx(o[:2500], h[:2500], lo[:2500], c[:2500], v[:2500]))
    early = lambda x: {e for e in events(x) if e[1] < 2475}  # noqa: E731
    assert early(full) == early(part)
    ev = events(full)
    assert len({e[0] for e in ev}) >= 6, sorted({e[0] for e in ev})
    for p, i, d, s in ev:
        assert REGISTRY[p].family == "I"
        assert d != 0 and s is not None
        assert (s <= h[i] + 1e-9) if d > 0 else (s >= lo[i] - 1e-9), (p, i, d, s)


def test_detect_speed_on_21000_candles():
    ctx = make_ctx(*random_walk(21_000, seed=11))
    t0 = time.perf_counter()
    harmonic.detect(ctx)
    assert time.perf_counter() - t0 < 5.0


def test_registry_entries():
    ids = [k for k, s in REGISTRY.items() if s.family == "I"]
    assert set(ids) == {*SHAPES, *FIBS}
    for k in ids:
        s = REGISTRY[k]
        assert s.status == "implemented" and s.entry == "next_open" and s.definition and s.invalidation
