"""Raw Dukascopy files -> normalized M1 -> validated M1 -> M5 ... W1, plus gaps and the coverage report (docs/HISTORICAL_DATA.md).

* Normalized M1 keeps every minute Dukascopy published, bid and ask side by side, in UTC.
* Clean M1 removes the feed's filler minutes (volume 0 and open = high = low = close: the feed was alive but no tick traded). Those are
  QUIET minutes, not gaps, and are not candles: nothing is ever forward-filled.
* A GAP is an open-market minute (FX calendar: closed Friday 17:00 to Sunday 17:00 New York, daylight saving handled; metals also
  17:00-18:00 New York daily) with no traded candle, whether the feed omitted it or only published filler. Runs of >= MATERIAL_GAP_MIN
  minutes are material and saved for research to exclude; 24-26 Dec and 1-2 Jan are reported as holidays. Coverage is measured on
  traded minutes (Dukascopy publishes filler for months before real trading starts, e.g. XAUUSD Jan-Apr 2003); feed coverage, which
  counts filler, is reported separately and never used as evidence of data.
* Higher timeframes are rebuilt from clean M1 only (open = first, high = max, low = min, close = last, volume = sum), on UTC boundaries
  (weeks start Monday 00:00, months on the 1st). Each M5 is built from M1 inside one year file; every coarser timeframe from a finer
  one whose boundaries nest in it (config.PARENT), which gives identical OHLC; verify_timeframes() proves it against direct M1
  aggregation. `n_minutes` says how many traded minutes a candle contains. D1_NY candles start at 17:00 New York instead of 00:00 UTC.
* Outliers (one-minute moves beyond OUTLIER_MOVE) are reported, not removed: flash crashes such as CHF on 2015-01-15 are real.
"""
import json
from datetime import date, datetime, timedelta, timezone

import polars as pl

from app.historical.config import (
    CLEAN,
    INSTRUMENTS,
    MATERIAL_GAP_MIN,
    NORMALIZED,
    NY_DAY_TF,
    PARENT,
    RAW,
    REPORTS,
    TIMEFRAMES,
)
from app.historical.download import SIDES
from app.historical.dukascopy import decode

OUTLIER_MOVE = {"default": 0.02, "XAUUSD": 0.03}
PRICE = ("open", "high", "low", "close")
SOURCE = "Dukascopy public datafeed (datafeed.dukascopy.com), 1-minute BID and ASK candles"
BINANCE_SOURCE = ("Binance public data archive (data.binance.vision), spot 1-minute klines (one price; bid/ask = price -/+ the $1 "
                  "half-spread cost model)")


# ---- raw -> normalized ------------------------------------------------------------------------------------------------------------
def _decode_side(symbol: str, side: str, year: int) -> pl.DataFrame:
    point = INSTRUMENTS[symbol].point
    rows = []
    for f in sorted((RAW / symbol / side / str(year)).glob("*.bi5")):
        day0 = int(datetime.fromisoformat(f.stem).replace(tzinfo=timezone.utc).timestamp())
        rows += [(day0 + t, o, h, lo, c, v) for t, o, h, lo, c, v in decode(f.read_bytes(), point)]
    p = side.lower()
    schema = {"t": pl.Int64, **{f"{p}_{k}": pl.Float64 for k in PRICE}, f"{p}_volume": pl.Float64}
    return pl.DataFrame(rows, schema=schema, orient="row")


def normalize_year(symbol: str, year: int, force: bool = False) -> int:
    out = NORMALIZED / symbol / "M1" / f"{year}.parquet"
    raw_files = [f for s in SIDES for f in (RAW / symbol / s / str(year)).glob("*.bi5")]
    if not raw_files:
        return 0
    if out.exists() and not force and out.stat().st_mtime >= max(f.stat().st_mtime for f in raw_files):
        return pl.scan_parquet(out).select(pl.len()).collect().item()
    bid, ask = _decode_side(symbol, "BID", year), _decode_side(symbol, "ASK", year)
    df = bid.join(ask, on="t", how="full", coalesce=True).sort("t")
    df = df.with_columns(pl.from_epoch("t", time_unit="s").dt.replace_time_zone("UTC").alias("ts")).drop("t")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.select("ts", *[c for c in df.columns if c != "ts"]).write_parquet(out, compression="zstd")
    return df.height


