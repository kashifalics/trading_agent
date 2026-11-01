"""BiQuote adapter (https://biquote.io, free public REST + SignalR; no API key).

Everything here follows the published API reference and the behaviour verified live on 2026-11-01
(docs/BIQUOTE_PROVIDER_EVALUATION.md). Key facts the code depends on:
  * OHLC: GET /api/{symbol}/ohlc?interval=&limit=&from=&to= ; valid intervals are exactly 1m 5m 15m 30m 1h 4h 1d. Anything else is HTTP 400 with
    `validIntervals`; case is ignored, so the string "1M" is silently ONE MINUTE (never monthly) - this adapter therefore never sends it.
  * Bars arrive newest-first, `limit=N` yields N closed bars + the in-progress bar (`isOpen: true`, which is never reported as complete).
  * History is a fixed retention window per interval (about 300 x 1m, 289 x 5m, 169 x 1h, 181 x 4h, 500 x 1d), not the "up to 2000 bars" the docs imply.
  * An unknown symbol answers HTTP 200 with an empty bar list (ticks answer 404).
  * Prices are indicative MT5 broker CFD quotes for FX/metals/indices (or aggregated venue prices for the `*USDT` symbols); `volume` is always 0, `tickVolume` is
    the number of ticks. The terms forbid re-exposing the raw feed through a public API.
Never mixed with another provider's candles: every stored candle keeps provider_id = biquote.
"""
import asyncio
import contextlib
import json
import threading
import time as _time
from collections import deque
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote

import httpx

from app.core.exceptions import ProviderError, UnsupportedError
from app.market_data.base import MarketDataProvider, ProviderInstrumentInfo
from app.market_data.coverage.gaps import find_gaps
from app.market_data.types import Candle, ProviderMetadata, Quote

INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1H": "1h", "4H": "4h", "1D": "1d"}
MAX_LIMIT = 1000
RECORD_SEP = "\x1e"
RETRY_STATUS = {500, 502, 503, 504}
STALE_AFTER_S = 300.0  # the API itself calls a quote stale after five minutes (allowStale=false)


