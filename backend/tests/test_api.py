import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import hash_api_key
from app.database.models import User
from app.main import create_app
from tests.chart_fixtures import png_bytes, render_chart
from tests.conftest import make_candles
from tests.test_chart_vision import walk_ohlc

BASE = "https://api.binance.com"


def klines(n=900, seed=4, vol=15.0, drift=0.0):
    now_h = int(datetime.now(timezone.utc).timestamp() // 3600 * 3600)
    start = datetime.fromtimestamp(now_h - n * 3600, tz=timezone.utc)
    rows = []
    for c in make_candles(n, start, 3600, base=60000, seed=seed, vol=vol, drift=drift):
        ms = int(c.ts.timestamp() * 1000)
        rows.append([ms, str(c.open), str(c.high), str(c.low), str(c.close), "12.5", ms + 3599_999, "1", 10, "1", "1", "0"])
    return rows


@pytest.fixture()
def client(engine):
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture()
def synced(client):
    """Client with 900 synthetic 1H BTCUSDT candles loaded through the real ingestion path (mocked HTTP)."""
    with respx.mock:
        respx.get(f"{BASE}/api/v3/klines").mock(return_value=httpx.Response(200, json=klines()))
        r = client.post("/api/v1/market/sync", json={"symbol": "BTCUSDT", "timeframe": "1H", "bars": 900})
        assert r.status_code == 200, r.text
    return client


def test_health_and_mode(client):
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["mode"] == "analysis_only"
    assert client.get("/openapi.json").status_code == 200


def test_instruments_are_honest_about_support(client):
    focus = client.get("/api/v1/market/instruments").json()
    assert {i["canonical_symbol"] for i in focus} == {"BTCUSDT", "XAUUSD", "EURUSD", "GBPUSD"}  # default focus: gold, bitcoin, two FX majors
    items = {i["canonical_symbol"]: i for i in client.get("/api/v1/market/instruments", params={"all": "true"}).json()}
    assert set(items) == {"XAUUSD", "US30", "BTCUSDT", "USOIL", "GBPUSD", "EURUSD"}
    assert items["BTCUSDT"]["mappings"][0]["provider"] == "binance" and items["BTCUSDT"]["mappings"][0]["status"] == "active"
    gbp = items["GBPUSD"]["mappings"][0]
    assert (gbp["provider"], gbp["provider_symbol"]) == ("twelve_data", "GBP/USD") and items["GBPUSD"]["price_precision"] == 5
    us30 = {m["provider"]: m for m in items["US30"]["mappings"]}
    assert us30["oanda"]["provider_symbol"] == "US30_USD" and us30["oanda"]["status"] == "unverified"
    assert "ETF" in us30["oanda"]["notes"] or "NOT the index" in us30["oanda"]["notes"]  # no silent ETF substitution
    assert items["XAUUSD"]["mappings"][0]["status"] == "active"  # live-verified 2026-11-01 (migration 0003)
    assert len(client.get("/api/v1/market/timeframes").json()) == 14


def test_unconfigured_providers_report_it_instead_of_inventing_data(client):
    q = {x["symbol"]: x for x in client.get("/api/v1/market/quotes", params={"symbols": "XAUUSD,GBPUSD"}).json()}
    assert all(x["status"] == "not_configured" and x["price"] is None for x in q.values())
    assert "TWELVE_DATA_API_KEY" in q["XAUUSD"]["message"] and "TWELVE_DATA_API_KEY" in q["GBPUSD"]["message"]
    with respx.mock:  # US30 is served by BiQuote (no key): a CLOSED market is returned as a last price that says so, never as a live one
        batch = json.loads((Path(__file__).parent / "fixtures" / "biquote" / "latest_batch.json").read_text(encoding="utf8"))
        respx.get("https://biquote.io/api/US30").mock(return_value=httpx.Response(200, json=batch["US30"]))
        us30 = client.get("/api/v1/market/quotes", params={"symbols": "US30"}).json()[0]
    assert us30["status"] == "ok" and us30["provider"] == "biquote" and "not a live price" in us30["message"]
    c = client.get("/api/v1/market/candles", params={"symbol": "US30", "timeframe": "1H"}).json()
    assert c["provider"] == "biquote" and c["count"] == 0  # nothing stored, nothing fabricated


def test_validation_errors_use_the_standard_envelope(client):
    r = client.post("/api/v1/analysis/run", json={"symbol": "BTCUSDT", "timeframe": "7m"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"


def test_sync_candles_coverage_patterns(synced):
    c = synced
    cs = c.get("/api/v1/market/candles", params={"symbol": "BTCUSDT", "timeframe": "1H", "limit": 100}).json()
    assert cs["provider"] == "binance" and cs["count"] == 100 and cs["candles"][0]["time"] < cs["candles"][-1]["time"]
    assert all(x["complete"] for x in cs["candles"])
    cov = c.get("/api/v1/market/coverage", params={"symbol": "BTCUSDT"}).json()
    assert cov and cov[0]["timeframe"] == "1H" and cov[0]["candle_count"] >= 899 and cov[0]["last_sync_status"] == "ok"
    p = c.get("/api/v1/patterns", params={"symbol": "BTCUSDT", "timeframe": "1H"}).json()
    assert p["n_bars"] >= 600 and p["events"] and {"kind", "direction", "time", "evidence"} <= set(p["events"][0])
    assert c.get("/api/v1/patterns/definitions").json()["candlestick"]["hammer"]


def test_analysis_flow_end_to_end(synced):
    c = synced
    r = c.post("/api/v1/analysis/run", json={"symbol": "BTCUSDT", "timeframe": "1H", "auto_sync": False,
                                             "mtf": {"entry": "1H"}})
    assert r.status_code == 202
    a = c.get(r.json()["poll_url"]).json()
    assert a["status"] == "completed", a
    res = a["result"]["decision"]
    assert res["decision"] in ("BUY", "SELL", "WAIT")
    if res["decision"] != "WAIT":
        assert res["plan"]["risk_reward"] >= 1.5 and res["plan"]["stop_loss"] and res["plan"]["targets"]
    assert res["confidence"]["model_probability"] is None  # no validated model exists -> no probabilities
    assert any("no trained ML model" in w for w in res["warnings"])
    preds = c.get("/api/v1/predictions", params={"analysis_id": a["id"]}).json()
    assert preds["total"] == 1
    d = c.get(f"/api/v1/predictions/{preds['items'][0]['id']}").json()
    assert d["symbol"] == "BTCUSDT" and d["evidence"] and d["confidence"]["data_quality"]["score"] > 0
    an = c.get(f"/api/v1/analysis/{a['id']}/analogues").json()
    assert "not a probability" in an["note"].lower() or "rank resemblance" in an["note"]
    assert an["summary"]["n_obs"] > 0
    assert c.get("/api/v1/predictions/stats").json()["total"] == 1


def test_analysis_without_data_or_credentials_fails_clearly(client):
    r = client.post("/api/v1/analysis/run", json={"symbol": "XAUUSD", "timeframe": "1H"})  # Twelve Data without a key: no data, no credentials
    assert r.status_code == 202
    a = client.get(r.json()["poll_url"]).json()
    assert a["status"] == "failed" and "Sync data first" in a["error"]


def test_backtest_flow(synced):
    c = synced
    r = c.post("/api/v1/backtests/run", json={"symbol": "BTCUSDT", "timeframe": "1H", "strategy": "ma_cross", "bars": 900,
                                              "auto_sync": False, "spread": 5.0, "eval_every": 1})
    assert r.status_code == 202
    b = c.get(r.json()["poll_url"]).json()
    assert b["status"] == "completed", b
    assert b["metrics"]["n_trades"] > 0 and len(b["trades"]) == b["metrics"]["n_trades"] and b["equity_curve"]
    assert any("same-bar" in x for x in b["metrics"]["caveats"])
    assert c.get("/api/v1/backtests").json()["total"] == 1
    assert c.get("/api/v1/backtests/strategies").json()


def test_user_isolation_and_auth_required(engine, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        from app.database.session import session_scope

        with session_scope() as s:
            s.add_all([User(email="a@x", api_key_hash=hash_api_key("key-a")), User(email="b@x", api_key_hash=hash_api_key("key-b"))])
        assert c.get("/api/v1/predictions").status_code == 401
        assert c.get("/api/v1/predictions", headers={"X-API-Key": "wrong"}).status_code == 401
        with respx.mock:
            respx.get(f"{BASE}/api/v3/klines").mock(return_value=httpx.Response(200, json=klines(400)))
            assert c.post("/api/v1/market/sync", json={"symbol": "BTCUSDT", "timeframe": "1H", "bars": 400},
                          headers={"X-API-Key": "key-a"}).status_code == 200
        r = c.post("/api/v1/analysis/run", json={"symbol": "BTCUSDT", "timeframe": "1H", "auto_sync": False},
                   headers={"X-API-Key": "key-a"})
        aid = r.json()["id"]
        assert c.get(f"/api/v1/analysis/{aid}", headers={"X-API-Key": "key-a"}).status_code == 200
        assert c.get(f"/api/v1/analysis/{aid}", headers={"X-API-Key": "key-b"}).status_code == 404
        assert c.get("/api/v1/analysis", headers={"X-API-Key": "key-b"}).json()["total"] == 0
        wl = c.post("/api/v1/watchlists", json={"name": "mine"}, headers={"X-API-Key": "key-a"}).json()
        assert c.delete(f"/api/v1/watchlists/{wl['id']}", headers={"X-API-Key": "key-b"}).status_code == 404
    get_settings.cache_clear()


def test_rate_limit(engine, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        codes = [c.get("/api/v1/market/timeframes").status_code for _ in range(8)]
        assert codes[:5] == [200] * 5 and 429 in codes[5:]
        assert c.get("/api/v1/health").status_code == 200  # health is exempt
    get_settings.cache_clear()


def test_watchlist_crud(client):
    wl = client.post("/api/v1/watchlists", json={"name": "core"}).json()
    out = client.post(f"/api/v1/watchlists/{wl['id']}/items", json={"symbol": "xauusd", "note": "gold"}).json()
    assert out["items"][0]["symbol"] == "XAUUSD"
    assert client.post(f"/api/v1/watchlists/{wl['id']}/items", json={"symbol": "NOPE"}).status_code == 404
    assert client.delete(f"/api/v1/watchlists/{wl['id']}/items/{out['items'][0]['id']}").status_code == 204
    assert client.get("/api/v1/watchlists").json()[0]["items"] == []


def test_model_training_job_is_research_only(synced):
    c = synced
    r = c.post("/api/v1/models/train", json={"symbol": "BTCUSDT", "timeframe": "1H", "algorithm": "logistic", "bars": 1000,
                                             "auto_sync": False, "horizon_bars": 12, "n_splits": 3})
    assert r.status_code == 202
    models = c.get("/api/v1/models").json()
    assert models["total"] == 1
    m = models["items"][0]
    assert m["validation_status"] == "research_only" and m["validation_reasons"] and m["is_active"]
    assert c.get(f"/api/v1/models/{m['id']}").json()["metrics"]["brier"] is not None


def test_screenshot_pipeline_without_ocr_stays_honest(client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    ohlc = walk_ohlc(70)
    img, info = render_chart(ohlc)
    pts = [{"y": 100, "price": info["price_of"](100)}, {"y": 500, "price": info["price_of"](500)}]
    r = client.post("/api/v1/charts/analyze", files={"file": ("chart.png", png_bytes(img), "image/png")},
                    data={"symbol": "US30", "timeframe": "1H", "calibration_points": json.dumps(pts)})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["n_candles"] == 70 and out["price_calibrated"] is True
    assert any("Tesseract" in w for w in out["warnings"]) or out["quality"]["ocr_available"]
    assert out["data_source"] == "extracted_from_pixels"
    pred = client.get(f"/api/v1/predictions/{out['prediction_id']}").json()
    assert pred["decision"] == "WAIT"  # 70 pixel-derived bars: data quality gate blocks any signal
    assert any("timestamps" in w for w in pred["warnings"])
    # same image without calibration or instrument -> no analysis, explicit reason
    r2 = client.post("/api/v1/charts/analyze", files={"file": ("chart.png", png_bytes(img), "image/png")}).json()
    assert r2["status"] == "needs_input" and r2["analysis_id"] is None
    # hostile upload
    bad = client.post("/api/v1/charts/analyze", files={"file": ("x.png", b"<html>", "image/png")})
    assert bad.status_code == 422
    get_settings.cache_clear()


def test_outcome_tracking_is_independent_of_backtests(synced):
    from app.market_data.bars import Bars
    from app.prediction.outcome import evaluate_outcome

    after = Bars.from_arrays([100, 101, 103], [101, 104, 106], [99.5, 100.5, 102], [100.5, 103, 105])
    r = evaluate_outcome("BUY", 99.8, 100.2, 98, 104, after)
    assert r["outcome"] == "tp_hit" and r["r_multiple"] == pytest.approx(abs(104 - r["entry_price"]) / abs(r["entry_price"] - 98))
    sl_first = Bars.from_arrays([100, 100], [105, 100], [97, 99], [101, 99.5])
    assert evaluate_outcome("BUY", 99.8, 100.2, 98, 104, sl_first)["outcome"] == "sl_hit"  # both in one bar -> stop first
    assert evaluate_outcome("WAIT", 0, 0, 0, 0, after)["outcome"] == "not_applicable"
    unfilled = Bars.from_arrays([110] * 5, [111] * 5, [109] * 5, [110] * 5)
    assert evaluate_outcome("BUY", 99.8, 100.2, 98, 104, unfilled, max_bars=5)["outcome"] == "expired"


def test_managed_postgres_urls_are_rewritten_to_the_psycopg_dialect(monkeypatch):
    from app.core.config import Settings

    assert Settings(database_url="postgres://u:p@h:5432/d").database_url == "postgresql+psycopg://u:p@h:5432/d"
    assert Settings(database_url="postgresql://u:p@h:5432/d").database_url == "postgresql+psycopg://u:p@h:5432/d"
    assert Settings(database_url="postgresql+psycopg://u:p@h/d").database_url == "postgresql+psycopg://u:p@h/d"
    assert Settings(database_url="sqlite:///./x.db").database_url == "sqlite:///./x.db"
    assert "p@h" not in repr(Settings(database_url="postgres://u:p@h:5432/d"))  # credentials never in repr


def test_screenshot_warns_when_the_typed_instrument_contradicts_the_chart_title(client, tmp_path, monkeypatch):
    import app.services.chart_service as cs

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(cs, "ocr_available", lambda: True)
    monkeypatch.setattr(cs, "read_title_text", lambda img: "XAUUSD 1H")
    monkeypatch.setattr(cs, "read_price_axis", lambda img, x: [])
    img, _ = render_chart(walk_ohlc(70))
    files = {"file": ("chart.png", png_bytes(img), "image/png")}
    wrong = client.post("/api/v1/charts/analyze", files=files, data={"symbol": "BTCUSDT"}).json()
    assert any("title reads XAUUSD" in w for w in wrong["warnings"]) and wrong["symbol"] == "BTCUSDT"
    auto = client.post("/api/v1/charts/analyze", files=files).json()
    assert auto["symbol"] == "XAUUSD" and auto["timeframe"] == "1H"  # blank field: the image decides
    assert not any("title reads" in w for w in auto["warnings"])
    get_settings.cache_clear()


def test_market_closure_candles_are_hidden_from_charts_and_analysis_but_stay_stored(client):
    """Some FX/metal feeds publish thin weekend quotes. They must not reach charts or the analysis engine."""
    from datetime import timedelta
    from decimal import Decimal

    from sqlalchemy import select

    from app.database.models import Candle as CandleRow
    from app.database.models import DataProvider, Instrument
    from app.database.session import session_scope
    from app.market_data.ingestion.service import store_candles
    from app.market_data.types import Candle
    from app.services.data_service import load_bars

    start = datetime(2024, 1, 5, 18, tzinfo=timezone.utc)  # Friday 13:00 New York (winter time)
    rows = [Candle(start + timedelta(hours=h), Decimal(2000 + h), Decimal(2001 + h), Decimal(1999 + h), Decimal(2000 + h)) for h in range(0, 56)]
    with session_scope() as s:
        inst = s.scalar(select(Instrument).where(Instrument.canonical_symbol == "XAUUSD"))
        prov = s.scalar(select(DataProvider).where(DataProvider.code == "twelve_data"))
        store_candles(s, inst.id, prov.id, "1H", rows)
        stored = len(s.scalars(select(CandleRow.ts)).all())
        bars = load_bars(s, inst, prov, "1H", 100)
    visible = client.get("/api/v1/market/candles", params={"symbol": "XAUUSD", "timeframe": "1H", "limit": 100}).json()["candles"]
    everything = client.get("/api/v1/market/candles", params={"symbol": "XAUUSD", "timeframe": "1H", "limit": 100, "trading_hours_only": "false"}).json()["candles"]
    hours = sorted(datetime.fromtimestamp(c["time"], tz=timezone.utc).strftime("%a %H") for c in visible)
    assert stored == len(everything) == 56
    assert hours == sorted(["Fri 18", "Fri 19", "Fri 20", "Fri 21", "Sun 22", "Sun 23", "Mon 00", "Mon 01"])  # closed Fri 22:00 - Sun 22:00 UTC
    assert len(bars) == len(visible) == 8 and all(datetime.fromtimestamp(int(t), tz=timezone.utc).strftime("%a") != "Sat" for t in bars.t)


def test_all_timeframe_scan_attaches_study_evidence_and_never_invents_it(synced, tmp_path, monkeypatch):
    import json

    import app.services.pattern_scan as ps

    c = synced
    monkeypatch.setattr(ps, "EVIDENCE_PATH", tmp_path / "missing.json")  # the real study file ships with the repo
    empty = c.get("/api/v1/patterns/scan", params={"symbol": "BTCUSDT", "recent": 20}).json()
    tfs = {f["timeframe"]: f for f in empty["timeframes"]}
    assert len(tfs) == 14 and tfs["1H"]["status"] == "ok" and tfs["1M"]["status"] == "insufficient_data"
    firing = tfs["1H"]["patterns_firing"]
    assert firing and all(f["verdict"] == "no_study_data" and f["evidence"] is None for f in firing)  # no file => no claims
    name = f"{firing[0]['pattern']}:{firing[0]['side']}"
    ev = {"meta": {"experiment_id": 1}, "symbols": {"BTCUSDT": {"1H": {name: {"i_n": 80, "cand": True, "cg": True, "cn": False, "o_n": 40, "o_lift": 0.2}}}}}
    f = tmp_path / "ev.json"
    f.write_text(json.dumps(ev))
    monkeypatch.setattr(ps, "EVIDENCE_PATH", f)
    got = c.get("/api/v1/patterns/scan", params={"symbol": "BTCUSDT", "recent": 20}).json()
    match = next(x for x in {g["timeframe"]: g for g in got["timeframes"]}["1H"]["patterns_firing"] if f"{x['pattern']}:{x['side']}" == name)
    assert match["verdict"] == "confirmed_not_profitable_after_costs" and match["evidence"]["o_lift"] == 0.2
    assert got["evidence_meta"]["experiment_id"] == 1


def test_buy_sell_carries_the_pattern_study_caveat_only_when_nothing_was_validated(tmp_path, monkeypatch):
    import json

    import app.services.pattern_scan as ps

    f = tmp_path / "ev.json"
    f.write_text(json.dumps({"meta": {"experiments": {"BTCUSDT": {"id": 7, "summary": {"tested": 600, "confirmed_net": 0}},
                                                      "XAUUSD": {"id": 8, "summary": {"tested": 600, "confirmed_net": 2}}}}, "symbols": {}}))
    assert "Pattern study #7" in ps.study_caveat("BTCUSDT", f) and "600 patterns" in ps.study_caveat("BTCUSDT", f)
    assert ps.study_caveat("XAUUSD", f) is None  # a validated pattern exists: no blanket warning
    assert ps.study_caveat("GBPUSD", f) is None  # never studied: no claim either way


def test_gold_research_endpoint_answers_without_research_data(client, monkeypatch, tmp_path):
    from app.gold_research import dashboard
    monkeypatch.setattr(dashboard, "DASHBOARD", tmp_path / "missing.json")
    r = client.get("/api/v1/research/gold")
    assert r.status_code == 200 and r.json()["available"] is False
