"""The one door research uses to read history: sealed by split segment, plus a memory-mapped M1 store.

    load_tf(symbol, tf, upto="train")                 candles that CLOSED before the end of training
    load_tf(symbol, tf, upto="validation")            ... before the end of validation (confirmation runs only)
    load_tf(symbol, tf, upto="test", final_test=True) everything; refused without final_test, and every such read is appended to
                                                      docs/research/{SYMBOL}_seal_log.md
Trades near a boundary simply run out of bars, so no outcome window ever reaches into a later segment.

M1 store: data/historical/m1/{SYMBOL}/ts.npy (int64 epoch seconds) and bid.npy / ask.npy (int32 points, columns open, high, low,
close), opened with mmap so worker processes share the pages instead of copying about 300 MB each.
"""
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.historical.config import CLEAN, DATA_ROOT, INSTRUMENTS, REPO_ROOT
from app.historical.split import SPLIT_DIR, load_split
from app.historical.sync import bar_close, epoch

SEGMENTS = ("train", "validation", "test")


class SealError(PermissionError):
    """Raised when code asks for final-test data without the explicit final-test flag."""


def segment_end(symbol: str, upto: str) -> int | None:
    """Exclusive end (epoch seconds) of the data visible when reading `upto`; None = no limit."""
    if upto not in SEGMENTS:
        raise ValueError(f"upto must be one of {SEGMENTS}")
    s = load_split(symbol)
    if upto == "test":
        return None
    end = s["train"]["end_exclusive"] if upto == "train" else s["validation"]["end_exclusive"]
    return int(datetime.fromisoformat(end).timestamp())


def _seal(symbol: str, what: str, final_test: bool, upto: str) -> None:
    if upto != "test":
        return
    if not final_test:
        raise SealError(f"{symbol}: the final-test period is sealed. Only the one-time final test may read it (final_test=True).")
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()
    except OSError:
        commit = "unknown"
    log = SPLIT_DIR / f"{symbol}_seal_log.md"
    new = not log.exists()
    with log.open("a", encoding="utf8") as f:
        if new:
            f.write(f"# {symbol} final-test seal log\n\nAppend-only. Every read of the final-test period is recorded here. More than "
                    "one research run listed below means the test set is no longer untouched.\n\n| UTC time | Read | Git commit |\n|---|---|---|\n")
        f.write(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {what} | {commit} |\n")


def load_tf(symbol: str, tf: str, upto: str = "train", final_test: bool = False) -> pl.DataFrame:
    _seal(symbol, f"{tf} candles", final_test, upto)
    df = pl.read_parquet(CLEAN / symbol / tf / "all.parquet").sort("ts")
    end = segment_end(symbol, upto)
    if end is None:
        return df
    return df.filter(pl.Series(bar_close(tf, epoch(df["ts"])) <= end))


@dataclass
class M1:
    ts: np.ndarray  # int64 epoch seconds, minute open
    bid: np.ndarray  # int32 points (n, 4): open, high, low, close
    ask: np.ndarray
    point: float

    def __len__(self) -> int:
        return len(self.ts)


def m1_dir(symbol: str):
    return DATA_ROOT / "m1" / symbol


def build_m1_store(symbol: str, log=print) -> int:
    point = INSTRUMENTS[symbol].point
    files = sorted((CLEAN / symbol / "M1").glob("*.parquet"))
    df = pl.concat([pl.read_parquet(f, columns=["ts", *[f"{s}_{k}" for s in ("bid", "ask") for k in ("open", "high", "low", "close")]])
                    for f in files]).sort("ts")
    out = m1_dir(symbol)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "ts.npy", epoch(df["ts"]))
    for side in ("bid", "ask"):
        arr = np.stack([np.rint(df[f"{side}_{k}"].to_numpy() / point) for k in ("open", "high", "low", "close")], axis=1)
        np.save(out / f"{side}.npy", arr.astype(np.int32))
    log(f"{symbol}: M1 store written ({df.height:,} minutes)")
    return df.height


def load_m1(symbol: str, upto: str = "train", final_test: bool = False) -> M1:
    _seal(symbol, "M1 store", final_test, upto)
    d = m1_dir(symbol)
    ts = np.load(d / "ts.npy", mmap_mode="r")
    end = segment_end(symbol, upto)
    n = len(ts) if end is None else int(np.searchsorted(ts, end - 59, side="left"))  # minutes that close before the end
    return M1(ts[:n], np.load(d / "bid.npy", mmap_mode="r")[:n], np.load(d / "ask.npy", mmap_mode="r")[:n], INSTRUMENTS[symbol].point)
