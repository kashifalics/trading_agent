"""Binance public data archive (data.binance.vision): spot 1-minute klines, one zip per month, each published with a SHA-256
checksum file. Free, no account or key.

* Raw zips are kept exactly as served, in data/historical/raw/binance/<SYMBOL>/, and a month counts as downloaded only once its
  bytes match the published checksum. A mismatch is deleted and fetched again.
* The archive has one price per candle (trades), not bid/ask. Clean M1 is written in the store's bid/ask schema with the owner's
  broker spread as the cost model: bid = price - half_spread, ask = price + half_spread (Experiment 6 plan, section 2).
* Volume is Binance's base volume (coins traded on Binance only), stored as bid_volume (ask_volume = 0, so bid + ask = the
  traded volume), plus taker_buy_base (coins bought by market orders).
* Open times are milliseconds before 2025 and microseconds from 2025; both are normalised.
"""
import csv
import hashlib
import io
import time
import zipfile
from collections.abc import Callable
from datetime import date, datetime, timezone

import polars as pl

from app.historical.config import CLEAN, RAW, REPORTS

RAW_BINANCE = RAW.parent / "binance"
BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
FIRST_MONTH = "2017-08"  # BTCUSDT trading on Binance started 2017-08-17
PRICE_COLS = ("open", "high", "low", "close")


def month_url(symbol: str, ym: str) -> str:
    return f"{BASE_URL}/{symbol}/1m/{symbol}-1m-{ym}.zip"


def zip_path(symbol: str, ym: str):
    return RAW_BINANCE / symbol / f"{symbol}-1m-{ym}.zip"


def months(start: str, end: str) -> list[str]:
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def last_complete_month(today: date | None = None) -> str:
    d = today or datetime.now(timezone.utc).date()
    y, m = (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
    return f"{y:04d}-{m:02d}"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _http_fetch() -> Callable[[str], bytes]:
    import httpx

    client = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "ai-trading-intelligence research downloader"})

    def fetch(url: str) -> bytes:
        r = client.get(url)
        r.raise_for_status()
        return r.content
    return fetch


def download(symbol: str, start: str = FIRST_MONTH, end: str | None = None, *, fetch: Callable[[str], bytes] | None = None,
             sleep: Callable[[float], None] = time.sleep, attempts: int = 6, log=print) -> dict:
    """Fetch every month in [start, end] not yet verified. Resumable: a month whose zip matches its stored checksum is skipped."""
    fetch = fetch or _http_fetch()
    end = end or last_complete_month()
    d = RAW_BINANCE / symbol
    d.mkdir(parents=True, exist_ok=True)
    out = {"symbol": symbol, "months": 0, "downloaded": 0, "skipped": 0, "checksum_retries": 0, "failed": []}
    for ym in months(start, end):
        out["months"] += 1
        zp, cp = zip_path(symbol, ym), zip_path(symbol, ym).with_suffix(".zip.CHECKSUM")
        if zp.exists() and cp.exists() and _sha(zp.read_bytes()) == cp.read_text().split()[0]:
            out["skipped"] += 1
            continue
        ok = False
        for k in range(attempts):
            try:
                expected = fetch(month_url(symbol, ym) + ".CHECKSUM").decode().split()[0]
                payload = fetch(month_url(symbol, ym))
            except Exception as exc:  # noqa: BLE001 - network: back off and retry
                log(f"{symbol} {ym}: {exc.__class__.__name__}, retry {k + 1}/{attempts}")
                sleep(min(600, 5 * 2 ** k))
                continue
            if _sha(payload) != expected:
                out["checksum_retries"] += 1
                zp.unlink(missing_ok=True)
                log(f"{symbol} {ym}: checksum mismatch, fetching again ({k + 1}/{attempts})")
                sleep(min(600, 5 * 2 ** k))
                continue
            zp.write_bytes(payload)
            cp.write_text(f"{expected}  {zp.name}\n")
            out["downloaded"] += 1
            ok = True
            break
        if not ok:
            zp.unlink(missing_ok=True)
            out["failed"].append(ym)
        else:
            log(f"{symbol} {ym}: ok ({zp.stat().st_size:,} bytes)")
    return out


