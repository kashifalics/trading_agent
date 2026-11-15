"""What Gann says at each candle, using only what was known at that candle's close.

panel(): one row per candle, vectorised, for research. gann_state(): the full detail for one candle, for display and for the
live engine; it recomputes from the candles up to i only. Both are built from the same helpers below, and tests assert they
agree, that the panel is causal (a prefix gives the same rows) and that the state equals the state computed on cut data.
"""
import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import polars as pl

from app.feature_engineering.indicators import atr as atr_fn
from app.gann.anchors import Anchor, active_spans, cut, major_anchors
from app.gann.angles import LABEL, balance_centres, fan, scale_atr, scale_swing
from app.gann.confluence import FAMILIES, families_at
from app.gann.params import GannParams
from app.gann.price import divisions, round_tick, twelfths
from app.gann.squares import cross, sq9_levels
from app.gann.time_cycles import (
    DAY,
    Window,
    active,
    anniversary_windows,
    bar_windows,
    day_index,
    day_windows,
    mask,
    seasonal_mask,
    sq9_time_counts,
    tol,
)
from app.market_data.bars import Bars

TIME_COLS = ("t_cycle_bars", "t_cycle_days", "t_fraction", "t_anniversary", "t_seasonal", "t_balance_swing",
             "t_balance_atr", "t_balance_fixed", "t_sq9_time")
DIST_COLS = ("d_division", "d_twelfths", "d_square9", "d_sq4", "d_angle_swing", "d_angle_atr", "d_symmetry")
TIME_FAMILY = {"t_cycle_bars": "cycles", "t_cycle_days": "cycles", "t_fraction": "cycles", "t_anniversary": "cycles",
               "t_sq9_time": "cycles", "t_seasonal": "seasonal", "t_balance_swing": "angles", "t_balance_atr": "angles",
               "t_balance_fixed": "angles"}
DIST_FAMILY = {"d_division": "divisions", "d_twelfths": "divisions", "d_square9": "square9", "d_sq4": "square9",
               "d_angle_swing": "angles", "d_angle_atr": "angles", "d_symmetry": "symmetry"}
METHOD_COL = {"division": "d_division", "twelfth": "d_twelfths", "square9": "d_square9", "symmetry": "d_symmetry"}
SQ4_BAND_ATR = 5.0  # Square of Four numbers listed in a state: within 5 ATR of the close
UPCOMING = 30


@dataclass
class GannState:
    i: int
    ts: int
    params_sha: str
    anchors: list[dict]
    windows: list[dict]  # active at candle i
    upcoming: list[dict]  # projected windows that start after candle i (from anchors known at i)
    levels: list[dict]  # price levels known at i
    families: list[str]  # families active at the close of i
    confluence: int


@dataclass
class _Ctx:
    n: int
    atr: np.ndarray
    anchors: list[Anchor]
    spans: list
    prev: dict
    bday: np.ndarray
    windows: list[Window]
    seasonal: np.ndarray
    sq4: np.ndarray


@lru_cache(maxsize=8)
def _sq4_numbers(n2: int) -> np.ndarray:
    return np.array(cross("diagonal", n2, square=4), dtype=float)


def _sq4(max_price: float) -> np.ndarray:
    return _sq4_numbers(1 << max(4, math.ceil(math.log2(max(max_price * 1.5, 16.0)))))


def _balance_windows(spans, prev, atr, bday, p: GannParams, daily: bool) -> list[Window]:
    out = []
    for a, s, e in spans:
        pv = prev.get(a)
        if pv is None:
            continue
        for col, sc in (("t_balance_swing", scale_swing(pv, a)), ("t_balance_atr", scale_atr(atr, a))):
            if not (np.isfinite(sc) and sc > 0):
                continue
            for C in balance_centres(pv, a, sc):
                L = C - a.idx
                c, w = int(math.floor(C + 0.5)), tol(L, p.tol_frac)
                if c - w > a.tc:
                    out.append(Window(col, "angles", "balance", "bar", a, float(L), 1.0, c - w, c + w, s, e))
        if daily:
            d0, dtc = int(bday[a.idx]), int(bday[a.tc])
            for L in (abs(a.price - pv.price) / p.fixed_scale, a.price / p.fixed_scale):
                c, w = int(math.floor(d0 + L + 0.5)), tol(L, p.tol_frac)
                if c - w > dtc:
                    out.append(Window("t_balance_fixed", "angles", "balance", "day", a, float(L), 1.0, c - w, c + w, s, e))
    return out


