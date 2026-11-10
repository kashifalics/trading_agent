"""Security and honesty guarantees checked before customer handover: every endpoint except the health check needs a key when
AUTH_REQUIRED=true, the quote endpoint cannot be used to grow memory, production CORS allows only the configured frontend, delayed
prices are flagged, and every signal plan carries an explicit validation label."""
import re
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import hash_api_key
from app.database.models import User
from app.main import create_app
from app.market_data.types import Quote


@pytest.fixture()
def auth_client(engine, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        from app.database.session import session_scope

        with session_scope() as s:
            s.add(User(email="owner@x", api_key_hash=hash_api_key("ati_good")))
        yield c
    get_settings.cache_clear()


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda m: "XAUUSD" if "symbol" in m.group(0) else "1", path)


def test_every_endpoint_except_health_requires_a_key(auth_client):
    # Enumerated from the OpenAPI schema (stable across FastAPI versions, unlike the internal route objects).
    paths = create_app().openapi()["paths"]
    routes = [(m.upper(), p) for p, ops in paths.items() if p.startswith("/api/v1") for m in ops]
    assert len(routes) > 50
    open_routes = []
    for method, path in routes:
        if path == "/api/v1/health":
            continue
        resp = auth_client.request(method, _concrete(path))
        if resp.status_code != 401:
            open_routes.append((method, path, resp.status_code))
    assert open_routes == [], f"endpoints reachable without a key: {open_routes}"
    assert auth_client.get("/api/v1/health").status_code == 200
    assert auth_client.get("/api/v1/health").json()["auth_required"] is True


def test_a_wrong_key_is_rejected_and_a_good_key_is_confirmed(auth_client):
    assert auth_client.get("/api/v1/auth/status", headers={"X-API-Key": "ati_wrong"}).status_code == 401
    r = auth_client.get("/api/v1/auth/status", headers={"X-API-Key": "ati_good"})
    assert r.status_code == 200 and r.json()["authenticated"] is True and r.json()["key_used"] is True
    assert "email" not in r.json()
    assert auth_client.get("/api/v1/market/instruments", headers={"X-API-Key": "ati_good"}).status_code == 200


def test_quotes_never_call_a_provider_or_cache_unknown_names(engine, monkeypatch):
    get_settings.cache_clear()
    from app.api.v1.routes import market

    market._quote_cache.clear()
    calls = []

    class FakeProvider:
        def get_latest_quote(self, symbol):
            calls.append(symbol)
            return Quote(symbol=symbol, price=Decimal("2000.5"), ts=datetime(2026, 11, 6, 21, 0, tzinfo=timezone.utc), provider="fake",
                         bid=Decimal("2000.3"), ask=Decimal("2000.7"), is_delayed=True)

    monkeypatch.setattr(market, "get_provider", lambda code: FakeProvider())
    with TestClient(create_app()) as c:
        names = ",".join(f"JUNK{i}" for i in range(500)) + ",XAUUSD"
        out = c.get("/api/v1/market/quotes", params={"symbols": names}).json()
        assert len(out) == market.MAX_QUOTE_SYMBOLS and all(q["status"] == "error" for q in out)
        assert calls == [] and market._quote_cache == {}
        q = c.get("/api/v1/market/quotes", params={"symbols": "XAUUSD,xauusd"}).json()
        assert len(q) == 1 and q[0]["status"] == "ok" and q[0]["delayed"] is True and "not a live price" in q[0]["message"]
        assert set(market._quote_cache) == {"XAUUSD"}
    market._quote_cache.clear()  # the cache is module-level: never leak the fake quote into other tests
    get_settings.cache_clear()


