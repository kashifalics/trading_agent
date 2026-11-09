"""Data-quality report for one instrument (brief Part 2): what the data is, how complete it is, and what was removed and why.

Everything is measured from the files on disk. Inputs: raw Dukascopy files, clean M1, the build's coverage JSON, the timeframe
verification and the Dukascopy cross-check (when they have been run). Output: docs/reports/{SYMBOL}_DATA_QUALITY.md and a SHA-256
manifest of every raw file (reports/{SYMBOL}_raw_manifest.txt) so later research can prove which bytes it used.
"""
import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.historical.build import SOURCE
from app.historical.config import (
    CLEAN,
    INSTRUMENTS,
    NORMALIZED,
    RAW,
    REPO_ROOT,
    REPORTS,
)


def raw_manifest(symbol: str) -> dict:
    """SHA-256 of every raw file (sorted by path) and one digest over the whole list."""
    lines, total, n_none = [], 0, 0
    for f in sorted((RAW / symbol).rglob("*")):
        if not f.is_file() or f.suffix not in (".bi5", ".none"):
            continue
        b = f.read_bytes()
        total += len(b)
        n_none += f.suffix == ".none"
        lines.append(f"{hashlib.sha256(b).hexdigest()}  {len(b)}  {f.relative_to(RAW).as_posix()}")
    text = "\n".join(lines) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{symbol}_raw_manifest.txt").write_text(text, encoding="utf8")
    return {"files": len(lines), "empty_day_markers": n_none, "bytes": total, "sha256": hashlib.sha256(text.encode()).hexdigest()}


def _dir_bytes(p) -> int:
    return sum(f.stat().st_size for f in p.rglob("*.parquet")) if p.exists() else 0


def m1_checks(symbol: str) -> dict:
    """Checks on the clean M1 actually used for research (after the build removed duplicates, filler and invalid candles)."""
    point = INSTRUMENTS[symbol].point
    years, out = [], {"rows": 0, "not_increasing": 0, "not_whole_minute": 0, "ohlc_violations": 0, "non_positive_or_nan": 0,
                      "off_point_grid": 0, "zero_volume_traded_minutes": 0, "negative_spread": 0}
    step_counts: dict[str, int] = {}
    last_ts = None
    for f in sorted((CLEAN / symbol / "M1").glob("*.parquet")):
        df = pl.read_parquet(f)
        ts = df["ts"]
        out["rows"] += df.height
        d = ts.diff().dt.total_seconds().drop_nulls()
        out["not_increasing"] += int((d <= 0).sum()) + int(last_ts is not None and ts[0] <= last_ts)
        last_ts = ts[-1]
        out["not_whole_minute"] += int((ts.dt.second() != 0).sum())
        for p in ("bid", "ask"):
            o, h, lo, c = (df[f"{p}_{k}"] for k in ("open", "high", "low", "close"))
            out["ohlc_violations"] += int(((h < o) | (h < c) | (h < lo) | (lo > o) | (lo > c)).sum())
            out["non_positive_or_nan"] += int(sum(((x <= 0) | x.is_nan()).sum() for x in (o, h, lo, c)))
            grid = np.abs(np.stack([x.to_numpy() for x in (o, h, lo, c)]) / point)
            out["off_point_grid"] += int((np.abs(grid - np.round(grid)) > 1e-4).sum())
        out["zero_volume_traded_minutes"] += int((df["bid_volume"] == 0).sum())
        out["negative_spread"] += int((df["spread"] < 0).sum())
        sec = d.to_numpy()
        for name, mask in (("1 min", sec == 60), ("2-29 min", (sec > 60) & (sec < 1800)), ("30 min - 2 h", (sec >= 1800) & (sec < 7200)),
                           ("2 h - 3 days", (sec >= 7200) & (sec < 259200)), ("3 days +", sec >= 259200)):
            step_counts[name] = step_counts.get(name, 0) + int(mask.sum())
        sp = df["spread"]
        years.append({"year": int(ts[0].year), "rows": df.height, "first": ts[0].isoformat(), "last": ts[-1].isoformat(),
                      "price_min": float(df["bid_low"].min()), "price_max": float(df["bid_high"].max()),
                      "spread_median": float(sp.median()), "spread_p95": float(sp.quantile(0.95)), "spread_max": float(sp.max()),
                      "spread_bps_median": float((sp / df["bid_close"]).median() * 1e4)})
    out["interval_between_traded_minutes"] = step_counts
    out["years"] = years
    return out


