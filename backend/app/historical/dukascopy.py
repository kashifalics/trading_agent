"""Dukascopy public datafeed: one LZMA file of 1-minute candles per instrument, UTC day and side (BID / ASK).

URL: https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YYYY}/{MM0}/{DD}/{SIDE}_candles_min_1.bi5 where MM0 is the month counted from 00.
Each record is 24 bytes, big-endian: seconds since 00:00 UTC (int32), open, close, low, high (int32 * point), volume (float32).
The feed is free and keyless but rate-limited (HTTP 429): requests are paced and backed off, never parallel.
"""
import lzma
import struct
import time
from datetime import date

import httpx

BASE = "https://datafeed.dukascopy.com/datafeed"
RECORD = struct.Struct(">5i1f")
USER_AGENT = "ai-trading-intelligence-historical/1.0"


def day_url(symbol: str, day: date, side: str) -> str:
    return f"{BASE}/{symbol}/{day.year}/{day.month - 1:02d}/{day.day:02d}/{side}_candles_min_1.bi5"


def decode(payload: bytes, point: float) -> list[tuple[int, float, float, float, float, float]]:
    """(seconds since 00:00 UTC, open, high, low, close, volume) per minute. An empty payload means no data that day."""
    if not payload:
        return []
    raw = lzma.decompress(payload)
    if len(raw) % RECORD.size:
        raise ValueError(f"corrupt candle file: {len(raw)} bytes is not a multiple of {RECORD.size}")
    out = []
    for off in range(0, len(raw), RECORD.size):
        t, o, c, lo, h, v = RECORD.unpack_from(raw, off)
        out.append((t, o * point, h * point, lo * point, c * point, float(v)))
    return out


class Client:
    """Paced, retrying fetcher. `fetch` returns the payload (b"" when Dukascopy has no file for that day)."""

    def __init__(self, min_interval: float = 1.0, max_backoff: float = 900.0, log=print):
        self.min_interval, self.max_backoff, self.log = min_interval, max_backoff, log
        self.http = httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        self._last = 0.0
        self.requests = self.throttled = 0

    def fetch(self, url: str) -> bytes:
        backoff = 60.0
        for attempt in range(12):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                r = self.http.get(url)
            except httpx.HTTPError as exc:
                self.log(f"network error ({exc.__class__.__name__}), retry in {backoff:.0f}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)
                continue
            if r.status_code == 200:
                return r.content
            if r.status_code == 404:
                return b""
            if r.status_code in (429, 500, 502, 503, 504):
                self.throttled += r.status_code == 429
                self.log(f"HTTP {r.status_code}, pausing {backoff:.0f}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)
                continue
            raise RuntimeError(f"unexpected HTTP {r.status_code} for {url}")
        raise RuntimeError(f"gave up after repeated failures: {url}")