def _utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BiQuoteProvider(MarketDataProvider):
    """Sync adapter for the existing ingestion pipeline + async helpers (`aget_*`, `stream_ticks`)."""

    code = "biquote"
    fixed_retention = True  # serves a fixed window of the most recent bars (see module docstring); ingestion asks for all of it, not a relative window
    native_timeframes = dict(INTERVALS)  # 3m / 2H / 1W are built from these by the ingestion planner; 1M and above are NOT available

    def __init__(self, base_url: str = "https://biquote.io", client: httpx.Client | None = None, max_per_minute: int = 12_000,
                 timeout: float = 30.0, max_pages: int = 6):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)
        self._timeout = timeout
        self._max_per_minute = max_per_minute  # the documented anonymous limit is 15,000/min per IP; stay well under it
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()
        self._sleep = _time.sleep
        self._max_pages = max_pages
        self.last_rate_headers: dict = {}

    # ------------------------------------------------------------------------------------------ transport
    def is_configured(self) -> bool:
        return True  # public API: no key, no signup

    def _throttle(self) -> float:
        """Seconds to wait so that no more than `max_per_minute` requests are made in any rolling minute."""
        with self._lock:
            now = _time.monotonic()
            while self._stamps and now - self._stamps[0] > 60:
                self._stamps.popleft()
            wait = 0.0
            if len(self._stamps) >= self._max_per_minute:
                wait = max(0.0, 60 - (now - self._stamps[0]) + 0.05)
            self._stamps.append(now + wait)
            return wait

    def _decide(self, resp: httpx.Response, attempt: int, rate_retries: int) -> tuple[str, float, object]:
        """('ok', 0, body) | ('retry', wait_s, None). Raises for errors that retrying cannot fix."""
        self.last_rate_headers = {k: resp.headers.get(k) for k in ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset") if k in resp.headers}
        status = resp.status_code
        try:
            body = resp.json()
        except ValueError:
            body = None
        msg = (body.get("message") if isinstance(body, dict) else None) or resp.text[:120]
        if status == 429:
            wait = min(float(resp.headers.get("retry-after", 60) or 60), 65.0)
            if rate_retries >= 2:
                raise ProviderError("BiQuote rate limit (15,000 requests/min per IP) still exceeded after waiting", details={"retry_after": wait})
            return "rate", wait, None
        if status in RETRY_STATUS:
            if attempt >= 3:
                raise ProviderError(f"BiQuote server error (HTTP {status}); the market-data store may be unreachable", details={"status": status})
            return "retry", min(float(resp.headers.get("retry-after", 0) or 0) or (1.0, 2.0, 4.0)[attempt], 30.0), None
        if status == 400:
            valid = body.get("validIntervals") if isinstance(body, dict) else None
            raise UnsupportedError(f"BiQuote rejected the request: {msg}" + (f" (valid intervals: {', '.join(valid)})" if valid else ""))
        if status == 404:
            raise UnsupportedError(f"BiQuote has no such symbol / no recent quote: {msg}")
        if status != 200 or body is None:
            raise ProviderError(f"BiQuote returned an unexpected response (HTTP {status})")
        return "ok", 0.0, body

    def _get(self, path: str, params: dict | list | None = None):
        attempt = rate = 0
        while True:
            self._sleep(self._throttle())
            try:
                resp = self._client.get(self.base_url + path, params=params)
            except httpx.HTTPError as exc:
                if attempt >= 3:
                    raise ProviderError(f"BiQuote request failed: {exc.__class__.__name__}") from exc
                self._sleep((1.0, 2.0, 4.0)[attempt])
                attempt += 1
                continue
            kind, wait, body = self._decide(resp, attempt, rate)
            if kind == "ok":
                return body
            self._sleep(wait)
            if kind == "rate":
                rate += 1
            else:
                attempt += 1

    async def _aget(self, client: httpx.AsyncClient, path: str, params: dict | list | None = None):
        attempt = rate = 0
        while True:
            await asyncio.sleep(self._throttle())
            try:
                resp = await client.get(self.base_url + path, params=params)
            except httpx.HTTPError as exc:
                if attempt >= 3:
                    raise ProviderError(f"BiQuote request failed: {exc.__class__.__name__}") from exc
                await asyncio.sleep((1.0, 2.0, 4.0)[attempt])
                attempt += 1
                continue
            kind, wait, body = self._decide(resp, attempt, rate)
            if kind == "ok":
                return body
            await asyncio.sleep(wait)
            if kind == "rate":
                rate += 1
            else:
                attempt += 1

    # ------------------------------------------------------------------------------------------ parsing
    @staticmethod
    def interval_for(timeframe: str) -> str:
        iv = INTERVALS.get(timeframe)
        if not iv:
            raise UnsupportedError(f"BiQuote has no native {timeframe} series (native: {', '.join(INTERVALS)}); "
                                   f"3m/2H/1W are built from lower timeframes and 1M and above are unavailable. "
                                   f"Note: BiQuote treats '1M' as ONE MINUTE, so it is never sent.")
        return iv

    @staticmethod
    def parse_bars(body: dict) -> list[Candle]:
        """Normalise an OHLC response: UTC timestamps, Decimal prices, `isOpen` -> complete=False, duplicates dropped, ascending."""
        seen: dict[datetime, Candle] = {}
        for b in body.get("bars", []) or []:
            try:
                ts = _utc(b["openTime"])
                tv = b.get("tickVolume")
                seen[ts] = Candle(ts=ts, open=Decimal(str(b["open"])), high=Decimal(str(b["high"])), low=Decimal(str(b["low"])),
                                  close=Decimal(str(b["close"])), volume=Decimal(str(tv)) if tv else None,
                                  complete=not bool(b.get("isOpen")), volume_type="tick" if tv else "none",
                                  meta={"is_open": bool(b.get("isOpen"))})
            except (KeyError, ValueError, ArithmeticError):
                continue  # an unparseable bar is skipped, never repaired or invented
        return [seen[k] for k in sorted(seen)]

    def _ohlc_params(self, timeframe, start, end, page_limit, cursor_end) -> dict:
        p: dict = {"interval": self.interval_for(timeframe), "limit": page_limit}
        if start:
            p["from"] = _iso(start)
        if cursor_end or end:
            p["to"] = _iso(cursor_end or end)
        return p

    # ------------------------------------------------------------------------------------------ MarketDataProvider
    def get_candles(self, symbol, timeframe, start=None, end=None, limit=None) -> list[Candle]:
        page_limit = min(limit or MAX_LIMIT, MAX_LIMIT)
        out: dict[datetime, Candle] = {}
        cursor_end = None
        for _ in range(self._max_pages):
            body = self._get(f"/api/{quote(symbol, safe='')}/ohlc", self._ohlc_params(timeframe, start, end, page_limit, cursor_end))
            raw = body.get("bars", []) if isinstance(body, dict) else []
            page = self.parse_bars(body) if isinstance(body, dict) else []
            new = [c for c in page if c.ts not in out]
            for c in page:
                out[c.ts] = c
            if not new or len(raw) <= page_limit:  # a short page means the retention window is exhausted
                break
            cursor_end = min(c.ts for c in page) - timedelta(seconds=1)
        res = [out[k] for k in sorted(out) if (not start or k >= start) and (not end or k <= end)]
        return res[-limit:] if limit else res

    def get_latest_quote(self, symbol: str) -> Quote:
        """Mid price of the latest tick. A closed market returns its LAST price flagged `is_delayed` (never presented as live)."""
        d = self._get(f"/api/{quote(symbol, safe='')}")
        return self._quote(d)

    @staticmethod
    def _quote(d: dict) -> Quote:
        ts = _utc(d.get("lastQuoteAt") or d["timestamp"])
        return Quote(symbol=d["symbol"], price=Decimal(str(d["mid"])), ts=ts, provider="biquote", bid=Decimal(str(d["bid"])),
                     ask=Decimal(str(d["ask"])), is_delayed=bool(d.get("stale")) or d.get("marketState") == "closed")

    def get_market_status(self, symbol: str) -> dict:
        d = self._get(f"/api/{quote(symbol, safe='')}")
        return {"open": d.get("marketState") == "open", "kind": "provider_reported", "exchange": None, "provider_status": "ok",
                "quote_age_seconds": d.get("quoteAgeSeconds"), "source": d.get("source")}

    def get_instruments(self, symbols: list[str] | None = None) -> list[ProviderInstrumentInfo]:
        out = []
        for s in symbols or []:
            try:
                d = self._get(f"/api/symbols/{quote(s, safe='')}")
            except UnsupportedError:
                continue
            out.append(ProviderInstrumentInfo(symbol=d["name"], name=d.get("description"), status="has_data" if d.get("hasData") else "listed",
                                              price_precision=d.get("digits"), tick_size=Decimal(str(d["tickSize"])) if d.get("tickSize") else None, raw=d))
        return out

    def get_provider_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            code=self.code, name="BiQuote (free public API)", base_url=self.base_url, requires_api_key=False, configured=True,
            free_plan={"price": "free, no key or signup", "auth": "none", "rate_limit": "15,000 requests/min per IP (anonymous); WebSocket stream unmetered",
                       "history": "fixed retention window: ~300 x 1m, 289 x 5m, 193 x 15m/30m, 169 x 1h, 181 x 4h, 500 x 1d; no weekly/monthly",
                       "timeframes": sorted(self.native_timeframes), "caveat": "indicative broker (MT5 CFD) quotes; volume is always 0 (tick count only); no SLA"},
            licensing="biquote.io/terms.html: may be used in your own product, displayed to your users and stored for the product; derived analytics are yours. "
                      "You may NOT resell or redistribute the raw feed (no public API / bulk download / competing data service) nor present it as exchange-licensed data. No SLA.",
            docs_url="https://biquote.io/docs/", signup_url=None)

    def check_data_coverage(self, symbol: str, timeframe: str, calendar: str = "continuous") -> dict:
        try:
            candles = self.get_candles(symbol, timeframe)
        except (UnsupportedError, ProviderError) as exc:
            return {"symbol": symbol, "timeframe": timeframe, "available": False, "error": exc.message}
        done = [c for c in candles if c.complete]
        gaps = find_gaps([c.ts for c in done], timeframe, calendar) if done else []
        return {"symbol": symbol, "timeframe": timeframe, "available": bool(candles), "n_candles": len(candles),
                "earliest": candles[0].ts.isoformat() if candles else None, "latest": candles[-1].ts.isoformat() if candles else None,
                "earliest_is_lower_bound": False, "latest_is_open_bar": bool(candles) and not candles[-1].complete, "has_volume": False,
                "has_tick_volume": any(c.volume for c in candles), "gaps": gaps[:20], "gap_count": len(gaps),
                "note": "history is a fixed retention window; an unknown symbol returns an empty list, not an error" if not candles else None}

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------------------------------ async helpers
    async def aget_candles(self, symbol, timeframe, start=None, end=None, limit=None, client: httpx.AsyncClient | None = None) -> list[Candle]:
        page_limit = min(limit or MAX_LIMIT, MAX_LIMIT)
        out: dict[datetime, Candle] = {}
        cursor_end = None
        async with contextlib.AsyncExitStack() as stack:
            c = client or await stack.enter_async_context(httpx.AsyncClient(timeout=self._timeout))
            for _ in range(self._max_pages):
                body = await self._aget(c, f"/api/{quote(symbol, safe='')}/ohlc", self._ohlc_params(timeframe, start, end, page_limit, cursor_end))
                raw = body.get("bars", []) if isinstance(body, dict) else []
                page = self.parse_bars(body) if isinstance(body, dict) else []
                new = [x for x in page if x.ts not in out]
                for x in page:
                    out[x.ts] = x
                if not new or len(raw) <= page_limit:
                    break
                cursor_end = min(x.ts for x in page) - timedelta(seconds=1)
        res = [out[k] for k in sorted(out) if (not start or k >= start) and (not end or k <= end)]
        return res[-limit:] if limit else res

    async def aget_latest_quotes(self, symbols: list[str], client: httpx.AsyncClient | None = None) -> dict[str, Quote]:
        """One batched request per 50 symbols (`symbols` is a REPEATED parameter; commas do not work). Absent symbols are simply missing."""
        res: dict[str, Quote] = {}
        async with contextlib.AsyncExitStack() as stack:
            c = client or await stack.enter_async_context(httpx.AsyncClient(timeout=self._timeout))
            for i in range(0, len(symbols), 50):
                body = await self._aget(c, "/api/latest", [("symbols", s) for s in symbols[i:i + 50]])
                for k, d in (body or {}).items():
                    res[k] = self._quote(d)
        return res

    async def stream_ticks(self, symbols: list[str], reconnect: bool = True, max_backoff_s: float = 30.0) -> AsyncIterator[dict]:
        """Live ticks over the SignalR hub /hubs/tick (WebSocket, unmetered, no polling). Yields dicts:
        {"kind": "tick", symbol, bid, ask, mid, ts, source, market_state, stale, age_seconds} and {"kind": "state", states} (one per Subscribe).
        The first tick per symbol is a SEED of the last known quote (a closed market therefore still yields one stale tick). Ticks carry no
        open/closed flag, so `stale` is derived from the tick's age (> 300 s) and `market_state` from the latest state frame ("unknown" before it arrives).
        Reconnects with exponential backoff; the caller stops by breaking out of the loop."""
        import websockets  # imported lazily: only needed for streaming

        backoff = 1.0
        ws_url = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        while True:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as c:
                    neg = (await c.post(f"{self.base_url}/hubs/tick/negotiate", params={"negotiateVersion": 1})).json()
                token = neg.get("connectionToken") or neg.get("connectionId")
                async with websockets.connect(f"{ws_url}/hubs/tick?id={quote(token, safe='')}", open_timeout=20, max_size=2**22) as ws:
                    await ws.send(json.dumps({"protocol": "json", "version": 1}) + RECORD_SEP)
                    await asyncio.wait_for(ws.recv(), 10)
                    await ws.send(json.dumps({"type": 1, "target": "Subscribe", "arguments": [symbols], "invocationId": "1"}) + RECORD_SEP)
                    backoff = 1.0

                    async def keepalive():
                        while True:
                            await asyncio.sleep(10)
                            await ws.send(json.dumps({"type": 6}) + RECORD_SEP)

                    ka = asyncio.create_task(keepalive())
                    market_state: dict[str, str] = {}  # the hub reports open/closed only in ReceiveSubscriptionState frames, never inside a tick
                    try:
                        async for msg in ws:
                            for frame in str(msg).split(RECORD_SEP):
                                if not frame:
                                    continue
                                f = json.loads(frame)
                                if f.get("type") == 1 and f.get("target") == "ReceiveTick":
                                    t = f["arguments"][0]
                                    ts = _utc(t["timestamp"])
                                    age = (datetime.now(timezone.utc) - ts).total_seconds()
                                    yield {"kind": "tick", "symbol": t["symbol"], "bid": Decimal(str(t["bid"])), "ask": Decimal(str(t["ask"])),
                                           "mid": Decimal(str(t["mid"])), "ts": ts, "source": t.get("source"),
                                           "market_state": t.get("marketState") or market_state.get(t["symbol"], "unknown"),
                                           "stale": bool(t["stale"]) if "stale" in t else age > STALE_AFTER_S, "age_seconds": age}
                                elif f.get("type") == 1 and f.get("target") == "ReceiveSubscriptionState":
                                    market_state.update({x["symbol"]: x["state"] for x in f["arguments"][0]})
                                    yield {"kind": "state", "states": f["arguments"][0]}
                                elif f.get("type") == 7:  # close message from the server
                                    raise ConnectionError(f.get("error") or "server closed the connection")
                    finally:
                        ka.cancel()
            except (OSError, ConnectionError, asyncio.TimeoutError, httpx.HTTPError, websockets.WebSocketException) as exc:
                if not reconnect:
                    raise ProviderError(f"BiQuote stream failed: {exc.__class__.__name__}") from exc
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff_s)
