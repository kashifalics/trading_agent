"""Family H (Wyckoff-style events) detectors: hand-built paths, causality and speed (TEST FIXTURES ONLY: synthetic candles)."""
import time

import numpy as np
import pytest

from app.feature_engineering.indicators import atr as atr_fn
from app.market_data.bars import Bars
from app.market_structure.swings import find_swings
from app.patterns import wyckoff
from app.patterns.ctx import ChunkCtx
from app.patterns.registry import REGISTRY

NAN = None
MIRROR = {"spring": "upthrust", "sign_of_strength": "sign_of_weakness", "last_point_of_support": "last_point_of_supply",
          "preliminary_support": "preliminary_supply", "selling_climax": "buying_climax", "automatic_rally": "automatic_reaction",
          "creek_breakout": "ice_breakdown", "wyckoff_accumulation": "wyckoff_distribution",
          "wyckoff_reaccumulation": "wyckoff_redistribution", "secondary_test": "secondary_test"}
MIRROR |= {v: k for k, v in MIRROR.items()}


def make_ctx(o, h, l, c, v) -> ChunkCtx:  # noqa: E741
    b = Bars.from_arrays(o, h, l, c, v, step=900)
    return ChunkCtx(t=b.t, o=b.o, h=b.h, l=b.l, c=b.c, v=b.v, atr=atr_fn(b.h, b.l, b.c, 14), step=b.step, swings=find_swings(b),
                    swings_int=find_swings(b, 2, 2), swings_ext=find_swings(b, 5, 5), levels=None, events={})


def events(hits) -> list[tuple]:
    pats, idx, d, stop, _, _ = hits.rows()
    return sorted((p, int(i), int(k), None if s != s else round(float(s), 6)) for p, i, k, s in zip(pats, idx, d, stop))


class Path:
    """Candles appended one by one. Trend candles move `step` each; the side of the candle facing the move has the full wick and the
    other side half of it, so a turn always leaves a strict 3/3 swing."""

    def __init__(self, p0: float) -> None:
        self.rows: list[tuple] = []
        self.p = p0

    def bar(self, o, h, l, c, v=100.0):  # noqa: E741
        self.rows.append((o, h, l, c, v))
        self.p = c
        return len(self.rows) - 1

    def trend(self, n, step, wick=0.2, v=100.0):
        for _ in range(n):
            o, c = self.p, self.p + step
            hi, lo = (c + wick, o - wick / 2) if step > 0 else (o + wick / 2, c - wick)
            self.bar(o, hi, lo, c, v)
        return len(self.rows) - 1

    def flat(self, n, lo, hi, v=100.0):
        for _ in range(n):
            self.bar((lo + hi) / 2, hi, lo, (lo + hi) / 2, v)
        return len(self.rows) - 1

    def arrays(self, mirror_k=None):
        o, h, lo, c, v = (np.array(x, dtype=float) for x in zip(*self.rows))
        if mirror_k is not None:
            o, h, lo, c = mirror_k - o, mirror_k - lo, mirror_k - h, mirror_k - c
        return o, h, lo, c, v


def spring_after_decline():
    """Down trend, then a tight 0.8-wide range (no volume history, so no climax): redistribution state, then a spring."""
    p = Path(400.0)
    p.trend(60, -5.0)  # candles 0..59, close 100
    p.flat(35, 98.6, 99.4)  # 60..94: the window 60..89 is the first that fits in 3 ATR
    spring = p.bar(99.0, 99.3, 98.0, 99.2)  # 95: trades below 98.6, closes back inside
    p.flat(10, 98.6, 99.4)
    return p, [("wyckoff_redistribution", 89, 0, NAN), ("spring", spring, 1, 98.0)]


def upthrust_sow_lpsy_after_advance():
    """Up trend, range (reaccumulation state: no buying climax), upthrust, wide breakdown (SOW), a lower bounce (LPSY)."""
    p = Path(100.0)
    p.trend(60, 5.0)  # close 400
    p.flat(32, 400.6, 401.4)  # 60..91
    ut = p.bar(401.0, 402.0, 400.7, 400.8)  # 92
    p.flat(7, 400.6, 401.4)  # 93..99
    sow = p.bar(401.0, 401.1, 397.8, 398.0)  # 100: range 3.3 >= 1.5 ATR, closes below 400.6
    p.trend(4, -0.5)  # 101..104
    top = p.trend(4, 0.4)  # 105..108: swing high 397.8 below the broken range low
    p.trend(8, -0.6)
    return p, [("wyckoff_reaccumulation", 89, 0, NAN), ("upthrust", ut, -1, 402.0), ("sign_of_weakness", sow, -1, 401.1),
               ("last_point_of_supply", top + 3, -1, 397.8)]