def test_production_cors_allows_only_the_configured_frontend(engine, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-not-default")
    monkeypatch.setenv("FRONTEND_URL", "https://app.example.com")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        pre = {"Access-Control-Request-Method": "GET"}
        ok = c.options("/api/v1/health", headers={"Origin": "https://app.example.com", **pre})
        assert ok.headers.get("access-control-allow-origin") == "https://app.example.com"
        bad = c.options("/api/v1/health", headers={"Origin": "http://localhost:3000", **pre})
        assert bad.headers.get("access-control-allow-origin") is None
    get_settings.cache_clear()


def test_every_plan_is_labelled_not_validated_unless_validated():
    from app.signals.track_record import validation_of

    for tr in ({"available": False, "status": "untested"},
               {"available": True, "status": "no_edge", "oos": {"n_trades": 78}},
               {"available": True, "status": "negative", "oos": {"n_trades": 414}}):
        v = validation_of(tr)
        assert v["status"] == "not_validated" and v["label"] == "Not validated" and "not a proven trade" in v["note"]
    assert "78 out-of-sample trades" in validation_of({"available": True, "status": "no_edge", "oos": {"n_trades": 78}})["note"]
    assert validation_of({"available": True, "status": "validated", "summary": "passed"})["status"] == "validated"


def test_the_shipped_track_record_validates_nothing():
    """The product must not present any signal series as validated: the shipped replay has no validated series."""
    from app.signals import track_record

    results = track_record.load().get("results", {})
    statuses = {r["status"] for series in results.values() for r in series.values()}
    assert statuses and "validated" not in statuses


def _best_plan():
    return {"decision": "BUY", "instruction": "EXECUTE NOW", "timeframe": "1H", "setup_type": "trend_pullback", "score": 72,
            "entry_type": "market", "entry": 3950.5, "stop_loss": 3935.25, "bias_tfs": ["4H", "1D"], "confirm_tf": "15m",
            "targets": [{"label": "TP1", "price": 3990.0, "rr": 2.59}, {"label": "TP2", "price": 4012.0, "rr": 4.03}],
            "reasons_for": ["4H trend bullish"], "reasons_against": ["no liquidity sweep"]}


def test_the_written_report_uses_exactly_the_plan_numbers_and_states_validation():
    from app.signals.engine import build_report, fmt
    from app.signals.service import attach_validation

    best = _best_plan()
    res = {"symbol": "XAUUSD", "best": best, "overall": {"label": "Bullish", "detail": "4H and 1D bullish"}, "session": "london",
           "timeframes": []}
    res["report"] = build_report(res, None)
    text = res["report"]["text"]
    for v in (best["entry"], best["stop_loss"], 3990.0, 4012.0):
        assert fmt(v) in text
    assert "2.59R" in text and "4.03R" in text and "72/100" in text and "EXECUTE NOW" in text
    assert res["report"]["decision"]["win_probability"] is None  # no probability is ever invented
    attach_validation("XAUUSD", res)
    assert best["validation"]["status"] == "not_validated"
    assert res["report"]["validation"]["label"] == "Not validated" and "Validation: Not validated" in res["report"]["text"]


def test_the_part15_report_copies_the_plan_levels_and_validation():
    from app.signals.classify import analysis_report

    best = {**_best_plan(), "validation": {"status": "not_validated", "label": "Not validated", "note": "n"}}
    r = analysis_report("XAUUSD", {"best": best, "quote": {"price": 3951.0}, "timeframes": [], "overall": {"label": "Bullish"}})
    tp = r["trade_plan"]
    assert (tp["entry"], tp["stop_loss"], tp["tp1"], tp["tp2"], tp["tp3"]) == (3950.5, 3935.25, 3990.0, 4012.0, None)
    assert tp["risk_reward"] == [2.59, 4.03] and r["validation"]["status"] == "not_validated"


def test_a_research_only_model_cannot_be_activated(engine):
    get_settings.cache_clear()
    from app.database.models import DataProvider, Instrument, ModelVersion
    from app.database.session import session_scope

    with TestClient(create_app()) as c:
        with session_scope() as s:
            inst = s.query(Instrument).filter_by(canonical_symbol="BTCUSDT").one()
            prov = s.query(DataProvider).filter_by(code="binance").one()
            common = dict(instrument_id=inst.id, provider_id=prov.id, timeframe="1H", algorithm="logistic", artifact_path="x.joblib",
                          n_samples=1000)
            research = ModelVersion(name="r", version="1", validation_status="research_only", is_calibrated=True, **common)
            passed = ModelVersion(name="p", version="2", validation_status="passed_minimum_checks", is_calibrated=True, **common)
            s.add_all([research, passed])
            s.flush()
            rid, pid = research.id, passed.id
        r = c.post(f"/api/v1/models/{rid}/activate")
        assert r.status_code == 409 and r.json()["error"]["code"] == "not_promotable"
        assert c.post(f"/api/v1/models/{pid}/activate").status_code == 200
    get_settings.cache_clear()