def closure_vs_missing(symbol: str, cov: dict) -> dict:
    """Split time without candles into scheduled closures (calendar) and missing data (gaps inside scheduled-open time)."""
    gaps = pl.read_parquet(CLEAN / symbol / "gaps.parquet") if (CLEAN / symbol / "gaps.parquet").exists() else pl.DataFrame()
    first = datetime.fromisoformat(cov["first_traded_minute"])
    last = datetime.fromisoformat(cov["timeframes"]["M1"]["latest"])
    total_min = int((last - first).total_seconds() // 60) + 1
    expected = cov["expected_open_minutes"]
    out = {"calendar_minutes_in_span": total_min, "scheduled_open_minutes": expected,
           "scheduled_closed_minutes_in_span": total_min - expected,
           "traded_open_minutes": cov["traded_open_minutes"], "missing_open_minutes": expected - cov["traded_open_minutes"]}
    if not gaps.is_empty():
        for name, f in (("material (30+ min, not holiday)", pl.col("material")), ("holiday (24-26 Dec, 1-2 Jan)", pl.col("holiday")),
                        ("short (<30 min)", (pl.col("minutes") < 30) & ~pl.col("holiday"))):
            g = gaps.filter(f)
            out[name] = {"count": g.height, "minutes": int(g["minutes"].sum()) if g.height else 0}
    return out


def report(symbol: str, log=print) -> str:
    cov = json.loads((REPORTS / f"{symbol}_coverage.json").read_text())
    log(f"{symbol}: hashing raw files")
    man = raw_manifest(symbol)
    log(f"{symbol}: checking clean M1")
    chk = m1_checks(symbol)
    cl = closure_vs_missing(symbol, cov)
    tfc = json.loads((REPORTS / f"{symbol}_timeframe_check.json").read_text()) if (REPORTS / f"{symbol}_timeframe_check.json").exists() else None
    xc = json.loads((REPORTS / f"{symbol}_dukascopy_crosscheck.json").read_text()) if (REPORTS / f"{symbol}_dukascopy_crosscheck.json").exists() else None
    pt = INSTRUMENTS[symbol].point
    L = [f"# {symbol} data-quality report", "",
         f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m app.historical quality`. Every number is measured from the "
         "files on disk._", "",
         "## What the data is", "",
         "| Item | Value |", "|---|---|",
         f"| Source | {SOURCE} |",
         "| Price type | **Bid and ask**, separately, for every minute (not midpoint). Research uses bid candles for patterns, ask for long entries and short exits |",
         f"| Price precision | integer multiples of {pt:g} (Dukascopy stores integer points); {chk['off_point_grid']:,} values off that grid |",
         "| Timestamps | candle OPEN time, UTC, whole minutes. Sessions are computed in New York time with daylight saving |",
         "| Volume | Dukascopy's own per-minute traded volume on its feed (not exchange volume, not tick count). Summed when aggregating |",
         "| Raw format | one LZMA-compressed binary file per UTC day and side (24-byte records); kept byte-for-byte, never modified |",
         f"| Raw files | {man['files']:,} ({man['empty_day_markers']:,} empty-day markers), {man['bytes'] / 1e6:,.0f} MB. SHA-256 of the manifest: `{man['sha256']}` |",
         f"| Processed | normalized M1 {_dir_bytes(NORMALIZED / symbol) / 1e6:,.0f} MB, clean data (all timeframes) {_dir_bytes(CLEAN / symbol) / 1e6:,.0f} MB (Parquet, zstd) |",
         f"| First traded minute | {cov['first_traded_minute']} (Dukascopy publishes flat filler before this; not counted as data) |",
         f"| Last minute | {cov['timeframes']['M1']['latest']} |",
         f"| Clean M1 candles | {chk['rows']:,} |", "",
         "## Validation of the clean M1", "",
         "| Check | Result |", "|---|---|",
         f"| Timestamps strictly increasing | {'yes' if chk['not_increasing'] == 0 else str(chk['not_increasing']) + ' violations'} |",
         f"| Whole-minute timestamps | {'yes' if chk['not_whole_minute'] == 0 else str(chk['not_whole_minute']) + ' violations'} |",
         f"| High >= open, close, low and low <= open, close (bid and ask) | {chk['ohlc_violations']:,} violations |",
         f"| Positive, finite prices | {chk['non_positive_or_nan']:,} violations |",
         f"| Ask >= bid | {chk['negative_spread']:,} violations |",
         f"| Duplicate timestamps in the feed (removed by the build) | {cov['duplicates']:,} |",
         f"| Minutes with only one side (removed) | {cov['one_side_missing']:,} |",
         f"| Invalid candles (removed) | {cov['invalid_candles']:,} |",
         f"| Filler minutes: feed alive, no tick (removed, never filled) | {cov['quiet_minutes']:,} |",
         f"| One-minute moves above {3 if symbol == 'XAUUSD' else 2}% (kept: real events) | {cov['outlier_moves']:,} |",
         f"| Traded minutes with zero reported volume | {chk['zero_volume_traded_minutes']:,} |", "",
         "## Market closures versus missing data", "",
         "Scheduled closures: Friday 17:00 to Sunday 17:00 New York, and for gold also 17:00-18:00 New York every day. Missing data = "
         "scheduled-open minutes without a traded candle. Nothing is fabricated to fill either.", "",
         "| Measure | Value |", "|---|---|",
         f"| Scheduled-open minutes since the first traded minute | {cl['scheduled_open_minutes']:,} |",
         f"| Of which traded (have a candle) | {cl['traded_open_minutes']:,} ({cov['coverage_pct']}%) |",
         f"| Missing | {cl['missing_open_minutes']:,} |",
         f"| Scheduled-closed minutes in the same span (weekends, daily metals break) | {cl['scheduled_closed_minutes_in_span']:,} |"]
    for k in ("material (30+ min, not holiday)", "holiday (24-26 Dec, 1-2 Jan)", "short (<30 min)"):
        if k in cl:
            L.append(f"| Missing runs: {k} | {cl[k]['count']:,} runs, {cl[k]['minutes']:,} minutes |")
    L += ["", "Material gaps are saved in `clean/{SYMBOL}/gaps.parquet`; research excludes trades whose window crosses one.", "",
          "| Time between consecutive traded minutes | Count |", "|---|---|",
          *[f"| {k} | {v:,} |" for k, v in chk["interval_between_traded_minutes"].items()], "",
          "## Timeframes", "",
          "All timeframes are rebuilt from clean M1 (open first, high max, low min, close last, volume summed) on UTC boundaries; "
          "D1_NY candles start at 17:00 New York.", "",
          "| TF | Earliest | Latest | Bars | Identical to direct M1 aggregation |", "|---|---|---|---|---|"]
    for tf, v in cov["timeframes"].items():
        ident = "-" if not tfc or tf not in tfc else ("yes" if tfc[tf]["identical"] else f"NO: {tfc[tf]}")
        L.append(f"| {tf} | {v['earliest'][:16]} | {v['latest'][:16]} | {v['bars']:,} | {ident} |")
    if xc:
        s = xc["summary"]
        L += ["", "## Cross-check against Dukascopy's own hourly and daily candles", "",
              f"Independent candles built by Dukascopy from ticks, compared on the timestamps both have (tolerance {xc['tolerance_points']} points). "
              "Opens can differ when the first minutes of a period had no trade (their open is then the previous close).", "",
              "| Candles | Compared | Open match | High match | Low match | Close match |", "|---|---|---|---|---|---|"]
        for kind in ("hourly", "daily"):
            a = s[kind]
            L.append(f"| {kind} | {a['candles_compared']:,} | {a['open_match_pct']}% | {a['high_match_pct']}% | {a['low_match_pct']}% | {a['close_match_pct']}% |")
    L += ["", "## Per year", "", "| Year | Clean M1 | Bid range | Median spread | 95th pct spread | Max spread | Median spread (bp) |",
          "|---|---|---|---|---|---|---|"]
    L += [f"| {y['year']} | {y['rows']:,} | {y['price_min']:,.2f} - {y['price_max']:,.2f} | {y['spread_median']:.3f} | {y['spread_p95']:.3f} | "
          f"{y['spread_max']:.2f} | {y['spread_bps_median']:.2f} |" for y in chk["years"]]
    L += ["", "## Limitations", "",
          "* Dukascopy is one liquidity provider's feed, not a consolidated market; other brokers' prices and spreads differ slightly.",
          "* Volume is Dukascopy's own, useful for relative comparisons only.",
          "* Spreads widen sharply around the daily 17:00 New York rollover and on thin holidays; research reports results with a "
          "capped rollover spread as well as the raw spread.",
          "* No news calendar is available, so news-driven moves are not labelled."]
    md = "\n".join(L) + "\n"
    doc = REPO_ROOT / "docs" / "reports" / f"{symbol}_DATA_QUALITY.md"
    doc.write_text(md, encoding="utf8")
    log(f"report written: {doc}")
    return md
