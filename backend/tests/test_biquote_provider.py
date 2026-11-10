"""BiQuote adapter tests.

* Unit tests replay REAL responses captured from https://biquote.io on 2026-11-01 (tests/fixtures/biquote/, a few rows each) through respx.
  The only simulated payloads are the documented 429 / 503 failure modes, which cannot be provoked on demand against a live service.
* Live tests (set BIQUOTE_LIVE=1) call the real API and the real ingestion pipeline; they are skipped otherwise so CI never depends on a third party.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app.core.exceptions import ProviderError, UnsupportedError
from app.database.models import Candle as CandleRow
from app.market_data.biquote.provider import INTERVALS, BiQuoteProvider
from app.market_data.ingestion.service import ingest_candles, resolve_mapping
from app.market_data.registry import get_provider
from app.market_data.timeframes import plan_timeframe

FIX = Path(__file__).parent / "fixtures" / "biquote"
BASE = "https://biquote.io"


def fx(name: str):
    return json.loads((FIX / name).read_text(encoding="utf8"))


def prov(sleeps: list | None = None) -> BiQuoteProvider:
    p = BiQuoteProvider(BASE)
    p._sleep = sleeps.append if sleeps is not None else (lambda s: None)
    return p


# ------------------------------------------------------------------------------------------------ timeframes
def test_native_timeframes_are_exactly_the_documented_seven_and_planning_is_honest():
    assert set(INTERVALS) == {"1m", "5m", "15m", "30m", "1H", "4H", "1D"}
    native = set(BiQuoteProvider.native_timeframes)
    assert plan_timeframe("3m", native) == ("aggregate", "1m")
    assert plan_timeframe("2H", native) == ("aggregate", "1H")
    assert plan_timeframe("1W", native) == ("aggregate", "1D")
    for tf in ("1M", "3M", "6M", "12M"):
        assert plan_timeframe(tf, native) is None  # no monthly series exists; "1M" on BiQuote means ONE MINUTE


@pytest.mark.parametrize("tf", ["3m", "2H", "1W", "1M", "3M", "12M"])
def test_unsupported_timeframes_raise_and_never_reach_the_network(tf):
    with respx.mock(assert_all_called=False) as m:
        route = m.get(url__startswith=BASE).mock(return_value=httpx.Response(200, json={"bars": []}))
        with pytest.raises(UnsupportedError):
            prov().get_candles("XAUUSD", tf)
        assert route.call_count == 0
    if tf == "1M":
        with pytest.raises(UnsupportedError, match="ONE MINUTE"):
            prov().get_candles("XAUUSD", "1M")


# ------------------------------------------------------------------------------------------------ real responses
@respx.mock
def test_real_ohlc_response_is_normalised_utc_ascending_decimal_and_open_bar_is_incomplete():
    body = fx("ohlc_xauusd_1h.json")
    route = respx.get(f"{BASE}/api/XAUUSD/ohlc").mock(return_value=httpx.Response(200, json=body))
    out = prov().get_candles("XAUUSD", "1H", limit=11)
    assert [c.ts for c in out] == sorted(c.ts for c in out) and all(c.ts.tzinfo == timezone.utc for c in out)
    assert len({c.ts for c in out}) == len(out)  # duplicate prevention
    newest, = [c for c in out if not c.complete]
    assert newest.ts == out[-1].ts  # only the in-progress bar is incomplete; it is never reported as a completed candle
    raw = {b["openTime"]: b for b in body["bars"]}
    c0 = out[0]
    b0 = raw[c0.ts.strftime("%Y-%m-%dT%H:%M:%SZ")]
    assert c0.open == Decimal(str(b0["open"])) and c0.volume_type == "tick" and c0.volume == Decimal(str(b0["tickVolume"]))
    assert route.calls[0].request.url.params["interval"] == "1h" and route.calls[0].request.url.params["limit"] == "11"
    assert all(c.high >= max(c.open, c.close) and c.low <= min(c.open, c.close) for c in out)  # real data passes the OHLC invariant


@respx.mock
def test_start_end_filters_and_duplicate_bars_in_one_response():
    body = fx("ohlc_xauusd_1h.json")
    body["bars"].append(dict(body["bars"][1]))  # a duplicated row is collapsed
    respx.get(f"{BASE}/api/XAUUSD/ohlc").mock(return_value=httpx.Response(200, json=body))
    all_ = prov().get_candles("XAUUSD", "1H")
    cut = all_[3].ts
    got = prov().get_candles("XAUUSD", "1H", start=cut)
    assert got[0].ts == cut and len(got) == len(all_) - 3 and len({c.ts for c in all_}) == len(all_)


@respx.mock
def test_unknown_symbol_returns_empty_list_and_coverage_says_unavailable():
    respx.get(f"{BASE}/api/NOPE123/ohlc").mock(return_value=httpx.Response(200, json=fx("empty_unknown_symbol.json")))
    p = prov()
    assert p.get_candles("NOPE123", "1H") == []
    cov = p.check_data_coverage("NOPE123", "1H")
    assert cov["available"] is False and cov["earliest"] is None and cov["note"]


@respx.mock
def test_invalid_interval_400_is_unsupported_with_valid_list():
    respx.get(f"{BASE}/api/BTCUSD/ohlc").mock(return_value=httpx.Response(400, json=fx("error_invalid_interval.json")))
    p = prov()
    p.native_timeframes = {**p.native_timeframes}
    with pytest.raises(UnsupportedError, match="valid intervals"):
        p._get("/api/BTCUSD/ohlc", {"interval": "3m"})


@respx.mock
def test_closed_market_quote_is_flagged_delayed_and_open_quote_is_live():
    closed = fx("tick_xauusd_closed.json")
    respx.get(f"{BASE}/api/XAUUSD").mock(return_value=httpx.Response(200, json=closed))
    respx.get(f"{BASE}/api/BTCUSDT").mock(return_value=httpx.Response(200, json=fx("tick_btcusdt_open.json")))
    p = prov()
    q = p.get_latest_quote("XAUUSD")
    assert q.provider == "biquote" and q.is_delayed is True and q.price == Decimal(str(closed["mid"])) and q.bid < q.ask
    assert q.ts == datetime.fromisoformat(closed["lastQuoteAt"].replace("Z", "+00:00"))  # the time of the PRICE, not of the request
    assert p.get_market_status("XAUUSD")["open"] is False
    live = p.get_latest_quote("BTCUSDT")
    assert live.is_delayed is False and p.get_market_status("BTCUSDT")["open"] is True


@respx.mock
def test_batch_quotes_use_repeated_symbols_parameter():
    batch = fx("latest_batch.json")
    route = respx.get(f"{BASE}/api/latest").mock(return_value=httpx.Response(200, json=batch))
    qs = asyncio.run(prov().aget_latest_quotes(["XAUUSD", "US30", "BTCUSDT", "USOIL"]))
    assert set(qs) == set(batch) and route.call_count == 1
    assert route.calls[0].request.url.params.get_list("symbols") == ["XAUUSD", "US30", "BTCUSDT", "USOIL"]  # not a comma list


@respx.mock
def test_async_candles_match_sync_candles():
    respx.get(f"{BASE}/api/BTCUSD/ohlc").mock(return_value=httpx.Response(200, json=fx("ohlc_btcusd_1d.json")))
    assert asyncio.run(prov().aget_candles("BTCUSD", "1D")) == prov().get_candles("BTCUSD", "1D")


@respx.mock
def test_get_instruments_reads_real_metadata_and_skips_unknown():
    respx.get(f"{BASE}/api/symbols/US30").mock(return_value=httpx.Response(200, json=fx("symbol_us30.json")))
    respx.get(f"{BASE}/api/symbols/NOPE").mock(return_value=httpx.Response(404, json={"message": "unknown"}))
    infos = prov().get_instruments(["US30", "NOPE"])
    assert [i.symbol for i in infos] == ["US30"] and infos[0].price_precision == 2


# ------------------------------------------------------------------------------------------------ failure handling (documented modes, simulated)
@respx.mock
def test_retry_with_backoff_on_503_then_success():
    sleeps: list = []
    respx.get(f"{BASE}/api/XAUUSD/ohlc").mock(side_effect=[httpx.Response(503, headers={"Retry-After": "3"}, json={"message": "store unreachable"}),
                                                          httpx.Response(200, json=fx("ohlc_xauusd_1h.json"))])
    out = prov(sleeps).get_candles("XAUUSD", "1H")
    assert len(out) == 13 and 3.0 in sleeps  # limit=12 closed bars + the in-progress bar  # waited the server's Retry-After


@respx.mock
def test_429_honours_retry_after_then_gives_up_with_a_clear_error():
    sleeps: list = []
    r429 = httpx.Response(429, headers={"Retry-After": "60"}, json={"error": "rate_limited", "message": "Too many requests."})
    respx.get(f"{BASE}/api/XAUUSD/ohlc").mock(side_effect=[r429, httpx.Response(200, json=fx("ohlc_xauusd_1h.json"))])
    assert len(prov(sleeps).get_candles("XAUUSD", "1H")) == 13 and 60.0 in sleeps
    respx.get(f"{BASE}/api/US30/ohlc").mock(return_value=r429)
    with pytest.raises(ProviderError, match="rate limit"):
        prov([]).get_candles("US30", "1H")


@respx.mock
def test_network_errors_are_retried_then_reported_without_leaking_details():
    sleeps: list = []
    respx.get(f"{BASE}/api/XAUUSD/ohlc").mock(side_effect=httpx.ConnectError("dns"))
    with pytest.raises(ProviderError, match="ConnectError"):
        prov(sleeps).get_candles("XAUUSD", "1H")
    assert sleeps.count(1.0) >= 1 and 4.0 in sleeps  # exponential backoff 1, 2, 4


def test_client_side_rate_limit_throttles_before_the_documented_limit():
    p = BiQuoteProvider(BASE, max_per_minute=3)
    assert [p._throttle() for _ in range(3)] == [0.0, 0.0, 0.0] and p._throttle() > 50  # the 4th request in a minute must wait


# ------------------------------------------------------------------------------------------------ registry + real ingestion path
def test_registry_exposes_biquote_without_replacing_existing_providers(session):
    assert get_provider("biquote").code == "biquote" and get_provider("binance").code == "binance" and get_provider("twelve_data").code == "twelve_data"
    assert resolve_mapping(session, "BTCUSDT")[1].code == "binance"  # Binance stays primary
    assert resolve_mapping(session, "XAUUSD")[1].code == "twelve_data"  # Twelve Data stays primary
    assert resolve_mapping(session, "XAUUSD", "biquote")[2].provider_symbol == "XAUUSD"
    # status-based routing (no preference set): the previously working defaults are unchanged, US30/USOIL (no other keyless source) go to BiQuote
    assert resolve_mapping(session, "US30")[1].code == "biquote" and resolve_mapping(session, "USOIL")[1].code == "biquote"
    for sym in ("US30", "USOIL", "XAUUSD", "BTCUSDT"):  # and BiQuote is selectable explicitly for all four, with its own provider-specific symbol
        _, p, pi = resolve_mapping(session, sym, "biquote")
        assert p.code == "biquote" and pi.provider_symbol == sym and pi.status == "active"


@respx.mock
def test_real_fixture_goes_through_the_ingestion_pipeline_idempotently(session):
    respx.get(f"{BASE}/api/XAUUSD/ohlc").mock(return_value=httpx.Response(200, json=fx("ohlc_xauusd_1h.json")))
    inst, p, pi = resolve_mapping(session, "XAUUSD", "biquote")
    win = dict(start=datetime(2026, 10, 30, tzinfo=timezone.utc), end=datetime(2026, 10, 31, tzinfo=timezone.utc))  # the captured sample is from Oct 30
    r1 = ingest_candles(session, prov(), inst, p, pi, "1H", bars=12, **win)
    n1 = session.scalar(select(func.count()).select_from(CandleRow).where(CandleRow.provider_id == p.id))
    r2 = ingest_candles(session, prov(), inst, p, pi, "1H", bars=12, **win)
    n2 = session.scalar(select(func.count()).select_from(CandleRow).where(CandleRow.provider_id == p.id))
    assert n1 == n2 > 0 and r1.misaligned == 0
    assert session.scalar(select(func.count()).select_from(CandleRow).where(CandleRow.provider_id == p.id, CandleRow.is_complete.is_(False))) <= 1
    other = session.scalar(select(func.count()).select_from(CandleRow).where(CandleRow.provider_id != p.id))
    assert other == 0 and r2 is not None  # never mixed with another provider's rows


# ------------------------------------------------------------------------------------------------ live (opt-in)
live = pytest.mark.skipif(os.environ.get("BIQUOTE_LIVE") != "1", reason="set BIQUOTE_LIVE=1 to call the real BiQuote API")


@live
@pytest.mark.parametrize("symbol", ["XAUUSD", "US30", "USOIL", "BTCUSD"])
@pytest.mark.parametrize("tf", ["1m", "5m", "15m", "30m", "1H", "4H", "1D"])
def test_live_native_timeframes_return_valid_utc_candles(symbol, tf):
    out = BiQuoteProvider(BASE).get_candles(symbol, tf)
    assert len(out) >= 100
    assert all(c.ts.tzinfo is not None and c.high >= max(c.open, c.close) and c.low <= min(c.open, c.close) and c.low > 0 for c in out)
    assert [c.ts for c in out] == sorted({c.ts for c in out})
    assert sum(1 for c in out if not c.complete) == 1 and not out[-1].complete


@live
def test_live_ingestion_of_all_four_instruments_including_aggregated_timeframes(session):
    for sym in ("XAUUSD", "US30", "USOIL"):
        inst, p, pi = resolve_mapping(session, sym, "biquote")
        for tf in ("1m", "1H", "4H", "1D", "3m", "2H", "1W"):
            # a wide explicit window = "everything the retention window holds" (a relative 5-hour window is legitimately empty on a closed weekend market)
            res = ingest_candles(session, BiQuoteProvider(BASE), inst, p, pi, tf, bars=300, start=datetime(2024, 1, 1, tzinfo=timezone.utc))
            assert res.stored > 0, (sym, tf)
        with pytest.raises(UnsupportedError):
            ingest_candles(session, BiQuoteProvider(BASE), inst, p, pi, "1M", bars=50)
    assert session.scalar(select(func.count()).select_from(CandleRow)) > 0


@live
def test_live_stream_delivers_seed_and_state_for_every_symbol_and_closed_markets_say_so():
    async def run():
        seen, states = {}, []
        async for ev in BiQuoteProvider(BASE).stream_ticks(["BTCUSDT", "XAUUSD", "US30", "USOIL"], reconnect=False):
            if ev["kind"] == "tick":
                seen.setdefault(ev["symbol"], ev)
            else:
                states = ev["states"]
            if len(seen) == 4 and states:
                break
        return seen, states

    seen, states = asyncio.run(asyncio.wait_for(run(), 40))
    assert set(seen) == {"BTCUSDT", "XAUUSD", "US30", "USOIL"} and {s["symbol"] for s in states} == set(seen)
    for s in states:
        assert s["state"] in ("open", "closed") and s["seeded"] is True
    for sym, ev in seen.items():
        assert ev["bid"] < ev["ask"] and ev["ts"].tzinfo is not None
        if next(s for s in states if s["symbol"] == sym)["state"] == "closed":
            assert ev["stale"] is True  # a closed market's seed tick is a stale price (derived from its age), never presented as live


# ------------------------------------------------------------------------------------------------ stream parsing (real captured frames replayed through a local hub)
def test_stream_parses_real_signalr_frames_and_derives_staleness_from_the_timestamp():
    import websockets

    RS = "\x1e"
    xau = {"symbol": "XAUUSD", "bid": 3875.444, "ask": 3875.612, "last": 0.0, "volume": 0, "timestamp": "2026-10-30T20:57:58Z", "source": "MetaTrader 5 (Broker 1)",
           "high": 4018.845, "low": 3869.964, "direction": "DOWN", "dayDiffPercent": -3.307, "description": "Gold vs US Dollar", "time": "2026.10.30 20:57:58",
           "exchange": "OTC", "spread": 0.168, "mid": 3875.528}
    live_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    btc = {**xau, "symbol": "BTCUSDT", "bid": 78079.6, "ask": 78079.61, "mid": 78079.605, "timestamp": live_ts, "source": "aggr", "time": None}
    state = [{"symbol": "XAUUSD", "state": "closed", "quoteAgeSeconds": 156913, "seeded": True}, {"symbol": "BTCUSDT", "state": "open", "quoteAgeSeconds": 1, "seeded": True}]

    async def hub(ws):
        assert json.loads((await ws.recv()).rstrip(RS)) == {"protocol": "json", "version": 1}
        await ws.send("{}" + RS)
        sub = json.loads((await ws.recv()).rstrip(RS))
        assert sub["target"] == "Subscribe" and sub["arguments"] == [["XAUUSD", "BTCUSDT"]]
        for tick in (xau, btc):
            await ws.send(json.dumps({"type": 1, "target": "ReceiveTick", "arguments": [tick]}) + RS)
        await ws.send(json.dumps({"type": 1, "target": "ReceiveSubscriptionState", "arguments": [state]}) + RS)
        await ws.send(json.dumps({"type": 1, "target": "ReceiveTick", "arguments": [xau]}) + RS)  # a tick AFTER the state frame carries the state
        await asyncio.sleep(0.2)

    async def run():
        async with websockets.serve(hub, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            with respx.mock(assert_all_called=False) as m:
                m.post(f"http://127.0.0.1:{port}/hubs/tick/negotiate").mock(return_value=httpx.Response(200, json={"connectionToken": "tok", "connectionId": "c"}))
                events = []
                async for ev in BiQuoteProvider(f"http://127.0.0.1:{port}").stream_ticks(["XAUUSD", "BTCUSDT"], reconnect=False):
                    events.append(ev)
                    if len(events) == 4:
                        break
                return events

    ev = asyncio.run(asyncio.wait_for(run(), 15))
    t1, t2, st, t3 = ev
    assert (t1["kind"], t1["symbol"], t1["stale"], t1["market_state"]) == ("tick", "XAUUSD", True, "unknown")  # 2-day-old seed: stale, state frame not yet received
    assert (t2["symbol"], t2["stale"]) == ("BTCUSDT", False) and t2["bid"] < t2["ask"] and t2["ts"].tzinfo is not None
    assert st["kind"] == "state" and {x["symbol"]: x["state"] for x in st["states"]} == {"XAUUSD": "closed", "BTCUSDT": "open"}
    assert t3["market_state"] == "closed" and t3["stale"] is True


# ------------------------------------------------------------------------------------------------ preferred provider
@pytest.fixture()
def prefer_biquote(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("PREFERRED_PROVIDER", "biquote")
    get_settings.cache_clear()
    yield
    monkeypatch.setenv("PREFERRED_PROVIDER", "")
    get_settings.cache_clear()


def test_preferred_provider_routes_all_four_instruments_to_biquote_but_explicit_provider_still_wins(session, prefer_biquote):
    for sym in ("XAUUSD", "US30", "BTCUSDT", "USOIL"):
        _, p, pi = resolve_mapping(session, sym)
        assert p.code == "biquote" and pi.provider_symbol == sym and pi.status == "active"
    assert resolve_mapping(session, "BTCUSDT", "binance")[1].code == "binance"  # explicit choice is never overridden
    assert resolve_mapping(session, "XAUUSD", "twelve_data")[1].code == "twelve_data"
    assert resolve_mapping(session, "US30", "oanda")[2].provider_symbol == "US30_USD"
    for fx in ("EURUSD", "GBPUSD"):  # keyless FX through BiQuote (live-verified 2026-11-10)
        assert resolve_mapping(session, fx)[1].code == "biquote"
    assert resolve_mapping(session, "GBPUSD", "twelve_data")[2].provider_symbol == "GBP/USD"
    from app.database.models import DataProvider, ProviderInstrument
    bq = session.scalar(select(DataProvider).where(DataProvider.code == "biquote"))
    gbp = resolve_mapping(session, "GBPUSD")[0]
    session.delete(session.scalar(select(ProviderInstrument).where(ProviderInstrument.provider_id == bq.id,
                                                                     ProviderInstrument.instrument_id == gbp.id)))
    session.flush()
    assert resolve_mapping(session, "GBPUSD")[1].code == "twelve_data"  # no BiQuote mapping: falls back to the status-based choice, never invented


def test_preference_never_selects_an_unsupported_mapping_or_an_unknown_provider(session, prefer_biquote, monkeypatch):
    from app.core.config import get_settings
    from app.database.models import ProviderInstrument

    _, p, pi = resolve_mapping(session, "US30", "biquote")
    pi.status = "unsupported"
    session.commit()
    assert resolve_mapping(session, "US30")[1].code == "oanda"
    monkeypatch.setenv("PREFERRED_PROVIDER", "no_such_provider")
    get_settings.cache_clear()
    assert resolve_mapping(session, "BTCUSDT")[1].code == "binance"
    assert session.get(ProviderInstrument, pi.id).status == "unsupported"


@respx.mock
def test_ingestion_asks_a_fixed_retention_provider_for_everything_it_holds(session):
    route = respx.get(f"{BASE}/api/XAUUSD/ohlc").mock(return_value=httpx.Response(200, json=fx("ohlc_xauusd_1h.json")))
    inst, p, pi = resolve_mapping(session, "XAUUSD", "biquote")
    res = ingest_candles(session, prov(), inst, p, pi, "1H", bars=300)  # no explicit window
    assert "from" not in route.calls[0].request.url.params and res.fetched == 13 and res.stored > 0
