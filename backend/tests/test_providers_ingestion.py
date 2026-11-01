from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app.core.exceptions import ProviderNotConfigured, UnsupportedError
from app.database.models import Candle as CandleRow
from app.market_data.binance.provider import BinanceProvider
from app.market_data.ingestion.service import (
    ingest_candles,
    load_candles,
    resolve_mapping,
)
from app.market_data.twelve_data.provider import TwelveDataProvider

BASE = "https://api.binance.com"


def fast_binance(sleeps: list | None = None) -> BinanceProvider:
    """Provider with no real sleeping; records requested sleeps."""
    p = BinanceProvider(BASE, min_interval_s=0)
    p._sleep = (sleeps.append if sleeps is not None else (lambda s: None))
    return p


def kline(open_ms: int, o="100", h="110", low="90", c="105", v="3", step=3600_000):
    return [open_ms, o, h, low, c, v, open_ms + step - 1, "300", 12, "1", "100", "0"]


@respx.mock
def test_binance_parses_decimal_and_completion():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    old = now_ms - 5 * 3600_000
    live = now_ms - 600_000
    respx.get(f"{BASE}/api/v3/klines").mock(return_value=httpx.Response(200, json=[
        kline(old, o="43000.12345678"), kline(live)]))
    p = fast_binance()
    out = p.get_candles("BTCUSDT", "1H", start=datetime.fromtimestamp(old / 1000, tz=timezone.utc))
    assert str(out[0].open) == "43000.12345678"
    assert out[0].complete is True and out[1].complete is False
    assert out[0].volume_type == "base"


@respx.mock
def test_binance_paginates_until_short_page():
    page1 = [kline(1_700_000_000_000 + i * 3600_000) for i in range(1000)]
    page2 = [kline(1_700_000_000_000 + (1000 + i) * 3600_000) for i in range(10)]
    route = respx.get(f"{BASE}/api/v3/klines").mock(side_effect=[httpx.Response(200, json=page1),
                                                                 httpx.Response(200, json=page2)])
    p = fast_binance()
    out = p.get_candles("BTCUSDT", "1H", start=datetime(2023, 11, 14, tzinfo=timezone.utc))
    assert len(out) == 1010 and route.call_count == 2


@respx.mock
def test_binance_rate_limit_and_unsupported_tf():
    respx.get(f"{BASE}/api/v3/klines").mock(return_value=httpx.Response(429, headers={"Retry-After": "5"}))
    p = fast_binance()
    with pytest.raises(Exception) as ei:
        p.get_candles("BTCUSDT", "1H")
    assert "rate limit" in str(ei.value)
    with pytest.raises(UnsupportedError):
        p.get_candles("BTCUSDT", "3M")


def test_twelve_data_requires_key():
    p = TwelveDataProvider(None)
    assert not p.is_configured()
    with pytest.raises(ProviderNotConfigured):
        p.get_candles("XAU/USD", "1H")
    assert p.get_provider_metadata().requires_api_key


@respx.mock
def test_twelve_data_parse_and_plan_error():
    td = "https://api.twelvedata.com"
    respx.get(f"{td}/time_series").mock(return_value=httpx.Response(200, json={
        "meta": {}, "status": "ok", "values": [
            {"datetime": "2024-01-02 10:00:00", "open": "2050.1", "high": "2052.0", "low": "2049.5", "close": "2051.2"},
            {"datetime": "2024-01-02 09:00:00", "open": "2049.0", "high": "2050.5", "low": "2048.0", "close": "2050.1"},
        ]}))
    p = TwelveDataProvider("k", td, min_interval_s=0)
    out = p.get_candles("XAU/USD", "1H", limit=2)
    assert [c.ts.hour for c in out] == [9, 10] and out[0].volume is None and out[0].volume_type == "none"
    respx.get(f"{td}/time_series").mock(return_value=httpx.Response(200, json={
        "code": 400, "status": "error", "message": "This symbol is available with the Grow plan"}))
    with pytest.raises(UnsupportedError):
        p.get_candles("DJI", "1H", limit=2)


def test_us30_maps_to_oanda_and_refuses_without_a_token_rather_than_substituting(session):
    inst, prov, pi = resolve_mapping(session, "US30")
    assert (prov.code, pi.provider_symbol, pi.status) == ("oanda", "US30_USD", "unverified")
    from app.market_data.oanda.provider import OandaProvider
    with pytest.raises(ProviderNotConfigured, match="OANDA_API_TOKEN"):
        OandaProvider(None).get_candles("US30_USD", "1H", limit=2)
    inst, prov, pi = resolve_mapping(session, "BTCUSDT")
    assert prov.code == "binance" and pi.status == "active"
    inst, prov, pi = resolve_mapping(session, "GBPUSD")
    assert (prov.code, pi.provider_symbol) == ("twelve_data", "GBP/USD")


