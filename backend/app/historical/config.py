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
    calendar: str = "fx_weekly"  # fx_weekly: closed Friday 17:00 to Sunday 17:00 New York; continuous: open every minute (crypto)
    daily_break: bool = False  # metals pause 17:00-18:00 New York every day; that hour is not a data gap
    source: str = "dukascopy"  # dukascopy (bid/ask bi5 files) | binance (public spot kline archive, one price + modelled spread)


INSTRUMENTS = {i.symbol: i for i in (
    Instrument("EURUSD", 1e-5), Instrument("GBPUSD", 1e-5), Instrument("USDJPY", 1e-3), Instrument("USDCHF", 1e-5),
    Instrument("USDCAD", 1e-5), Instrument("AUDUSD", 1e-5), Instrument("NZDUSD", 1e-5), Instrument("XAUUSD", 1e-3, daily_break=True),
    Instrument("BTCUSDT", 1e-2, calendar="continuous", source="binance"),
)}

# Rebuilt from M1 only (never the other way round). polars duration strings on UTC boundaries: intraday windows are aligned to
# multiples of their length since 00:00 UTC, days start 00:00 UTC, weeks Monday 00:00 UTC, months on the 1st.
TIMEFRAMES = {"M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h", "H2": "2h", "H4": "4h", "H6": "6h", "H8": "8h", "H12": "12h",
              "D1": "1d", "W1": "1w", "MN1": "1mo"}
# Each timeframe is aggregated from a finer one whose boundaries nest inside it, which gives identical OHLC to aggregating M1
# directly (verified by verify_timeframes). M5 itself comes from M1.
PARENT = {"M15": "M5", "M30": "M15", "H1": "M30", "H2": "H1", "H4": "H2", "H6": "H2", "H8": "H4", "H12": "H4", "D1": "H4",
          "W1": "D1", "MN1": "D1"}
# Optional trading-day candles that start at 17:00 New York (the FX/metals daily close), daylight saving handled. Saved as "D1_NY".
NY_DAY_TF = "D1_NY"
TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H2": 7200, "H4": 14400, "H6": 21600, "H8": 28800,
              "H12": 43200, "D1": 86400, "D1_NY": 86400, "W1": 604800, "MN1": 2_678_400}  # MN1: nominal 31 days (calendar-aware close in sync.py)
MATERIAL_GAP_MIN = 30  # consecutive missing open-market minutes that make a gap material (flagged, excluded from research)
