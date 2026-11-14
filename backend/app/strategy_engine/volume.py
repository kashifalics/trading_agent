"""Volume type, reliability and session-normalised relative volume (docs/engine_v2/CONFIRMATION_DESIGN.md section 3).

Everything here is causal: the value at candle i uses candles up to i (relative volume uses only candles before i).
Clock: New York local time for FX-calendar instruments (sessions follow New York and London, daylight saving included), UTC for a
continuous (24/7) market.
"""
import warnings
from dataclasses import dataclass

import numpy as np
import polars as pl

from app.strategy_engine.config import VOLUME_LABELS, VOLUME_RULES

SAMPLES = VOLUME_RULES["weeks"]  # one sample per week in the candle's own slot of the week = the last 20 weeks


@dataclass
class VolumeQuality:
    type: str  # base | tick | venue | none
    label: str  # customer copy (VOLUME_LABELS)
    reliable: bool
    reason: str  # why not reliable; "" when reliable


def _parts(t: np.ndarray, calendar: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(weekday Monday=0, hour, minute) of each candle open, in New York time (FX calendars) or UTC (continuous)."""
    t = np.asarray(t, dtype=np.int64)
    if calendar == "continuous":
        days = t // 86400
        return ((days + 3) % 7).astype(np.int64), ((t // 3600) % 24).astype(np.int64), ((t // 60) % 60).astype(np.int64)
    s = pl.Series(t * 1_000_000, dtype=pl.Int64).cast(pl.Datetime("us", "UTC")).dt.convert_time_zone("America/New_York")
    return ((s.dt.weekday() - 1).to_numpy().astype(np.int64), s.dt.hour().to_numpy().astype(np.int64),
            s.dt.minute().to_numpy().astype(np.int64))


def hour_of_week(t: np.ndarray, calendar: str) -> np.ndarray:
    wd, hr, _ = _parts(t, calendar)
    return wd * 24 + hr


def session_ids(t: np.ndarray, calendar: str) -> np.ndarray:
    """A new id at each session start: 17:00 New York for FX calendars (daylight saving included), 00:00 UTC for continuous."""
    t = np.asarray(t, dtype=np.int64)
    if calendar == "continuous":
        return t // 86400
    s = pl.Series(t * 1_000_000, dtype=pl.Int64).cast(pl.Datetime("us", "UTC")).dt.convert_time_zone("America/New_York")
    return s.dt.offset_by("7h").dt.date().cast(pl.Int32).to_numpy().astype(np.int64)


def _prev_median(v: np.ndarray, groups: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """For each candle: the median of the previous k finite values in its group (time order) and how many there were."""
    med, cnt = np.full(len(v), np.nan), np.zeros(len(v), dtype=np.int64)
    order = np.argsort(groups, kind="stable")  # stable: time order kept inside each group
    g_sorted = groups[order]
    starts = np.r_[0, np.flatnonzero(np.diff(g_sorted)) + 1, len(order)]
    for a, b in zip(starts[:-1], starts[1:]):
        idx = order[a:b]
        x = v[idx]
        m = len(x)
        for j in range(min(k, m)):  # the first k candles of a group: fewer than k earlier values
            w = x[:j][np.isfinite(x[:j])]
            cnt[idx[j]] = len(w)
            if len(w):
                med[idx[j]] = np.median(w)
        if m > k:  # every later candle: a full window of the k previous values, vectorised
            win = np.lib.stride_tricks.sliding_window_view(x, k)[:m - k]  # row s = x[s:s+k], the window before candle s+k
            fin = np.isfinite(win)
            cnt[idx[k:]] = fin.sum(axis=1)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)  # an all-NaN window gives NaN, as intended
                med[idx[k:]] = np.nanmedian(win, axis=1)
    return med, cnt


def rvol(v: np.ndarray, t: np.ndarray, step: int, calendar: str) -> tuple[np.ndarray, np.ndarray]:
    """(relative volume, baseline sample count). Up to 4H: v / median of the same slot of the week over the previous 20 weeks
    (slot = the candle's hour of the week; minute of the week below 1H), falling back to the same slot of the day over the previous
    20 days (weekdays only on FX calendars) while the week has fewer than 4 samples. 8H and above: the previous 20 candles.
    NaN without 4 samples."""
    v = np.asarray(v, dtype=float)
    v = np.where(v > 0, v, np.nan)  # zero volume = missing (a feed gap): no relative volume, and never part of a baseline
    n = len(v)
    need = VOLUME_RULES["min_samples"]
    if n == 0:
        return np.full(0, np.nan), np.zeros(0, dtype=np.int64)
    if step >= 28800:
        base, cnt = _prev_median(v, np.zeros(n, dtype=np.int64), SAMPLES)
    else:
        wd, hr, mi = _parts(t, calendar)
        day_slot = hr * 60 + mi if step < 3600 else hr
        week_slot = wd * (24 * 60 if step < 3600 else 24) + day_slot
        wbase, wcnt = _prev_median(v, week_slot, SAMPLES)
        vv = v.copy()
        if calendar != "continuous":
            vv[wd >= 5] = np.nan  # the day fallback compares with weekdays only (FX)
        dbase, dcnt = _prev_median(vv, day_slot, SAMPLES)
        use_week = wcnt >= need
        base = np.where(use_week, wbase, dbase)
        cnt = np.where(use_week, wcnt, np.where(dcnt >= need, dcnt, np.maximum(wcnt, dcnt)))
    ok = (cnt >= need) & np.isfinite(base) & (base > 0)
    out = np.full(n, np.nan)
    out[ok] = v[ok] / base[ok]
    return out, cnt


def _longest_run(w: np.ndarray) -> int:
    if len(w) < 2:
        return len(w)
    same = np.r_[False, w[1:] == w[:-1]]
    best = run = 1
    for s in same[1:]:
        run = run + 1 if s else 1
        best = max(best, run)
    return best


def quality(v: np.ndarray, vtype: str, i: int, rv_n: np.ndarray, window: int = VOLUME_RULES["window"]) -> VolumeQuality:
    """Is the volume at candle i trustworthy enough for VSA, VWAP, relative volume, OBV and MFI?"""
    label = VOLUME_LABELS.get(vtype, VOLUME_LABELS["none"])
    if vtype not in VOLUME_LABELS or vtype == "none" or i < 0:
        return VolumeQuality("none", VOLUME_LABELS["none"], False, "no volume from this source")
    w = np.asarray(v[max(0, i - window + 1):i + 1], dtype=float)
    good = np.isfinite(w) & (w > 0)
    if good.mean() < VOLUME_RULES["min_nonzero"]:
        return VolumeQuality(vtype, label, False, f"zero or missing volume on {100 * (1 - good.mean()):.0f}% of recent candles")
    run = _longest_run(w)
    if run >= VOLUME_RULES["max_run"]:
        return VolumeQuality(vtype, label, False, f"constant volume ({run} identical values in a row): the feed looks stuck")
    if int(rv_n[i]) < VOLUME_RULES["min_samples"]:
        return VolumeQuality(vtype, label, False,
                             f"the volume baseline needs {VOLUME_RULES['min_samples']} comparable candles (same time of the week or day), "
                             f"has {int(rv_n[i])}: the history is too short for this timeframe")
    return VolumeQuality(vtype, label, True, "")
