"""Resumable Dukascopy download into the immutable raw store.

Layout: raw/dukascopy/{SYMBOL}/{BID|ASK}/{YYYY}/{YYYY-MM-DD}.bi5, exactly as served. A day Dukascopy has no file for is recorded as
`{date}.none` so a restart never asks again (except for the last 7 days, which may still be published). Every file is written atomically
(temporary name, then rename), so an interrupted run resumes at the first missing day. Saturdays are skipped: FX and metals are closed
from Friday 17:00 to Sunday 17:00 New York time, so a Saturday UTC day can hold no trading minute.
"""
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.historical.config import EARLIEST_YEAR, INSTRUMENTS, RAW
from app.historical.dukascopy import Client, day_url

SIDES = ("BID", "ASK")
RECENT_DAYS = 7


def raw_path(symbol: str, side: str, day: date) -> Path:
    return RAW / symbol / side / str(day.year) / f"{day.isoformat()}.bi5"


def none_path(symbol: str, side: str, day: date) -> Path:
    return raw_path(symbol, side, day).with_suffix(".none")


def have(symbol: str, side: str, day: date) -> bool:
    return raw_path(symbol, side, day).exists() or none_path(symbol, side, day).exists()


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(payload)
    tmp.replace(path)


def trading_days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() != 5:
            yield d
        d += timedelta(days=1)


def discover_start(client: Client, symbol: str, log=print) -> date:
    """First month with data: probe the second Wednesday of each month from EARLIEST_YEAR on. Cached in raw/{SYMBOL}/start.json."""
    cache = RAW / symbol / "start.json"
    if cache.exists():
        return date.fromisoformat(json.loads(cache.read_text())["first_month"])
    today = datetime.now(timezone.utc).date()
    y, m = EARLIEST_YEAR, 1
    while date(y, m, 1) <= today:
        d = date(y, m, 8)
        while d.weekday() != 2:
            d += timedelta(days=1)
        if client.fetch(day_url(symbol, d, "BID")):
            first = date(y, m, 1) - timedelta(days=1)
            first = date(first.year, first.month, 1) if (y, m) != (EARLIEST_YEAR, 1) else date(y, m, 1)
            _write(cache, json.dumps({"first_month": first.isoformat(), "probe_hit": d.isoformat()}).encode())
            log(f"{symbol}: data found from {d.isoformat()}; downloading from {first.isoformat()}")
            return first
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    raise RuntimeError(f"{symbol}: Dukascopy returned no data for any month since {EARLIEST_YEAR}")


def download(symbols: list[str], until: date | None = None, min_interval: float = 1.0, log=print) -> dict:
    client = Client(min_interval=min_interval, log=log)
    until = until or datetime.now(timezone.utc).date() - timedelta(days=1)
    recent = until - timedelta(days=RECENT_DAYS)
    summary = {}
    for symbol in symbols:
        if symbol not in INSTRUMENTS:
            raise ValueError(f"unknown instrument {symbol}: add it to app/historical/config.py")
        start = discover_start(client, symbol, log)
        days = list(trading_days(start, until))
        todo = [(d, s) for d in days for s in SIDES if not have(symbol, s, d)]
        log(f"{symbol}: {len(days)} trading days {start}..{until}, {len(todo)} files to fetch")
        got = empty = 0
        t0 = time.monotonic()
        for i, (d, side) in enumerate(todo, 1):
            payload = client.fetch(day_url(symbol, d, side))
            if payload:
                _write(raw_path(symbol, side, d), payload)
                got += 1
            else:
                empty += 1
                if d < recent:
                    _write(none_path(symbol, side, d), b"")
            if i % 200 == 0 or i == len(todo):
                rate = i / max(time.monotonic() - t0, 1e-9)
                log(f"{symbol}: {i}/{len(todo)} files ({d}), {got} with data, {empty} empty, "
                    f"~{(len(todo) - i) / rate / 3600:.1f} h left, {client.throttled} throttled responses so far")
        summary[symbol] = {"start": start.isoformat(), "until": until.isoformat(), "fetched": got, "empty": empty}
    return summary
