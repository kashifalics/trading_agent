"""Chronological 70 / 15 / 15 split of one instrument's history, computed once from the real data and then frozen.

The cut points are the clean-M1 rows at 70% and 85% of all observations, each moved forward to the next Saturday 00:00 UTC (the
market is always closed then, so no candle, trade or session straddles a boundary). The result is written to
docs/research/{SYMBOL}_split.json with a SHA-256 of its content and is never recomputed: data that arrives later belongs to the
test period (and, after the one-time final test, to the forward paper test).

    train       first traded minute  ..  train_end        pattern research, features, model fitting, calibration
    validation  train_end            ..  validation_end   confirmation only
    test        validation_end       ..  (open)           sealed: read only by the final test (store.load_tf(final_test=True))
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone

import polars as pl

from app.historical.config import CLEAN, INSTRUMENTS, REPO_ROOT, REPORTS

SPLIT_DIR = REPO_ROOT / "docs" / "research"
FRACTIONS = (0.70, 0.15, 0.15)


def split_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_split.json"


def next_saturday(ts: datetime) -> datetime:
    """The first Saturday 00:00 UTC strictly after ts."""
    d = (ts + timedelta(days=1)).date()
    while d.weekday() != 5:
        d += timedelta(days=1)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def next_boundary(ts: datetime, calendar: str) -> datetime:
    """The segment boundary after ts: Saturday 00:00 UTC for the FX weekly calendar (inside the weekend closure), Monday
    00:00 UTC for a continuous (24/7) market (the start of a calendar week)."""
    if calendar != "continuous":
        return next_saturday(ts)
    d = (ts + timedelta(days=1)).date()
    while d.weekday() != 0:
        d += timedelta(days=1)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _row_ts(files: list, counts: list[int], k: int) -> datetime:
    for f, n in zip(files, counts):
        if k < n:
            return pl.read_parquet(f, columns=["ts"])["ts"].sort()[k]
        k -= n
    raise IndexError(k)


def compute_split(symbol: str) -> dict:
    files = sorted((CLEAN / symbol / "M1").glob("*.parquet"))
    if not files:
        raise RuntimeError(f"{symbol}: no clean M1 yet (run the build first)")
    counts = [pl.scan_parquet(f).select(pl.len()).collect().item() for f in files]
    total = sum(counts)
    cal = INSTRUMENTS[symbol].calendar if symbol in INSTRUMENTS else "fx_weekly"
    b1 = next_boundary(_row_ts(files, counts, int(total * FRACTIONS[0])), cal)
    b2 = next_boundary(_row_ts(files, counts, int(total * (FRACTIONS[0] + FRACTIONS[1]))), cal)
    lf = pl.scan_parquet(files)
    stats = lf.select(pl.col("ts").min().alias("first"), pl.col("ts").max().alias("last"),
                      (pl.col("ts") < b1).sum().alias("n_train"), ((pl.col("ts") >= b1) & (pl.col("ts") < b2)).sum().alias("n_val"),
                      (pl.col("ts") >= b2).sum().alias("n_test")).collect().row(0, named=True)
    man = REPORTS / f"{symbol}_raw_manifest.txt"
    content = {
        "symbol": symbol,
        "method": "clean-M1 observations at 70% and 85%, each moved to the next "
                  + ("Monday" if cal == "continuous" else "Saturday") + " 00:00 UTC",
        "fractions": list(FRACTIONS),
        "train": {"start": stats["first"].isoformat(), "end_exclusive": b1.isoformat(), "m1_rows": stats["n_train"]},
        "validation": {"start": b1.isoformat(), "end_exclusive": b2.isoformat(), "m1_rows": stats["n_val"]},
        "test": {"start": b2.isoformat(), "data_end_when_frozen": stats["last"].isoformat(), "m1_rows_when_frozen": stats["n_test"]},
        "m1_rows_total": total,
        "raw_manifest_sha256": hashlib.sha256(man.read_bytes()).hexdigest() if man.exists() else None,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    content["sha256"] = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return content


def freeze_split(symbol: str, log=print) -> dict:
    """Write the split once. An existing split is returned unchanged: the boundaries never move."""
    p = split_path(symbol)
    if p.exists():
        s = json.loads(p.read_text())
        log(f"{symbol}: split already frozen on {s['created']} (sha256 {s['sha256'][:12]}), not recomputed")
        return s
    s = compute_split(symbol)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s, indent=1), encoding="utf8")
    log(f"{symbol}: split frozen: train until {s['train']['end_exclusive'][:10]}, validation until {s['validation']['end_exclusive'][:10]}")
    return s


def load_split(symbol: str) -> dict:
    p = split_path(symbol)
    if not p.exists():
        raise RuntimeError(f"{symbol}: no frozen split; run `python -m app.historical split --symbols {symbol}`")
    s = json.loads(p.read_text())
    body = {k: v for k, v in s.items() if k != "sha256"}
    if hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != s["sha256"]:
        raise RuntimeError(f"{p} was edited after it was frozen (hash mismatch)")
    return s
