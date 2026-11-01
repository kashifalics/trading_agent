"""Support / resistance, trendlines + channels, breakouts / retests / failed breakouts.

Every detector is causal: it only uses swings CONFIRMED at or before `as_of`, and each definition is parameterised so it
can be tested and tuned explicitly (no hidden thresholds). Events use the shared `Event` structure.

Definitions (defaults in the dataclasses below):
  support / resistance : cluster of >= `min_touches` confirmed swing extremes whose prices lie within `tol_atr` * ATR of the
                         cluster mean; role is set by where the last close sits (below the band = resistance, above = support).
  trendline            : straight line through two confirmed same-kind swings with >= `min_touches` swings within
                         `tol_atr` * ATR of it and no close beyond it by more than `tol_atr` * ATR since the first anchor.
  channel              : a support and a resistance trendline whose slopes differ by <= `parallel_tol` (relative).
  breakout             : close beyond a level's band by >= `break_atr` * ATR after a prior close inside / behind it, in the direction
                         AWAY from the side price had been on (median of the previous `ref_bars` closes): a resistance is broken
                         upward, a support downward; dropping further below a resistance is not a breakout.
  retest               : within `retest_window` bars of a breakout, price trades back into the band and closes on the
                         breakout side again (flip of role confirmed).
  failed_breakout      : within `fail_window` bars of a breakout, a close back on the original side of the band.
"""
from dataclasses import dataclass

import numpy as np

from app.core.events import Event
from app.market_data.bars import Bars
from app.market_structure.swings import Swing


@dataclass
class LevelParams:
    tol_atr: float = 0.5
    min_touches: int = 2
    lookback_swings: int = 40


@dataclass
class TrendlineParams:
    tol_atr: float = 0.3
    min_touches: int = 3
    max_anchor_swings: int = 6
    parallel_tol: float = 0.25


@dataclass
class BreakoutParams:
    break_atr: float = 0.25
    retest_window: int = 12
    fail_window: int = 5
    lookback_bars: int = 400
    ref_bars: int = 10  # closes before the break that decide which side of the band price was on


def _atr_at(atr: np.ndarray, i: int) -> float:
    a = atr[min(i, len(atr) - 1)] if len(atr) else np.nan
    return float(a) if np.isfinite(a) and a > 0 else float("nan")


def detect_levels(b: Bars, swings: list[Swing], atr: np.ndarray, as_of: int | None = None,
                  p: LevelParams | None = None) -> list[Event]:
    """Horizontal support/resistance bands from clustered confirmed swings (information available at bar `as_of`)."""
    p = p or LevelParams()
    n = len(b)
    if n == 0:
        return []
    i = n - 1 if as_of is None else as_of
    a = _atr_at(atr, i)
    if not np.isfinite(a):
        return []
    sw = [s for s in swings if s.confirm_idx <= i][-p.lookback_swings:]
    if len(sw) < p.min_touches:
        return []
    order = sorted(sw, key=lambda s: s.price)
    clusters: list[list[Swing]] = [[order[0]]]
    for s in order[1:]:
        cur = clusters[-1]
        if s.price - float(np.mean([x.price for x in cur])) <= p.tol_atr * a:
            cur.append(s)
        else:
            clusters.append([s])
    px = float(b.c[i])
    out: list[Event] = []
    for cl in clusters:
        if len(cl) < p.min_touches:
            continue
        prices = [x.price for x in cl]
        lo, hi, mid = min(prices), max(prices), float(np.mean(prices))
        last = max(cl, key=lambda x: x.confirm_idx)
        kind = "support" if px >= hi else "resistance" if px <= lo else ("support" if px >= mid else "resistance")
        out.append(Event(kind=kind, direction="bullish" if kind == "support" else "bearish", idx=last.confirm_idx,
                         ts=int(b.t[last.confirm_idx]), price=mid, low=lo, high=hi,
                         start_idx=min(x.idx for x in cl), start_ts=int(b.t[min(x.idx for x in cl)]), status="active",
                         evidence=f"{len(cl)} swing touches within {p.tol_atr} ATR around {mid:.6g}",
                         params={"tol_atr": p.tol_atr, "min_touches": p.min_touches},
                         meta={"touches": len(cl), "first_confirm_idx": min(x.confirm_idx for x in cl),
                               "second_confirm_idx": sorted(x.confirm_idx for x in cl)[1],
                               "kinds": sorted({x.kind for x in cl})}))
    return sorted(out, key=lambda e: abs(e.price - px))


