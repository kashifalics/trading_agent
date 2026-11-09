"""Historical pipeline on synthetic Dukascopy files (TEST FIXTURES ONLY, never market data)."""
import lzma
from datetime import date, datetime, timezone

import polars as pl
import pytest

from app.historical import build as B
from app.historical import download as D
from app.historical.dukascopy import RECORD, day_url, decode


def bi5(rows: list[tuple[int, float, float, float, float, float]], point: float = 1e-5) -> bytes:
    """rows: (seconds since midnight, open, high, low, close, volume) -> Dukascopy file bytes (record order open, close, low, high)."""
    raw = b"".join(RECORD.pack(t, round(o / point), round(c / point), round(lo / point), round(h / point), v) for t, o, h, lo, c, v in rows)
    return lzma.compress(raw, format=lzma.FORMAT_ALONE)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    for mod in (B, D):
        monkeypatch.setattr(mod, "RAW", tmp_path / "raw")
    for name in ("NORMALIZED", "CLEAN", "REPORTS"):
        monkeypatch.setattr(B, name, tmp_path / name.lower())
    return tmp_path


def test_url_uses_zero_based_months_and_decode_round_trips():
    assert day_url("EURUSD", date(2004, 1, 5), "BID").endswith("/EURUSD/2004/00/05/BID_candles_min_1.bi5")
    assert day_url("XAUUSD", date(2020, 12, 31), "ASK").endswith("/2020/11/31/ASK_candles_min_1.bi5")
    rows = decode(bi5([(60, 1.25, 1.2503, 1.2499, 1.2501, 3.5)]), 1e-5)
    assert rows[0][0] == 60 and rows[0][1:5] == pytest.approx((1.25, 1.2503, 1.2499, 1.2501)) and rows[0][5] == pytest.approx(3.5)
    assert decode(b"", 1e-5) == []
    with pytest.raises(ValueError):
        decode(lzma.compress(b"x" * 25, format=lzma.FORMAT_ALONE), 1e-5)


def test_client_keeps_retrying_rate_limits_and_network_errors():
    import httpx

    from app.historical.dukascopy import Client

    replies = iter([429] * 15 + ["timeout", 503, 200])

    def handler(request):
        r = next(replies)
        if r == "timeout":
            raise httpx.ConnectTimeout("slow", request=request)
        return httpx.Response(r, content=b"ok" if r == 200 else b"")

    waits = []
    c = Client(min_interval=0, log=lambda m: None, sleep=waits.append, transport=httpx.MockTransport(handler))
    assert c.fetch("https://datafeed.dukascopy.com/x") == b"ok"  # 17 failures in a row, more than the old 12-attempt limit
    assert c.throttled == 15 and waits[0] == 60 and max(waits) == 1800  # backoff doubles from 1 min, capped at 30 min


class FakeClient:
    def __init__(self, data: dict[str, bytes]):
        self.data, self.urls, self.throttled = data, [], 0

    def fetch(self, url: str) -> bytes:
        self.urls.append(url)
        return self.data.get(url, b"")


def test_download_is_resumable_and_skips_saturdays(store, monkeypatch):
    payload = bi5([(0, 1.1, 1.1, 1.1, 1.1, 1.0)])
    days = [date(2010, 3, 5), date(2010, 3, 6), date(2010, 3, 7), date(2010, 3, 8)]  # Fri, Sat, Sun, Mon
    data = {day_url("EURUSD", d, s): payload for d in days for s in D.SIDES if d != date(2010, 3, 7)}
    fake = FakeClient(data)
    monkeypatch.setattr(D, "Client", lambda **kw: fake)
    monkeypatch.setattr(D, "discover_start", lambda client, symbol, log=print: days[0])
    until = date(2010, 3, 20)
    D.download(["EURUSD"], until=until, log=lambda m: None)
    assert not any("/2010/02/06/" in u or "/2010/02/13/" in u for u in fake.urls)  # Saturdays never requested
    assert D.raw_path("EURUSD", "BID", days[0]).exists() and D.none_path("EURUSD", "ASK", days[2]).exists()  # empty Sunday recorded
    assert not D.none_path("EURUSD", "BID", date(2010, 3, 19)).exists()  # last 7 days: may still be published, asked again
    fake.urls.clear()
    D.download(["EURUSD"], until=until, log=lambda m: None)
    assert fake.urls and all(day_url("EURUSD", date(2010, 3, 14), "BID")[:-26] <= u for u in fake.urls)  # only the recent days


