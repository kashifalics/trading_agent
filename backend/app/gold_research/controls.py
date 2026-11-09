"""Matched random controls: what the same kind of trade earned when placed WITHOUT the pattern (docs/PATTERN_STUDY.md).

A shared pool of random trades is simulated once per timeframe and segment with exactly the same engine as the pattern trades:
  * market controls: entry at the next open after a random candle, stop at fixed ATR distances (the centres of RISK_EDGES);
  * limit controls: a fake zone below (long) / above (short) the random candle's close at fixed ATR distances and widths, with the
    same limit fill, cancel rule, waiting time and stop buffer as zone patterns.
Each pattern trade is compared with the mean of the controls in its stratum: direction, entry type, risk (or zone distance and
width) bucket, New York session of the fill, volatility bucket and period (year and split segment). Sparse strata back off to
coarser ones (session dropped, then volatility, then year), and the level used is recorded. Removing gold's long uptrend and its
volatility / time-of-day structure is the point: a pattern only has an edge if it beats this.
"""
import numpy as np
import polars as pl

from app.gold_research import sim

RISK_EDGES = np.array([0.0, 0.5, 0.75, 1.0, 1.5, 2.5, np.inf])
RISK_CENTRES = np.array([0.375, 0.625, 0.875, 1.25, 2.0, 3.0])
DIST_EDGES = np.array([-np.inf, 0.25, 0.75, 1.5, np.inf])
DIST_CENTRES = np.array([0.1, 0.5, 1.0, 2.0])
WIDTH_EDGES = np.array([0.0, 0.35, 0.75, 1.5, np.inf])
WIDTH_CENTRES = np.array([0.25, 0.5, 1.0, 2.0])
STOP_BUFFER_ATR = 0.1
ZONE_WAIT = 50
MIN_CELL = 30
LEVELS = (("period", "vol", "session"), ("period", "vol"), ("period",), ("segment",))


def bucket(x: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges, x, side="right") - 1, 0, len(edges) - 2)


def session_ny(ts: np.ndarray) -> np.ndarray:
    """New York-time session of epoch seconds (daylight saving handled): asia 19-03, london 03-08, overlap 08-12, new_york 12-17,
    rollover 17-19."""
    s = pl.Series((ts.astype(np.int64) * 1_000_000).astype("datetime64[us]")).dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York").dt.hour().to_numpy()
    return np.select([(s >= 3) & (s < 8), (s >= 8) & (s < 12), (s >= 12) & (s < 17), (s >= 17) & (s < 19)],
                     ["london", "overlap", "new_york", "rollover"], "asia")


def vol_bucket(atr: np.ndarray) -> np.ndarray:
    """Scale-free volatility: ATR versus its own trailing 500-candle median (low < 0.8, high > 1.25)."""
    med = pl.Series(atr).rolling_median(500, min_periods=50).to_numpy()
    ratio = atr / med
    return np.select([ratio < 0.8, ratio > 1.25], ["low", "high"], "normal")


def period_key(ts: np.ndarray, segment: str) -> np.ndarray:
    years = ts.astype("datetime64[s]").astype("datetime64[Y]").astype(np.int64) + 1970
    return np.char.add(np.char.add(years.astype(str), ":"), segment)


