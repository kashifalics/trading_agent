from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Candle:
    """Normalized candle. `ts` is the OPEN time in UTC."""

    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    complete: bool = True
    volume_type: str = "none"  # base | quote | tick | none
    origin: str = "native"  # native | aggregated
    meta: dict = field(default_factory=dict, compare=False, hash=False)


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    price: Decimal
    ts: datetime  # time the price refers to (provider time if given, else fetch time)
    provider: str
    bid: Decimal | None = None
    ask: Decimal | None = None
    is_delayed: bool = False


@dataclass(slots=True)
class ProviderMetadata:
    code: str
    name: str
    base_url: str
    requires_api_key: bool
    configured: bool
    free_plan: dict
    licensing: str
    docs_url: str
    signup_url: str | None = None
