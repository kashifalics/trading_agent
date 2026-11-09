"""Point-in-time reference levels for every candle, computed once over the whole series (not inside detection chunks, whose
warm-up is too short for weekly or monthly levels):

* previous New York trading day (17:00 to 17:00), previous week (Sunday 17:00 New York to Friday close) and previous calendar month:
  high and low of the last COMPLETED period;
* the latest completed Asian (19:00-03:00 New York) and London (03:00-08:00 New York) session high and low.

For each candle the level is the one known at its close. `first_touch_*` marks the first candle of the current period whose high
(low) trades beyond that level, which is what a sweep or a break of the level is measured on.
"""
from dataclasses import dataclass

import numpy as np
import polars as pl


@dataclass
class Levels:
    pdh: np.ndarray
    pdl: np.ndarray
    pwh: np.ndarray
    pwl: np.ndarray
    pmh: np.ndarray
    pml: np.ndarray
    asia_h: np.ndarray
    asia_l: np.ndarray
    london_h: np.ndarray
    london_l: np.ndarray
    day_id: np.ndarray
    week_id: np.ndarray
    month_id: np.ndarray

    def slice(self, a: int, e: int) -> "Levels":
        return Levels(**{k: v[a:e] for k, v in self.__dict__.items()})


def _prev_period(ts: pl.Series, h: np.ndarray, lo: np.ndarray, key: pl.Expr) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    df = pl.DataFrame({"ts": ts, "h": h, "l": lo}).with_columns(key.alias("k"))
    agg = df.group_by("k", maintain_order=True).agg(pl.col("h").max(), pl.col("l").min()).with_columns(
        ph=pl.col("h").shift(1), pl_=pl.col("l").shift(1))
    j = df.select("k").join(agg.select("k", "ph", "pl_"), on="k", how="left", maintain_order="left")
    ids = df["k"].rank("dense").to_numpy().astype(np.int64)
    return j["ph"].to_numpy().astype(float), j["pl_"].to_numpy().astype(float), ids


def _last_session(ts_epoch: np.ndarray, close_epoch: np.ndarray, h: np.ndarray, lo: np.ndarray, in_sess: np.ndarray, sess_key: np.ndarray):
    """High/low of the latest session (candles flagged in_sess, grouped by sess_key) that had ended by each candle's close."""
    n = len(ts_epoch)
    out_h, out_l = np.full(n, np.nan), np.full(n, np.nan)
    if not in_sess.any():
        return out_h, out_l
    df = pl.DataFrame({"k": sess_key[in_sess], "h": h[in_sess], "l": lo[in_sess], "end": close_epoch[in_sess]})
    agg = df.group_by("k", maintain_order=True).agg(pl.col("h").max(), pl.col("l").min(), pl.col("end").max()).sort("end")
    ends = agg["end"].to_numpy()
    j = np.searchsorted(ends, close_epoch, side="right") - 1
    ok = j >= 0
    out_h[ok] = agg["h"].to_numpy()[j[ok]]
    out_l[ok] = agg["l"].to_numpy()[j[ok]]
    return out_h, out_l


def compute_levels(ts: pl.Series, close_epoch: np.ndarray, h: np.ndarray, lo: np.ndarray) -> Levels:
    """ts: candle open times (UTC datetime series); close_epoch: candle close times (epoch seconds)."""
    ny = pl.col("ts").dt.convert_time_zone("America/New_York")
    trade_day = (ny + pl.duration(hours=7)).dt.date()
    pdh, pdl, day_id = _prev_period(ts, h, lo, trade_day)
    week = (ny + pl.duration(hours=7)).dt.truncate("1w")  # trading week from Sunday 17:00 New York
    pwh, pwl, week_id = _prev_period(ts, h, lo, week)
    month = pl.col("ts").dt.truncate("1mo")
    pmh, pml, month_id = _prev_period(ts, h, lo, month)
    nyt = pl.DataFrame({"ts": ts}).select(ny.dt.hour().alias("hr"), trade_day.alias("d"))
    hr = nyt["hr"].to_numpy()
    d = nyt["d"].cast(pl.Int32).to_numpy()
    te = ts.dt.epoch("s").to_numpy().astype(np.int64)
    asia = (hr >= 19) | (hr < 3)
    london = (hr >= 3) & (hr < 8)
    ah, al = _last_session(te, close_epoch, h, lo, asia, d)
    lh, ll = _last_session(te, close_epoch, h, lo, london, d)
    return Levels(pdh, pdl, pwh, pwl, pmh, pml, ah, al, lh, ll, day_id, week_id, month_id)


def first_touch(level: np.ndarray, x: np.ndarray, period_id: np.ndarray, above: bool) -> np.ndarray:
    """True on the first candle of each period (with the same level) whose high (above=True) / low trades beyond the level."""
    beyond = (x > level) if above else (x < level)
    beyond &= np.isfinite(level)
    key = period_id.astype(np.int64) * 1_000_003 + np.nan_to_num(np.round(level * 1000)).astype(np.int64) % 1_000_003
    out = np.zeros(len(x), dtype=bool)
    idx = np.flatnonzero(beyond)
    if len(idx):
        _, first = np.unique(key[idx], return_index=True)
        out[idx[first]] = True
    return out
