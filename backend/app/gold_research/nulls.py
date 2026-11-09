"""Null worlds with no edge, used to prove the research pipeline does not invent one (TEST AND CALIBRATION DATA ONLY).

* brownian_m1: synthetic 1-minute bid/ask candles whose high, low and close come from a real path inside each minute, so candles
  of every timeframe aggregated from them are internally consistent. A pattern study on this must find edges of about zero.
* sign_flip: the REAL M1 history with each minute's move flipped up or down at random (log space, wicks mirrored with it). It
  keeps gold's volatility, its time-of-day and weekday rhythm and its gaps, and destroys any directional predictability.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl

from app.historical.store import M1


def brownian_m1(start: datetime, days: int, seed: int = 0, price: float = 1800.0, vol: float = 0.12, spread: float = 0.30,
                point: float = 1e-3, substeps: int = 8, weekend_gap: float = 1.5) -> pl.DataFrame:
    """Clean-M1-shaped frame (ts, bid_*, ask_*, volumes, spread) for weekdays only, Monday 00:00 to Friday 21:00 UTC."""
    rng = np.random.default_rng(seed)
    ts_list = []
    for k in range(days):
        d = start + timedelta(days=k)
        if d.weekday() >= 5:
            continue
        mins = 21 * 60 if d.weekday() == 4 else 1440
        base = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())
        ts_list.append(base + 60 * np.arange(mins))
    ts = np.concatenate(ts_list)
    n = len(ts)
    steps = rng.normal(0, vol / np.sqrt(substeps), (n, substeps))
    gaps = np.r_[0, np.diff(ts) > 60] * rng.normal(0, weekend_gap, n)
    path = np.cumsum(steps, axis=1)
    o = price + np.cumsum(path[:, -1] + gaps) - path[:, -1]
    c = o + path[:, -1]
    h = o + np.maximum(path.max(1), 0)
    lo = o + np.minimum(path.min(1), 0)
    rnd = lambda x: np.round(x / point) * point  # noqa: E731
    o, h, lo, c = rnd(o), rnd(h), rnd(lo), rnd(c)
    df = pl.DataFrame({"ts": pl.Series(ts * 1_000_000).cast(pl.Datetime("us", "UTC")), "bid_open": o, "bid_high": h, "bid_low": lo,
                       "bid_close": c, "bid_volume": np.ones(n), "ask_open": o + spread, "ask_high": h + spread, "ask_low": lo + spread,
                       "ask_close": c + spread, "ask_volume": np.ones(n)})
    return df.with_columns(spread=pl.col("ask_close") - pl.col("bid_close"))


def m1_from_frame(df: pl.DataFrame, point: float = 1e-3) -> M1:
    ts = df["ts"].dt.epoch("s").to_numpy().astype(np.int64)
    sides = {s: np.stack([np.rint(df[f"{s}_{k}"].to_numpy() / point) for k in ("open", "high", "low", "close")], 1).astype(np.int32)
             for s in ("bid", "ask")}
    return M1(ts, sides["bid"], sides["ask"], point)


def sign_flip(df: pl.DataFrame, seed: int = 0) -> pl.DataFrame:
    """Real minutes with random-sign moves: log-return open->close, the wicks and the gap to the previous close are kept as they
    are (gap sign also randomised), the spread is unchanged."""
    rng = np.random.default_rng(seed)
    bo, bh, bl, bc = (np.log(df[f"bid_{k}"].to_numpy()) for k in ("open", "high", "low", "close"))
    n = len(bo)
    s = rng.choice([-1.0, 1.0], n)
    g = rng.choice([-1.0, 1.0], n)
    gap = np.r_[0.0, bo[1:] - bc[:-1]] * g
    move = (bc - bo) * s
    up = np.where(s > 0, bh - bo, bo - bl)
    dn = np.where(s > 0, bo - bl, bh - bo)
    o = bo[0] + np.cumsum(gap + np.r_[0.0, move[:-1]])
    spread = (df["ask_close"] - df["bid_close"]).to_numpy()
    out = {"ts": df["ts"], "bid_open": np.exp(o), "bid_high": np.exp(o + up), "bid_low": np.exp(o - dn), "bid_close": np.exp(o + move)}
    for k in ("open", "high", "low", "close"):
        out[f"ask_{k}"] = out[f"bid_{k}"] + spread
    return pl.DataFrame({**out, "bid_volume": df["bid_volume"], "ask_volume": df["ask_volume"]}).with_columns(
        spread=pl.col("ask_close") - pl.col("bid_close"))
