"""Experiment-2 data rules: the frozen development / screening split inside the training period, and gaps re-classified with the
US holiday calendar (experiment-1 files are left untouched)."""
import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.historical.config import CLEAN
from app.historical.holidays import holiday_windows, in_holiday_window
from app.historical.split import SPLIT_DIR, load_split

DEV_END = "2015-01-03T00:00:00+00:00"  # first Saturday after 2014-12-31: development 2003-05-05 .. 2015-01-02, screening after


def split_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp2_split.json"


def freeze_split(symbol: str) -> dict:
    """Experiment-2 boundaries inside the experiment-1 TRAINING period. Written once, hash-checked."""
    p = split_path(symbol)
    if p.exists():
        return load(symbol)
    s = load_split(symbol)
    doc = {"symbol": symbol, "development": {"start": s["train"]["start"], "end_exclusive": DEV_END},
           "screening": {"start": DEV_END, "end_exclusive": s["train"]["end_exclusive"],
                         "note": "previously examined in experiment 1 (aggregates); screening and comparison only, NOT independent validation"},
           "not_used": {"experiment1_validation": [s["validation"]["start"], s["validation"]["end_exclusive"]],
                        "sealed_final_test_from": s["test"]["start"]},
           "experiment1_split_sha256": s["sha256"], "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    doc["sha256"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    p.write_text(json.dumps(doc, indent=1), encoding="utf8")
    return doc


def load(symbol: str) -> dict:
    d = json.loads(split_path(symbol).read_text())
    body = {k: v for k, v in d.items() if k != "sha256"}
    if hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != d["sha256"]:
        raise RuntimeError("experiment-2 split was edited after it was frozen")
    return d


def gaps_v2(symbol: str) -> pl.DataFrame:
    """Experiment-1 gap runs with US holiday closures re-classified as scheduled. Unscheduled = 30+ minutes, not a holiday."""
    g = pl.read_parquet(CLEAN / symbol / "gaps.parquet")
    if g.height == 0:
        return g.with_columns(us_holiday=pl.lit(False), start_epoch=pl.lit(0, pl.Int64), end_epoch=pl.lit(0, pl.Int64),
                              unscheduled=pl.lit(False))
    st = g["start"].dt.epoch("s").to_numpy().astype(np.int64)
    w = holiday_windows(int(g["start"].dt.year().min()), int(g["start"].dt.year().max()))
    us = in_holiday_window(st, w)
    out = g.with_columns(us_holiday=pl.Series(us), start_epoch=pl.Series(st),
                         end_epoch=pl.Series(st + 60 * g["minutes"].to_numpy().astype(np.int64)))
    return out.with_columns(unscheduled=(pl.col("minutes") >= 30) & ~pl.col("holiday") & ~pl.col("us_holiday"))


def unscheduled_starts(symbol: str) -> np.ndarray:
    g = gaps_v2(symbol).filter(pl.col("unscheduled"))
    return np.sort(g["start_epoch"].to_numpy())


def gap_between(gs: np.ndarray, entry: np.ndarray, exit_: np.ndarray) -> np.ndarray:
    """True where an unscheduled gap starts at or after entry and before exit (the trade was actually open)."""
    if len(gs) == 0:
        return np.zeros(len(entry), dtype=bool)
    return np.searchsorted(gs, exit_, side="left") > np.searchsorted(gs, entry, side="left")
