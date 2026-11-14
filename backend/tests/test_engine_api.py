"""Strategy engine v2 end to end on stored synthetic candles (TEST FIXTURES ONLY): API output contract, plan invariants, H8, paper
trades kept separate (EXIT), and the signal lifecycle on 1-minute candles."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.database.models import Instrument, SignalRecord
from app.database.session import session_scope
from app.main import create_app
from app.market_data.bars import Bars
from app.signals import service as v1
from app.strategy_engine import lifecycle
from app.strategy_engine import service as v2
from app.strategy_engine.config import RESEARCH_STATUS
from tests.test_signals_api import _seed

ACTIONS = {"BUY", "SELL", "WAIT FOR BUY", "WAIT FOR SELL", "EXIT", "NO TRADE"}


@pytest.fixture()
def client(engine, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setattr(v1, "_quote", lambda prov, pi: None)  # never reach a real provider from tests
    v1._FRAMES.clear()
    v1._MEMORY.clear()
    v2._RESULTS.clear()
    v2._TFD.clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def _check_plan(p: dict, d: int, precision: int):
    tick = 10.0 ** -precision
    seq = [p["stop_loss"], p["entry"]] + [t["price"] for t in p["targets"]]
    assert all((seq[k + 1] - seq[k]) * d > 0 for k in range(len(seq) - 1)), seq
    assert all(abs(v / tick - round(v / tick)) < 1e-6 for v in seq)
    assert [t["label"] for t in p["targets"]] == ["TP1", "TP2", "TP3"] and all(t["rr"] > 0 for t in p["targets"])
    assert p["targets"][0]["rr"] >= 1.5 - 1e-9 and p["entry_status"] in ("READY", "WAITING FOR ENTRY")
    assert p["signal_time"] and p["expires_at"] and p["cost_r"] >= 0


def test_old_data_never_produces_a_plan(client):
    _seed("XAUUSD")  # candles ending 3 days ago
    d = client.get("/api/v1/engine/XAUUSD").json()
    stale = [t for t in d["timeframes"] if t["n_bars"] >= 120 and t["timeframe"] in ("5m", "15m", "1H")]
    assert stale and all(t["action"] == "NO TRADE" and "data stale" in t["headline"] and t["plan"] is None for t in stale)


def test_every_instrument_gets_one_clear_action_with_valid_levels(client):
    _seed("XAUUSD", end=datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0))  # fresh candles
    s = client.get("/api/v1/engine").json()
    items = {i["symbol"]: i for i in s["items"]}
    assert set(items) == set(get_settings().signal_list) and "NOT filtered" in s["news"]["note"]
    assert items["BTCUSDT"]["primary"]["action"] == "NO TRADE"  # no candles: never a signal
    gold = items["XAUUSD"]
    assert gold["status"] == "ok" and gold["primary"]["action"] in ACTIONS
    assert [t["timeframe"] for t in gold["tfs"]] == ["1m", "3m", "5m", "15m", "30m", "1H", "4H", "8H", "1D", "1W", "1M"]
    d = client.get("/api/v1/engine/XAUUSD").json()
    checked = []
    for t in d["timeframes"]:
        assert t["action"] in ACTIONS - {"EXIT"}
        if t["action"] == "NO TRADE":
            assert t["plan"] is None and t["headline"].startswith("NO TRADE") and t["missing"]
        else:
            assert t["research_status"] == RESEARCH_STATUS[t["strategy"]] and t["plan_label"] == "UNVALIDATED — HYPOTHETICAL TRADE PLAN"
            _check_plan(t["plan"], 1 if t["direction"] == "BUY" else -1, d["price_precision"])
        if t["n_bars"] >= 120 and "data stale" not in t["headline"]:  # every strategy is evaluated, both sides, and each says why
            checked.append(t["timeframe"])
            assert {c["strategy"] for c in t["candidates"]} == {"trend_pullback", "breakout_retest", "momentum_continuation", "range_reversion",
                                                                 "sweep_reversal", "volatility_expansion"}
            assert all(c["status"] in ("ready", "pending", "forming", "rejected", "not run") for c in t["candidates"])
    assert checked  # at least one fresh timeframe had every strategy evaluated
    tf = {t["timeframe"]: t for t in d["timeframes"]}
    assert tf["1m"]["action"] == "NO TRADE" and "insufficient" in tf["1m"]["regime"]["subtype"]  # never seeded: not assumed
    assert tf["8H"]["n_bars"] > 0  # built from the stored 4H candles


def test_an_open_paper_trade_at_its_stop_is_exit_but_does_not_hide_new_opportunities(client):
    from app.database.models import PaperTrade
    _seed("XAUUSD")
    with session_scope() as s:
        inst = s.query(Instrument).filter_by(canonical_symbol="XAUUSD").one()
        t0 = datetime.now(timezone.utc) - timedelta(days=4)
        s.add(PaperTrade(setup_key="BUY:x", order_type="market", status="open", fill_price=2000.0, filled_at=t0, risk=5.0, last_price=1990.0,
                         instrument_id=inst.id, symbol="XAUUSD", timeframe="1H", direction="BUY", signal_ts=t0, detected_at=t0,
                         valid_until=t0 + timedelta(days=1), entry_price=2000.0, stop_loss=1995.0, take_profit=2010.0, invalidation=1996.0,
                         cursor_at=t0, spread=0.3))
    d = client.get("/api/v1/engine/XAUUSD").json()
    assert d["primary"]["action"] == "EXIT" and "stop-loss" in d["primary"]["headline"]
    assert d["exits"][0]["trade_id"] and d["trades"][0]["management"]["action"] == "EXIT"
    assert all(t["action"] != "EXIT" for t in d["timeframes"])  # the opportunity analysis itself is untouched by the paper trade


# ------------------------------------------------------------------ lifecycle
def test_engine_detail_exposes_confirmations_volume_and_vsa(client):
    from app.strategy_engine.config import VOLUME_LABELS
    from app.strategy_engine.confirm import ORDER
    _seed("XAUUSD", end=datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0))
    d = client.get("/api/v1/engine/XAUUSD").json()
    live = 0
    for t in d["timeframes"]:
        assert "confirmations" in t and "volume" in t and "vsa" in t
        if t["volume"] is not None:
            assert t["volume"]["label"] in VOLUME_LABELS.values() and set(t["volume"]) == {"type", "label", "reliable", "reason"}
        if t["action"] == "NO TRADE":
            assert t["confirmations"] == []
            continue
        live += 1
        assert [c["key"] for c in t["confirmations"]] == list(ORDER)
        assert all(c["verdict"] in ("PASS", "FAIL", "NEUTRAL", "UNAVAILABLE") and c["reason"] for c in t["confirmations"])
        assert all(c["note"] in ("evidence only — not tested", "did not pass Experiment 6") and not c["gating"]
                   for c in t["confirmations"] if not c["mandatory"])  # Experiment 6 promoted nothing
        assert set(t["vsa"]) == {"events", "pressure", "context"}
    s = client.get("/api/v1/engine").json()
    gold = next(i for i in s["items"] if i["symbol"] == "XAUUSD")
    if gold.get("opportunity"):
        assert [c["key"] for c in gold["opportunity"]["confirmations"]] == list(ORDER)  # the summary carries the primary plan's matrix
    assert live or gold["primary"]["action"] == "NO TRADE"


def _m1(rows: list[tuple[float, float, float, float]], start: datetime) -> Bars:
    a = np.array(rows, float)
    t = np.array([int(start.timestamp()) + 60 * k for k in range(len(rows))], dtype=np.int64)
    return Bars(t=t, o=a[:, 0], h=a[:, 1], l=a[:, 2], c=a[:, 3], v=np.zeros(len(rows)), step=60)


def _analysis(mode: str, status: str, d: str = "BUY", entry=100.0, stop=99.0, tps=(102.0, 103.0, 105.0), inval=99.2, at=None) -> dict:
    at = at or datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
    plan = {"entry_mode": mode, "entry": entry, "stop_loss": stop, "risk": abs(entry - stop), "invalidation": inval,
            "targets": [{"label": f"TP{k}", "price": p, "rr": abs(p - entry) / abs(entry - stop)} for k, p in enumerate(tps, 1)],
            "entry_status": status, "signal_time": at.isoformat(), "expires_at": (at + timedelta(hours=2)).isoformat(), "price_now": entry,
            "trigger": "test"}
    return {"symbol": "XAUUSD", "timeframes": [{"timeframe": "1H", "action": d if status == "READY" else f"WAIT FOR {d}", "direction": d,
                                                "strategy": "breakout_retest", "strategy_name": "Breakout and retest", "regime": {"label": "UNKNOWN"},
                                                "research_status": "INSUFFICIENT EVIDENCE", "plan": plan, "headline": "test"}]}


def test_a_signal_held_back_by_a_promoted_gate_is_not_recorded_as_taken(session):
    inst = session.scalar(select(Instrument).where(Instrument.canonical_symbol == "XAUUSD"))
    at = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
    gated = _analysis("market", "READY", at=at)
    gated["timeframes"][0].update(action="WAIT FOR BUY", missing=["missing confirmation: momentum (MACD histogram falling)"])
    assert lifecycle.record(session, gated, inst.id, None, at) == []  # the card says WAIT: the track record must not count it
    taken = lifecycle.record(session, _analysis("market", "READY", at=at), inst.id, None, at)
    assert len(taken) == 1 and taken[0].status == "ACTIVE"  # once the gate passes, the same setup is recorded and triggered


def test_signal_lifecycle_runs_from_detection_through_targets_and_is_recorded_once(session):
    inst = session.scalar(select(Instrument).where(Instrument.canonical_symbol == "XAUUSD"))
    at = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
    recs = lifecycle.record(session, _analysis("limit", "WAITING FOR ENTRY", at=at), inst.id, None, at)
    assert len(recs) == 1 and recs[0].status == "WAITING FOR ENTRY"
    assert lifecycle.record(session, _analysis("limit", "WAITING FOR ENTRY", at=at), inst.id, None, at) == []  # no duplicate on refresh
    m1 = _m1([(100.5, 100.8, 100.3, 100.6),  # above the BUY limit: still waiting
              (100.6, 100.6, 99.9, 100.2),   # touches 100.0: ENTRY TRIGGERED, ACTIVE
              (100.2, 102.1, 100.1, 101.9),  # TP1 102
              (101.9, 103.2, 101.8, 103.0),  # TP2 103
              (103.0, 103.1, 98.9, 99.0)],   # back to the stop 99: STOP LOSS HIT after TP2
             at)
    lifecycle.step_symbol(session, "XAUUSD", m1)
    r = recs[0]
    seq = [h["status"] for h in r.history]
    assert seq == ["DETECTED", "WAITING FOR ENTRY", "ENTRY TRIGGERED", "ACTIVE", "TP1 HIT", "TP2 HIT", "STOP LOSS HIT"]
    assert r.status == "STOP LOSS HIT" and r.best_target == 2 and r.closed_at is not None
    lifecycle.step_symbol(session, "XAUUSD", m1)  # running again changes nothing
    assert [h["status"] for h in r.history] == seq


@pytest.mark.parametrize("rows,expected", [
    ([(100.5, 100.6, 100.3, 100.4), (100.4, 100.5, 99.0, 99.1)], "INVALIDATED"),  # BUY stop at 101 never reached; a close below 99.2
    ([(100.5, 102.5, 100.4, 102.2)], "ENTRY MISSED"),  # TP1 trades before the BUY limit at 100.0
])
def test_signals_that_never_fill_end_invalidated_or_missed(session, rows, expected):
    inst = session.scalar(select(Instrument).where(Instrument.canonical_symbol == "XAUUSD"))
    at = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
    stop_entry = expected == "INVALIDATED"
    an = _analysis("stop" if stop_entry else "limit", "WAITING FOR ENTRY", entry=101.0 if stop_entry else 100.0, stop=99.0, inval=99.2, at=at)
    rec = lifecycle.record(session, an, inst.id, None, at)[0]
    lifecycle.step_symbol(session, "XAUUSD", _m1(rows, at))
    assert rec.status == expected and rec.closed_at is not None and rec.triggered_at is None


def test_market_signals_start_active_and_expired_entries_close(session):
    inst = session.scalar(select(Instrument).where(Instrument.canonical_symbol == "XAUUSD"))
    at = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
    m = lifecycle.record(session, _analysis("market", "READY", d="SELL", entry=100.0, stop=101.0, tps=(98.0, 97.0, 95.0), inval=100.8, at=at),
                         inst.id, None, at)[0]
    assert m.status == "ACTIVE" and [h["status"] for h in m.history] == ["DETECTED", "ENTRY READY", "ENTRY TRIGGERED", "ACTIVE"]
    lifecycle.step_symbol(session, "XAUUSD", _m1([(99.8, 99.9, 97.9, 98.0), (98.0, 98.1, 96.9, 97.0), (97.0, 97.1, 94.9, 95.0)], at))
    assert m.status == "TP3 HIT" and m.best_target == 3
    later = at + timedelta(hours=1)
    w = lifecycle.record(session, _analysis("limit", "WAITING FOR ENTRY", entry=95.0, stop=94.0, tps=(97.0, 98.0, 99.0), inval=94.2, at=later),
                         inst.id, None, later)[0]
    lifecycle.step_symbol(session, "XAUUSD", _m1([(96.0, 96.2, 95.8, 96.1)], later + timedelta(hours=3)))  # after the 2 h expiry
    assert w.status == "EXPIRED"


def test_signal_history_endpoint_lists_records_newest_first(client):
    with session_scope() as s:
        inst = s.query(Instrument).filter_by(canonical_symbol="XAUUSD").one()
        lifecycle.record(s, _analysis("limit", "WAITING FOR ENTRY"), inst.id, None)
    r = client.get("/api/v1/engine/signals", params={"symbol": "XAUUSD"}).json()
    assert r["items"][0]["status"] == "WAITING FOR ENTRY" and r["items"][0]["hypothetical"] is True
    assert r["items"][0]["history"][0]["status"] == "DETECTED"
    assert client.get("/api/v1/engine/signals", params={"open_only": "true"}).json()["items"]
    with session_scope() as s:
        assert s.scalar(select(SignalRecord.id)) is not None
