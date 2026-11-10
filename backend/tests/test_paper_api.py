"""Paper trading end to end: signal recording, account rules, simulation on stored candles and the API (TEST FIXTURES ONLY)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.models import PaperTrade
from app.database.session import session_scope
from app.main import create_app
from app.market_data.ingestion.service import store_candles
from app.market_data.types import Candle
from app.paper import service as paper
from app.paper.worker import next_delay
from app.signals import service as signals

T0 = datetime(2025, 3, 3, 10, 0, tzinfo=timezone.utc)  # a Monday: markets open
T0S = int(T0.timestamp())


def seed_1m(symbol: str, rows: list[tuple[float, float, float, float]], start: datetime) -> None:
    with session_scope() as s:
        inst, prov, _ = signals.resolve(s, symbol)
        store_candles(s, inst.id, prov.id, "1m", [
            Candle(ts=start + timedelta(minutes=i), open=Decimal(str(o)), high=Decimal(str(h)), low=Decimal(str(lo)), close=Decimal(str(c)),
                   volume=Decimal("1"), volume_type="tick") for i, (o, h, lo, c) in enumerate(rows)])
        s.commit()


def plan(**kw) -> dict:
    p = {"timeframe": "15m", "state": "ENTRY_READY", "instruction": "EXECUTE NOW", "side": "BUY", "score": 72, "grade": "A",
         "setup_type": "trend_pullback", "entry_type": "market", "entry": 2000.0, "stop_loss": 1995.0, "invalidation": 1995.0,
         "targets": [{"label": "TP1", "price": 2010.0, "rr": 1.8, "basis": "swing high"}], "risk_reward": 1.8, "spread": 0.3,
         "setup_key": "BUY:order_block:1740995100", "signal_ts": T0S, "valid_until_ts": T0S + 16 * 900, "factors": [],
         "summary": "BUY 15m trend pullback at bullish order block: 72/100"}
    p.update(kw)
    return p


def fake_analyze(plans_by_symbol: dict):
    def analyze(session, symbol, now=None):
        plans = plans_by_symbol.get(symbol.upper())
        if plans is None:
            return {"symbol": symbol.upper(), "status": "unavailable", "reason": "no stored candles yet."}
        return {"symbol": symbol.upper(), "status": "ok", "plans": plans, "config_version": "test"}
    return analyze


@pytest.fixture()
def client(engine, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setattr(signals, "_quote", lambda prov, pi: None)  # never reach a real provider from tests
    signals._FRAMES.clear()
    signals._MEMORY.clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_signal_is_recorded_once_filled_at_the_next_open_and_closed_at_tp1(client, monkeypatch):
    seed_1m("XAUUSD", [(2000, 2000.5, 1999.5, 2000)] * 30, T0 - timedelta(minutes=30))
    monkeypatch.setattr(signals, "analyze", fake_analyze({"XAUUSD": [plan()]}))
    with session_scope() as s:
        first = paper.process_symbol(s, "XAUUSD", T0 + timedelta(seconds=20))
    with session_scope() as s:
        again = paper.process_symbol(s, "XAUUSD", T0 + timedelta(seconds=40))
    assert len(first["new"]) == 1 and first["new"][0]["order_type"] == "market" and again["new"] == []  # recorded once
    seed_1m("XAUUSD", [(2000.5, 2001, 2000, 2001), (2001, 2004, 2000.5, 2004), (2004, 2007, 2003, 2006), (2006, 2011, 2005, 2010)],
            T0 + timedelta(minutes=1))
    with session_scope() as s:
        done = paper.process_symbol(s, "XAUUSD", T0 + timedelta(minutes=6))
    assert done["updated"][0]["status"] == "closed" and done["new"] == []  # the same setup is never traded twice

    t = client.get("/api/v1/paper/trades", params={"status": "closed"}).json()["items"][0]
    risk = 2000.5 - 1995
    assert t["fill_price"] == 2000.5 and t["filled_at"].startswith("2025-03-03T10:01")  # first candle after the signal was seen
    assert t["exit_reason"] == "target" and t["exit_price"] == 2010
    assert t["r_net"] == pytest.approx((2010 - 2000.5) / risk - 0.3 / risk)
    assert t["account_taken"] and t["risk_amount"] == 50.0 and t["pnl"] == pytest.approx(round(t["r_net"] * 50, 2))
    detail = client.get(f"/api/v1/paper/trades/{t['id']}").json()
    assert detail["plan"]["summary"].startswith("BUY 15m") and detail["plan"]["targets"][0]["price"] == 2010.0

    summary = client.get("/api/v1/paper/summary").json()
    assert summary["forward"]["counts"]["closed"] == 1 and summary["forward"]["n_trades"] == 1
    assert summary["forward"]["verdict"]["status"] == "collecting"  # 1 trade is not evidence
    assert summary["account"]["balance"] == pytest.approx(10_000 + t["pnl"])
    assert len(summary["forward"]["equity_curve"]) == 1 and summary["breakdowns"]["series"][0]["key"] == "XAUUSD 15m"
    assert summary["method"] and "no real money" in summary["disclaimer"]


def test_account_rules_skip_signals_but_every_signal_is_still_tracked(client, monkeypatch):
    assert client.patch("/api/v1/paper/account", json={"max_open_positions": 1}).status_code == 200
    plans = [plan(), plan(timeframe="1H", setup_key="BUY:fvg:1", state="SETUP_DEVELOPING", instruction="PLACE LIMIT ORDER"),
             plan(timeframe="4H", setup_key="SELL:x:1", state="WAITING_FOR_CONFIRMATION", instruction="WAIT FOR CONFIRMATION")]
    monkeypatch.setattr(signals, "analyze", fake_analyze({"XAUUSD": plans}))
    with session_scope() as s:
        res = paper.process_symbol(s, "XAUUSD", T0)
    assert [(n["timeframe"], n["order_type"]) for n in res["new"]] == [("15m", "market"), ("1H", "limit")]  # WAIT is not a signal
    items = {i["timeframe"]: i for i in client.get("/api/v1/paper/trades").json()["items"]}
    assert items["15m"]["account_taken"] is True
    assert items["1H"]["account_taken"] is False and "max open positions (1)" in items["1H"]["account_note"]
    assert client.get("/api/v1/paper/summary").json()["account"]["skipped_signals"] == 1


def test_daily_loss_limit_blocks_new_trades_until_the_next_utc_day(session):
    acc = paper.active_account(session)
    day = datetime(2025, 3, 3, 15, 0, tzinfo=timezone.utc)
    inst_id = signals.resolve(session, "XAUUSD")[0].id
    common = dict(account_id=acc.id, instrument_id=inst_id, symbol="XAUUSD", direction="BUY", order_type="market", status="closed",
                  signal_ts=day, detected_at=day, valid_until=day, entry_price=1, stop_loss=0.5, take_profit=2, cursor_at=day,
                  account_taken=True, risk_amount=50.0)
    session.add(PaperTrade(timeframe="1H", setup_key="a", closed_at=day - timedelta(days=1), pnl=-300.0, **common))  # yesterday
    session.add(PaperTrade(timeframe="4H", setup_key="b", closed_at=day - timedelta(hours=1), pnl=-150.0, **common))
    session.flush()
    st = paper.account_state(session, acc, day)
    assert st["balance"] == 9550 and st["today_pnl"] == -150 and st["can_trade"]  # 150 of 9,700 is below 2%
    session.add(PaperTrade(timeframe="1D", setup_key="c", closed_at=day - timedelta(minutes=5), pnl=-50.0, **common))
    session.flush()
    st = paper.account_state(session, acc, day)
    assert not st["can_trade"] and "daily loss limit" in st["blocked_reason"]
    assert paper.account_state(session, acc, day + timedelta(days=1))["can_trade"]  # a new UTC day


def test_account_endpoints_and_validation(client):
    acc = client.get("/api/v1/paper/account").json()
    assert (acc["start_balance"], acc["risk_pct"], acc["max_open_positions"], acc["max_daily_loss_pct"]) == (10_000, 0.5, 5, 2.0)
    assert acc["risk_per_trade"] == 50.0 and acc["can_trade"] is True
    assert client.patch("/api/v1/paper/account", json={"risk_pct": 1.0}).json()["risk_per_trade"] == 100.0
    assert client.patch("/api/v1/paper/account", json={"risk_pct": 10}).status_code == 422
    new = client.post("/api/v1/paper/account/reset", json={"start_balance": 5000}).json()
    assert new["id"] != acc["id"] and new["balance"] == 5000 and new["risk_pct"] == 1.0  # rules carried over
    assert client.get("/api/v1/paper/trades/9999").status_code == 404
    assert client.get("/api/v1/paper/trades", params={"status": "bogus"}).status_code == 422


def test_run_endpoint_syncs_keyless_providers_and_processes_every_instrument(client, monkeypatch):
    synced = []
    monkeypatch.setattr(signals, "sync", lambda s, sym, now=None: synced.append(sym) or {"synced": True})
    monkeypatch.setattr(signals, "analyze", fake_analyze({"XAUUSD": [plan()]}))
    res = client.post("/api/v1/paper/run").json()
    by = {r["symbol"]: r for r in res["results"]}
    assert set(by) == set(get_settings().signal_list) and set(synced) == set(get_settings().signal_list)
    assert len(by["XAUUSD"]["new"]) == 1 and by["BTCUSDT"]["status"] == "unavailable"
    worker = client.get("/api/v1/paper/summary").json()["worker"]
    assert worker["cycles"] >= 1 and worker["running"] is False
    assert paper._LOCK.acquire(blocking=False)
    try:
        assert client.post("/api/v1/paper/run", params={"sync": "false"}).status_code == 409  # one cycle at a time
    finally:
        paper._LOCK.release()


def test_worker_cycles_start_just_after_the_interval_boundary():
    assert next_delay(60, now=120.5) == pytest.approx(63.5)
    assert next_delay(300, now=1000.0) == pytest.approx(204.0)


def test_open_and_pending_trades_carry_hold_exit_or_wait_from_the_central_decision(client):
    from app.database.models import Instrument, PaperTrade
    from app.database.session import session_scope as scope
    with scope() as s:
        inst = s.query(Instrument).filter_by(canonical_symbol="XAUUSD").one()
        common = dict(instrument_id=inst.id, symbol="XAUUSD", timeframe="1H", direction="BUY", signal_ts=T0, detected_at=T0,
                      valid_until=T0 + timedelta(days=1), entry_price=2000.0, stop_loss=1995.0, take_profit=2010.0, invalidation=1996.0,
                      cursor_at=T0, spread=0.3)
        s.add(PaperTrade(setup_key="BUY:a", order_type="market", status="open", fill_price=2000.0, filled_at=T0, risk=5.0,
                         last_price=2003.0, **common))
        s.add(PaperTrade(setup_key="BUY:b", order_type="market", status="open", fill_price=2000.0, filled_at=T0, risk=5.0,
                         last_price=1994.0, **{**common, "timeframe": "4H"}))
        s.add(PaperTrade(setup_key="BUY:c", order_type="limit", status="pending", **{**common, "timeframe": "15m", "last_price": 2002.0}))
    summ = client.get("/api/v1/paper/summary").json()
    by_tf = {t["timeframe"]: t for t in summ["open"] + summ["pending"]}
    assert by_tf["1H"]["management"]["action"] == "HOLD" and by_tf["1H"]["management"]["stop_distance"] == pytest.approx(8.0)
    assert by_tf["4H"]["management"]["action"] == "EXIT" and by_tf["4H"]["management"]["exit_kind"] == "stop_loss"
    assert by_tf["15m"]["management"]["action"] == "WAIT" and "fill" in by_tf["15m"]["management"]["reason"]
    closed = client.get("/api/v1/paper/trades", params={"status": "closed"}).json()["items"]
    assert all("management" not in t for t in closed)  # finished trades are never given a HOLD / EXIT
