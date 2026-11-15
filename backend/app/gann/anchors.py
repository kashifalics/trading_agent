"""Gann anchors: swing highs and lows chosen by fixed rules, each KNOWN only from its confirmation candle `tc`.

minor: the existing 3/3 fractal swings (tc = idx + 3).
major: a causal zigzag. A high is confirmed at the first candle whose low is at least k x ATR below the running high since the
       last pivot (a low mirrors this). The pivot can never be confirmed on its own candle.
chart{n}: Gann's N-bar swing chart. The line turns up after n consecutive higher highs and down after n consecutive lower
       lows; the pivot is the previous swing's extreme. The first turn only sets the direction (the data may start mid-swing).
"""
from dataclasses import dataclass

import numpy as np

from app.market_data.bars import Bars
from app.market_structure.swings import find_swings


@dataclass(frozen=True)
class Anchor:
    idx: int  # candle of the extreme
    tc: int  # candle at whose close the anchor becomes known
    price: float
    kind: str  # "high" | "low"
    tier: str  # "minor" | "major" | "chart{n}"


def cut(b: Bars, stop: int) -> Bars:
    """The first `stop` candles: what was known at the close of candle stop - 1."""
    return Bars(t=b.t[:stop], o=b.o[:stop], h=b.h[:stop], l=b.l[:stop], c=b.c[:stop], v=b.v[:stop], step=b.step,
                vtype=b.vtype, tb=None if b.tb is None else b.tb[:stop])


def minor_anchors(b: Bars) -> list[Anchor]:
    return [Anchor(s.idx, s.confirm_idx, s.price, s.kind, "minor") for s in find_swings(b, 3, 3)]


def major_anchors(b: Bars, atr: np.ndarray, k: float = 5.0) -> list[Anchor]:
    h, l = b.h, b.l  # noqa: E741
    out: list[Anchor] = []
    mode = None  # None (no pivot yet) | "up" (last pivot a low: tracking a high) | "down"
    hi_v = lo_v = np.nan
    hi_i = lo_i = -1
    for i in range(len(h)):
        a = atr[i]
        if not np.isfinite(a):
            continue
        if mode is None:
            if hi_i < 0:
                hi_v, hi_i, lo_v, lo_i = h[i], i, l[i], i
                continue
            if h[i] > hi_v:
                hi_v, hi_i = h[i], i
            if l[i] < lo_v:
                lo_v, lo_i = l[i], i
            top = hi_i < i and l[i] <= hi_v - k * a
            bottom = lo_i < i and h[i] >= lo_v + k * a
            if top and (not bottom or hi_i < lo_i):
                out.append(Anchor(hi_i, i, float(hi_v), "high", "major"))
                j = hi_i + 1 + int(np.argmin(l[hi_i + 1:i + 1]))
                mode, lo_v, lo_i = "down", l[j], j
            elif bottom:
                out.append(Anchor(lo_i, i, float(lo_v), "low", "major"))
                j = lo_i + 1 + int(np.argmax(h[lo_i + 1:i + 1]))
                mode, hi_v, hi_i = "up", h[j], j
        elif mode == "up":
            if h[i] > hi_v:
                hi_v, hi_i = h[i], i
            if hi_i < i and l[i] <= hi_v - k * a:
                out.append(Anchor(hi_i, i, float(hi_v), "high", "major"))
                j = hi_i + 1 + int(np.argmin(l[hi_i + 1:i + 1]))
                mode, lo_v, lo_i = "down", l[j], j
        else:
            if l[i] < lo_v:
                lo_v, lo_i = l[i], i
            if lo_i < i and h[i] >= lo_v + k * a:
                out.append(Anchor(lo_i, i, float(lo_v), "low", "major"))
                j = lo_i + 1 + int(np.argmax(h[lo_i + 1:i + 1]))
                mode, hi_v, hi_i = "up", h[j], j
    return out


def swing_chart(b: Bars, n: int) -> list[Anchor]:
    h, l = b.h, b.l  # noqa: E741
    out: list[Anchor] = []
    mode = None
    hh = ll = 0
    ext_v, ext_i = np.nan, -1  # running extreme of the current swing (low in a down swing, high in an up swing)
    for i in range(1, len(h)):
        hh = hh + 1 if h[i] > h[i - 1] else 0
        ll = ll + 1 if l[i] < l[i - 1] else 0
        if mode == "down" and l[i] < ext_v:
            ext_v, ext_i = l[i], i
        elif mode == "up" and h[i] > ext_v:
            ext_v, ext_i = h[i], i
        if mode != "up" and hh >= n:
            if mode == "down":
                out.append(Anchor(ext_i, i, float(ext_v), "low", f"chart{n}"))
                j = ext_i + 1 + int(np.argmax(h[ext_i + 1:i + 1]))
            else:
                j = i - n + 1 + int(np.argmax(h[i - n + 1:i + 1]))
            mode, ext_v, ext_i = "up", h[j], j
        elif mode != "down" and ll >= n:
            if mode == "up":
                out.append(Anchor(ext_i, i, float(ext_v), "high", f"chart{n}"))
                j = ext_i + 1 + int(np.argmin(l[ext_i + 1:i + 1]))
            else:
                j = int(np.argmax(h[:i + 1]))  # the down swing began at the highest high so far
                j = j + int(np.argmin(l[j:i + 1]))
            mode, ext_v, ext_i = "down", l[j], j
    return out


def active_spans(anchors: list[Anchor], n: int, per_kind: int = 2) -> list[tuple[Anchor, int, int]]:
    """(anchor, start, end): the candles [start, end) during which the anchor is among the latest `per_kind` confirmed
    anchors of its kind. It starts at its own tc and ends at the tc of the anchor that pushes it out (or at n)."""
    out = []
    for kind in ("high", "low"):
        ks = sorted((a for a in anchors if a.kind == kind), key=lambda a: (a.tc, a.idx))
        for j, a in enumerate(ks):
            end = ks[j + per_kind].tc if j + per_kind < len(ks) else n
            out.append((a, a.tc, end))
    return sorted(out, key=lambda x: (x[1], x[0].idx))
