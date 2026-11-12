"""Signals API end to end on stored synthetic candles (TEST FIXTURES ONLY), plus the historical replay on the same kind of data."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.session import session_scope
from app.main import create_app
from app.market_data.ingestion.service import store_candles
from app.signals import service
from tests.conftest import make_candles

TFS = {"5m": 300, "15m": 900, "1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800}


def _seed(symbol: str, n: int = 700, base: float = 2000.0, end: datetime | None = None) -> str:
    end = end or datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(days=3)
    with session_scope() as s:
        inst, prov, _ = service.resolve(s, symbol)
        for i, (tf, sec) in enumerate(TFS.items()):
            count = min(n, 400) if tf in ("1D", "1W") else n
            start = end - timedelta(seconds=sec * count)
            store_candles(s, inst.id, prov.id, tf, make_candles(count, start, sec, base=base, seed=11 + i, vol=base * 0.002))
        s.commit()
        return prov.code


@pytest.fixture()
def client(engine, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setattr(service, "_quote", lambda prov, pi: None)  # never reach a real provider from tests
    service._FRAMES.clear()
    service._MEMORY.clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_signal_detail_returns_a_plan_or_reason_for_every_timeframe(client):
    _seed("XAUUSD")
    r = client.get("/api/v1/signals/XAUUSD")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok" and body["symbol"] == "XAUUSD"
    assert len(body["plans"]) == 14 and len(body["timeframes"]) == 14
    by_tf = {p["timeframe"]: p for p in body["plans"]}
    assert by_tf["1M"]["status"] == "insufficient_data" and by_tf["1M"]["instruction"] == "NO TRADE"
    assert by_tf["1H"]["status"] in ("ok", "stale")
    for p in body["plans"]:
        assert p["probability_note"] and p["win_probability"] is None  # nothing is validated on synthetic data
        assert p["track_record"]["status"] in ("untested", "no_edge", "negative", "validated")
        if p.get("side") and p.get("targets"):
            d = 1 if p["side"] == "BUY" else -1
            assert d * (p["entry"] - p["stop_loss"]) > 0
    assert body["news_filter"]["available"] is False
    assert body["report"]["final_instruction"] in ("EXECUTE NOW", "WAIT FOR CONFIRMATION", "PLACE LIMIT ORDER", "NO TRADE")
    calls = [p["call"] for p in body["plans"]]
    assert all(c["decision"] in ("ENTER", "WAIT", "EXIT", "NO TRADE") and c["label"] and c["headline"] for c in calls)
    assert all(c["decision"] != "ENTER" for c in calls)  # nothing is validated: a technical entry is "WAIT — UNVALIDATED SETUP"
    assert all(c["decision"] != "EXIT" and c["trade"] is None for c in calls)  # no tracked trade, so no EXIT / HOLD is invented
    assert by_tf["1M"]["call"]["label"] == "NO TRADE — DATA" and all(c["levels"] is None and c["hypothetical"] is None for c in calls)
    assert body["call"]["decision"] in ("WAIT", "NO TRADE") and body["experimental"] is False
    for p in body["plans"]:  # the call never contradicts the technical state
        if p["state"] in ("NO_SETUP", "TRADE_INVALIDATED", "TRADE_EXPIRED") or p["status"] != "ok":
            assert p["call"]["decision"] == "NO TRADE"
        if p["call"]["label"] == "WAIT — UNVALIDATED SETUP":
            assert p["state"] == "ENTRY_READY" or p["instruction"] == "PLACE LIMIT ORDER"
    x = client.get("/api/v1/signals/XAUUSD", params={"experimental": "true"}).json()
    assert x["experimental"] is True and all(p["call"]["decision"] != "ENTER" for p in x["plans"])
    for p in x["plans"]:
        if p["call"]["hypothetical"] is not None:
            assert p["call"]["hypothetical"]["label"] == "HYPOTHETICAL — UNVALIDATED" and p["call"]["decision"] in ("WAIT", "NO TRADE")


def test_summary_lists_configured_instruments_and_is_honest_about_missing_data(client):
    _seed("XAUUSD")
    items = {i["symbol"]: i for i in client.get("/api/v1/signals").json()["items"]}
    assert set(items) == set(get_settings().signal_list)
    assert items["XAUUSD"]["status"] == "ok" and "overall" in items["XAUUSD"]
    assert items["BTCUSDT"]["status"] == "unavailable" and items["BTCUSDT"]["reason"]
    assert items["BTCUSDT"]["call"]["decision"] == "NO TRADE" and items["BTCUSDT"]["call"]["label"] == "NO TRADE — DATA"
    assert items["XAUUSD"]["call"]["decision"] in ("WAIT", "NO TRADE")


def test_summary_reuses_each_instruments_latest_analysis_until_it_is_too_old(client, monkeypatch):
    _seed("XAUUSD")
    detail = client.get("/api/v1/signals/XAUUSD").json()  # any fresh analysis is kept for the summary
    calls = []
    real = service.analyze
    monkeypatch.setattr(service, "analyze", lambda s, sym, *a, **k: calls.append(sym) or real(s, sym, *a, **k))
    first = {i["symbol"]: i for i in client.get("/api/v1/signals").json()["items"]}
    assert "XAUUSD" not in calls  # answered from the analysis above, not recomputed
    assert first["XAUUSD"]["as_of"] == detail["generated_at"] and first["XAUUSD"]["call"] == service.compact_call(detail["call"])
    calls.clear()
    client.get("/api/v1/signals")
    assert calls.count("XAUUSD") == 0  # still fresh
    cached = service._ITEMS[("XAUUSD", False)]
    service._ITEMS[("XAUUSD", False)] = (cached[0] - service.SUMMARY_TTL_S - 1, cached[1])  # now too old
    again = {i["symbol"]: i for i in client.get("/api/v1/signals").json()["items"]}
    assert calls.count("XAUUSD") == 1 and again["XAUUSD"]["as_of"] >= first["XAUUSD"]["as_of"]
    calls.clear()
    client.get("/api/v1/signals?experimental=true")
    assert "XAUUSD" in calls  # experimental decisions are kept separately


def test_summary_lists_the_timeframes_where_a_paper_trade_is_held_with_its_levels():
    trade = {"trade_id": 5, "status": "open", "direction": "SELL", "entry_price": 4061.7, "current_price": 3990.0, "stop_loss": 4076.4,
             "take_profit": 3891.0, "unrealized_r": 4.9, "action": "HOLD", "reason": "Between the stop and the first target"}
    held = {"timeframe": "3m", "state": "SETUP_DEVELOPING", "targets": [], "call": {"decision": "HOLD", "label": "HOLD — PAPER TRADE OPEN",
                                                                                   "trade": trade}}
    free = {"timeframe": "1H", "state": "WATCHLIST", "targets": [], "call": {"decision": "NO TRADE", "label": "NO TRADE", "trade": None}}
    r = {"symbol": "XAUUSD", "status": "ok", "plans": [held, free], "active": ["1H"], "timeframes": [], "best": None, "call": held["call"],
         "generated_at": "2026-11-12T10:00:00+00:00"}
    item = service.summary_item(r)
    assert [p["timeframe"] for p in item["trades"]] == ["3m"] and item["trades"][0]["call"]["trade"] == trade
    assert item["call"]["label"] == "HOLD — PAPER TRADE OPEN" and item["call"]["trade"]["entry_price"] == 4061.7
    assert [p["timeframe"] for p in item["active"]] == ["1H"]


def test_config_track_record_and_validation_errors(client):
    cfg = client.get("/api/v1/signals/config").json()
    assert sum(cfg["factors"].values()) == 100 and cfg["thresholds"]["signal"] == 60
    assert cfg["spreads"]["XAUUSD"] == pytest.approx(0.30) and cfg["spreads"]["BTCUSDT"] == pytest.approx(2.0)
    assert "results" in client.get("/api/v1/signals/track-record").json()
    assert client.get("/api/v1/signals/NOPE").status_code == 404
    assert client.get("/api/v1/signals/xa").status_code == 422


def test_sync_fetches_only_due_timeframes_from_keyless_providers(client, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "fetch_candles", lambda s, inst, prov, pi, tf: calls.append((prov.code, tf)) or [])
    r = client.post("/api/v1/signals/BTCUSDT/sync")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "binance" and body["synced"] is True  # BTCUSDT is routed to Binance (deep history, keyless)
    assert ("binance", "1H") in calls and body["analysis"]["symbol"] == "BTCUSDT"


def test_a_timeframe_is_due_only_when_a_candle_closed_since_the_last_attempt(session):
    from app.database.models import DataCoverage

    btc = service.resolve(session, "BTCUSDT")[0]  # 24/7
    gold = service.resolve(session, "XAUUSD")[0]  # closed at the weekend
    now = datetime(2025, 3, 8, 18, 25, tzinfo=timezone.utc)  # a Saturday

    def cov(last_ts, count, last_sync):
        return DataCoverage(last_ts=last_ts, candle_count=count, last_sync_at=last_sync)

    four_h = datetime(2025, 3, 8, 8, 0, tzinfo=timezone.utc)  # the 12:00-16:00 candle is complete but not stored
    assert service.is_due(cov(four_h, 1539, datetime(2025, 3, 8, 14, 38, tzinfo=timezone.utc)), "4H", now, btc)  # long series, one missing
    asked_after_close = datetime(2025, 3, 8, 16, 5, tzinfo=timezone.utc)
    assert not service.is_due(cov(four_h, 1539, asked_after_close), "4H", datetime(2025, 3, 8, 16, 20, tzinfo=timezone.utc), btc)
    assert service.is_due(cov(four_h, 1539, asked_after_close), "4H", datetime(2025, 3, 8, 16, 40, tzinfo=timezone.utc), btc)  # retry
    fresh = datetime(2025, 3, 8, 17, 0, tzinfo=timezone.utc)
    assert not service.is_due(cov(fresh, 1664, now - timedelta(minutes=20)), "1H", now, btc)  # nothing new yet
    month = datetime(2025, 2, 1, tzinfo=timezone.utc)
    assert not service.is_due(cov(month, 111, now - timedelta(hours=1)), "1M", now, btc)  # short series: not every cycle
    assert service.is_due(cov(month, 111, now - timedelta(hours=7)), "1M", now, btc)
    friday = datetime(2025, 3, 7, 21, 30, tzinfo=timezone.utc)  # thin feed: the last candles before the close never arrived
    assert not service.is_due(cov(friday, 192, now - timedelta(minutes=10)), "15m", now, gold)
    assert service.is_due(cov(friday, 192, now - timedelta(minutes=31)), "15m", now, gold)
    assert service.is_due(None, "15m", now, gold)


def test_replay_runs_the_live_engine_and_accounts_trades_consistently(session):
    from app.research.run_signal_track_record import replay

    _seed("BTCUSDT", n=900, base=60000.0, end=datetime(2025, 6, 1, tzinfo=timezone.utc))
    res = replay("BTCUSDT", "1H", max_steps=150)
    assert res["n_steps"] == 150 and res["status"] in ("no_edge", "negative", "validated")
    assert set(res["oos_buckets"]) == {"60-69", "70-79", "80-100"}
    for t in res["trades"]:
        assert t["score"] >= 60 and t["dir"] in ("BUY", "SELL")
        assert (t["r"] > 0) == t["tp_hit"] or t["r"] <= 0  # a target exit is the only way to a positive R
