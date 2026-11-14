import time
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.core.exceptions import ProviderError, UnsupportedError
from app.market_data.base import MarketDataProvider, ProviderInstrumentInfo
from app.market_data.timeframes import TIMEFRAMES
from app.market_data.types import Candle, ProviderMetadata, Quote

KLINE_LIMIT = 1000


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


class BinanceProvider(MarketDataProvider):
    """Binance spot public market data (no API key, no account access)."""

    code = "binance"
    native_timeframes = {
        c: t.binance for c, t in TIMEFRAMES.items() if t.binance  # 1m..1M; 3M/6M/12M are aggregated
    }

    def __init__(self, base_url: str = "https://api.binance.com", client: httpx.Client | None = None,
                 min_interval_s: float = 0.12):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=20.0)
        self.min_interval_s = min_interval_s
        self._last_call = 0.0
        self.last_used_weight = 0
        self._sleep = time.sleep

    def is_configured(self) -> bool:
        return True

    #: seconds to wait before retry k (k=0,1,2) when no Retry-After header is given
    BACKOFF = (2.0, 5.0, 15.0)
    WEIGHT_SOFT_LIMIT = 1000  # of 1200 request-weight per minute: pause before reaching the hard limit

    def _get(self, path: str, params: dict | None = None):
        """GET with pacing and retries. 429 -> honour Retry-After and retry; 5xx/network -> backoff and retry;
        418 (IP banned) -> fail immediately (retrying makes the ban longer); other 4xx -> fail."""
        for attempt in range(len(self.BACKOFF) + 1):
            since = time.monotonic() - self._last_call
            if since < self.min_interval_s:
                self._sleep(self.min_interval_s - since)
            self._last_call = time.monotonic()
            retry_in: float | None = None
            try:
                resp = self._client.get(self.base_url + path, params=params)
            except httpx.HTTPError as exc:
                if attempt >= len(self.BACKOFF):
                    raise ProviderError(f"Binance request failed: {exc.__class__.__name__}") from exc
                self._sleep(self.BACKOFF[attempt])
                continue
            used = resp.headers.get("x-mbx-used-weight-1m")
            self.last_used_weight = int(used) if used and used.isdigit() else self.last_used_weight
            if self.last_used_weight >= self.WEIGHT_SOFT_LIMIT:
                self._sleep(20.0)  # let the 1-minute window drain
            if resp.status_code == 418:
                raise ProviderError("Binance has temporarily banned this IP (HTTP 418)",
                                    details={"retry_after": resp.headers.get("Retry-After")})
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt >= len(self.BACKOFF):
                    kind = "rate limit hit" if resp.status_code == 429 else f"HTTP {resp.status_code}"
                    raise ProviderError(f"Binance {kind}", details={"retry_after": resp.headers.get("Retry-After")})
                ra = resp.headers.get("Retry-After")
                retry_in = min(float(ra), 60.0) if ra and ra.replace(".", "", 1).isdigit() else self.BACKOFF[attempt]
                self._sleep(retry_in)
                continue
            if resp.status_code >= 400:
                raise ProviderError(f"Binance HTTP {resp.status_code}", details={"body": resp.text[:300]})
            return resp.json()
        raise ProviderError("Binance request failed")  # pragma: no cover

    def get_instruments(self, symbols: list[str] | None = None) -> list[ProviderInstrumentInfo]:
        data = self._get("/api/v3/exchangeInfo", {"symbols": _json_list(symbols)} if symbols else None)
        out = []
        for s in data.get("symbols", []):
            tick = next((f["tickSize"] for f in s.get("filters", []) if f.get("filterType") == "PRICE_FILTER"), None)
            out.append(ProviderInstrumentInfo(
                symbol=s["symbol"], name=f'{s.get("baseAsset")}/{s.get("quoteAsset")}', status=s.get("status"),
                price_precision=s.get("quotePrecision"), tick_size=Decimal(tick) if tick else None,
            ))
        return out

    def get_candles(self, symbol, timeframe, start=None, end=None, limit=None) -> list[Candle]:
        interval = self.native_timeframes.get(timeframe)
        if not interval:
            raise UnsupportedError(f"Binance has no native {timeframe} klines; aggregate from a lower timeframe")
        now_ms = _ms(datetime.now(timezone.utc))
        end_ms = _ms(end) if end else None
        cursor = _ms(start) if start else None
        out: list[Candle] = []
        while True:
            params: dict = {"symbol": symbol, "interval": interval, "limit": min(limit or KLINE_LIMIT, KLINE_LIMIT)}
            if cursor is not None:
                params["startTime"] = cursor
            if end_ms is not None:
                params["endTime"] = end_ms
            rows = self._get("/api/v3/klines", params)
            for r in rows:
                out.append(self._parse(r, now_ms))
            if limit and len(out) >= limit:
                return out[:limit] if start else out[-limit:]
            if len(rows) < params["limit"] or not rows:
                break
            cursor = rows[-1][0] + 1
            if start is None and end is None:
                break
        return out

    @staticmethod
    def _parse(r: list, now_ms: int) -> Candle:
        return Candle(
            ts=datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc),
            open=Decimal(r[1]), high=Decimal(r[2]), low=Decimal(r[3]), close=Decimal(r[4]),
            volume=Decimal(r[5]), volume_type="base",
            complete=int(r[6]) < now_ms,  # close time already passed
            meta={"quote_volume": r[7], "trades": r[8], "taker_buy_base": r[9]},
        )

    def get_latest_quote(self, symbol: str) -> Quote:
        d = self._get("/api/v3/ticker/bookTicker", {"symbol": symbol})
        bid, ask = Decimal(d["bidPrice"]), Decimal(d["askPrice"])
        return Quote(symbol=symbol, price=(bid + ask) / 2, bid=bid, ask=ask,
                     ts=datetime.now(timezone.utc), provider=self.code)

    def get_market_status(self, symbol: str) -> dict:
        infos = self.get_instruments([symbol])
        status = infos[0].status if infos else "UNKNOWN"
        return {"open": status == "TRADING", "kind": "continuous_24_7", "provider_status": status}

    def get_provider_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            code=self.code, name="Binance Spot (public market data)", base_url=self.base_url,
            requires_api_key=False, configured=True,
            free_plan={
                "price": "free", "auth": "none for public market data",
                "rate_limit": "1200 request weight / minute / IP (klines limit>=500 costs 2)",
                "history": "full exchange history per symbol since listing",
                "timeframes": sorted(self.native_timeframes), "max_candles_per_request": KLINE_LIMIT,
            },
            licensing="Binance Market Data terms apply. Public data is for personal/analysis use; "
                      "do not redistribute raw data commercially without checking Binance's terms.",
            docs_url="https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints",
        )

    def check_data_coverage(self, symbol: str, timeframe: str) -> dict:
        first = self.get_candles(symbol, timeframe, start=datetime(2010, 1, 1, tzinfo=timezone.utc), limit=1)
        latest = self.get_candles(symbol, timeframe, limit=1)
        return {
            "symbol": symbol, "timeframe": timeframe, "available": bool(first),
            "earliest": first[0].ts.isoformat() if first else None,
            "latest": latest[-1].ts.isoformat() if latest else None,
        }


def _json_list(symbols: list[str]) -> str:
    import json

    return json.dumps(symbols, separators=(",", ":"))
