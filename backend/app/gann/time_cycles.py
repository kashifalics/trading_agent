"""Gann time cycles (methodology 4.1, 4.9, 4.10): windows projected from anchors, never before the anchor is confirmed.

A window [centre - w, centre + w] exists only if its first candle (or calendar day) comes AFTER the anchor's confirmation, and
it marks only the candles of the anchor's active span (while it is one of the latest anchors of its kind). Bar counts are not
calendar time: weekends, holidays and gaps make them differ, so the two are separate methods.
"""
import calendar
import math
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.gann.anchors import Anchor
from app.gann.squares import cross

COUNTS = (7, 14, 21, 28, 30, 45, 49, 60, 72, 90, 108, 120, 135, 144, 180, 216, 240, 270, 288, 360, 365.25)
FRACS = (1 / 8, 1 / 4, 1 / 3, 3 / 8, 1 / 2, 5 / 8, 2 / 3, 3 / 4, 7 / 8)
SEASONAL = ((3, 21), (6, 21), (9, 23), (12, 21), (2, 4), (5, 6), (8, 8), (11, 8))  # cardinal, then mid-season
DAY = 86400


def tol(n: float, frac: float = 0.025) -> int:
    """Window half-width in the cycle's own units: max(1, round half up of frac x n)."""
    return max(1, int(math.floor(frac * n + 0.5)))


def session_day(ts: np.ndarray) -> np.ndarray:
    """FX session index: the trading day rolls at 17:00 America/New_York (DST-aware)."""
    s = pl.from_epoch(pl.Series("t", np.asarray(ts, dtype=np.int64)), time_unit="s")
    local = s.dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York").dt.replace_time_zone(None)
    return (local.dt.offset_by("7h").dt.date().cast(pl.Int32)).to_numpy()


def _dt(t: int) -> datetime:
    return datetime.fromtimestamp(int(t), timezone.utc)


def add_months(t: int, m: int) -> int:
    d = _dt(t)
    k = d.year * 12 + (d.month - 1) + int(m)
    y, mo = divmod(k, 12)
    day = min(d.day, calendar.monthrange(y, mo + 1)[1])
    return int(d.replace(year=y, month=mo + 1, day=day).timestamp())


def add_years(t: int, y: int) -> int:
    return add_months(t, 12 * int(y))


def calendar_window(t0: int, n: float, unit: str) -> tuple[int, int]:
    """(start, end) epoch seconds of the window n units after t0, +- tol(n) units."""
    w = tol(n)
    if unit in ("day", "week"):
        u = DAY * (7 if unit == "week" else 1)
        c = t0 + int(round(n * u))
        return c - w * u, c + w * u
    if unit == "month":
        return add_months(t0, int(n) - w), add_months(t0, int(n) + w)
    if unit == "year":
        return add_years(t0, int(n) - w), add_years(t0, int(n) + w)
    raise ValueError("unit must be day, week, month or year")


@dataclass(frozen=True)
class Window:
    """One projected time window. unit "bar": lo/hi are candle indices; unit "day": UTC day numbers. Both inclusive.
    It counts only on candles of the anchor's active span [s, e)."""
    column: str  # panel column it feeds, e.g. "t_cycle_bars"
    family: str  # confluence family: "cycles" | "angles" (balance) | "seasonal"
    method: str
    unit: str
    anchor: Anchor | None
    count: float
    frac: float
    lo: int
    hi: int
    s: int
    e: int


def _mark(diff: np.ndarray, lo: int, hi: int, s: int, e: int) -> None:
    lo, hi = max(lo, s, 0), min(hi, e - 1, len(diff) - 2)
    if lo <= hi:
        diff[lo] += 1
        diff[hi + 1] -= 1


def day_index(bar_ts: np.ndarray) -> np.ndarray:
    return np.floor_divide(np.asarray(bar_ts, dtype=np.int64), DAY)


def mask(windows, n: int, bday: np.ndarray | None = None) -> np.ndarray:
    """Candles inside any of the windows (and inside each window's active span)."""
    diff = np.zeros(n + 1, dtype=np.int32)
    for w in windows:
        if w.unit == "bar":
            _mark(diff, w.lo, w.hi, w.s, w.e)
        else:
            i0 = int(np.searchsorted(bday, w.lo, side="left"))
            i1 = int(np.searchsorted(bday, w.hi, side="right")) - 1
            _mark(diff, i0, i1, w.s, w.e)
    return np.cumsum(diff[:n]) > 0


