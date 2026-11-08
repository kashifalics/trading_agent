"""Instruments, storage layout and timeframes for the historical pipeline. Add an instrument by adding a line to INSTRUMENTS."""
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path(os.environ.get("HISTORICAL_DATA_DIR") or REPO_ROOT / "data" / "historical")
RAW = DATA_ROOT / "raw" / "dukascopy"  # immutable: exactly the bytes Dukascopy served (one file per UTC day and side)
NORMALIZED = DATA_ROOT / "normalized"  # decoded M1 bid/ask per year, every minute Dukascopy published (incl. no-tick minutes)
CLEAN = DATA_ROOT / "clean"  # validated M1 (no-tick filler minutes removed) and the timeframes rebuilt from it
REPORTS = DATA_ROOT / "reports"
EARLIEST_YEAR = 2003  # Dukascopy's archive starts no earlier; the real first day is discovered per instrument


@dataclass(frozen=True)
class Instrument:
    symbol: str
    point: float  # Dukascopy stores prices as integers: price = value * point
    calendar: str = "fx_weekly"
    daily_break: bool = False  # metals pause 17:00-18:00 New York every day; that hour is not a data gap


INSTRUMENTS = {i.symbol: i for i in (
    Instrument("EURUSD", 1e-5), Instrument("GBPUSD", 1e-5), Instrument("USDJPY", 1e-3), Instrument("USDCHF", 1e-5),
    Instrument("USDCAD", 1e-5), Instrument("AUDUSD", 1e-5), Instrument("NZDUSD", 1e-5), Instrument("XAUUSD", 1e-3, daily_break=True),
)}

# Rebuilt from M1 only (never the other way round). polars duration strings; weeks start Monday 00:00 UTC, days at 00:00 UTC.
TIMEFRAMES = {"M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h", "H4": "4h", "D1": "1d", "W1": "1w"}
MATERIAL_GAP_MIN = 30  # consecutive missing open-market minutes that make a gap material (flagged, excluded from research)
