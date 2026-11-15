"""Experiment 7 statistics (spec 4.3, 4.6, 4.7): vectorised Gann windows and level lines, and their controls.

Time: a WindowSet holds every projected window as arrays. The real mask is identical to the Gann panel's (tested). A control
replaces the Gann lengths with random ones on the SAME anchors, spans and tolerance rule, matched to the real coverage within
1 percentage point:
  shared   (cycle counts, fractions, Square of Nine time counts): one random count per Gann count, drawn from the same range
           excluding every Gann count's tolerance band; counts are then added or removed at random until coverage matches.
  jitter   (price-time balance): each window's length times U(0.5, 1.5), never within its own tolerance of the real length.
  anniversary: one random day offset per anniversary year, from [200, 1200], never within 7 days of a whole year.
Levels: a LineSet holds every level or angle line with the candles where it is known; a control shifts every line by the same
random fraction (0.15-0.85) of its own spacing, in a random direction, so the spacing of the set is unchanged.
"""
from dataclasses import dataclass, field
from math import erf, sqrt

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.gann.anchors import Anchor

COV_PP = 0.01
MAX_REDRAW = 50
ANNIV_RANGE = (200, 1200)


# ---- p-values and lifts -------------------------------------------------------------------------------------------------------------
def lift(y: np.ndarray, inside: np.ndarray) -> float:
    if inside.all() or not inside.any():
        return float("nan")
    mi, mo = float(np.mean(y[inside])), float(np.mean(y[~inside]))
    return mi / mo if mo > 0 else float("nan")


