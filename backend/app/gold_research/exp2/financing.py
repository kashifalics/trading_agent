"""Overnight financing cost scenarios for experiment 2. Analysis only.

A night is a 17:00 New York rollover crossed while the position is open; the Friday rollover counts 3 nights (Friday, Saturday,
Sunday), the usual convention for weekend financing. Cost per night is charged in dollars per ounce and converted to R with each
trade's own risk.

Scenarios (pre-registered):
  none        no financing (baseline)
  fixed_0.10  $0.10 per ounce per night, long and short alike (primary scenario)
  fred_proxy  a PROXY built from the US effective federal funds rate (FRED series DFF, daily, percent):
              long pays price x (DFF + 2.5%) / 365 per night; short pays price x (2.5% - DFF) / 365 (receives when DFF > 2.5%).
              This is NOT any broker's historical swap: real swaps also depend on gold lease rates, the broker's own markup and
              its triple-swap day. It is only a plausible order of magnitude. Used only when the official FRED file is present at
              data/historical/reference/FRED_DFF.csv (downloaded from fred.stlouisfed.org); otherwise reported as unavailable.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import polars as pl

from app.historical.config import DATA_ROOT

MARKUP = 0.025
FIXED = 0.10
FRED_FILE = DATA_ROOT / "reference" / "FRED_DFF.csv"
SCENARIOS = ("none", "fixed_0.10", "fred_proxy")


def rollovers(start_year: int, end_year: int) -> tuple[np.ndarray, np.ndarray]:
    """(epoch of every weekday 17:00 New York rollover Monday-Friday, nights it counts for: 3 on Fridays, else 1)."""
    days = pl.date_range(datetime(start_year, 1, 1), datetime(end_year, 12, 31), "1d", eager=True)
    df = pl.DataFrame({"d": days}).with_columns(wd=pl.col("d").dt.weekday()).filter(pl.col("wd") <= 5)
    ts = (df["d"].cast(pl.Datetime("us")) + timedelta(hours=17)).dt.replace_time_zone("America/New_York").dt.convert_time_zone("UTC")
    return ts.dt.epoch("s").to_numpy().astype(np.int64), np.where(df["wd"].to_numpy() == 5, 3, 1).astype(np.int64)


def nights(entry_ts: np.ndarray, exit_ts: np.ndarray, roll: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    """Nights charged between entry (exclusive) and exit (inclusive of a rollover exactly at exit)."""
    t, w = roll
    cum = np.r_[0, np.cumsum(w)]
    a = np.searchsorted(t, entry_ts, side="right")
    b = np.searchsorted(t, exit_ts, side="right")
    return cum[b] - cum[a]


def load_fred(path: Path = FRED_FILE) -> pl.DataFrame | None:
    """Daily DFF from the official FRED CSV (columns observation_date/DATE, DFF). None when the file is not present."""
    if not path.exists():
        return None
    df = pl.read_csv(path, try_parse_dates=True, null_values=[".", ""])
    dcol = next(c for c in df.columns if c.lower() in ("observation_date", "date"))
    return df.select(pl.col(dcol).cast(pl.Date).alias("date"), pl.col("DFF").cast(pl.Float64).alias("dff")).drop_nulls().sort("date")


def cost_usd_per_oz(scenario: str, direction: np.ndarray, entry_ts: np.ndarray, exit_ts: np.ndarray, price: np.ndarray,
                    roll: tuple[np.ndarray, np.ndarray], fred: pl.DataFrame | None = None) -> np.ndarray | None:
    """Financing cost in $ per ounce for each trade (positive = cost). None when the scenario's data is unavailable."""
    n = nights(entry_ts, exit_ts, roll).astype(float)
    if scenario == "none":
        return np.zeros(len(n))
    if scenario == "fixed_0.10":
        return FIXED * n
    if scenario == "fred_proxy":
        if fred is None:
            return None
        days = fred["date"].cast(pl.Datetime("us")).dt.replace_time_zone("UTC").dt.epoch("s").to_numpy()
        j = np.clip(np.searchsorted(days, entry_ts, side="right") - 1, 0, len(days) - 1)
        rate = fred["dff"].to_numpy()[j] / 100.0  # rate known at entry, held for the trade (a simplification)
        per_night = np.where(direction > 0, rate + MARKUP, MARKUP - rate) * price / 365.0
        return per_night * n
    raise ValueError(scenario)


def fred_status() -> dict:
    if not FRED_FILE.exists():
        return {"available": False, "note": f"FRED file not present at {FRED_FILE}; the automated download was refused by the server "
                                            "(connection reset / timeout). The proxy scenario is reported as unavailable, never estimated."}
    import hashlib
    df = load_fred()
    return {"available": True, "rows": df.height, "first": str(df["date"].min()), "last": str(df["date"].max()),
            "sha256": hashlib.sha256(FRED_FILE.read_bytes()).hexdigest(),
            "file_time": datetime.fromtimestamp(FRED_FILE.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")}