def detect_trendlines(b: Bars, swings: list[Swing], atr: np.ndarray, as_of: int | None = None,
                      p: TrendlineParams | None = None) -> list[Event]:
    p = p or TrendlineParams()
    n = len(b)
    if n == 0:
        return []
    i = n - 1 if as_of is None else as_of
    a = _atr_at(atr, i)
    if not np.isfinite(a):
        return []
    out: list[Event] = []
    for kind, role in (("low", "trendline_support"), ("high", "trendline_resistance")):
        pts = [s for s in swings if s.kind == kind and s.confirm_idx <= i][-p.max_anchor_swings:]
        best = None
        for x in range(len(pts)):
            for y in range(x + 1, len(pts)):
                s1, s2 = pts[x], pts[y]
                if s2.idx == s1.idx:
                    continue
                slope = (s2.price - s1.price) / (s2.idx - s1.idx)
                line = lambda k, s1=s1, slope=slope: s1.price + slope * (k - s1.idx)  # noqa: E731
                touches = [s for s in pts if abs(s.price - line(s.idx)) <= p.tol_atr * a]
                if len(touches) < p.min_touches:
                    continue
                seg = np.arange(s1.idx, i + 1)
                lv = s1.price + slope * (seg - s1.idx)
                breach = (b.c[seg] < lv - p.tol_atr * a) if kind == "low" else (b.c[seg] > lv + p.tol_atr * a)
                if breach.any():
                    continue
                key = (len(touches), s2.idx)
                if best is None or key > best[0]:
                    best = (key, s1, s2, slope, touches)
        if best:
            _, s1, s2, slope, touches = best
            val = s1.price + slope * (i - s1.idx)
            out.append(Event(kind=role, direction="bullish" if kind == "low" else "bearish", idx=max(t.confirm_idx for t in touches),
                             ts=int(b.t[max(t.confirm_idx for t in touches)]), price=float(val), start_idx=s1.idx,
                             start_ts=int(b.t[s1.idx]), status="active",
                             evidence=f"{len(touches)} swing {kind}s on a line sloping {slope:+.6g}/bar; no close beyond it",
                             params={"tol_atr": p.tol_atr, "min_touches": p.min_touches},
                             meta={"slope": float(slope), "anchor_idx": [s1.idx, s2.idx], "anchor_price": [s1.price, s2.price],
                                   "touches": len(touches), "value_now": float(val)}))
    sup = next((e for e in out if e.kind == "trendline_support"), None)
    res = next((e for e in out if e.kind == "trendline_resistance"), None)
    if sup and res:
        s_, r_ = sup.meta["slope"], res.meta["slope"]
        scale = max(abs(s_), abs(r_), 1e-12)
        if abs(s_ - r_) / scale <= p.parallel_tol and res.meta["value_now"] > sup.meta["value_now"]:
            out.append(Event(kind="channel", direction="bullish" if s_ > 0 else "bearish" if s_ < 0 else "neutral",
                             idx=max(sup.idx, res.idx), ts=max(sup.ts, res.ts), low=sup.meta["value_now"], high=res.meta["value_now"],
                             start_idx=min(sup.start_idx or 0, res.start_idx or 0), start_ts=min(sup.start_ts or 0, res.start_ts or 0),
                             status="active", evidence=f"parallel trendlines (slope diff {abs(s_ - r_) / scale:.0%})",
                             meta={"upper_slope": r_, "lower_slope": s_}))
    return out


