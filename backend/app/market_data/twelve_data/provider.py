import threading
import time as _time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx

from app.core.exceptions import ProviderError, ProviderNotConfigured, UnsupportedError
from app.market_data.base import MarketDataProvider, ProviderInstrumentInfo
from app.market_data.timeframes import TIMEFRAMES, UTC_ANCHOR, bucket_end
from app.market_data.types import Candle, ProviderMetadata, Quote

MAX_OUTPUT = 5000
MINUTE_WAIT_S = 62.0
FREE_MIN_INTERVAL_S = 7.6  # free plan: 8 API credits / minute


class TwelveDataProvider(MarketDataProvider):
    """Twelve Data REST adapter. Free ("Basic") plan only; requires TWELVE_DATA_API_KEY.

    Which symbols/timeframes are served on the free plan must be confirmed per account via
    `check_data_coverage` - nothing is assumed here. Volume is not provided for FX/metals.
    """

    code = "twelve_data"
    MINUTE_WAIT_S = MINUTE_WAIT_S
    # 2H and 4H are deliberately NOT native: Twelve Data's grid for them shifts by one hour with US daylight saving
    # (verified live on XAU/USD and GBP/USD), so they are built from 1H on our UTC grid instead.
    native_timeframes = {c: t.twelve_data for c, t in TIMEFRAMES.items() if t.twelve_data and c not in ("2H", "4H")}

    def __init__(self, api_key: str | None, base_url: str = "https://api.twelvedata.com",
                 client: httpx.Client | None = None, min_interval_s: float = FREE_MIN_INTERVAL_S):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=30.0)
        self._min_interval = min_interval_s
        self._last_call = 0.0
        self._lock = threading.Lock()
        self.last_quota: dict = {}
        self._sleep = _time.sleep

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict, _retried: bool = False):
        if not self.api_key:
            raise ProviderNotConfigured("TWELVE_DATA_API_KEY is not set")
        with self._lock:
            wait = self._min_interval - (_time.monotonic() - self._last_call)
            if wait > 0:
                self._sleep(wait)
            self._last_call = _time.monotonic()
        resp = None
        for attempt in range(4):  # transient DNS/connect failures are common on home networks: retry with backoff
            try:
                resp = self._client.get(self.base_url + path, params={**params, "apikey": self.api_key})
                break
            except httpx.HTTPError as exc:
                if attempt == 3:
                    raise ProviderError(f"Twelve Data request failed: {exc.__class__.__name__}") from exc
                self._sleep((2.0, 5.0, 10.0)[attempt])
        self.last_quota = {k: resp.headers.get(k) for k in ("api-credits-used", "api-credits-left") if k in resp.headers}
        try:
            body = resp.json()
        except ValueError as exc:
            raise ProviderError(f"Twelve Data returned a non-JSON response (HTTP {resp.status_code})") from exc
        err = isinstance(body, dict) and body.get("status") == "error"
        code = body.get("code") if err else None
        msg = self._scrub(body.get("message", "unknown error") if err else "")
        http = resp.status_code
        if http in (401, 403) or code in (401, 403):
            raise ProviderError("Twelve Data rejected the API key (invalid, expired or not permitted for this endpoint)",
                                details={"code": code or http})
        if http == 429 or code == 429:
            per_minute = "minute" in msg.lower() or "minute" in self._scrub(resp.text).lower()
            if per_minute and not _retried:  # free plan: 8 credits/minute - wait for the window to roll, retry once
                self._sleep(self.MINUTE_WAIT_S)
                return self._get(path, params, _retried=True)
            raise ProviderError(f"Twelve Data credit limit reached ({'per-minute' if per_minute else 'daily/plan'}): {msg}",
                                details={"scope": "minute" if per_minute else "day", "quota": self.last_quota})
        if code == 404 or http == 404:
            raise UnsupportedError(f"Twelve Data has no such symbol/endpoint: {msg}")
        if err:
            if code == 400 and "plan" in msg.lower():
                raise UnsupportedError(f"Not available on current Twelve Data plan: {msg}")
            raise ProviderError(f"Twelve Data error {code}: {msg}")
        if http >= 500:
            raise ProviderError(f"Twelve Data server error (HTTP {http})")
        return body

    def _scrub(self, text: str) -> str:
        """Provider messages are shown to users and logged: never let the API key travel with them."""
        return text.replace(self.api_key, "***") if self.api_key else text

    def get_quota(self) -> dict:
        """Current usage vs plan limits (`/api_usage`). Returns the provider's own numbers, unmodified."""
        return self._get("/api_usage", {})

    def get_instruments(self, symbols: list[str] | None = None) -> list[ProviderInstrumentInfo]:
        out: list[ProviderInstrumentInfo] = []
        for s in symbols or []:
            body = self._get("/symbol_search", {"symbol": s, "outputsize": 5})
            for d in body.get("data", []):
                out.append(ProviderInstrumentInfo(symbol=d.get("symbol"), name=d.get("instrument_name"),
                                                  status="listed", raw=d))
        return out

    def get_candles(self, symbol, timeframe, start=None, end=None, limit=None) -> list[Candle]:
        """Candles in [start, end] (UTC), ascending. Twelve Data returns the MOST RECENT `outputsize` points of the
        requested range whatever `order` says (verified against the live API), so long ranges are fetched
        backwards: newest page first, then the page ending just before it, until the range is covered."""
        interval = self.native_timeframes.get(timeframe)
        if not interval:
            raise UnsupportedError(f"Twelve Data has no native {timeframe} series; aggregate from a lower timeframe")
        now = datetime.now(timezone.utc)
        pages: list[list[Candle]] = []
        total = 0
        cursor_end = end
        while True:
            size = min(limit or MAX_OUTPUT, MAX_OUTPUT)
            params: dict = {"symbol": symbol, "interval": interval, "timezone": "UTC", "outputsize": size}
            if start:
                params["start_date"] = start.strftime("%Y-%m-%d %H:%M:%S")
            if cursor_end:
                params["end_date"] = cursor_end.strftime("%Y-%m-%d %H:%M:%S")
            values = self._get("/time_series", params).get("values", [])
            batch = sorted((self._parse(v, timeframe, now) for v in values), key=lambda c: c.ts)
            if not batch:
                break
            pages.insert(0, batch)
            total += len(batch)
            if len(values) < size or (limit and total >= limit):
                break
            cursor_end = batch[0].ts - timedelta(seconds=1)
        out = [c for page in pages for c in page]
        return out[-limit:] if limit else out

    @staticmethod
    def _parse(v: dict, timeframe: str, now: datetime) -> Candle:
        raw = v["datetime"]
        fmt = "%Y-%m-%d %H:%M:%S" if " " in raw else "%Y-%m-%d"
        ts = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        vol = v.get("volume")
        end = bucket_end(ts, TIMEFRAMES[timeframe], UTC_ANCHOR)
        return Candle(
            ts=ts, open=Decimal(v["open"]), high=Decimal(v["high"]), low=Decimal(v["low"]), close=Decimal(v["close"]),
            volume=Decimal(vol) if vol not in (None, "", "0") else None,
            volume_type="tick" if vol not in (None, "", "0") else "none",
            complete=end <= now,
        )

    def get_latest_quote(self, symbol: str) -> Quote:
        body = self._get("/price", {"symbol": symbol})
        return Quote(symbol=symbol, price=Decimal(str(body["price"])), ts=datetime.now(timezone.utc),
                     provider=self.code)

    def get_market_status(self, symbol: str) -> dict:
        body = self._get("/quote", {"symbol": symbol})
        return {"open": bool(body.get("is_market_open")), "kind": "provider_reported",
                "exchange": body.get("exchange"), "provider_status": "ok"}

    def get_provider_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            code=self.code, name="Twelve Data (Basic / free plan)", base_url=self.base_url,
            requires_api_key=True, configured=self.is_configured(),
            free_plan={
                "price": "free tier (Basic)", "auth": "API key (TWELVE_DATA_API_KEY)",
                "rate_limit": "8 API credits / minute, ~800 / day (verify in your dashboard)",
                "history": "up to 5000 points per request; depth varies by instrument/plan - probe with check_data_coverage",
                "timeframes": sorted(self.native_timeframes),
                "caveat": "Availability of XAU/USD, indices and commodities on the free plan is NOT assumed; "
                          "it is probed at runtime.",
            },
            licensing="Twelve Data terms: free plan data is for personal use; display/redistribution restrictions "
                      "apply. Review https://twelvedata.com/terms before any commercial use.",
            docs_url="https://twelvedata.com/docs", signup_url="https://twelvedata.com/pricing",
        )

    def check_data_coverage(self, symbol: str, timeframe: str, max_pages: int = 4) -> dict:
        """What this plan really serves. Latest candle = one small request. Earliest = walk backwards page by page
        (<= max_pages requests); if the budget runs out first, `earliest_is_lower_bound` is True."""
        try:
            latest = self.get_candles(symbol, timeframe, limit=2)
            earliest, pages, floor = None, 0, True
            interval = self.native_timeframes[timeframe]
            cursor_end = latest[-1].ts if latest else None
            while cursor_end is not None and pages < max_pages:
                body = self._get("/time_series", {"symbol": symbol, "interval": interval, "timezone": "UTC",
                                                  "outputsize": MAX_OUTPUT, "end_date": cursor_end.strftime("%Y-%m-%d %H:%M:%S")})
                vals = body.get("values", [])
                pages += 1
                if not vals:
                    floor = False
                    break
                earliest = self._parse(vals[-1], timeframe, datetime.now(timezone.utc)).ts  # DESC: last = oldest
                if len(vals) < MAX_OUTPUT:
                    floor = False
                    break
                cursor_end = earliest - timedelta(seconds=1)
        except (UnsupportedError, ProviderError) as exc:
            return {"symbol": symbol, "timeframe": timeframe, "available": False, "error": exc.message}
        return {
            "symbol": symbol, "timeframe": timeframe, "available": bool(latest),
            "earliest": earliest.isoformat() if earliest else None, "earliest_is_lower_bound": bool(earliest) and floor,
            "latest": latest[-1].ts.isoformat() if latest else None,
            "has_volume": any(c.volume is not None for c in latest), "history_pages_walked": pages,
        }
