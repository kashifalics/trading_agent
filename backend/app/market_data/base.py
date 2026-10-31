from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.market_data.types import Candle, ProviderMetadata, Quote


@dataclass(slots=True)
class ProviderInstrumentInfo:
    symbol: str
    name: str | None = None
    status: str | None = None
    price_precision: int | None = None
    tick_size: Decimal | None = None
    raw: dict | None = None


class MarketDataProvider(ABC):
    """Contract every market-data adapter implements. Adapters return NORMALISED candles
    (Decimal prices, UTC open time, explicit completion flag) and never fabricate values."""

    code: str
    #: our timeframe code -> provider interval string
    native_timeframes: dict[str, str]

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def get_instruments(self, symbols: list[str] | None = None) -> list[ProviderInstrumentInfo]: ...

    @abstractmethod
    def get_candles(
        self, symbol: str, timeframe: str, start: datetime | None = None, end: datetime | None = None,
        limit: int | None = None,
    ) -> list[Candle]: ...

    @abstractmethod
    def get_latest_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    def get_market_status(self, symbol: str) -> dict: ...

    @abstractmethod
    def get_provider_metadata(self) -> ProviderMetadata: ...

    @abstractmethod
    def check_data_coverage(self, symbol: str, timeframe: str) -> dict:
        """Probe what the provider can actually serve (earliest/latest candle) for this plan."""

    def close(self) -> None:  # pragma: no cover
        pass