def test_twelve_data_builds_2h_and_4h_from_1h_because_its_native_grid_shifts_with_dst():
    from app.market_data.timeframes import plan_timeframe

    native = set(TwelveDataProvider.native_timeframes)
    assert {"1H", "1D"} <= native and not ({"2H", "4H"} & native)
    assert plan_timeframe("4H", native) == ("aggregate", "1H")
    assert plan_timeframe("2H", native) == ("aggregate", "1H")


@respx.mock
def test_ingestion_idempotent_and_coverage(session):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start = (now_ms // 3600_000 - 20) * 3600_000
    rows = [kline(start + i * 3600_000) for i in range(18) if i != 7]  # one missing candle
    respx.get(f"{BASE}/api/v3/klines").mock(return_value=httpx.Response(200, json=rows))
    inst, prov, pi = resolve_mapping(session, "BTCUSDT")
    p = fast_binance()
    r1 = ingest_candles(session, p, inst, prov, pi, "1H", bars=20)
    n1 = session.scalar(select(func.count()).select_from(CandleRow))
    r2 = ingest_candles(session, p, inst, prov, pi, "1H", bars=20)
    n2 = session.scalar(select(func.count()).select_from(CandleRow))
    assert n1 == n2 == 17 and r1.stored == r2.stored == 17
    assert r2.coverage["gap_count"] == 1 and r2.coverage["gaps"][0]["missing"] == 1
    loaded = load_candles(session, inst.id, prov.id, "1H")
    assert len(loaded) == 17


@respx.mock
def test_ingestion_aggregates_unsupported_native_timeframe(session):
    start = 1_700_006_400_000  # aligned to 4h
    rows = [kline(start + i * 3600_000) for i in range(8)]
    respx.get(f"{BASE}/api/v3/klines").mock(return_value=httpx.Response(200, json=rows))
    inst, prov, pi = resolve_mapping(session, "BTCUSDT")
    # 4H is native on Binance -> native. Use 12M (aggregate from 1M) to test the plan result type.
    r = ingest_candles(session, fast_binance(), inst, prov, pi, "12M", bars=2,
                       start=datetime(2023, 1, 1, tzinfo=timezone.utc), end=datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert r.plan == "aggregate" and r.aggregated_from == "1M"


@respx.mock
def test_binance_retries_429_honouring_retry_after_then_succeeds():
    sleeps: list = []
    route = respx.get(f"{BASE}/api/v3/klines").mock(side_effect=[
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(503),
        httpx.Response(200, json=[kline(1_700_000_000_000)])])
    out = fast_binance(sleeps).get_candles("BTCUSDT", "1H", start=datetime(2023, 11, 1, tzinfo=timezone.utc))
    assert len(out) == 1 and route.call_count == 3
    assert sleeps[0] == 7.0 and sleeps[1] == BinanceProvider.BACKOFF[1]


@respx.mock
def test_binance_gives_up_after_bounded_retries_and_never_retries_a_ban():
    sleeps: list = []
    route = respx.get(f"{BASE}/api/v3/klines").mock(return_value=httpx.Response(429))
    with pytest.raises(Exception, match="rate limit"):
        fast_binance(sleeps).get_candles("BTCUSDT", "1H")
    assert route.call_count == len(BinanceProvider.BACKOFF) + 1
    route.mock(return_value=httpx.Response(418, headers={"Retry-After": "120"}))
    before = route.call_count
    with pytest.raises(Exception, match="banned"):
        fast_binance().get_candles("BTCUSDT", "1H")
    assert route.call_count - before == 1  # retrying a ban would extend it


@respx.mock
def test_binance_pauses_when_request_weight_nears_the_limit():
    sleeps: list = []
    respx.get(f"{BASE}/api/v3/klines").mock(return_value=httpx.Response(
        200, json=[kline(1_700_000_000_000)], headers={"x-mbx-used-weight-1m": "1100"}))
    p = fast_binance(sleeps)
    p.get_candles("BTCUSDT", "1H", start=datetime(2023, 11, 1, tzinfo=timezone.utc))
    assert 20.0 in sleeps and p.last_used_weight == 1100


TD = "https://api.twelvedata.com"


def fast_td(sleeps: list | None = None) -> TwelveDataProvider:
    p = TwelveDataProvider("test-key", TD, min_interval_s=0)
    p._sleep = sleeps.append if sleeps is not None else (lambda s: None)
    return p


@respx.mock
def test_twelve_data_error_handling_matrix():
    route = respx.get(f"{TD}/time_series")
    route.mock(return_value=httpx.Response(200, json={"code": 401, "status": "error", "message": "apikey parameter is incorrect"}))
    with pytest.raises(Exception, match="rejected the API key"):
        fast_td().get_candles("XAU/USD", "1H", limit=2)
    route.mock(return_value=httpx.Response(200, json={"code": 404, "status": "error", "message": "symbol not found"}))
    with pytest.raises(UnsupportedError, match="no such symbol"):
        fast_td().get_candles("NOPE", "1H", limit=2)
    route.mock(return_value=httpx.Response(200, text="<html>bad gateway</html>"))
    with pytest.raises(Exception, match="non-JSON"):
        fast_td().get_candles("XAU/USD", "1H", limit=2)
    route.mock(return_value=httpx.Response(503, json={"status": "error", "code": 503, "message": "down"}))
    with pytest.raises(Exception, match="Twelve Data error 503|server error"):
        fast_td().get_candles("XAU/USD", "1H", limit=2)


@respx.mock
def test_twelve_data_per_minute_limit_waits_once_then_succeeds_daily_limit_fails_fast():
    sleeps: list = []
    ok = {"status": "ok", "values": [{"datetime": "2024-01-02 09:00:00", "open": "1", "high": "2", "low": "0.5", "close": "1.5"}]}
    route = respx.get(f"{TD}/time_series").mock(side_effect=[
        httpx.Response(200, json={"code": 429, "status": "error", "message": "You have run out of API credits for the current minute."}),
        httpx.Response(200, json=ok)])
    out = fast_td(sleeps).get_candles("XAU/USD", "1H", limit=1)
    assert len(out) == 1 and 62.0 in sleeps and route.call_count == 2
    route.mock(return_value=httpx.Response(429, json={"code": 429, "status": "error", "message": "You have run out of daily API credits."},
                                           headers={"api-credits-used": "800", "api-credits-left": "0"}))
    p = fast_td()
    with pytest.raises(Exception) as ei:
        p.get_candles("XAU/USD", "1H", limit=1)
    assert ei.value.details["scope"] == "day" and p.last_quota["api-credits-left"] == "0"


@respx.mock
def test_twelve_data_quota_and_discovery_use_provider_numbers_verbatim():
    respx.get(f"{TD}/api_usage").mock(return_value=httpx.Response(200, json={"current_usage": 12, "plan_limit": 800, "plan_category": "basic"}))
    assert fast_td().get_quota()["plan_limit"] == 800
    respx.get(f"{TD}/symbol_search").mock(return_value=httpx.Response(200, json={"data": [
        {"symbol": "XAU/USD", "instrument_name": "Gold Spot", "instrument_type": "Physical Currency"}]}))
    found = fast_td().get_instruments(["XAU/USD"])
    assert [i.symbol for i in found] == ["XAU/USD"]


@respx.mock
def test_twelve_data_pages_backwards_because_the_api_returns_the_newest_points_of_a_range(monkeypatch):
    import app.market_data.twelve_data.provider as td_mod

    monkeypatch.setattr(td_mod, "MAX_OUTPUT", 3)
    days = [datetime(2024, 1, d, tzinfo=timezone.utc) for d in range(1, 11)]  # 10 daily points
    served: list[tuple] = []

    def emulate(request: httpx.Request):  # real API behaviour: newest `outputsize` points in [start, end], DESC
        q = request.url.params
        lo = datetime.strptime(q["start_date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) if "start_date" in q else days[0]
        hi = datetime.strptime(q["end_date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) if "end_date" in q else days[-1]
        rows = [d for d in days if lo <= d <= hi][-int(q["outputsize"]):][::-1]
        served.append((lo, hi, len(rows)))
        return httpx.Response(200, json={"status": "ok", "values": [
            {"datetime": d.strftime("%Y-%m-%d"), "open": "1", "high": "2", "low": "0.5", "close": "1.5"} for d in rows]})

    respx.get(f"{TD}/time_series").mock(side_effect=emulate)
    out = fast_td().get_candles("XAU/USD", "1D", start=days[0], end=days[-1])
    assert [c.ts for c in out] == days  # complete, ascending, no duplicates, nothing lost from the old end
    assert len(served) == 4  # 3 + 3 + 3 + 1 points
    tail = fast_td().get_candles("XAU/USD", "1D", limit=4)
    assert [c.ts for c in tail] == days[-4:]
    cov = fast_td().check_data_coverage("XAU/USD", "1D")
    assert cov["available"] and cov["earliest"] == days[0].isoformat() and cov["latest"] == days[-1].isoformat()


@respx.mock
def test_sync_rejects_candles_off_the_timeframe_grid_instead_of_storing_them(session):
    base_ms = (int(datetime.now(timezone.utc).timestamp() // 14400) - 6) * 14400_000  # 4H-aligned open
    on_grid = [kline(base_ms + i * 14400_000, step=14400_000) for i in range(3)]
    off_grid = [kline(base_ms + (3 + i) * 14400_000 + 3600_000, step=14400_000) for i in range(2)]  # +1h: DST-shifted style
    respx.get(f"{BASE}/api/v3/klines").mock(return_value=httpx.Response(200, json=on_grid + off_grid))
    inst, prov, pi = resolve_mapping(session, "BTCUSDT", "binance")
    r = ingest_candles(session, fast_binance(), inst, prov, pi, "4H", bars=10)
    assert r.misaligned == 2 and r.stored == 3
    assert session.scalar(select(func.count()).select_from(CandleRow)) == 3


OA = "https://api-fxpractice.oanda.com"


def fast_oanda(sleeps=None, token="tok-secret-123"):
    from app.market_data.oanda.provider import OandaProvider

    p = OandaProvider(token, OA, min_interval_s=0)
    p._sleep = sleeps.append if sleeps is not None else (lambda s: None)
    return p


def oa_candle(t, o="100.0", h="101.0", low="99.0", c="100.5", complete=True, vol=77):
    return {"complete": complete, "volume": vol, "time": t, "mid": {"o": o, "h": h, "l": low, "c": c}}


@respx.mock
def test_oanda_parses_candles_and_requests_the_platform_utc_grid():
    route = respx.get(f"{OA}/v3/instruments/US30_USD/candles").mock(return_value=httpx.Response(200, json={
        "instrument": "US30_USD", "granularity": "H1", "candles": [
            oa_candle("2024-01-02T10:00:00.000000000Z", o="37000.5"), oa_candle("2024-01-02T11:00:00.000000000Z", complete=False)]}))
    out = fast_oanda().get_candles("US30_USD", "1H", start=datetime(2024, 1, 2, 10, tzinfo=timezone.utc))
    assert [c.ts.hour for c in out] == [10, 11] and out[0].complete and not out[1].complete
    assert str(out[0].open) == "37000.5" and out[0].volume_type == "tick" and out[0].ts.tzinfo is not None
    q = route.calls[0].request.url.params
    assert q["granularity"] == "H1" and q["alignmentTimezone"] == "UTC" and q["dailyAlignment"] == "0"
    assert q["weeklyAlignment"] == "Monday" and q["price"] == "M"
    assert route.calls[0].request.headers["authorization"] == "Bearer tok-secret-123"


@respx.mock
def test_oanda_pages_forward_without_duplicates(monkeypatch):
    import app.market_data.oanda.provider as om

    monkeypatch.setattr(om, "MAX_COUNT", 3)
    hours = [datetime(2024, 1, 2, h, tzinfo=timezone.utc) for h in range(0, 8)]

    def serve(request: httpx.Request):
        frm = datetime.strptime(request.url.params["from"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        rows = [t for t in hours if t >= frm][:3]
        return httpx.Response(200, json={"candles": [oa_candle(t.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")) for t in rows]})

    respx.get(f"{OA}/v3/instruments/GBP_USD/candles").mock(side_effect=serve)
    out = fast_oanda().get_candles("GBP_USD", "1H", start=hours[0], end=hours[-1])
    assert [c.ts for c in out] == hours


@respx.mock
def test_oanda_errors_and_secret_hygiene():
    route = respx.get(f"{OA}/v3/instruments/US30_USD/candles")
    route.mock(return_value=httpx.Response(401, json={"errorMessage": "Insufficient authorization"}))
    with pytest.raises(Exception, match="rejected the API token") as ei:
        fast_oanda().get_candles("US30_USD", "1H", limit=2)
    assert "tok-secret-123" not in str(ei.value)
    route.mock(return_value=httpx.Response(400, json={"errorMessage": "Invalid value specified for instrument tok-secret-123"}))
    with pytest.raises(UnsupportedError) as ei:
        fast_oanda().get_candles("US30_USD", "1H", limit=2)
    assert "tok-secret-123" not in str(ei.value) and "***" in str(ei.value)
    sleeps: list = []
    route.mock(side_effect=[httpx.Response(429), httpx.Response(200, json={"candles": [oa_candle("2024-01-02T10:00:00.000000000Z")]})])
    assert len(fast_oanda(sleeps).get_candles("US30_USD", "1H", limit=1)) == 1 and sleeps == [2.0]
    with pytest.raises(UnsupportedError):
        fast_oanda().get_candles("US30_USD", "3m", limit=1)  # no native 3m: aggregate from 1m


@respx.mock
def test_oanda_quote_and_coverage_probe():
    respx.get(f"{OA}/v3/instruments/US30_USD/candles").mock(side_effect=lambda r: httpx.Response(200, json={"candles": [
        {"complete": False, "volume": 5, "time": "2026-11-02T10:00:00.000000000Z", "bid": {"c": "37000.0"}, "ask": {"c": "37002.0"}}
        if r.url.params.get("price") == "BA" else oa_candle("2000-01-03T00:00:00.000000000Z" if r.url.params.get("from") else "2026-11-02T10:00:00.000000000Z")]}))
    q = fast_oanda().get_latest_quote("US30_USD")
    assert (q.bid, q.ask, q.price) == (Decimal("37000.0"), Decimal("37002.0"), Decimal("37001.0"))
    cov = fast_oanda().check_data_coverage("US30_USD", "1H")
    assert cov["available"] and cov["earliest"].startswith("2000-01-03") and cov["latest"].startswith("2026-11-02")


def test_building_4h_from_1h_ignores_closed_market_quotes(session):
    """Friday evening 4H candle must be made only of trading hours, even if the feed also published weekend quotes."""
    from datetime import timedelta

    from app.market_data.base import MarketDataProvider

    class Hourly(MarketDataProvider):
        code, native_timeframes = "fake", {"1H": "1h"}
        def is_configured(self): return True
        def get_instruments(self, symbols=None): return []
        def get_latest_quote(self, symbol): raise NotImplementedError
        def get_market_status(self, symbol): return {}
        def get_provider_metadata(self): raise NotImplementedError
        def check_data_coverage(self, symbol, timeframe): return {}

        def get_candles(self, symbol, timeframe, start=None, end=None, limit=None):
            from app.market_data.types import Candle
            t0 = datetime(2024, 1, 5, 16, tzinfo=timezone.utc)  # Friday 11:00 New York (winter): closes 22:00 UTC
            out = []
            for h in range(0, 48):  # through Sunday
                t = t0 + timedelta(hours=h)
                weekend = t >= datetime(2024, 1, 5, 22, tzinfo=timezone.utc)
                price = Decimal(900 if weekend else 2000 + h)  # weekend quotes are wildly different: contamination is obvious
                out.append(Candle(t, price, price + 1, price - 1, price, complete=True))
            return out

    inst, prov, pi = resolve_mapping(session, "XAUUSD", "twelve_data")
    r = ingest_candles(session, Hourly(), inst, prov, pi, "4H", bars=40, start=datetime(2024, 1, 5, 16, tzinfo=timezone.utc),
                       end=datetime(2024, 1, 7, 16, tzinfo=timezone.utc))
    assert r.plan == "aggregate"
    fri = [c for c in load_candles(session, inst.id, prov.id, "4H", complete_only=False) if c.ts == datetime(2024, 1, 5, 16, tzinfo=timezone.utc)][0]
    assert fri.high < 2100 and fri.low > 1900  # no 900-ish weekend price inside the Friday bucket
    assert fri.meta["n_base"] == 6 == fri.meta["expected_base"] or fri.meta["n_base"] == fri.meta["expected_base"]


@respx.mock
def test_twelve_data_retries_transient_network_failures_then_gives_up():
    sleeps: list = []
    ok = {"status": "ok", "values": [{"datetime": "2024-01-02 09:00:00", "open": "1", "high": "2", "low": "0.5", "close": "1.5"}]}
    route = respx.get(f"{TD}/time_series").mock(side_effect=[httpx.ConnectError("dns"), httpx.ConnectError("dns"), httpx.Response(200, json=ok)])
    assert len(fast_td(sleeps).get_candles("XAU/USD", "1H", limit=1)) == 1 and route.call_count == 3 and sleeps == [2.0, 5.0]
    route.mock(side_effect=httpx.ConnectError("dns"))
    with pytest.raises(Exception, match="request failed: ConnectError"):
        fast_td().get_candles("XAU/USD", "1H", limit=1)