def detect_breakouts(b: Bars, levels: list[Event], atr: np.ndarray, p: BreakoutParams | None = None) -> list[Event]:
    """Breakouts, retests and failed breakouts of already-known levels. A level only counts for a breakout at bar k if its
    second touch was confirmed before k (so the band existed in the information set at k)."""
    p = p or BreakoutParams()
    n = len(b)
    out: list[Event] = []
    start = max(2, n - p.lookback_bars)
    for lv in levels:
        lo, hi = lv.low, lv.high
        ready = lv.meta.get("second_confirm_idx", lv.idx)
        k = max(start, ready + 1)
        while k < n:
            a = _atr_at(atr, k)
            if not np.isfinite(a):
                k += 1
                continue
            side = float(np.median(b.c[max(0, k - p.ref_bars):k])) - (lo + hi) / 2  # >0: price had been above (band acted as support)
            up = side < 0 and b.c[k] > hi + p.break_atr * a and b.c[k - 1] <= hi + p.break_atr * a
            dn = side > 0 and b.c[k] < lo - p.break_atr * a and b.c[k - 1] >= lo - p.break_atr * a
            if not (up or dn):
                k += 1
                continue
            d = "bullish" if up else "bearish"
            out.append(Event(kind="breakout", direction=d, idx=k, ts=int(b.t[k]), price=float(b.c[k]), low=lo, high=hi,
                             start_idx=lv.start_idx, start_ts=lv.start_ts, status="confirmed",
                             evidence=f"close {b.c[k]:.6g} beyond {lv.kind} band {lo:.6g}-{hi:.6g} by >= {p.break_atr} ATR",
                             params={"break_atr": p.break_atr}, meta={"level_kind": lv.kind, "touches": lv.meta.get("touches")}))
            resolved = False
            for j in range(k + 1, min(n, k + 1 + max(p.retest_window, p.fail_window))):
                if j - k <= p.fail_window and ((up and b.c[j] <= hi) or (dn and b.c[j] >= lo)):
                    out.append(Event(kind="failed_breakout", direction="bearish" if up else "bullish", idx=j, ts=int(b.t[j]),
                                     price=float(b.c[j]), low=lo, high=hi, status="confirmed",
                                     evidence=f"closed back inside/behind the band {j - k} bar(s) after the breakout",
                                     params={"fail_window": p.fail_window}, meta={"breakout_idx": k}))
                    resolved = True
                    break
                touched = (b.l[j] <= hi) if up else (b.h[j] >= lo)
                held = (b.c[j] > hi) if up else (b.c[j] < lo)
                if touched and held and j - k <= p.retest_window:
                    out.append(Event(kind="retest", direction=d, idx=j, ts=int(b.t[j]), price=float(b.c[j]), low=lo, high=hi,
                                     status="confirmed", evidence="price traded back into the broken band and closed on the breakout side",
                                     params={"retest_window": p.retest_window}, meta={"breakout_idx": k}))
                    resolved = True
                    break
            k = (j if resolved else k) + 1
    return sorted(out, key=lambda e: e.idx)


DEFINITIONS = {
    "support": "Cluster of >= 2 confirmed swing extremes within 0.5 ATR of each other; price currently above the band.",
    "resistance": "Same cluster definition, price currently below the band.",
    "trendline_support": "Line through confirmed swing lows with >= 3 touches within 0.3 ATR and no close beyond it by > 0.3 ATR.",
    "trendline_resistance": "Mirror of trendline_support on swing highs.",
    "channel": "A support and a resistance trendline with slopes within 25% of each other.",
    "breakout": "Close beyond a support/resistance band by >= 0.25 ATR after a prior close inside or behind it.",
    "retest": "Within 12 bars of a breakout, price trades back into the band and closes on the breakout side again.",
    "failed_breakout": "Within 5 bars of a breakout, a close back on the original side of the band.",
}
