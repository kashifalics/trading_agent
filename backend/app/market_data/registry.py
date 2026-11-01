"""Provider registry + seed data for the tracked instruments.

Honesty rules encoded here (what has actually been verified is recorded in docs/MARKET_DATA_PROVIDERS.md):
  * BTCUSDT -> Binance spot (verified, free, keyless).
  * XAUUSD, GBPUSD -> Twelve Data spot (free plan serves 1H/1D; 2H/4H are built from 1H).
  * US30, USOIL -> OANDA CFD feed (needs a free practice-account token; 'unverified' until a live probe passes).
    Twelve Data's free plan does NOT serve the Dow index (only ETFs, which are different instruments).
  * We never substitute a different instrument (PAXG for gold, an ETF for the index, CL futures for spot oil).
"""
from decimal import Decimal

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.market_data.base import MarketDataProvider
from app.market_data.binance.provider import BinanceProvider
from app.market_data.oanda.provider import OandaProvider
from app.market_data.twelve_data.provider import TwelveDataProvider

PROVIDER_CODES = ["binance", "twelve_data", "oanda"]


def get_provider(code: str, settings: Settings | None = None) -> MarketDataProvider:
    s = settings or get_settings()
    if code == "binance":
        return BinanceProvider(s.binance_api_base_url)
    if code == "twelve_data":
        return TwelveDataProvider(s.twelve_data_api_key, s.twelve_data_base_url)
    if code == "oanda":
        return OandaProvider(s.oanda_api_token, s.oanda_base_url)
    raise NotFoundError(f"No adapter implemented for provider '{code}'")


SEED_PROVIDERS = [
    {"code": "binance", "name": "Binance Spot (public market data)", "base_url": "https://api.binance.com",
     "requires_api_key": False, "is_enabled": True,
     "meta": {"docs": "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints"}},
    {"code": "twelve_data", "name": "Twelve Data (free plan)", "base_url": "https://api.twelvedata.com",
     "requires_api_key": True, "is_enabled": True, "meta": {"docs": "https://twelvedata.com/docs"}},
    {"code": "oanda", "name": "OANDA v20 (fxTrade Practice, free demo)", "base_url": "https://api-fxpractice.oanda.com",
     "requires_api_key": True, "is_enabled": True, "meta": {"docs": "https://developer.oanda.com/rest-live-v20/instrument-ep/"}},
]

SEED_INSTRUMENTS = [
    {"canonical_symbol": "XAUUSD", "name": "Gold / US Dollar (spot)", "asset_class": "commodity_metal",
     "quote_currency": "USD", "price_precision": 2, "tick_size": Decimal("0.01"), "calendar": "fx_weekly",
     "session_tz": "UTC", "session_open": "00:00", "trading_session": "Sun 17:00 - Fri 17:00 New York time",
     "contract_size": Decimal("100"), "meta": {"feed": "spot gold (OTC), provider-dependent"}},
    {"canonical_symbol": "GBPUSD", "name": "British Pound / US Dollar (spot)", "asset_class": "forex",
     "quote_currency": "USD", "price_precision": 5, "tick_size": Decimal("0.00001"), "calendar": "fx_weekly",
     "session_tz": "UTC", "session_open": "00:00", "trading_session": "Sun 17:00 - Fri 17:00 New York time",
     "contract_size": Decimal("100000"), "meta": {"feed": "spot FX, provider-dependent"}},
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
    ("XAUUSD", "twelve_data", "XAU/USD", None, "spot", "active",
     "Live-verified 2026-11-01 (docs/reports/XAUUSD_COVERAGE.md): free plan serves 1m-1D natively except 3m/2H/4H, which are built "
     "from 1m/1H. Feed contains thin weekend quotes: hidden."),
    ("GBPUSD", "twelve_data", "GBP/USD", None, "spot", "active",
     "Free plan serves 1H/1D (probed 2026-11-01). 2H/4H are built from 1H (native grid shifts with US DST)."),
    ("US30", "oanda", "US30_USD", None, "cfd", "unverified",
     "Not on Twelve Data's free plan (index symbol rejected; only ETFs listed, which are NOT the index). "
     "Needs a free OANDA practice-account token in OANDA_API_TOKEN. Broker CFD prices, not exchange index prices."),
    ("USOIL", "oanda", "WTICO_USD", None, "cfd", "unverified",
     "WTI crude CFD via OANDA (needs OANDA_API_TOKEN). Not NYMEX CL futures - do not substitute."),
]