def _phi(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def p_upper(real: float, null: np.ndarray, tail: str = "empirical") -> float:
    null = null[np.isfinite(null)]
    if not np.isfinite(real) or not len(null):
        return float("nan")
    if tail == "gaussian":
        sd = float(np.std(null, ddof=1))
        return float(1 - _phi((real - float(np.mean(null))) / sd)) if sd > 0 else (0.0 if real > np.mean(null) else 1.0)
    return float((1 + np.sum(null >= real)) / (1 + len(null)))


def p_two_sided_log(real: float, null: np.ndarray, tail: str = "empirical") -> float:
    ok = np.isfinite(null) & (null > 0)
    if not (np.isfinite(real) and real > 0) or not ok.any():
        return float("nan")
    return p_upper(abs(np.log(real)), np.abs(np.log(null[ok])), tail)


# ---- time windows --------------------------------------------------------------------------------------------------------------------
def tol_arr(L: np.ndarray, frac: float) -> np.ndarray:
    return np.maximum(1, np.floor(frac * np.asarray(L, dtype=float) + 0.5)).astype(np.int64)


@dataclass
class WindowSet:
    unit: str  # "bar" | "day"
    kind: str  # "shared" | "jitter" | "anniversary"
    a0: np.ndarray  # anchor position per row (candle index, or UTC day number)
    atc: np.ndarray  # anchor confirmation per row (same unit)
    s: np.ndarray  # active span start (candle index)
    e: np.ndarray  # active span end, exclusive
    L: np.ndarray  # real length per row
    W: np.ndarray  # real half-width per row
    group: np.ndarray  # shared/anniversary: index of the row's base count
    base: np.ndarray  # shared/anniversary: the base counts
    frac: np.ndarray  # shared: the row's fraction of its base count
    tol_frac: float = 0.025
    bday: np.ndarray | None = None
    n: int = 0
    lo_hi: tuple = (7.0, 366.0)
    template: dict = field(default_factory=dict)  # shared: per-anchor arrays and fractions, to build any count's rows

    @classmethod
    def from_bar_counts(cls, anchors_or_spans, n: int, counts, fracs, tol_frac: float, unit: str = "bar",
                        bday: np.ndarray | None = None) -> "WindowSet":
        spans = [(x, x.tc, n) if isinstance(x, Anchor) else x for x in anchors_or_spans]
        a = np.array([x[0].idx for x in spans], dtype=np.int64)
        tc = np.array([x[0].tc for x in spans], dtype=np.int64)
        if unit == "day":
            a, tc = bday[a], bday[tc]
        s = np.array([x[1] for x in spans], dtype=np.int64)
        e = np.array([x[2] for x in spans], dtype=np.int64)
        fr = np.array(fracs if fracs else [1.0], dtype=float)
        base = np.array(counts, dtype=float)
        k, m, f = len(base), len(a), len(fr)
        g = np.repeat(np.arange(k), m * f)
        frac = np.tile(np.repeat(fr, m), k)
        L = base[g] * frac
        ws = cls(unit, "shared", np.tile(np.tile(a, f), k), np.tile(np.tile(tc, f), k), np.tile(np.tile(s, f), k),
                 np.tile(np.tile(e, f), k), L, tol_arr(L, tol_frac), g, base, frac, tol_frac, bday, n,
                 (min(7.0, float(base.min())), max(366.0, float(base.max()))) if k else (7.0, 366.0))
        ws.template = {"a0": np.tile(a, f), "atc": np.tile(tc, f), "s": np.tile(s, f), "e": np.tile(e, f),
                       "frac": np.repeat(fr, m)}
        return ws

    @classmethod
    def from_windows(cls, windows, kind: str, bday: np.ndarray, n: int, tol_frac: float, base=None) -> "WindowSet":
        """Rows from Gann Window objects (balance, anniversary): lengths taken from each window's own centre."""
        unit = windows[0].unit if windows else "bar"
        if unit == "day":
            a0 = np.array([bday[w.anchor.idx] for w in windows], dtype=np.int64)
            atc = np.array([bday[w.anchor.tc] for w in windows], dtype=np.int64)
        else:
            a0 = np.array([w.anchor.idx for w in windows], dtype=np.int64)
            atc = np.array([w.anchor.tc for w in windows], dtype=np.int64)
        c = np.array([(w.lo + w.hi) // 2 for w in windows], dtype=np.int64)
        W = np.array([(w.hi - w.lo) // 2 for w in windows], dtype=np.int64)
        s = np.array([w.s for w in windows], dtype=np.int64)
        e = np.array([w.e for w in windows], dtype=np.int64)
        L = (c - a0).astype(float)
        if base is not None:
            base = np.asarray(base, dtype=float)
            g = np.array([int(np.argmin(np.abs(base - w.count))) for w in windows], dtype=np.int64)
        else:
            base, g = np.array([]), np.full(len(windows), -1, dtype=np.int64)
        return cls(unit, kind, a0, atc, s, e, L, W, g, base, np.ones(len(windows)), tol_frac, bday, n)


def vmask(ws: WindowSet, L: np.ndarray, W: np.ndarray, n: int, bday: np.ndarray | None,
          a0=None, atc=None, s=None, e=None) -> np.ndarray:
    a0 = ws.a0 if a0 is None else a0
    atc = ws.atc if atc is None else atc
    s = ws.s if s is None else s
    e = ws.e if e is None else e
    if not len(a0):
        return np.zeros(n, dtype=bool)
    c = np.floor(a0 + np.asarray(L, dtype=float) + 0.5).astype(np.int64)
    lo, hi = c - W, c + W
    ok = lo > atc
    if ws.unit == "day":
        i0 = np.searchsorted(bday, lo, side="left")
        i1 = np.searchsorted(bday, hi, side="right") - 1
    else:
        i0, i1 = lo, hi
    i0 = np.maximum(np.maximum(i0, s), 0)
    i1 = np.minimum(np.minimum(i1, e - 1), n - 1)
    ok &= i0 <= i1
    d = np.bincount(i0[ok], minlength=n + 1)[: n + 1] - np.bincount(i1[ok] + 1, minlength=n + 1)[: n + 1]
    return np.cumsum(d[:n]) > 0


def _banned(base: np.ndarray, tol_frac: float, lo: float, hi: float) -> np.ndarray:
    xs = np.arange(int(np.floor(lo)), int(np.ceil(hi)) + 1)
    ok = np.ones(len(xs), dtype=bool)
    for N in base:
        ok &= np.abs(xs - N) > max(1, int(np.floor(tol_frac * N + 0.5)))
    return xs[ok]


def _count_mask(ws: WindowSet, N: float, n: int) -> np.ndarray:
    t = ws.template
    L = N * t["frac"]
    return vmask(ws, L, tol_arr(L, ws.tol_frac), n, ws.bday, t["a0"], t["atc"], t["s"], t["e"])


def control_masks(ws: WindowSet, p, draws: int, rng: np.random.Generator, target_cov: float):
    """Yield `draws` control masks with coverage within COV_PP of target_cov (see the module docstring)."""
    n = ws.n
    if ws.kind == "shared":
        allowed = _banned(ws.base, ws.tol_frac, *ws.lo_hi)
        for _ in range(draws):
            counts = list(rng.choice(allowed, size=len(ws.base), replace=True))
            masks = [_count_mask(ws, N, n) for N in counts]
            tot = np.sum(masks, axis=0)
            cov = float(np.mean(tot > 0))
            guard = 0
            while cov > target_cov + COV_PP and len(masks) > 1 and guard < 4 * len(ws.base):
                tot -= masks.pop(int(rng.integers(len(masks))))
                cov, guard = float(np.mean(tot > 0)), guard + 1
            while cov < target_cov - COV_PP and guard < 8 * len(ws.base):
                m = _count_mask(ws, float(rng.choice(allowed)), n)
                masks.append(m)
                tot += m
                cov, guard = float(np.mean(tot > 0)), guard + 1
            yield tot > 0
        return
    for _ in range(draws):
        best, best_gap = None, np.inf
        for _ in range(MAX_REDRAW):
            if ws.kind == "jitter":
                Lc = ws.L * rng.uniform(0.5, 1.5, len(ws.L))
                bad = np.abs(Lc - ws.L) <= ws.W
                while bad.any():
                    Lc[bad] = ws.L[bad] * rng.uniform(0.5, 1.5, int(bad.sum()))
                    bad = np.abs(Lc - ws.L) <= ws.W
                m = vmask(ws, Lc, tol_arr(Lc, ws.tol_frac), n, ws.bday)
            else:  # anniversary
                xs = np.arange(*ANNIV_RANGE)
                xs = xs[np.min(np.abs(xs[:, None] - 365.25 * np.arange(1, 5)[None, :]), axis=1) > 7]
                offs = rng.choice(xs, size=len(ws.base))
                m = vmask(ws, offs[ws.group].astype(float), ws.W, n, ws.bday)
            gap = abs(float(m.mean()) - target_cov)
            if gap < best_gap:
                best, best_gap = m, gap
            if gap <= COV_PP:
                break
        yield best


def time_test(y: np.ndarray, inside: np.ndarray, ws: WindowSet, p, eval_mask: np.ndarray, draws: int,
              rng: np.random.Generator, two_sided: bool, tail: str = "empirical") -> dict:
    e = eval_mask & np.isfinite(y)
    real = lift(y[e], inside[e])
    null = np.array([lift(y[e], m[e]) for m in control_masks(ws, p, draws, rng, float(inside.mean()))])
    pv = p_two_sided_log(real, null, tail) if two_sided else p_upper(real, null, tail)
    return {"lift": real, "p": pv, "control_mean": float(np.nanmean(null)) if len(null) else None, "draws": len(null)}


def event_control_masks(n: int, bday: np.ndarray, event_days: np.ndarray, tol_days: int, draws: int,
                        rng: np.random.Generator, target_cov: float, lo_day: int, hi_day: int, periodic: bool = False):
    """Random event dates (astro, seasonal) with the same window width, matched to the real coverage by adding or removing
    random dates. periodic=True draws day-of-year positions repeated every year (seasonal)."""
    def mk(days):
        d = np.zeros(n + 1, dtype=np.int64)
        i0 = np.searchsorted(bday, days - tol_days, side="left")
        i1 = np.searchsorted(bday, days + tol_days, side="right") - 1
        ok = i0 <= i1
        d += np.bincount(i0[ok], minlength=n + 1)[: n + 1] - np.bincount(i1[ok] + 1, minlength=n + 1)[: n + 1]
        return np.cumsum(d[:n])

    real_set = set(int(x) for x in event_days)
    k = len(event_days)
    for _ in range(draws):
        days = rng.integers(lo_day, hi_day + 1, size=max(k, 1))
        days = np.array([x for x in days if all(abs(x - r) > tol_days for r in real_set)] or [lo_day])
        tot = mk(days)
        cov = float(np.mean(tot > 0))
        guard = 0
        while cov > target_cov + COV_PP and len(days) > 1 and guard < 4 * k:
            j = int(rng.integers(len(days)))
            tot -= mk(days[j:j + 1])
            days = np.delete(days, j)
            cov, guard = float(np.mean(tot > 0)), guard + 1
        while cov < target_cov - COV_PP and guard < 8 * k + 8:
            x = int(rng.integers(lo_day, hi_day + 1))
            tot += mk(np.array([x]))
            days = np.append(days, x)
            cov, guard = float(np.mean(tot > 0)), guard + 1
        yield tot > 0


# ---- price levels -------------------------------------------------------------------------------------------------------------------
@dataclass
class LineSet:
    """Lines known on candles [x0, x1): price(i) = p0 + slope x (i - aidx). gap: the line's spacing to its neighbour, or for an
    angle, the growth rate of that spacing (gap_slope), used to shift the line in a control."""
    x0: np.ndarray
    x1: np.ndarray
    p0: np.ndarray
    slope: np.ndarray
    aidx: np.ndarray
    gap: np.ndarray
    gap_slope: np.ndarray

    @classmethod
    def static(cls, x0, x1, levels: list[np.ndarray]) -> "LineSet":
        parts = []
        for a, b, lv in zip(x0, x1, levels):
            lv = np.sort(np.asarray(lv, dtype=float))
            if not len(lv):
                continue
            g = np.diff(lv)
            gap = np.r_[g, g[-1:]] if len(g) else np.array([0.0])
            parts.append((np.full(len(lv), a), np.full(len(lv), b), lv, gap))
        if not parts:
            z = np.array([])
            return cls(z, z, z, z, z, z, z)
        x0s, x1s, p0, gap = (np.concatenate(v) for v in zip(*parts))
        z = np.zeros(len(p0))
        return cls(x0s.astype(np.int64), x1s.astype(np.int64), p0, z, z.astype(np.int64), gap, z)

    @classmethod
    def concat(cls, sets: list["LineSet"]) -> "LineSet":
        sets = [s for s in sets if len(s.p0)]
        if not sets:
            z = np.array([])
            return cls(z, z, z, z, z, z, z)
        return cls(*(np.concatenate([getattr(s, f) for s in sets]) for f in
                     ("x0", "x1", "p0", "slope", "aidx", "gap", "gap_slope")))


def _pairs(lines: LineSet, eval_mask: np.ndarray):
    lens = np.maximum(lines.x1 - lines.x0, 0).astype(np.int64)
    if not lens.sum():
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    line = np.repeat(np.arange(len(lens)), lens)
    start = np.repeat(lines.x0.astype(np.int64), lens)
    off = np.arange(lens.sum()) - np.repeat(np.cumsum(lens) - lens, lens)
    i = start + off
    keep = eval_mask[i] & (i >= 1)
    return line[keep], i[keep]


def reactions(h, l, c, atr, touch_i, level, side, horizon: int) -> np.ndarray:  # noqa: E741
    """1 when price, after touching `level` on candle touch_i, moves 1 ATR away on the rejection side before any later candle
    CLOSES 1 ATR beyond the level (a candle doing both counts as a reaction: its close is its last price); the touch candle
    closing 1 ATR beyond is a failure. side +1: support (approached from above), -1: resistance."""
    n = len(c)
    if not len(touch_i):
        return np.array([])
    pad = np.full(horizon, np.nan)
    H = sliding_window_view(np.r_[h, pad], horizon)[1:n + 1][touch_i]
    Lw = sliding_window_view(np.r_[l, pad], horizon)[1:n + 1][touch_i]
    C = sliding_window_view(np.r_[c, pad], horizon)[1:n + 1][touch_i]
    a = atr[touch_i]
    up = side > 0
    target = np.where(up, level + a, level - a)
    fail = np.where(up, level - a, level + a)
    succ = np.where(up[:, None], H >= target[:, None], Lw <= target[:, None])
    brk = np.where(up[:, None], C < fail[:, None], C > fail[:, None])
    s_first = np.where(succ.any(axis=1), succ.argmax(axis=1), horizon + 1)
    f_first = np.where(brk.any(axis=1), brk.argmax(axis=1), horizon + 1)
    immediate = np.where(up, c[touch_i] < fail, c[touch_i] > fail)
    return ((~immediate) & (s_first <= horizon) & (s_first <= f_first)).astype(float)


def _rate(h, l, c, atr, tolp, lines: LineSet, line, i, shift, horizon):  # noqa: E741
    v = lines.p0[line] + lines.slope[line] * (i - lines.aidx[line]) + shift
    t = tolp[i]
    touched = (l[i] <= v + t) & (h[i] >= v - t)
    side = np.sign(c[i - 1] - v)
    touched &= side != 0
    if not touched.any():
        return float("nan"), 0, 0
    r = reactions(h, l, c, atr, i[touched], v[touched], side[touched], horizon)
    return float(r.mean()), int(touched.sum()), int(r.sum())


def level_test(h, l, c, atr, lines: LineSet, eval_mask: np.ndarray, p, draws: int, rng: np.random.Generator,  # noqa: E741
               horizon: int = 20, tail: str = "empirical") -> dict:
    tolp = np.maximum(p.price_tol_atr * atr, p.tick)
    tolp = np.where(np.isfinite(tolp), tolp, -np.inf)  # no ATR yet: nothing can touch
    line, i = _pairs(lines, eval_mask & np.isfinite(atr))
    real, touches, reacts = _rate(h, l, c, atr, tolp, lines, line, i, 0.0, horizon)
    null = []
    for _ in range(draws):
        u = rng.uniform(0.15, 0.85) * (1 if rng.random() < 0.5 else -1)
        shift = u * (lines.gap[line] + lines.gap_slope[line] * (i - lines.aidx[line]))
        null.append(_rate(h, l, c, atr, tolp, lines, line, i, shift, horizon)[0])
    null = np.array(null)
    cm = float(np.nanmean(null)) if np.isfinite(null).any() else float("nan")
    return {"lift": real / cm if cm and np.isfinite(cm) and cm > 0 else float("nan"), "p": p_upper(real, null, tail),
            "real_rate": real, "control_mean": cm, "touches": touches, "reactions": reacts, "draws": len(null)}
