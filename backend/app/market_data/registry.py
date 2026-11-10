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
from app.market_data.biquote.provider import BiQuoteProvider
from app.market_data.oanda.provider import OandaProvider
from app.market_data.twelve_data.provider import TwelveDataProvider

PROVIDER_CODES = ["binance", "twelve_data", "oanda", "biquote"]


def get_provider(code: str, settings: Settings | None = None) -> MarketDataProvider:
    s = settings or get_settings()
    if code == "binance":
        return BinanceProvider(s.binance_api_base_url)
    if code == "twelve_data":
        return TwelveDataProvider(s.twelve_data_api_key, s.twelve_data_base_url)
    if code == "oanda":
        return OandaProvider(s.oanda_api_token, s.oanda_base_url)
    if code == "biquote":
        return BiQuoteProvider(s.biquote_base_url)
    raise NotFoundError(f"No adapter implemented for provider '{code}'")


SEED_PROVIDERS = [
    {"code": "binance", "name": "Binance Spot (public market data)", "base_url": "https://api.binance.com",
     "requires_api_key": False, "is_enabled": True,
     "meta": {"docs": "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints"}},
    {"code": "twelve_data", "name": "Twelve Data (free plan)", "base_url": "https://api.twelvedata.com",
     "requires_api_key": True, "is_enabled": True, "meta": {"docs": "https://twelvedata.com/docs"}},
    {"code": "oanda", "name": "OANDA v20 (fxTrade Practice, free demo)", "base_url": "https://api-fxpractice.oanda.com",
     "requires_api_key": True, "is_enabled": True, "meta": {"docs": "https://developer.oanda.com/rest-live-v20/instrument-ep/"}},
    {"code": "biquote", "name": "BiQuote (free public API, indicative broker quotes)", "base_url": "https://biquote.io",
     "requires_api_key": False, "is_enabled": True, "meta": {"docs": "https://biquote.io/docs/", "terms": "https://biquote.io/terms.html"}},
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
    {"canonical_symbol": "EURUSD", "name": "Euro / US Dollar (spot)", "asset_class": "forex",
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
    # BiQuote (docs/BIQUOTE_PROVIDER_EVALUATION.md): MT5 broker-CFD quotes, no key. Shallow fixed history (1h ~7 days, 4h ~30 days, 1d ~500 bars), no 1W/1M.
    ("BTCUSDT", "biquote", "BTCUSDT", None, "spot", "active",
     "Aggregated-venue feed whose closes match Binance spot (median diff 0.0 bp): not an independent source. History is ~7 days of 1H (Binance has years); "
     "live stream verified (about 1 tick/s). Default source via PREFERRED_PROVIDER=biquote; Binance stays registered (provider=binance)."),
    ("XAUUSD", "biquote", "XAUUSD", None, "cfd", "active",
     "MT5 broker CFD (OTC gold, contract 100). Candles verified 2026-11-01; live stream NOT yet verified in market hours; 1h history ~7 days only. "
     "Default source via PREFERRED_PROVIDER=biquote; Twelve Data stays registered (provider=twelve_data)."),
    ("US30", "biquote", "US30", None, "cfd", "active",
     "MT5 broker CFD 'US Wall Street 30 Index'. Candles verified 2026-11-01 (1m..1d, valid OHLC); live stream NOT yet verified in market hours (market was closed). "
     "Indicative CFD price, not the exchange index. Default source via PREFERRED_PROVIDER=biquote."),
    ("EURUSD", "biquote", "EURUSD", None, "cfd", "active",
     "MT5 broker FX quotes, no key. Live-verified 2026-11-10 in market hours: quote (bid/ask, 0.6 pip spread) and 15m/1H/4H/1D candles "
     "(0 invalid OHLC; 1H ~7 days, 4H ~6 weeks, 1D 500 bars). Default source via PREFERRED_PROVIDER=biquote."),
    ("GBPUSD", "biquote", "GBPUSD", None, "cfd", "active",
     "MT5 broker FX quotes, no key. Live-verified 2026-11-10 in market hours: quote and 15m/1H/4H/1D candles (0 invalid OHLC). "
     "Default source via PREFERRED_PROVIDER=biquote; Twelve Data stays registered (provider=twelve_data)."),
    ("EURUSD", "twelve_data", "EUR/USD", None, "spot", "unverified",
     "Same plan rules as GBP/USD are expected (1H/1D native) but not probed with a key: unverified."),
    ("USOIL", "biquote", "USOIL", None, "cfd", "active",
     "MT5 broker CFD 'Crude Oil' (about 0.8% below the aggregated WTI perpetual). Candles verified 2026-11-01; live stream NOT yet verified in market hours. "
     "Not NYMEX CL futures. Default source via PREFERRED_PROVIDER=biquote."),
]