def climax_ar_st_creek():
    """250-candle decline on volume 100, selling climax (range 6.1, volume 500), automatic rally, secondary test, jump across."""
    p = Path(600.0)
    p.trend(250, -1.0)  # close 350
    sc = p.bar(350.0, 350.1, 344.0, 345.5, v=500.0)  # 250
    ar = p.trend(6, 1.0)  # 251..256: swing high 351.7 (the creek), confirmed at 259
    p.trend(4, -1.0)  # 257..260: lows stay > 2 above the climax low
    st = p.bar(347.5, 347.6, 344.1, 344.9)  # 261: within 0.5 ATR of 344.0, closes above it, volume 100 < 500
    p.trend(5, 1.2)  # 262..266: closes below the creek
    jac = p.bar(350.9, 355.5, 350.8, 355.3)  # 267: range 4.7 >= 1.5 ATR, closes above 351.7
    p.trend(5, 1.0)
    return p, [("selling_climax", sc, 1, 344.0), ("automatic_rally", ar + 3, 0, NAN), ("secondary_test", st, 1, 344.0),
               ("creek_breakout", jac, 1, 350.8)]


def climax_then_range():
    """Selling climax followed by a tight range: accumulation state at the range's confirmation."""
    p = Path(600.0)
    p.trend(250, -1.0)
    sc = p.bar(350.0, 350.1, 344.0, 345.5, v=500.0)  # 250
    p.flat(40, 345.0, 345.8)  # 251..290: the window 251..280 is the first that fits
    return p, [("selling_climax", sc, 1, 344.0), ("wyckoff_accumulation", 280, 0, NAN)]


def preliminary_support():
    """In a decline, one new-low candle on volume 180 (above the 80th percentile of 100s) that closes in its upper half."""
    p = Path(600.0)
    p.trend(230, -1.0)  # close 370
    ps = p.bar(370.0, 370.1, 368.4, 369.6, v=180.0)  # 230: range 1.7 < 2 ATR (not a climax)
    p.trend(29, -1.0)
    return p, [("preliminary_support", ps, 1, 368.4)]


PATHS = {f.__name__: f for f in (spring_after_decline, upthrust_sow_lpsy_after_advance, climax_ar_st_creek, climax_then_range,
                                 preliminary_support)}


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("name", sorted(PATHS))
def test_hand_built_wyckoff_paths_give_exactly_their_events(name, mirror):
    p, want = PATHS[name]()
    k = 1000.0
    hits = wyckoff.detect(make_ctx(*p.arrays(k if mirror else None)))
    if mirror:  # the mirror image (prices k - x) must give the mirrored events
        want = [(MIRROR[pid], i, -d, None if s is None else round(k - s, 6)) for pid, i, d, s in want]
    assert events(hits) == sorted((pid, i, d, None if s is None else round(s, 6)) for pid, i, d, s in want)


def test_narrow_breakout_ends_the_range_without_a_sign_of_strength():
    p = Path(400.0)
    p.trend(60, -5.0)
    p.flat(35, 98.6, 99.4)
    p.bar(99.3, 99.7, 99.2, 99.6)  # closes above the range on a 0.5-wide candle: range over, no SOS
    p.trend(5, 0.1)
    assert [e[0] for e in events(wyckoff.detect(make_ctx(*p.arrays())))] == ["wyckoff_redistribution"]


def test_constant_or_missing_volume_gives_no_climax():
    for v in (100.0, np.nan):
        p, _ = climax_ar_st_creek()
        p.rows = [r[:4] + (v,) for r in p.rows]
        assert events(wyckoff.detect(make_ctx(*p.arrays()))) == []


def random_walk(n, seed=7):
    rng = np.random.default_rng(seed)
    c = 1800 + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[c[0], c[:-1]] + rng.normal(0, 0.2, n)
    h = np.maximum(o, c) + rng.exponential(0.6, n)
    lo = np.minimum(o, c) - rng.exponential(0.6, n)
    return o, h, lo, c, rng.lognormal(5, 0.6, n) * (1 + (h - lo) / 3)


def test_detect_is_causal_and_stops_sit_on_the_right_side():
    o, h, lo, c, v = random_walk(4000)
    full = wyckoff.detect(make_ctx(o, h, lo, c, v))
    part = wyckoff.detect(make_ctx(o[:2500], h[:2500], lo[:2500], c[:2500], v[:2500]))
    early = lambda x: {e for e in events(x) if e[1] < 2475}  # noqa: E731
    assert early(full) == early(part)
    ev = events(full)
    assert len({e[0] for e in ev}) >= 8, sorted({e[0] for e in ev})
    for p, i, d, s in ev:
        assert REGISTRY[p].family == "H"
        if d == 0:
            assert s is None and REGISTRY[p].direction == "neutral"
        else:
            assert s is not None and ((s <= h[i] + 1e-9) if d > 0 else (s >= lo[i] - 1e-9)), (p, i, d, s)


def test_detect_speed_on_21000_candles():
    ctx = make_ctx(*random_walk(21_000, seed=11))
    t0 = time.perf_counter()
    wyckoff.detect(ctx)
    assert time.perf_counter() - t0 < 5.0


def test_registry_entries():
    ids = {k for k, s in REGISTRY.items() if s.family == "H"}
    assert ids == set(MIRROR)
    for k in ids:
        s = REGISTRY[k]
        assert s.status == "implemented" and s.entry == "next_open" and s.definition and s.invalidation