def raw_manifest(symbol: str) -> dict:
    """SHA-256 and size of every raw zip (sorted), written like the Dukascopy manifest; the split records the digest of this file."""
    lines = []
    for f in sorted((RAW_BINANCE / symbol).glob(f"{symbol}-1m-*.zip")):
        b = f.read_bytes()
        lines.append(f"{_sha(b)}  {len(b)}  binance/{symbol}/{f.name}")
    text = "\n".join(lines) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{symbol}_raw_manifest.txt").write_text(text, encoding="utf8")
    return {"files": len(lines), "sha256": _sha(text.encode())}


def parse_month(zip_bytes: bytes) -> pl.DataFrame:
    """One month's klines: ts (UTC candle open), open, high, low, close, volume, taker_buy_base."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        text = z.read(z.namelist()[0]).decode()
    rows = [r for r in csv.reader(io.StringIO(text)) if r and r[0].strip().lstrip("-").isdigit()]  # a header line is skipped
    t = [int(r[0]) for r in rows]
    ms = [x // 1000 if x > 10**14 else x for x in t]  # microseconds from 2025
    return pl.DataFrame({
        "ts": pl.Series(ms, dtype=pl.Int64).cast(pl.Datetime("ms")).dt.cast_time_unit("us").dt.replace_time_zone("UTC"),
        **{c: [float(r[i]) for r in rows] for i, c in enumerate(PRICE_COLS, start=1)},
        "volume": [float(r[5]) for r in rows], "taker_buy_base": [float(r[9]) for r in rows],
    }, schema={"ts": pl.Datetime("us", "UTC"), "open": pl.Float64, "high": pl.Float64, "low": pl.Float64, "close": pl.Float64,
               "volume": pl.Float64, "taker_buy_base": pl.Float64})


def write_clean_m1(symbol: str, half_spread: float = 1.0, log=print) -> dict[int, dict]:
    """Clean M1 per year in the store's schema; returns per-year stats (the keys the coverage report sums)."""
    files = sorted((RAW_BINANCE / symbol).glob(f"{symbol}-1m-*.zip"))
    if not files:
        raise RuntimeError(f"{symbol}: nothing downloaded yet (run download-binance)")
    df = pl.concat([parse_month(f.read_bytes()) for f in files]).sort("ts")
    published = df.height
    dup = published - df.unique(subset="ts").height
    df = df.unique(subset="ts", keep="first").sort("ts")
    bad = (pl.col("high") < pl.max_horizontal("open", "close")) | (pl.col("low") > pl.min_horizontal("open", "close")) | \
          (pl.col("low") <= 0)
    invalid_rows = df.filter(bad)
    df = df.filter(~bad)
    sides = {f"bid_{c}": pl.col(c) - half_spread for c in PRICE_COLS}
    sides |= {f"ask_{c}": pl.col(c) + half_spread for c in PRICE_COLS}
    clean = df.with_columns(**sides, bid_volume=pl.col("volume"), ask_volume=pl.lit(0.0), spread=pl.lit(2 * half_spread)).select(
        "ts", "bid_open", "bid_high", "bid_low", "bid_close", "bid_volume", "ask_open", "ask_high", "ask_low", "ask_close",
        "ask_volume", "spread", "taker_buy_base")
    stats = {}
    for y in sorted(clean["ts"].dt.year().unique().to_list()):
        part = clean.filter(pl.col("ts").dt.year() == y)
        p = CLEAN / symbol / "M1" / f"{y}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        part.write_parquet(p, compression="zstd")
        stats[y] = {"year": y, "rows_published": int(df.filter(pl.col("ts").dt.year() == y).height
                                                     + invalid_rows.filter(pl.col("ts").dt.year() == y).height),
                    "duplicates": 0, "one_side_missing": 0, "quiet_minutes": 0,
                    "invalid_candles": int(invalid_rows.filter(pl.col("ts").dt.year() == y).height), "outlier_moves": 0,
                    "clean_rows": part.height}
        log(f"{symbol} {y}: {part.height:,} clean M1")
    if stats:  # duplicates are counted once over the whole archive (month files never overlap; any overlap is reported here)
        stats[min(stats)]["duplicates"] = dup
        stats[min(stats)]["rows_published"] += dup
    return stats
