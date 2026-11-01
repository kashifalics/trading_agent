"""Integration tests: the scan orchestrator on stored candles (database) and the /opportunities API.

The candles are deterministic synthetic TEST FIXTURES inserted straight into a throw-away in-memory database; they are never
presented as market data. Providers are never contacted (no keys are configured in tests).
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_api_key
from app.database.base import utcnow
from app.database.models import Candle as CandleRow
from app.database.models import (
    Instrument,
    MarketScan,
    OpportunityStatusHistory,
    ProviderInstrument,
    TimeframeAnalysis,
    TradeOpportunity,
    User,
)
from app.main import create_app
from app.market_data.ingestion.service import resolve_mapping
from app.opportunities import scanner
from app.opportunities.analysis import prepare_tf
from app.opportunities.config import PROFILES, STYLE_ORDER
from tests.conftest import make_candles

N = 1500


def load_btc(session, n=N, incomplete_tail=False):
    inst, prov, _ = resolve_mapping(session, "BTCUSDT")
    now_h = int(datetime.now(timezone.utc).timestamp() // 3600 * 3600)
    start = datetime.fromtimestamp(now_h - (n + 2) * 3600, tz=timezone.utc)
    cs = make_candles(n, start, 3600, base=60000, seed=11, vol=150.0, drift=2.0)
    rows = [CandleRow(instrument_id=inst.id, provider_id=prov.id, timeframe="1H", ts=c.ts, open=c.open, high=c.high, low=c.low, close=c.close,
                      volume=c.volume, volume_type="base", is_complete=True, origin="native") for c in cs]
    if incomplete_tail:
        last = cs[-1]
        rows.append(CandleRow(instrument_id=inst.id, provider_id=prov.id, timeframe="1H", ts=last.ts + timedelta(hours=1), open=last.close,
                              high=last.close * 3, low=last.close / 2, close=last.close * 2, volume=last.volume, volume_type="base",
                              is_complete=False, origin="native"))
    session.add_all(rows)
    session.commit()
    return inst, prov


def run(session, symbols=("BTCUSDT", "US30", "USOIL", "XAUUSD")):
    scan, dup = scanner.create_scan(session, None, {"symbols": list(symbols)}, "manual")
    assert not dup
    scanner.execute_scan(session, scan)
    session.expire_all()
    return session.get(MarketScan, scan.id)


# ----------------------------------------------------------------------------------------------- orchestrator
def test_scan_reports_every_timeframe_and_marks_unsupported_instruments_unavailable(session):
    inst, _ = load_btc(session)
    scan = run(session)
    assert scan.status == "completed" and scan.config_version and scan.code_version["source_sha256"]
    info = {i["symbol"]: i for i in scan.instruments}
    for sym in ("US30", "USOIL"):
        assert info[sym]["status"] == "unavailable" and "OANDA_API_TOKEN" in info[sym]["reason"]
    assert info["XAUUSD"]["status"] == "unavailable" and "TWELVE_DATA_API_KEY" in info["XAUUSD"]["reason"]
    tfs = {t["timeframe"]: t for t in info["BTCUSDT"]["timeframes"]}
    assert len(tfs) == 14
    assert tfs["1H"]["status"] == "completed" and tfs["1H"]["n_bars"] == N and tfs["1H"]["derived_from"] is None
    assert tfs["4H"]["status"] == "completed" and tfs["4H"]["derived_from"] == "1H"  # built from stored 1H, flagged as derived
    assert tfs["1m"]["status"] == "insufficient_data" and tfs["12M"]["status"] == "insufficient_data"
    assert session.scalar(select(func.count()).select_from(TimeframeAnalysis).where(TimeframeAnalysis.instrument_id == inst.id)) == 14
    # no analysis, opportunity or candle is ever created for instruments without data
    others = session.scalars(select(Instrument.id).where(Instrument.canonical_symbol.in_(("US30", "USOIL", "XAUUSD")))).all()
    assert session.scalar(select(func.count()).select_from(TradeOpportunity).where(TradeOpportunity.instrument_id.in_(others))) == 0
    assert session.scalar(select(func.count()).select_from(CandleRow).where(CandleRow.instrument_id.in_(others))) == 0
    assert scan.summary["instruments_unavailable"] == ["US30", "USOIL", "XAUUSD"] and scan.summary["timeframes_completed"] == 3  # 1H native + 2H and 4H derived from it


def test_one_headline_per_style_and_scalping_needs_native_fresh_data(session):
    load_btc(session)
    run(session, ("BTCUSDT",))
    heads = session.scalars(select(TradeOpportunity).where(TradeOpportunity.is_headline.is_(True))).all()
    assert sorted(h.style for h in heads) == sorted(STYLE_ORDER)
    scalp = next(h for h in heads if h.style == "scalping")
    assert scalp.direction == "WAIT" and scalp.status == "none"  # only 1H+ data exists: no scalp is invented
    assert scalp.evidence["wait_reasons"] and scalp.evidence["score"] is None
    for h in heads:
        assert h.direction in ("BUY", "SELL", "WAIT")
        if h.direction in ("BUY", "SELL"):  # an actionable setup always carries every required level and a transparent score
            assert None not in (h.entry_low, h.entry_high, h.stop_loss, h.take_profit_1, h.take_profit_2, h.invalidation, h.risk_reward)
            assert h.evidence["score"]["label"] == "Evidence Score — Not Win Probability"
            assert h.risk_reward >= PROFILES[h.style].min_rr
            assert h.validation_status != "validated"  # nothing shipped is validated


def test_unchanged_data_is_not_reanalysed_and_creates_no_duplicates(session):
    load_btc(session)
    first = run(session, ("BTCUSDT",))
    n_heads = session.scalar(select(func.count()).select_from(TradeOpportunity))
    second = run(session, ("BTCUSDT",))
    assert second.id != first.id and second.status == "completed"
    rows = session.scalars(select(TimeframeAnalysis).where(TimeframeAnalysis.scan_id == second.id, TimeframeAnalysis.status == "completed")).all()
    assert rows and all(r.reused_from_id is not None and r.result is None for r in rows)  # pointers to the earlier identical analysis
    assert all(s["cache"] == "unchanged_data_reused" for s in second.instruments[0]["styles"].values())
    assert session.scalar(select(func.count()).select_from(TradeOpportunity)) == n_heads  # nothing duplicated
    assert {o.last_scan_id for o in session.scalars(select(TradeOpportunity))} == {second.id}
    # new data invalidates the cache
    inst, prov, _ = resolve_mapping(session, "BTCUSDT")
    last = session.scalar(select(func.max(CandleRow.ts)).where(CandleRow.instrument_id == inst.id))
    c = make_candles(1, last + timedelta(hours=1), 3600, base=61000, seed=2, vol=100)[0]
    session.add(CandleRow(instrument_id=inst.id, provider_id=prov.id, timeframe="1H", ts=c.ts, open=c.open, high=c.high, low=c.low, close=c.close,
                          volume=c.volume, volume_type="base", is_complete=True, origin="native"))
    session.commit()
    third = run(session, ("BTCUSDT",))
    assert any(s["cache"] == "recomputed" for s in third.instruments[0]["styles"].values())


def test_incomplete_candles_are_never_analysed_as_completed(session):
    load_btc(session, incomplete_tail=True)
    scan = run(session, ("BTCUSDT",))
    tf = next(t for t in scan.instruments[0]["timeframes"] if t["timeframe"] == "1H")
    assert tf["n_bars"] == N  # the forming candle (with an absurd range) was excluded
    inst, prov, pi = resolve_mapping(session, "BTCUSDT")
    t = prepare_tf(session, inst, prov, pi, "1H")
    assert float(t.bars.h.max()) < 100_000 and len(t.bars) == N


def test_a_failing_timeframe_is_reported_and_does_not_fail_the_scan(session, monkeypatch):
    load_btc(session)
    from app.opportunities import analysis

    real = analysis.load_bars

    def flaky(s, inst, prov, tf, n, *a, **k):
        if tf == "2H":
            raise RuntimeError("simulated storage failure")
        return real(s, inst, prov, tf, n, *a, **k)

    monkeypatch.setattr(analysis, "load_bars", flaky)
    scan = run(session, ("BTCUSDT",))
    assert scan.status == "completed"
    tfs = {t["timeframe"]: t for t in scan.instruments[0]["timeframes"]}
    assert tfs["2H"]["status"] == "failed" and "simulated storage failure" in tfs["2H"]["reason"]
    assert tfs["1H"]["status"] == "completed" and tfs["4H"]["status"] == "completed"  # the other timeframes are unaffected


def test_scan_deduplication_blocks_overlapping_runs(session):
    a, dup_a = scanner.create_scan(session, None, {}, "manual")
    b, dup_b = scanner.create_scan(session, None, {}, "scheduled")
    assert not dup_a and dup_b and b.id == a.id
    a.status, a.finished_at = "completed", utcnow()
    session.commit()
    c, dup_c = scanner.create_scan(session, None, {}, "manual")
    assert not dup_c and c.id != a.id


# ----------------------------------------------------------------------------------------------- lifecycle
def _open_opp(session, direction, invalidation, tp1, expires_in_h=100, sig_back=30):
    inst, prov = load_btc(session)
    scan = MarketScan(status="completed", trigger="manual", config_version="t")
    session.add(scan)
    session.commit()
    inst, prov, pi = resolve_mapping(session, "BTCUSDT")
    t = prepare_tf(session, inst, prov, pi, "1H")
    sig = datetime.fromtimestamp(int(t.bars.t[-sig_back]), tz=timezone.utc)
    o = TradeOpportunity(scan_id=scan.id, last_scan_id=scan.id, instrument_id=inst.id, provider_id=prov.id, style="swing", direction=direction,
                         status="waiting_for_confirmation", setup_timeframe="1H", setup_type="trend_pullback", dedupe_key="k", entry_low=1,
                         entry_high=2, stop_loss=0.5, take_profit_1=tp1, invalidation=invalidation, signal_ts=sig,
                         expires_at=utcnow() + timedelta(hours=expires_in_h), evidence={"setup": {"direction": direction}})
    session.add(o)
    session.commit()
    return scan, inst, o, {"1H": t}


@pytest.mark.parametrize("direction,case,expected", [
    ("BUY", "invalidated", "invalidated"), ("SELL", "invalidated", "invalidated"),
    ("BUY", "tp", "expired"), ("BUY", "time", "expired"), ("BUY", "alive", "waiting_for_confirmation")])
def test_open_opportunities_are_closed_by_invalidation_target_or_time(session, direction, case, expected):
    scan, inst, o, tfs = _open_opp(session, direction, 0.0, 10**9, expires_in_h=100)
    b = tfs["1H"].bars
    after = b.c[-30:]
    if case == "invalidated":  # a later candle closed beyond the invalidation level
        o.invalidation = float(after.max()) + 1.0 if direction == "BUY" else float(after.min()) - 1.0
    elif case == "tp":
        o.take_profit_1 = float(b.h[-30:].min())  # trivially reached after the signal
    elif case == "time":
        o.expires_at = utcnow() - timedelta(hours=1)
    session.commit()
    scanner.reconcile(session, scan, inst, tfs)
    session.refresh(o)
    assert o.status == expected
    hist = session.scalars(select(OpportunityStatusHistory).where(OpportunityStatusHistory.opportunity_id == o.id)).all()
    assert (len(hist) == 1 and hist[0].note["reason"]) if expected != "waiting_for_confirmation" else not hist


def test_same_setup_is_updated_in_place_and_its_levels_never_drift(session):
    scan, inst, o, tfs = _open_opp(session, "BUY", 0.0, 10**9)
    _, prov, _ = resolve_mapping(session, "BTCUSDT")
    fields = dict(direction="BUY", status="entry_triggered", entry_low=999.0, entry_high=1000.0, stop_loss=1.0, evidence_score=61.0, evidence={"a": 1})
    scan2 = MarketScan(status="running", trigger="manual")
    session.add(scan2)
    session.commit()
    row = scanner._upsert(session, scan2, inst, prov, PROFILES["swing"], "sk", "k", fields, headline=True)
    session.commit()
    assert row.id == o.id and session.scalar(select(func.count()).select_from(TradeOpportunity)) == 1
    assert (float(row.entry_low), float(row.stop_loss)) == (1.0, 0.5)  # published plan unchanged
    assert row.status == "entry_triggered" and row.evidence_score == 61.0 and row.last_scan_id == scan2.id
    back = scanner._upsert(session, scan2, inst, prov, PROFILES["swing"], "sk", "k", {**fields, "status": "waiting_for_confirmation"}, headline=True)
    assert back.status == "entry_triggered"  # a trigger that happened is never un-happened


# ----------------------------------------------------------------------------------------------- API
@pytest.fixture()
def client(engine):
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def seeded(client, session_factory=None):
    from app.database.session import session_scope

    with session_scope() as s:
        load_btc(s)
    r = client.post("/api/v1/opportunities/scan", json={"symbols": ["BTCUSDT", "US30"]})
    assert r.status_code == 202 and r.json()["deduplicated"] is False
    return r.json()


def test_api_scan_flow_summary_and_detail(client):
    acc = seeded(client)
    scan = client.get(acc["poll_url"]).json()
    assert scan["status"] == "completed" and scan["summary"]["instruments_scanned"] == 1
    s = client.get("/api/v1/opportunities/summary").json()
    assert s["scan"]["id"] == acc["id"] and [x["style"] for x in s["styles"]] == list(STYLE_ORDER)
    assert {i["symbol"]: i["status"] for i in s["instruments"]} == {"BTCUSDT": "scanned", "US30": "unavailable"}
    assert s["score_label"] == "Evidence Score — Not Win Probability" and s["next_scan"]["enabled"] is False
    page = client.get("/api/v1/opportunities", params={"symbol": "btcusdt"}).json()
    assert page["total"] == 4 and all(i["symbol"] == "BTCUSDT" for i in page["items"])
    one = page["items"][0]
    d = client.get(f"/api/v1/opportunities/{one['id']}").json()
    ev = d["evidence"]
    assert {"multi_timeframe", "wait_reasons", "validation", "bias", "analogues"} <= set(ev) and d["style_profile"]["min_rr"] > 0
    assert len(ev["multi_timeframe"]) == 14 and d["status_history"]
    if d["direction"] in ("BUY", "SELL") or ev.get("setup"):
        assert {"thesis", "structure", "candlesticks", "risks", "chart", "data"} <= set(ev)
        assert {"opposing_evidence", "warnings"} <= set(ev["risks"]) and ev["structure"]["timeframe"] == d["setup_timeframe"]


def test_api_filters_pagination_validation_and_history(client):
    acc = seeded(client)
    assert client.get("/api/v1/opportunities", params={"style": "swing"}).json()["total"] == 1
    assert client.get("/api/v1/opportunities", params={"style": "nonsense"}).status_code == 422
    assert client.get("/api/v1/opportunities", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/opportunities", params={"direction": "HOLD"}).status_code == 422
    p = client.get("/api/v1/opportunities", params={"limit": 2, "offset": 2}).json()
    assert len(p["items"]) == 2 and p["total"] == 4 and p["offset"] == 2
    assert client.get("/api/v1/opportunities", params={"actionable_only": True}).json()["total"] <= 4
    assert client.get("/api/v1/opportunities/999999").status_code == 404
    assert client.get("/api/v1/opportunities/scans/999999").status_code == 404
    h = client.get("/api/v1/opportunities/scans").json()
    assert h["total"] == 1 and h["items"][0]["id"] == acc["id"]
    tf = client.get("/api/v1/opportunities/timeframes", params={"symbol": "BTCUSDT"}).json()
    by = {t["timeframe"]: t for t in tf["timeframes"]}
    assert len(by) == 14 and by["1H"]["status"] == "completed" and by["1H"]["analysis"]["n_bars"] == N and by["4H"]["derived_from"] == "1H"
    v = client.get("/api/v1/opportunities/validation").json()
    assert "reference_backtests" in v and v["config"]["weights"] and all(r["status"] != "validated" or r["oos"] for r in v["results"])
    assert abs(sum(client.get("/api/v1/opportunities/config").json()["weights"].values()) - 1) < 1e-9


def test_api_scan_request_validation_and_overlap(client):
    assert client.post("/api/v1/opportunities/scan", json={"symbols": ["A"] * 11}).status_code == 422
    a = client.post("/api/v1/opportunities/scan", json={"symbols": ["NOPE"]})
    assert a.status_code == 202  # unknown symbols are reported as unsupported inside the scan, not as a crash
    s = client.get(a.json()["poll_url"]).json()
    assert s["instruments"][0]["status"] == "unsupported"
    from app.database.session import session_scope

    with session_scope() as sess:
        sess.add(MarketScan(status="running", trigger="manual"))
    b = client.post("/api/v1/opportunities/scan", json={})
    assert b.status_code == 202 and b.json()["deduplicated"] is True


def test_api_empty_state_before_any_scan(client):
    s = client.get("/api/v1/opportunities/summary").json()
    assert s["scan"] is None and s["ranking"] == [] and s["styles"] == []
    assert client.get("/api/v1/opportunities").json()["items"] == []
    assert client.get("/api/v1/opportunities/timeframes", params={"symbol": "BTCUSDT"}).status_code == 404


def test_api_requires_authentication_when_enabled(engine, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        from app.database.session import session_scope

        with session_scope() as s:
            s.add(User(email="a@x", api_key_hash=hash_api_key("key-a")))
        for method, path in (("get", "/api/v1/opportunities"), ("get", "/api/v1/opportunities/summary"), ("post", "/api/v1/opportunities/scan")):
            assert getattr(c, method)(path).status_code == 401
            assert getattr(c, method)(path, headers={"X-API-Key": "nope"}).status_code == 401
        assert c.get("/api/v1/opportunities/summary", headers={"X-API-Key": "key-a"}).status_code == 200
    get_settings.cache_clear()


def test_provider_mapping_for_xauusd_is_active_in_the_registry(session):
    status = session.scalar(select(ProviderInstrument.status).join(Instrument).where(Instrument.canonical_symbol == "XAUUSD"))
    assert status == "active"
