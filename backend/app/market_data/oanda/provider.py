import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx

from app.core.exceptions import ProviderError, ProviderNotConfigured, UnsupportedError
from app.market_data.base import MarketDataProvider, ProviderInstrumentInfo
from app.market_data.types import Candle, ProviderMetadata, Quote

MAX_COUNT = 5000
PRACTICE_URL = "https://api-fxpractice.oanda.com"
# Our timeframe -> OANDA granularity. With dailyAlignment=0 / alignmentTimezone=UTC (set on every request) H2/H4/D/W
# buckets sit on the same UTC grid the platform uses, and weekly candles start on Monday.
GRANULARITY = {"1m": "M1", "5m": "M5", "15m": "M15", "30m": "M30", "1H": "H1", "2H": "H2", "4H": "H4", "1D": "D",
               "1W": "W", "1M": "M"}
ALIGN = {"dailyAlignment": 0, "alignmentTimezone": "UTC", "weeklyAlignment": "Monday"}


def _ts(raw: str) -> datetime:
    """OANDA stamps carry nanoseconds ('2024-01-02T10:00:00.000000000Z'); whole seconds are all we need."""
    return datetime.fromisoformat(raw[:19] + "+00:00").astimezone(timezone.utc)


class OandaProvider(MarketDataProvider):
    """OANDA v20 REST candles (fxTrade Practice = free demo account; personal use). Needs OANDA_API_TOKEN.

    Index/metal/FX/oil CFDs: US30_USD, XAU_USD, GBP_USD, WTICO_USD... These are broker CFD prices, not exchange
    prices; they are stored under the `oanda` provider and never mixed with other providers' candles.
    Read-only: only market-data endpoints are called, never order or account endpoints."""

    code = "oanda"
    native_timeframes = dict(GRANULARITY)
    BACKOFF = (2.0, 5.0, 15.0)

    def __init__(self, token: str | None, base_url: str = PRACTICE_URL, client: httpx.Client | None = None,
                 min_interval_s: float = 0.05):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=30.0)
        self.min_interval_s = min_interval_s
        self._last_call = 0.0
        self._sleep = time.sleep

    def is_configured(self) -> bool:
        return bool(self.token)

    def _scrub(self, text: str) -> str:
        return text.replace(self.token, "***") if self.token else text

    def _get(self, path: str, params: dict):
        if not self.token:
            raise ProviderNotConfigured("OANDA_API_TOKEN is not set (free practice-account token: see docs/MARKET_DATA_PROVIDERS.md)")
        for attempt in range(len(self.BACKOFF) + 1):
            since = time.monotonic() - self._last_call
            if since < self.min_interval_s:
                self._sleep(self.min_interval_s - since)
            self._last_call = time.monotonic()
            try:
                resp = self._client.get(self.base_url + path, params=params,
                                        headers={"Authorization": f"Bearer {self.token}", "Accept-Datetime-Format": "RFC3339"})
            except httpx.HTTPError as exc:
                if attempt >= len(self.BACKOFF):
                    raise ProviderError(f"OANDA request failed: {exc.__class__.__name__}") from exc
                self._sleep(self.BACKOFF[attempt])
                continue
            if resp.status_code in (401, 403):
                raise ProviderError("OANDA rejected the API token (invalid, expired, or for a different environment)",
                                    details={"status": resp.status_code})
            if resp.status_code in (400, 404):
                msg = ""
                try:
                    msg = self._scrub(resp.json().get("errorMessage", ""))
                except ValueError:
                    pass
                raise UnsupportedError(f"OANDA has no such instrument/parameters: {msg}".strip())
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt >= len(self.BACKOFF):
                    raise ProviderError(f"OANDA {'rate limit' if resp.status_code == 429 else f'server error {resp.status_code}'}")
                self._sleep(self.BACKOFF[attempt])
                continue
            return resp.json()
        raise ProviderError("OANDA request failed")  # pragma: no cover

    @staticmethod
    def _parse(c: dict) -> Candle:
        m = c["mid"]
        return Candle(ts=_ts(c["time"]), open=Decimal(m["o"]), high=Decimal(m["h"]), low=Decimal(m["l"]), close=Decimal(m["c"]),
                      volume=Decimal(c["volume"]) if c.get("volume") is not None else None, volume_type="tick",
                      complete=bool(c.get("complete")))

    def get_candles(self, symbol, timeframe, start=None, end=None, limit=None) -> list[Candle]:
        gran = GRANULARITY.get(timeframe)
        if not gran:
            raise UnsupportedError(f"OANDA has no native {timeframe}; aggregate from a lower timeframe")
        path = f"/v3/instruments/{symbol}/candles"
        base = {"price": "M", "granularity": gran, **ALIGN}
        if start is None:  # most recent `limit` candles
            body = self._get(path, {**base, "count": min(limit or 500, MAX_COUNT)})
            return [self._parse(c) for c in body.get("candles", [])]
        out: list[Candle] = []
        cursor = start
        while True:
            body = self._get(path, {**base, "from": cursor.strftime("%Y-%m-%dT%H:%M:%SZ"), "count": MAX_COUNT})
            batch = [self._parse(c) for c in body.get("candles", [])]
            if end is not None:
                batch = [c for c in batch if c.ts <= end]
            if not batch:
                break
            out.extend(batch)
            if len(body.get("candles", [])) < MAX_COUNT or (end is not None and batch[-1].ts >= end):
                break
            if limit and len(out) >= limit:
                break
            cursor = batch[-1].ts + timedelta(seconds=1)
        # `from` is inclusive of the candle that contains it; drop a duplicate boundary candle
        seen, uniq = set(), []
        for c in out:
            if c.ts not in seen:
                seen.add(c.ts)
                uniq.append(c)
        return uniq[:limit] if limit else uniq

    def get_instruments(self, symbols: list[str] | None = None) -> list[ProviderInstrumentInfo]:
        out = []
        for s in symbols or []:
            try:
                got = self._get(f"/v3/instruments/{s}/candles", {"price": "M", "granularity": "D", "count": 1})
                out.append(ProviderInstrumentInfo(symbol=got.get("instrument", s), name=got.get("instrument", s), status="listed"))
            except UnsupportedError:
                continue
        return out

    def get_latest_quote(self, symbol: str) -> Quote:
        body = self._get(f"/v3/instruments/{symbol}/candles", {"price": "BA", "granularity": "M1", "count": 1})
        cs = body.get("candles", [])
        if not cs:
            raise ProviderError(f"OANDA returned no recent price for {symbol}")
        bid, ask = Decimal(cs[-1]["bid"]["c"]), Decimal(cs[-1]["ask"]["c"])
        return Quote(symbol=symbol, price=(bid + ask) / 2, bid=bid, ask=ask, ts=datetime.now(timezone.utc), provider=self.code)

    def get_market_status(self, symbol: str) -> dict:
        cs = self._get(f"/v3/instruments/{symbol}/candles", {"price": "M", "granularity": "M1", "count": 1}).get("candles", [])
        age = (datetime.now(timezone.utc) - _ts(cs[-1]["time"])).total_seconds() if cs else None
        return {"open": age is not None and age < 300, "kind": "inferred_from_last_candle", "last_candle_age_s": age,
                "provider_status": "ok"}

    def get_provider_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            code=self.code, name="OANDA v20 (fxTrade Practice, free demo)", base_url=self.base_url,
            requires_api_key=True, configured=self.is_configured(),
            free_plan={
                "price": "free demo (practice) account", "auth": "API token (OANDA_API_TOKEN), read-only use here",
                "rate_limit": "documented at ~120 requests/second; candles <= 5,000 per request",
                "timeframes": sorted(self.native_timeframes), "history": "probed per instrument (check_data_coverage)",
                "caveat": "Broker CFD prices (not exchange index/futures prices). Daily/weekly buckets requested with "
                          "UTC alignment so they match the platform grid.",
            },
            licensing="OANDA demo-account/API terms: personal, non-commercial use; no redistribution of price data. "
                      "Review https://www.oanda.com/legal/ before any other use.",
            docs_url="https://developer.oanda.com/rest-live-v20/instrument-ep/",
            signup_url="https://www.oanda.com/register/#/sign-up/demo")

    def check_data_coverage(self, symbol: str, timeframe: str) -> dict:
        try:
            latest = self.get_candles(symbol, timeframe, limit=2)
            first = self._get(f"/v3/instruments/{symbol}/candles",
                              {"price": "M", "granularity": GRANULARITY[timeframe], **ALIGN, "from": "2000-01-01T00:00:00Z", "count": 1})
            earliest = _ts(first["candles"][0]["time"]) if first.get("candles") else None
        except (UnsupportedError, ProviderError) as exc:
            return {"symbol": symbol, "timeframe": timeframe, "available": False, "error": exc.message}
        return {"symbol": symbol, "timeframe": timeframe, "available": bool(latest),
                "earliest": earliest.isoformat() if earliest else None, "earliest_is_lower_bound": False,
                "latest": latest[-1].ts.isoformat() if latest else None,
                "has_volume": any(c.volume is not None for c in latest)}
