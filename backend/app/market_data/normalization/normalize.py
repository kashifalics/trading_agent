from dataclasses import dataclass, field
from datetime import timezone
from decimal import Decimal

from app.market_data.types import Candle


@dataclass
class NormalizationReport:
    accepted: int = 0
    duplicates: int = 0
    rejected: list[dict] = field(default_factory=list)


def candle_error(c: Candle) -> str | None:
    """Returns why a candle is structurally invalid, else None. Invalid candles are rejected,
    never repaired - we do not fabricate OHLC values."""
    if c.ts.tzinfo is None:
        return "naive timestamp"
    if min(c.open, c.high, c.low, c.close) <= 0:
        return "non-positive price"
    if c.high < max(c.open, c.close, c.low):
        return "high below open/close/low"
    if c.low > min(c.open, c.close, c.high):
        return "low above open/close/high"
    if c.volume is not None and c.volume < 0:
        return "negative volume"
    return None


def normalize_candles(candles: list[Candle]) -> tuple[list[Candle], NormalizationReport]:
    """Validate, UTC-normalise, sort ascending and de-duplicate by timestamp (last wins)."""
    report = NormalizationReport()
    by_ts: dict = {}
    for c in candles:
        err = candle_error(c)
        if err:
            report.rejected.append({"ts": c.ts.isoformat() if c.ts else None, "reason": err})
            continue
        ts = c.ts.astimezone(timezone.utc)
        if ts in by_ts:
            report.duplicates += 1
        by_ts[ts] = c if c.ts == ts else Candle(ts, c.open, c.high, c.low, c.close, c.volume,
                                                 c.complete, c.volume_type, c.origin, c.meta)
    out = [by_ts[k] for k in sorted(by_ts)]
    report.accepted = len(out)
    return out, report


def to_decimal(value: object) -> Decimal:
    return Decimal(str(value))