def test_market_hours_follow_new_york_daylight_saving():
    winter = B.open_minutes(datetime(2021, 1, 10, 20, tzinfo=timezone.utc), datetime(2021, 1, 11, 0, tzinfo=timezone.utc), "EURUSD")
    summer = B.open_minutes(datetime(2021, 7, 11, 20, tzinfo=timezone.utc), datetime(2021, 7, 12, 0, tzinfo=timezone.utc), "EURUSD")
    assert winter["ts"].min().hour == 22 and summer["ts"].min().hour == 21  # Sunday 17:00 New York in UTC
    gold = B.open_minutes(datetime(2021, 7, 12, 20, tzinfo=timezone.utc), datetime(2021, 7, 12, 23, tzinfo=timezone.utc), "XAUUSD")
    assert gold.height == 120  # Monday 21:00-22:00 UTC is the metals daily break in summer


def _day(base: float, skip: range = range(0), quiet: set[int] = frozenset(), bad: set[int] = frozenset()):
    rows = []
    for m in range(24 * 60):
        if m in skip:
            continue
        p = base + m * 1e-5
        if m in quiet:
            rows.append((m * 60, p, p, p, p, 0.0))
        elif m in bad:
            rows.append((m * 60, p, p - 0.001, p + 0.001, p, 1.0))  # high below low
        else:
            rows.append((m * 60, p, p + 0.0002, p - 0.0002, p + 0.0001, 2.0))
    return rows


def test_build_validates_finds_material_gaps_and_rebuilds_timeframes(store):
    mon, tue = date(2021, 3, 1), date(2021, 3, 2)
    for side, off in (("BID", 0.0), ("ASK", 0.0001)):
        for d, kw in ((mon, {"skip": range(600, 645), "quiet": {700, 701}, "bad": {800}}), (tue, {})):
            p = D.raw_path("EURUSD", side, d)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(bi5(_day(1.2 + off, **kw)))
    rep = B.build("EURUSD", log=lambda m: None)
    assert rep["quiet_minutes"] == 2 and rep["invalid_candles"] == 1 and rep["duplicates"] == 0
    assert rep["material_gaps"] == 1 and rep["material_gap_minutes"] == 45  # 10:00-10:45 UTC Monday
    assert rep["coverage_pct"] < 100
    m1 = pl.read_parquet(store / "clean" / "EURUSD" / "M1" / "2021.parquet")
    assert m1.height == 2 * 1440 - 45 - 3 and (m1["spread"] > 0).all()
    h1 = pl.read_parquet(store / "clean" / "EURUSD" / "H1" / "all.parquet").filter(pl.col("ts") == datetime(2021, 3, 2, 5, tzinfo=timezone.utc))
    src = m1.filter((pl.col("ts") >= datetime(2021, 3, 2, 5, tzinfo=timezone.utc)) & (pl.col("ts") < datetime(2021, 3, 2, 6, tzinfo=timezone.utc)))
    assert h1["bid_open"][0] == src["bid_open"][0] and h1["bid_close"][0] == src["bid_close"][-1]
    assert h1["bid_high"][0] == src["bid_high"].max() and h1["bid_low"][0] == src["bid_low"].min() and h1["n_minutes"][0] == 60
    w1 = pl.read_parquet(store / "clean" / "EURUSD" / "W1" / "all.parquet")
    assert w1.height == 1 and w1["ts"][0] == datetime(2021, 3, 1, tzinfo=timezone.utc)  # weeks start Monday 00:00 UTC
    assert "| EURUSD | M1 | 2021-03-01 |" in B.report_markdown(["EURUSD"])