# ---- validation ---------------------------------------------------------------------------------------------------------------------
def _invalid(p: str) -> pl.Expr:
    o, h, lo, c = (pl.col(f"{p}_{k}") for k in PRICE)
    finite = pl.all_horizontal([x.is_finite() & (x > 0) for x in (o, h, lo, c)])
    return ~finite | (h < pl.max_horizontal(o, c)) | (lo > pl.min_horizontal(o, c)) | (h < lo)


def validate_year(symbol: str, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """Clean M1 for one year and the counts of what was removed or flagged."""
    n = df.height
    dup = n - df.unique("ts").height
    df = df.unique("ts", keep="first").sort("ts")
    missing_side = df.filter(pl.col("bid_close").is_null() | pl.col("ask_close").is_null()).height
    df = df.drop_nulls(["bid_close", "ask_close"])
    quiet = (pl.col("bid_volume") == 0) & (pl.col("bid_high") == pl.col("bid_low"))
    n_quiet = df.filter(quiet).height
    df = df.filter(~quiet)
    bad = _invalid("bid") | _invalid("ask") | (pl.col("ask_close") < pl.col("bid_close"))
    n_bad = df.filter(bad).height
    df = df.filter(~bad)
    lim = OUTLIER_MOVE.get(symbol, OUTLIER_MOVE["default"])
    moves = (pl.col("bid_close") / pl.col("bid_close").shift(1) - 1).abs()
    n_out = df.select((moves > lim).sum()).item() or 0
    df = df.with_columns((pl.col("ask_close") - pl.col("bid_close")).alias("spread"))
    return df, {"rows_published": n, "duplicates": dup, "one_side_missing": missing_side, "quiet_minutes": n_quiet,
                "invalid_candles": n_bad, "outlier_moves": n_out, "clean_rows": df.height}


# ---- gaps ----------------------------------------------------------------------------------------------------------------------------
def open_minutes(start: datetime, end: datetime, symbol: str) -> pl.DataFrame:
    """Every minute in [start, end) the market is scheduled open (New York rules, daylight saving included)."""
    grid = pl.DataFrame({"ts": pl.datetime_range(start, end, "1m", closed="left", time_zone="UTC", eager=True)})
    if INSTRUMENTS[symbol].calendar == "continuous":
        return grid  # a 24/7 market: every minute is scheduled open
    ny = pl.col("ts").dt.convert_time_zone("America/New_York")
    wd = ny.dt.weekday()  # Monday = 1 ... Sunday = 7
    hm = ny.dt.hour().cast(pl.Int32) * 60 + ny.dt.minute().cast(pl.Int32)  # hour is Int8: widen before multiplying
    closed = ((wd == 5) & (hm >= 17 * 60)) | (wd == 6) | ((wd == 7) & (hm < 17 * 60))
    if INSTRUMENTS[symbol].daily_break:
        closed = closed | ((hm >= 17 * 60) & (hm < 18 * 60))
    return grid.filter(~closed)


def find_gaps(symbol: str, published: pl.Series, start: datetime, end: datetime) -> tuple[pl.DataFrame, int, int]:
    """(gaps with start/minutes/material/holiday, expected open minutes, published open minutes) for [start, end)."""
    expected = open_minutes(start, end, symbol)
    present = expected.join(pl.DataFrame({"ts": published}), on="ts", how="semi").height
    absent = expected.join(pl.DataFrame({"ts": published}), on="ts", how="anti").sort("ts")
    if absent.is_empty():
        return pl.DataFrame(schema={"start": pl.Datetime("us", "UTC"), "minutes": pl.Int64, "holiday": pl.Boolean,
                                    "material": pl.Boolean}), expected.height, present
    runs = (absent.with_columns(((pl.col("ts").diff().dt.total_minutes().fill_null(0)) != 1).cum_sum().alias("run"))
            .group_by("run").agg(pl.col("ts").min().alias("start"), pl.len().alias("minutes")).sort("start"))
    holiday = ((pl.col("start").dt.month() == 12) & (pl.col("start").dt.day().is_between(24, 26))) | \
              ((pl.col("start").dt.month() == 1) & (pl.col("start").dt.day() <= 2))
    if INSTRUMENTS[symbol].calendar == "continuous":
        holiday = pl.lit(False)  # no exchange holidays: a missing run is missing data
    runs = runs.with_columns(holiday.alias("holiday")).with_columns(
        ((pl.col("minutes") >= MATERIAL_GAP_MIN) & ~pl.col("holiday")).alias("material"))
    return runs.select("start", pl.col("minutes").cast(pl.Int64), "holiday", "material"), expected.height, present


# ---- resampling ----------------------------------------------------------------------------------------------------------------------
EXTRA_SUMS = ("taker_buy_base",)  # optional per-candle sums carried through every timeframe when the source has them (Binance)


def _aggs(minutes_col: str | None, columns=()) -> list[pl.Expr]:
    """OHLC per side (first / max / min / last), summed volumes and the number of traded minutes."""
    aggs = []
    for p in ("bid", "ask"):
        aggs += [pl.col(f"{p}_open").first(), pl.col(f"{p}_high").max(), pl.col(f"{p}_low").min(), pl.col(f"{p}_close").last()]
    return aggs + [pl.col("bid_volume").sum(), pl.col("ask_volume").sum(),
                   (pl.col(minutes_col).sum() if minutes_col else pl.len()).alias("n_minutes")] + \
        [pl.col(c).sum() for c in EXTRA_SUMS if c in columns]


def resample(df: pl.DataFrame, every: str, minutes_col: str | None = None) -> pl.DataFrame:
    out = (df.sort("ts").group_by_dynamic("ts", every=every, closed="left", label="left",
                                          start_by="monday" if every == "1w" else "window").agg(_aggs(minutes_col, df.columns)))
    return out.with_columns((pl.col("ask_close") - pl.col("bid_close")).alias("spread"))


def resample_ny_day(df: pl.DataFrame, minutes_col: str | None = None) -> pl.DataFrame:
    """Trading-day candles from 17:00 New York to 17:00 the next day (daylight saving handled), labelled with their UTC start.
    `df` must have boundaries that nest in New York hours (M1 ... H1)."""
    ny = pl.col("ts").dt.convert_time_zone("America/New_York")
    day = (ny + pl.duration(hours=7)).dt.date().alias("trading_day")
    out = df.sort("ts").with_columns(day).group_by("trading_day", maintain_order=True).agg(_aggs(minutes_col, df.columns))
    start = (pl.col("trading_day").cast(pl.Datetime("us")).dt.replace_time_zone("America/New_York", ambiguous="earliest")
             - pl.duration(hours=7)).dt.convert_time_zone("UTC").alias("ts")
    return (out.with_columns(start).drop("trading_day").select("ts", pl.exclude("ts"))
            .with_columns((pl.col("ask_close") - pl.col("bid_close")).alias("spread")).sort("ts"))


def build_timeframes(m5: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Every timeframe from M5, each from its nesting parent (config.PARENT), plus the New York trading day from H1."""
    frames = {"M5": m5}
    for tf in TIMEFRAMES:
        if tf != "M5":
            frames[tf] = resample(frames[PARENT[tf]], TIMEFRAMES[tf], "n_minutes")
    frames[NY_DAY_TF] = resample_ny_day(frames["H1"], "n_minutes")
    return frames


def verify_timeframes(symbol: str, tfs: list[str] | None = None, log=print) -> dict:
    """Independent check: aggregate every timeframe straight from clean M1 and compare with the chained build, column by column.
    OHLC and minute counts must be identical; volumes (float sums in a different order) within 1e-6 relative."""
    m1 = pl.concat([pl.read_parquet(f) for f in sorted((CLEAN / symbol / "M1").glob("*.parquet"))]).sort("ts")
    out = {}
    for tf in tfs or [*TIMEFRAMES, NY_DAY_TF]:
        built = pl.read_parquet(CLEAN / symbol / tf / "all.parquet")
        direct = resample_ny_day(m1) if tf == NY_DAY_TF else resample(m1, TIMEFRAMES[tf])
        res = {"bars_built": built.height, "bars_direct": direct.height}
        if built.height == direct.height and (built["ts"] == direct["ts"]).all():
            sums = ("bid_volume", "ask_volume", *(c for c in EXTRA_SUMS if c in direct.columns))
            exact = [c for c in direct.columns if c not in ("ts", *sums)]
            res["mismatched_values"] = {c: int((built[c] != direct[c]).sum()) for c in exact if (built[c] != direct[c]).any()}
            for c in sums:
                rel = ((built[c] - direct[c]).abs() / direct[c].abs().clip(lower_bound=1e-9))
                if (rel > 1e-6).any():
                    res["mismatched_values"][c] = int((rel > 1e-6).sum())
            res["identical"] = not res["mismatched_values"]
        else:
            res["identical"] = False
        out[tf] = res
        log(f"{symbol} {tf}: {'identical to direct M1 aggregation' if res['identical'] else 'MISMATCH ' + str(res)}")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{symbol}_timeframe_check.json").write_text(json.dumps(out, indent=1))
    return out


# ---- whole pipeline -----------------------------------------------------------------------------------------------------------------
def build_binance(symbol: str, log=print) -> dict:
    """Clean M1 from the Binance archive (binance_archive.write_clean_m1), then the same gap map, timeframes and coverage."""
    from app.historical import binance_archive

    per_year = binance_archive.write_clean_m1(symbol, log=log)
    stats, gaps, m5 = [], [], []
    expected = present = 0
    for y, st in per_year.items():
        clean = pl.read_parquet(CLEAN / symbol / "M1" / f"{y}.parquet")
        lo = max(datetime(y, 1, 1, tzinfo=timezone.utc), clean["ts"].min())
        hi = min(datetime(y + 1, 1, 1, tzinfo=timezone.utc), clean["ts"].max() + timedelta(minutes=1))
        g, e, p = find_gaps(symbol, clean["ts"], lo, hi)
        st["feed_open_minutes"], st["traded_open_minutes"], st["expected_open_minutes"] = p, p, e
        expected, present = expected + e, present + p
        stats.append(st)
        gaps.append(g)
        m5.append(resample(clean, "5m"))
        log(f"{symbol} {y}: {st['clean_rows']:,} clean M1, {g.filter(pl.col('material')).height} material gaps")
    frames = build_timeframes(pl.concat(m5).sort("ts"))
    for tf, df in frames.items():
        path = CLEAN / symbol / tf / "all.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path, compression="zstd")
    gap_df = pl.concat(gaps) if gaps else pl.DataFrame()
    gap_df.write_parquet(CLEAN / symbol / "gaps.parquet")
    return coverage(symbol, stats, gap_df, expected, present)


def build(symbol: str, log=print, force: bool = False) -> dict:
    if INSTRUMENTS[symbol].source == "binance":
        return build_binance(symbol, log)
    years = sorted(int(p.name) for p in (RAW / symbol / "BID").glob("*") if p.is_dir())
    if not years:
        raise RuntimeError(f"{symbol}: nothing downloaded yet")
    stats, gaps, m5 = [], [], []
    expected = present = 0
    for y in years:
        normalize_year(symbol, y, force)
        npath = NORMALIZED / symbol / "M1" / f"{y}.parquet"
        if not npath.exists():
            continue
        raw = pl.read_parquet(npath)
        clean, st = validate_year(symbol, raw)
        st["year"] = y
        stats.append(st)
        cpath = CLEAN / symbol / "M1" / f"{y}.parquet"
        cpath.parent.mkdir(parents=True, exist_ok=True)
        clean.write_parquet(cpath, compression="zstd")
        lo = max(datetime(y, 1, 1, tzinfo=timezone.utc), raw["ts"].min().replace(second=0, microsecond=0))
        hi = min(datetime(y + 1, 1, 1, tzinfo=timezone.utc), raw["ts"].max() + timedelta(minutes=1))
        g, e, p = find_gaps(symbol, clean["ts"], lo, hi)
        feed = open_minutes(lo, hi, symbol).join(raw.select("ts"), on="ts", how="semi").height
        st["feed_open_minutes"], st["traded_open_minutes"], st["expected_open_minutes"] = feed, p, e
        expected, present = expected + e, present + p
        gaps.append(g)
        m5.append(resample(clean, "5m"))
        log(f"{symbol} {y}: {st['clean_rows']:,} clean M1, {st['quiet_minutes']:,} quiet, {st['invalid_candles']} invalid, "
            f"{g.filter(pl.col('material')).height} material gaps")
    frames = build_timeframes(pl.concat(m5).sort("ts"))
    for tf, df in frames.items():
        path = CLEAN / symbol / tf / "all.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path, compression="zstd")
    gap_df = pl.concat(gaps) if gaps else pl.DataFrame()
    (CLEAN / symbol).mkdir(parents=True, exist_ok=True)
    gap_df.write_parquet(CLEAN / symbol / "gaps.parquet")
    return coverage(symbol, stats, gap_df, expected, present)


def coverage(symbol: str, stats: list[dict], gaps: pl.DataFrame, expected: int, present: int) -> dict:
    tfs = {}
    for tf in ("M1", *TIMEFRAMES, NY_DAY_TF):
        files = sorted((CLEAN / symbol / tf).glob("*.parquet"))
        if not files:
            continue
        lf = pl.scan_parquet(files)
        r = lf.select(pl.col("ts").min().alias("first"), pl.col("ts").max().alias("last"), pl.len().alias("bars")).collect().row(0)
        tfs[tf] = {"earliest": r[0].isoformat(), "latest": r[1].isoformat(), "bars": r[2]}
    mat = gaps.filter(pl.col("material")) if not gaps.is_empty() else gaps
    raw_bytes = sum(f.stat().st_size for f in (RAW / symbol).rglob("*.bi5"))
    tot = {k: sum(s[k] for s in stats) for k in ("rows_published", "duplicates", "one_side_missing", "quiet_minutes",
                                                     "invalid_candles", "outlier_moves", "clean_rows")}
    start = json.loads((RAW / symbol / "start.json").read_text()) if (RAW / symbol / "start.json").exists() else {}
    binance = INSTRUMENTS[symbol].source == "binance"
    rep = {"symbol": symbol, "source": BINANCE_SOURCE if binance else SOURCE, "bid_ask": not binance, "timezone": "UTC (candle open time); sessions computed in New York time",
           "first_data_probe": start.get("probe_hit"), "timeframes": tfs, "raw_files_bytes": raw_bytes, **tot,
           "expected_open_minutes": expected, "traded_open_minutes": present,
           "coverage_pct": round(100 * present / expected, 2) if expected else None,
           "feed_coverage_pct": round(100 * sum(s.get("feed_open_minutes", 0) for s in stats) / expected, 2) if expected else None,
           "first_traded_minute": tfs.get("M1", {}).get("earliest"),
           "material_gaps": mat.height if not mat.is_empty() else 0,
           "material_gap_minutes": int(mat["minutes"].sum()) if not mat.is_empty() else 0,
           "largest_gaps": [{"start": r["start"].isoformat(), "minutes": r["minutes"]} for r in
                            (mat.sort("minutes", descending=True).head(5).to_dicts() if not mat.is_empty() else [])],
           "per_year": stats, "built_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{symbol}_coverage.json").write_text(json.dumps(rep, indent=1, default=str))
    return rep


def report_markdown(symbols: list[str]) -> str:
    lines = ["# Historical data coverage", "", f"Source: {SOURCE}. Times in UTC. Generated {date.today().isoformat()}.", "",
             "| Instrument | Timeframe | Earliest | Latest | Bars | Missing (M1: material gaps / minutes) |", "|---|---|---|---|---:|---|"]
    totals = {"bars": 0, "bytes": 0}
    extra = []
    for s in symbols:
        p = REPORTS / f"{s}_coverage.json"
        if not p.exists():
            lines.append(f"| {s} | — | not downloaded | | | |")
            continue
        r = json.loads(p.read_text())
        totals["bytes"] += r["raw_files_bytes"]
        for tf, v in r["timeframes"].items():
            totals["bars"] += v["bars"]
            miss = f"{r['material_gaps']} / {r['material_gap_minutes']:,}" if tf == "M1" else "rebuilt from M1"
            lines.append(f"| {s} | {tf} | {v['earliest'][:10]} | {v['latest'][:16]} | {v['bars']:,} | {miss} |")
        extra.append(f"| {s} | {(r.get('first_traded_minute') or '')[:16]} | {r['coverage_pct']}% | {r.get('feed_coverage_pct')}% | {r['rows_published']:,} | {r['quiet_minutes']:,} | {r['duplicates']} | "
                     f"{r['invalid_candles']} | {r['outlier_moves']} | {r['one_side_missing']} |")
    lines += ["", f"Total bars across timeframes: {totals['bars']:,}. Raw download size: {totals['bytes'] / 1e9:.2f} GB. Bid and ask: both.",
              "", "| Instrument | First traded minute | Traded coverage | Feed coverage (incl. filler) | M1 published | Quiet minutes (no ticks, removed) | "
              "Duplicates | Invalid | Outlier moves (kept) | One side missing |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|", *extra, "",
              "Traded coverage = minutes with at least one tick / minutes the market was scheduled open (FX: Friday 17:00 to Sunday 17:00 New York closed; "
              "XAUUSD also 17:00-18:00 New York daily). Material gap = 30+ consecutive scheduled-open minutes missing from the feed, "
              "excluding 24-26 Dec and 1-2 Jan."]
    return "\n".join(lines)