def active(w: Window, i: int, bday: np.ndarray) -> bool:
    if not (w.s <= i < w.e):
        return False
    x = i if w.unit == "bar" else int(bday[i])
    return w.lo <= x <= w.hi


def bar_windows(spans, counts, fracs=None, tol_frac: float = 0.025, column: str = "t_cycle_bars",
                method: str = "cycle") -> list[Window]:
    """Windows counted in candles from each anchor; fracs: the fractional divisions instead of whole cycles."""
    out = []
    for a, s, e in spans:
        for N in counts:
            for f in fracs or (1.0,):
                L = N * f
                c = int(math.floor(a.idx + L + 0.5))
                w = tol(L, tol_frac)
                if c - w <= a.tc:
                    continue
                out.append(Window(column, "cycles", method, "bar", a, float(N), float(f), c - w, c + w, s, e))
    return out


def day_windows(bar_ts: np.ndarray, spans, counts_days, tol_frac: float = 0.025, column: str = "t_cycle_days",
                method: str = "cycle_days") -> list[Window]:
    """Windows counted in calendar (UTC) days from each anchor's candle."""
    bday = day_index(bar_ts)
    out = []
    for a, s, e in spans:
        d0, dtc = int(bday[a.idx]), int(bday[a.tc])
        for N in counts_days:
            c = int(math.floor(d0 + N + 0.5))
            w = tol(N, tol_frac)
            if c - w <= dtc:
                continue
            out.append(Window(column, "cycles", method, "day", a, float(N), 1.0, c - w, c + w, s, e))
    return out


def anniversary_windows(bar_ts: np.ndarray, anchors, tol_days: int = 2, years=(1, 2, 3)) -> list[Window]:
    """Calendar anniversaries of EVERY confirmed anchor passed in (an anniversary looks back years), from its confirmation."""
    bday = day_index(bar_ts)
    n = len(bday)
    out = []
    for a in anchors:
        dtc = int(bday[a.tc])
        for y in years:
            c = add_years(int(bar_ts[a.idx]), y) // DAY
            if c - tol_days <= dtc:
                continue
            out.append(Window("t_anniversary", "cycles", "anniversary", "day", a, float(y), 1.0, c - tol_days,
                              c + tol_days, a.tc, n))
    return out


def bar_cycle_mask(n: int, spans, counts, fracs=None, tol_frac: float = 0.025) -> np.ndarray:
    return mask(bar_windows(spans, counts, fracs, tol_frac), n)


def calendar_cycle_mask(bar_ts: np.ndarray, spans, counts_days, tol_frac: float = 0.025) -> np.ndarray:
    return mask(day_windows(bar_ts, spans, counts_days, tol_frac), len(bar_ts), day_index(bar_ts))


def sq9_time_counts(max_n: int = 400) -> list[int]:
    return cross("cardinal", max_n)


def anniversary_mask(bar_ts: np.ndarray, anchors, tol_days: int = 2, years=(1, 2, 3)) -> np.ndarray:
    return mask(anniversary_windows(bar_ts, anchors, tol_days, years), len(bar_ts), day_index(bar_ts))


def seasonal_mask(bar_ts: np.ndarray, tol_days: int = 2, dates=SEASONAL) -> np.ndarray:
    """Candles whose UTC date is within +- tol_days of a cardinal or mid-season date (anchor-free)."""
    d = np.asarray(bar_ts, dtype=np.int64).astype("datetime64[s]").astype("datetime64[D]")
    months = d.astype("datetime64[Y]").astype("datetime64[M]")
    out = np.zeros(len(d), dtype=bool)
    for m, dd in dates:
        target = (months + (m - 1)).astype("datetime64[D]") + (dd - 1)
        out |= np.abs((d - target).astype(np.int64)) <= tol_days
    return out


def coverage(mask: np.ndarray) -> float:
    return float(np.mean(mask)) if len(mask) else 0.0
