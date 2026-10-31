"""Shared structure for every detector output (candlestick, structure, price action)."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def iso(ts: int | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@dataclass
class Event:
    """A detected condition.

    idx/ts: bar at which the event is CONFIRMED (information available only up to that bar's close).
    start_idx/start_ts: bar where the underlying structure originated (may precede idx).
    """

    kind: str
    direction: str  # bullish | bearish | neutral
    idx: int
    ts: int
    price: float | None = None  # key level
    low: float | None = None  # zone lower bound
    high: float | None = None  # zone upper bound
    start_idx: int | None = None
    start_ts: int | None = None
    status: str | None = None
    evidence: str = ""
    params: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["time"] = iso(self.ts)
        d["start_time"] = iso(self.start_ts)
        return d
