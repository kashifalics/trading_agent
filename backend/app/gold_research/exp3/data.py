"""Experiment-3 data rules (route 1): development is the whole training period of the frozen experiment-1 split.

* The experiment-1 validation period (2020-02-08 to 2023-06-24) is not used; the sealed final test is never read here (the sealed
  loader refuses it, and nothing in this module asks for it).
* F1: a gap that starts at the daily rollover break (21:00-21:05 or 22:00-22:05 UTC, at most 2 hours) is a scheduled closure that
  ran longer or later than the calendar assumes, not missing data. Experiment 2 counted it as missing and excluded the trades.
* F4: the gap list is limited to the development period when it is loaded.
Experiment-2 files and functions are not changed.
"""
import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.gold_research.exp2 import data as D2
from app.historical.split import SPLIT_DIR, load_split

BREAK_STARTS_UTC = ((21 * 3600, 21 * 3600 + 300), (22 * 3600, 22 * 3600 + 300))
BREAK_MAX_MINUTES = 120


def split_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp3_split.json"


def _sha(doc: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in doc.items() if k != "sha256"}, sort_keys=True).encode()).hexdigest()


def freeze_split(symbol: str) -> dict:
    """Written once, hash-checked afterwards."""
    p = split_path(symbol)
    if p.exists():
        return load(symbol)
    s = load_split(symbol)
    doc = {"symbol": symbol, "route": "1: develop on all training data; confirm once on the sealed period only with the owner's "
                                      "separate approval; then forward paper trading",
           "development": {"start": s["train"]["start"], "end_exclusive": s["train"]["end_exclusive"],
                           "halves_boundary": "2012-01-01T00:00:00+00:00"},
           "not_used": {"experiment1_validation": [s["validation"]["start"], s["validation"]["end_exclusive"]]},
           "sealed_final_test_from": s["test"]["start"],
           "experiment1_split_sha256": s["sha256"], "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    doc["sha256"] = _sha(doc)
    p.write_text(json.dumps(doc, indent=1), encoding="utf8")
    return doc


def load(symbol: str) -> dict:
    d = json.loads(split_path(symbol).read_text())
    if _sha(d) != d["sha256"]:
        raise RuntimeError("experiment-3 split was edited after it was frozen")
    return d


def epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp())


def is_break_gap(start_epoch: np.ndarray, minutes: np.ndarray) -> np.ndarray:
    sec = np.asarray(start_epoch) % 86400
    at_break = np.zeros(len(sec), dtype=bool)
    for lo, hi in BREAK_STARTS_UTC:
        at_break |= (sec >= lo) & (sec <= hi)
    return at_break & (np.asarray(minutes) <= BREAK_MAX_MINUTES)


def unscheduled_starts(symbol: str, start_iso: str, end_iso: str) -> np.ndarray:
    """Start times of gaps that make a trade unusable: experiment 2's rule (30+ minutes, not a holiday) restricted to the period
    (F4) and without daily-break closures (F1)."""
    lo, hi = epoch(start_iso), epoch(end_iso)
    g = D2.gaps_v2(symbol).filter(pl.col("unscheduled") & (pl.col("start_epoch") >= lo) & (pl.col("start_epoch") < hi))
    st = g["start_epoch"].to_numpy()
    keep = ~is_break_gap(st, g["minutes"].to_numpy())
    return np.sort(st[keep])