def pool(S: sim.Series, atr: np.ndarray, vol: np.ndarray, bars: np.ndarray, segment: str) -> pl.DataFrame:
    """Simulate the control pool for random signal candles `bars` (all inside one segment)."""
    frames = []
    nb = len(bars)
    a = atr[bars]
    eb = bars + 1
    ok = eb < S.n
    for d in (1, -1):
        px = np.where(d > 0, S.ao[np.minimum(eb, S.n - 1)], S.bo[np.minimum(eb, S.n - 1)])
        for k, rc in enumerate(RISK_CENTRES):
            o = sim.Orders(d=np.full(nb, d), entry_bar=np.where(ok, eb, -1), stop=px - d * rc * a, atr=a)
            frames.append(_frame(S, sim.simulate(S, o), bars, "market", d, risk_b=k, dist_b=-1, width_b=-1, vol=vol, segment=segment))
        close = S.bc[bars]
        for i, dc in enumerate(DIST_CENTRES):
            for j, wc in enumerate(WIDTH_CENTRES):
                near = close - d * dc * a
                far = near - d * wc * a
                o = sim.Orders(d=np.full(nb, d), entry_bar=np.where(ok, eb, -1), stop=far - d * STOP_BUFFER_ATR * a, atr=a,
                               limit=near, cancel=far, wait=ZONE_WAIT)
                frames.append(_frame(S, sim.simulate(S, o), bars, "limit", d, risk_b=-1, dist_b=i, width_b=j, vol=vol, segment=segment))
    return pl.concat(frames)


def _frame(S, res, bars, entry, d, risk_b, dist_b, width_b, vol, segment) -> pl.DataFrame:
    keep = res["simulated"]
    ts = np.where(res["fill_ts"] > 0, res["fill_ts"], S.t[bars])[keep]
    cols = {"entry": entry, "direction": np.int8(d), "risk_b": np.int8(risk_b), "dist_b": np.int8(dist_b), "width_b": np.int8(width_b),
            "session": session_ny(ts), "vol": vol[bars][keep], "period": period_key(ts, segment), "segment": segment,
            "stop_r": res["stop_r"][keep].astype(np.float32)}
    for h in sim.HOLDS:
        for c in (f"mfe_{h}", f"mfe_opt_{h}", f"stopped_{h}", f"end_r_{h}"):
            cols[c] = res[c][keep]
    return pl.DataFrame(cols)


def expectation(trades: pl.DataFrame, controls: pl.DataFrame, r_col: str) -> pl.DataFrame:
    """Per trade: control mean, variance and count in its stratum for the R column `r_col` (present in both frames), using the
    finest level with at least MIN_CELL controls. Adds ctrl_mean, ctrl_var, ctrl_n, ctrl_level."""
    base = ["entry", "direction", "risk_b", "dist_b", "width_b"]
    out = trades.with_row_index("_row").with_columns(ctrl_mean=pl.lit(None, pl.Float64), ctrl_var=pl.lit(None, pl.Float64),
                                                     ctrl_n=pl.lit(None, pl.UInt32), ctrl_level=pl.lit(None, pl.Int8),
                                                     ctrl_cell=pl.lit(None, pl.Utf8))
    for lvl, extra in enumerate(LEVELS):
        keys = base + list(extra)
        cells = (controls.filter(pl.col(r_col).is_not_nan()).group_by(keys)
                 .agg(pl.col(r_col).mean().alias("m"), pl.col(r_col).var().alias("v"), pl.len().alias("n"))
                 .filter(pl.col("n") >= MIN_CELL)
                 .with_columns(pl.concat_str([pl.lit(str(lvl)), *[pl.col(k).cast(pl.Utf8) for k in keys]], separator="|").alias("c")))
        todo = out.filter(pl.col("ctrl_mean").is_null()).select("_row", *keys).join(cells, on=keys, how="inner")
        if todo.height == 0:
            continue
        out = out.join(todo.select("_row", "m", "v", "n", "c"), on="_row", how="left").with_columns(
            ctrl_mean=pl.coalesce("ctrl_mean", "m"), ctrl_var=pl.coalesce("ctrl_var", "v"),
            ctrl_n=pl.coalesce("ctrl_n", pl.col("n").cast(pl.UInt32)),
            ctrl_level=pl.coalesce("ctrl_level", pl.when(pl.col("m").is_not_null()).then(pl.lit(lvl, pl.Int8))),
            ctrl_cell=pl.coalesce("ctrl_cell", "c")).drop("m", "v", "n", "c")
    return out.drop("_row")
