"""Independent cross-check of the rebuilt timeframes against Dukascopy's OWN hourly and daily candles (docs/HISTORICAL_DATA.md).

Dukascopy also publishes pre-aggregated candles: one file of hourly candles per month
({SYMBOL}/{YYYY}/{MM0}/BID_candles_hour_1.bi5, times in seconds from the month start) and one file of daily candles per year
({SYMBOL}/{YYYY}/BID_candles_day_1.bi5, seconds from the year start), same 24-byte record as the minute files. They are built by
Dukascopy from ticks, independently of our M1 -> H1 aggregation, so agreement is evidence that the rebuild is right.

Expected differences, reported rather than hidden: Dukascopy candles exist for hours with no trade (flat filler), which our clean
data never contains, and their open may be the previous close when the first minutes of the hour had no ticks.
"""
import json
import random
from datetime import datetime, timezone

import polars as pl

from app.historical.config import CLEAN, INSTRUMENTS, REPORTS
from app.historical.dukascopy import BASE, Client, decode

TOL_POINTS = 1.5  # prices are integers of `point`; allow rounding of one point


def hour_url(symbol: str, year: int, month: int, side: str = "BID") -> str:
    return f"{BASE}/{symbol}/{year}/{month - 1:02d}/{side}_candles_hour_1.bi5"


def day_url(symbol: str, year: int, side: str = "BID") -> str:
    return f"{BASE}/{symbol}/{year}/{side}_candles_day_1.bi5"


def to_frame(payload: bytes, point: float, origin: datetime) -> pl.DataFrame:
    rows = decode(payload, point)
    base = int(origin.timestamp())
    return pl.DataFrame({"ts": [datetime.fromtimestamp(base + r[0], timezone.utc) for r in rows],
                         "open": [r[1] for r in rows], "high": [r[2] for r in rows], "low": [r[3] for r in rows],
                         "close": [r[4] for r in rows], "volume": [r[5] for r in rows]},
                        schema={"ts": pl.Datetime("us", "UTC"), "open": pl.Float64, "high": pl.Float64, "low": pl.Float64,
                                "close": pl.Float64, "volume": pl.Float64})


def compare(ours: pl.DataFrame, theirs: pl.DataFrame, point: float) -> dict:
    """Match rates on candles present in both (Dukascopy filler candles, volume 0, are skipped)."""
    theirs = theirs.filter(pl.col("volume") > 0)
    j = ours.select("ts", *[pl.col(f"bid_{k}").alias(k) for k in ("open", "high", "low", "close")]).join(
        theirs, on="ts", how="inner", suffix="_dk")
    out = {"ours": ours.height, "dukascopy_traded": theirs.height, "matched_timestamps": j.height}
    tol = TOL_POINTS * point
    for k in ("open", "high", "low", "close"):
        diff = (j[k] - j[f"{k}_dk"]).abs()
        out[f"{k}_match_pct"] = round(100 * float((diff <= tol).mean()), 2) if j.height else None
        out[f"{k}_max_diff"] = float(diff.max()) if j.height else None
    return out


def cross_check(symbol: str, months: int = 24, seed: int = 7, log=print) -> dict:
    """Compare our H1 with Dukascopy hourly candles for `months` random months and our D1 with their daily candles for the same
    years. A handful of polite requests (the client paces and backs off)."""
    point = INSTRUMENTS[symbol].point
    h1 = pl.read_parquet(CLEAN / symbol / "H1" / "all.parquet")
    d1 = pl.read_parquet(CLEAN / symbol / "D1" / "all.parquet")
    first, last = h1["ts"].min(), h1["ts"].max()
    cal = [(y, m) for y in range(first.year, last.year + 1) for m in range(1, 13)
           if (y, m) > (first.year, first.month) and (y, m) < (last.year, last.month)]
    sample = sorted(random.Random(seed).sample(cal, min(months, len(cal))))
    client = Client(min_interval=3.0, log=log)
    res: dict = {"symbol": symbol, "hourly": {}, "daily": {}, "tolerance_points": TOL_POINTS}
    for y, m in sample:
        theirs = to_frame(client.fetch(hour_url(symbol, y, m)), point, datetime(y, m, 1, tzinfo=timezone.utc))
        start, end = datetime(y, m, 1, tzinfo=timezone.utc), datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
        res["hourly"][f"{y}-{m:02d}"] = compare(h1.filter(pl.col("ts").is_between(start, end, closed="left")), theirs, point)
        log(f"{symbol} H1 {y}-{m:02d}: {res['hourly'][f'{y}-{m:02d}']}")
    for y in sorted({y for y, _ in sample}):
        theirs = to_frame(client.fetch(day_url(symbol, y)), point, datetime(y, 1, 1, tzinfo=timezone.utc))
        ours = d1.filter(pl.col("ts").dt.year() == y)
        res["daily"][str(y)] = compare(ours, theirs, point)
        log(f"{symbol} D1 {y}: {res['daily'][str(y)]}")
    agg = {}
    for kind in ("hourly", "daily"):
        rows = list(res[kind].values())
        n = sum(r["matched_timestamps"] for r in rows)
        agg[kind] = {"candles_compared": n, **{f"{k}_match_pct": round(sum(r[f"{k}_match_pct"] * r["matched_timestamps"] for r in rows
                                                                        if r[f"{k}_match_pct"] is not None) / n, 2) if n else None
                                                 for k in ("open", "high", "low", "close")}}
    res["summary"] = agg
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{symbol}_dukascopy_crosscheck.json").write_text(json.dumps(res, indent=1, default=str))
    return res
