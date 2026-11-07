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


def test_summary_lists_configured_instruments_and_is_honest_about_missing_data(client):
    _seed("XAUUSD")
    items = {i["symbol"]: i for i in client.get("/api/v1/signals").json()["items"]}
    assert set(items) == set(get_settings().signal_list)
    assert items["XAUUSD"]["status"] == "ok" and "overall" in items["XAUUSD"]
    assert items["BTCUSDT"]["status"] == "unavailable" and items["BTCUSDT"]["reason"]


def test_config_track_record_and_validation_errors(client):
    cfg = client.get("/api/v1/signals/config").json()
    assert sum(cfg["factors"].values()) == 100 and cfg["thresholds"]["signal"] == 60
    assert cfg["spreads"]["XAUUSD"] == pytest.approx(0.30) and cfg["spreads"]["BTCUSDT"] == pytest.approx(2.0)
    assert "results" in client.get("/api/v1/signals/track-record").json()
    assert client.get("/api/v1/signals/NOPE").status_code == 404
    assert client.get("/api/v1/signals/xa").status_code == 422


def test_sync_fetches_only_due_timeframes_from_keyless_providers(client, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "ensure_data", lambda s, inst, prov, pi, tf, n, auto: calls.append((prov.code, tf)) or [])
    r = client.post("/api/v1/signals/BTCUSDT/sync")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "binance" and body["synced"] is True  # BTCUSDT is routed to Binance (deep history, keyless)
    assert ("binance", "1H") in calls and body["analysis"]["symbol"] == "BTCUSDT"


def test_replay_runs_the_live_engine_and_accounts_trades_consistently(session):
    from app.research.run_signal_track_record import replay

    _seed("BTCUSDT", n=900, base=60000.0, end=datetime(2025, 6, 1, tzinfo=timezone.utc))
    res = replay("BTCUSDT", "1H", max_steps=150)
    assert res["n_steps"] == 150 and res["status"] in ("no_edge", "negative", "validated")
    assert set(res["oos_buckets"]) == {"60-69", "70-79", "80-100"}
    for t in res["trades"]:
        assert t["score"] >= 60 and t["dir"] in ("BUY", "SELL")
        assert (t["r"] > 0) == t["tp_hit"] or t["r"] <= 0  # a target exit is the only way to a positive R
