"""Timeframe synchronization: which candle of every timeframe was COMPLETE at a given decision time (brief Part 3).

A candle labelled with its open time t covers [t, close) and is usable only at or after its close: intraday and daily candles close
t + their length, weeks 7 days later, months at the next 1st (calendar-aware). A decision taken at the close of an M5 candle at time
T may use a higher-timeframe candle only if its close <= T. Everything here works on int64 epoch seconds and numpy searchsorted,
so millions of decision times are aligned at once.
"""
import numpy as np
import polars as pl

from app.historical.config import TF_SECONDS


def epoch(ts: pl.Series) -> np.ndarray:
    return ts.dt.epoch("s").to_numpy().astype(np.int64)


def bar_close(tf: str, open_ts: np.ndarray) -> np.ndarray:
    """Close time (epoch seconds) of candles opened at open_ts."""
    if tf == "MN1":
        m = open_ts.astype("datetime64[s]").astype("datetime64[M]")
        return (m + 1).astype("datetime64[s]").astype(np.int64)
    return open_ts + TF_SECONDS[tf]


def last_closed(close_ts: np.ndarray, t: np.ndarray | int) -> np.ndarray:
    """Index of the last candle whose close <= t (-1 if none). close_ts must be sorted."""
    return np.searchsorted(close_ts, t, side="right") - 1


class Frame:
    """One timeframe's candles as arrays, with close times for alignment."""

    def __init__(self, df: pl.DataFrame, tf: str):
        self.tf = tf
        self.df = df.sort("ts")
        self.open_ts = epoch(self.df["ts"])
        self.close_ts = bar_close(tf, self.open_ts)
        self.h, self.l = self.df["bid_high"].to_numpy(), self.df["bid_low"].to_numpy()  # noqa: E741
        self.o, self.c = self.df["bid_open"].to_numpy(), self.df["bid_close"].to_numpy()

    def __len__(self) -> int:
        return len(self.open_ts)

    def available(self, t: np.ndarray | int) -> np.ndarray:
        return last_closed(self.close_ts, t)


def previous_period_levels(frame: Frame, t: np.ndarray) -> dict[str, np.ndarray]:
    """High / low / close of the last COMPLETED candle of `frame` at each decision time t (e.g. previous day high/low with D1,
    previous week with W1, previous month with MN1). NaN where no candle had closed yet."""
    i = frame.available(t)
    ok = i >= 0
    j = np.where(ok, i, 0)
    return {k: np.where(ok, arr[j], np.nan) for k, arr in (("high", frame.h), ("low", frame.l), ("close", frame.c))} | {
        "close_ts": np.where(ok, frame.close_ts[j], -1)}
