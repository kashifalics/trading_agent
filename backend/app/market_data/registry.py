"""Provider registry + seed data for the four initial instruments.

Honesty rules encoded here:
  * BTCUSDT -> Binance spot (verified, free, keyless).
  * XAUUSD  -> Twelve Data 'XAU/USD' spot gold. Status 'unverified' until a key is configured and
               check_data_coverage proves free-plan availability.
  * US30 / USOIL -> no free, licensed source is assumed. They are registered but 'unsupported'
               until a broker/CFD feed adapter is configured. We never substitute a different
               instrument (e.g. PAXG for gold, a futures ETF for oil).
"""
from decimal import Decimal

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.market_data.base import MarketDataProvider
from app.market_data.binance.provider import BinanceProvider
from app.market_data.twelve_data.provider import TwelveDataProvider

PROVIDER_CODES = ["binance", "twelve_data", "broker_cfd"]


def get_provider(code: str, settings: Settings | None = None) -> MarketDataProvider:
    s = settings or get_settings()
    if code == "binance":
        return BinanceProvider(s.binance_api_base_url)
    if code == "twelve_data":
        return TwelveDataProvider(s.twelve_data_api_key, s.twelve_data_base_url)
    raise NotFoundError(f"No adapter implemented for provider '{code}'")


SEED_PROVIDERS = [
    {"code": "binance", "name": "Binance Spot (public market data)", "base_url": "https://api.binance.com",
     "requires_api_key": False, "is_enabled": True,
     "meta": {"docs": "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints"}},
    {"code": "twelve_data", "name": "Twelve Data (free plan)", "base_url": "https://api.twelvedata.com",
     "requires_api_key": True, "is_enabled": True, "meta": {"docs": "https://twelvedata.com/docs"}},
    {"code": "broker_cfd", "name": "Broker-specific CFD feed (not configured)", "base_url": None,
     "requires_api_key": True, "is_enabled": False,
     "meta": {"note": "Placeholder for an MT5/cTrader/OANDA-style feed adapter; not implemented."}},
]

SEED_INSTRUMENTS = [
    {"canonical_symbol": "XAUUSD", "name": "Gold / US Dollar (spot)", "asset_class": "commodity_metal",
     "quote_currency": "USD", "price_precision": 2, "tick_size": Decimal("0.01"), "calendar": "fx_weekly",
     "session_tz": "UTC", "session_open": "00:00", "trading_session": "Sun 17:00 - Fri 17:00 New York time",
     "contract_size": Decimal("100"), "meta": {"feed": "spot gold (OTC), provider-dependent"}},
    {"canonical_symbol": "US30", "name": "Dow Jones Industrial Average (index/CFD)", "asset_class": "index",
     "quote_currency": "USD", "price_precision": 1, "tick_size": Decimal("0.1"), "calendar": "fx_weekly",
     "session_tz": "UTC", "session_open": "00:00", "trading_session": "broker-specific (CFD ~23h/day)",
     "contract_size": Decimal("1"), "meta": {"feed": "must be a clearly named index or broker CFD feed"}},
    {"canonical_symbol": "BTCUSDT", "name": "Bitcoin / Tether (Binance spot)", "asset_class": "crypto",
     "quote_currency": "USDT", "price_precision": 2, "tick_size": Decimal("0.01"), "calendar": "continuous",
     "session_tz": "UTC", "session_open": "00:00", "trading_session": "24/7",
     "contract_size": Decimal("1"), "meta": {"feed": "Binance spot BTCUSDT"}},
    {"canonical_symbol": "USOIL", "name": "WTI Crude Oil (spot/CFD)", "asset_class": "commodity_energy",
     "quote_currency": "USD", "price_precision": 2, "tick_size": Decimal("0.01"), "calendar": "fx_weekly",
     "session_tz": "UTC", "session_open": "00:00", "trading_session": "broker-specific (CFD ~23h/day)",
     "contract_size": Decimal("1000"),
     "meta": {"feed": "WTI spot/CFD - NOT the same series as NYMEX CL futures (contract rolls differ)"}},
]

# (canonical, provider, provider_symbol, exchange, market_kind, status, notes)
SEED_MAPPINGS = [
    ("BTCUSDT", "binance", "BTCUSDT", "BINANCE", "spot", "active", "Public klines; verified working."),
    ("XAUUSD", "twelve_data", "XAU/USD", None, "spot", "unverified",
     "Requires TWELVE_DATA_API_KEY. Free-plan availability must be confirmed with a coverage probe."),
    ("US30", "broker_cfd", "US30", None, "cfd", "unsupported",
     "No free licensed US30 feed configured. Configure a broker/CFD adapter. Index (DJI) vs CFD prices differ."),
    ("USOIL", "broker_cfd", "USOIL", None, "cfd", "unsupported",
     "No free licensed WTI spot/CFD feed configured. Do not substitute NYMEX CL futures."),
]