def _context(b: Bars, p: GannParams, daily: bool) -> _Ctx:
    n = len(b.c)
    atr = atr_fn(b.h, b.l, b.c, p.atr_n)
    anchors = major_anchors(b, atr, p.major_k)
    spans = active_spans(anchors, n, p.per_kind)
    prev = {a: (anchors[j - 1] if j else None) for j, a in enumerate(anchors)}
    bday = day_index(b.t)
    ws = bar_windows(spans, p.counts, None, p.tol_frac, "t_cycle_bars", "cycle")
    ws += bar_windows(spans, p.counts, p.fracs, p.tol_frac, "t_fraction", "fraction")
    ws += bar_windows(spans, sq9_time_counts(p.sq9_time_max), None, p.tol_frac, "t_sq9_time", "sq9_time")
    if daily:
        ws += day_windows(b.t, spans, p.counts, p.tol_frac)
    ws += anniversary_windows(b.t, anchors, p.anniv_tol_days, p.anniv_years)
    ws += _balance_windows(spans, prev, atr, bday, p, daily)
    sq4 = _sq4(float(np.max(b.h))) if n else np.array([])
    return _Ctx(n, atr, anchors, spans, prev, bday, ws, seasonal_mask(b.t, p.seasonal_tol_days, p.seasonal), sq4)


def _lv(family: str, method: str, price: float, a: Anchor | None, **kw) -> dict:
    d = {"family": family, "method": method, "price": float(price), "anchor_idx": a.idx if a else None,
         "anchor_tc": a.tc if a else None}
    d.update(kw)
    return d


def _static_levels(A: list[Anchor], L: Anchor | None, pv: Anchor | None, p: GannParams) -> list[dict]:
    """Levels that stay fixed while the set of active anchors does not change."""
    out = []
    if L is not None and pv is not None:
        lo, hi = sorted((L.price, pv.price))
        for f, px in divisions(lo, hi, p.tick, ext=True, down=L.kind == "low"):
            out.append(_lv("divisions", "division", px, L, fraction=f, swing_from=pv.idx))
        for f, px in twelfths(lo, hi, p.tick):
            out.append(_lv("divisions", "twelfth", px, L, fraction=f, swing_from=pv.idx))
        sign = 1.0 if L.kind == "low" else -1.0
        for r in p.symmetry_ratios:
            out.append(_lv("symmetry", "symmetry", round_tick(L.price + sign * r * (hi - lo), p.tick), L, ratio=r))
    for a in A:
        for deg, px in sq9_levels(a.price, p.tick, p.sq9_steps, p.sq9_step_deg):
            out.append(_lv("square9", "square9", px, a, degrees=deg))
    return out


def _scale(a: Anchor, kind: str, cx: _Ctx) -> float | None:
    if kind == "swing":
        pv = cx.prev.get(a)
        s = scale_swing(pv, a) if pv is not None else None
    else:
        s = scale_atr(cx.atr, a)
    return s if s is not None and np.isfinite(s) and s > 0 else None


def _latest(A: list[Anchor]) -> Anchor | None:
    return max(A, key=lambda a: (a.tc, a.idx)) if A else None


def _nearest(x: np.ndarray, lv: np.ndarray) -> np.ndarray:
    pos = np.searchsorted(lv, x)
    lo = lv[np.clip(pos - 1, 0, len(lv) - 1)]
    hi = lv[np.clip(pos, 0, len(lv) - 1)]
    return np.minimum(np.abs(x - lo), np.abs(x - hi))


def panel(b: Bars, p: GannParams, *, daily: bool) -> pl.DataFrame:
    n = len(b.c)
    cx = _context(b, p, daily)
    cols = {}
    for col in TIME_COLS:
        ws = [w for w in cx.windows if w.column == col]
        cols[col] = mask(ws, n, cx.bday) if ws else np.zeros(n, dtype=bool)
    cols["t_seasonal"] = cx.seasonal
    absd = {c: np.full(n, np.nan) for c in DIST_COLS}
    side = {"swing": np.zeros(n), "atr": np.zeros(n)}
    bounds = sorted({0, n} | {min(max(s, 0), n) for _, s, _ in cx.spans} | {min(max(e, 0), n) for _, _, e in cx.spans})
    for x0, x1 in zip(bounds[:-1], bounds[1:]):
        A = [a for a, s, e in cx.spans if s <= x0 < e]
        if x0 >= x1 or not A:
            continue
        L = _latest(A)
        static = _static_levels(A, L, cx.prev.get(L), p)
        cc = b.c[x0:x1]
        for method, col in METHOD_COL.items():
            lv = np.sort(np.array([x["price"] for x in static if x["method"] == method]))
            if len(lv):
                absd[col][x0:x1] = _nearest(cc, lv)
        idx = np.arange(x0, x1)
        for kind, col in (("swing", "d_angle_swing"), ("atr", "d_angle_atr")):
            best = np.full(x1 - x0, np.inf)
            for a in A:
                s_ = _scale(a, kind, cx)
                if s_ is not None:
                    best = np.minimum(best, np.abs(round_tick(fan(a, s_, idx - a.idx, p.rates), p.tick) - cc).min(axis=0))
            absd[col][x0:x1] = np.where(np.isfinite(best), best, np.nan)
            s_ = _scale(L, kind, cx)
            if s_ is not None:
                side[kind][x0:x1] = np.sign(cc - round_tick(fan(L, s_, idx - L.idx, rates=(1,))[0], p.tick))
    if len(cx.sq4):
        absd["d_sq4"] = _nearest(b.c, cx.sq4)
    tolp = np.maximum(p.price_tol_atr * cx.atr, p.tick)
    fi = {f: k for k, f in enumerate(FAMILIES)}
    fam = np.zeros((n, len(FAMILIES)), dtype=bool)
    for col, f in TIME_FAMILY.items():
        fam[:, fi[f]] |= cols[col]
    for col, f in DIST_FAMILY.items():
        fam[:, fi[f]] |= np.nan_to_num(absd[col], nan=np.inf) <= tolp
    out = dict(cols)
    for col in DIST_COLS:
        out[col] = absd[col] / cx.atr
    out["side_swing"], out["side_atr"] = side["swing"], side["atr"]
    out["families"] = fam.sum(axis=1).astype(np.int64)
    out["atr"] = cx.atr
    return pl.DataFrame(out)


def _wdict(w: Window, bday: np.ndarray, t: np.ndarray, step: int, i: int) -> dict:
    start = int(t[i] + (w.lo - i) * step) if w.unit == "bar" else int(w.lo * DAY)
    return {"column": w.column, "family": w.family, "method": w.method, "unit": w.unit,
            "anchor_idx": w.anchor.idx if w.anchor else None, "anchor_tc": w.anchor.tc if w.anchor else None,
            "anchor_price": w.anchor.price if w.anchor else None, "count": w.count, "frac": w.frac, "lo": w.lo,
            "hi": w.hi, "approx_start_ts": start}


def _angle_levels(A: list[Anchor], i: int, cx: _Ctx, p: GannParams) -> list[dict]:
    out = []
    for a in A:
        for kind in ("swing", "atr"):
            s_ = _scale(a, kind, cx)
            if s_ is None:
                continue
            vals = round_tick(fan(a, s_, np.array([i - a.idx]), p.rates), p.tick)[:, 0]
            for r, v in zip(p.rates, vals):
                out.append(_lv("angles", f"angle_{kind}", v, a, rate=r, label=LABEL.get(r, str(r)), scale=s_))
    return out


def gann_state(b: Bars, i: int, p: GannParams, *, daily: bool) -> GannState:
    bc = cut(b, i + 1)
    cx = _context(bc, p, daily)
    A = [a for a, s, e in cx.spans if s <= i < e]
    L = _latest(A)
    windows = [_wdict(w, cx.bday, bc.t, bc.step, i) for w in cx.windows if active(w, i, cx.bday)]
    if cx.seasonal[i]:
        windows.append({"column": "t_seasonal", "family": "seasonal", "method": "seasonal", "unit": "day",
                        "anchor_idx": None, "anchor_tc": None, "anchor_price": None, "count": None, "frac": None,
                        "lo": None, "hi": None, "approx_start_ts": None})
    now_day, aset = int(cx.bday[i]), set(A)
    up = [w for w in cx.windows if (w.method == "anniversary" or w.anchor in aset)
          and w.lo > (i if w.unit == "bar" else now_day)]
    upcoming = sorted((_wdict(w, cx.bday, bc.t, bc.step, i) for w in up), key=lambda d: (d["approx_start_ts"], d["column"]))
    levels = _static_levels(A, L, cx.prev.get(L), p) + _angle_levels(A, i, cx, p)
    a_i, c_i = cx.atr[i], float(bc.c[i])
    if np.isfinite(a_i) and len(cx.sq4):
        band = cx.sq4[(cx.sq4 >= c_i - SQ4_BAND_ATR * a_i) & (cx.sq4 <= c_i + SQ4_BAND_ATR * a_i)]
        levels += [_lv("square9", "sq4", float(v), None) for v in band]
    tol_i = float(np.maximum(p.price_tol_atr * a_i, p.tick))
    fams = sorted(families_at(levels, windows, c_i, tol_i))
    return GannState(i, int(bc.t[i]), p.sha(),
                     [{"idx": a.idx, "tc": a.tc, "price": a.price, "kind": a.kind, "tier": a.tier} for a in A],
                     windows, upcoming[:UPCOMING], levels, fams, len(fams))


def levels_at(b: Bars, i: int, p: GannParams) -> list[dict]:
    """Every price level known at candle i (filters and Gann-only rules test them against an entry price)."""
    return gann_state(b, i, p, daily=False).levels
