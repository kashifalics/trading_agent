"""The central trading decision (app.decision): ENTER / WAIT / EXIT / NO TRADE, the precedence of its rules, and the adapters."""
import random

import pytest

from app.decision.adapters import (
    opportunity_call,
    prediction_call,
    redact_explanation,
    signal_call,
)
from app.decision.core import (
    ENTER,
    EXIT,
    NO_TRADE,
    WAIT,
    Check,
    DecisionInput,
    decide,
    manage_trade,
    rank,
)

VALID = {"status": "validated", "label": "Validated", "note": "passed"}
UNVALID = {"status": "not_validated", "label": "Not validated", "note": "no out-of-sample edge"}


def plan(**over) -> dict:
    """A signal-engine plan (shape of app.signals.engine output) for a 1H BUY at 100, stop 98, TP1 106 (3R)."""
    p = {"timeframe": "1H", "status": "ok", "state": "ENTRY_READY", "instruction": "EXECUTE NOW", "side": "BUY", "direction": "BUY",
         "score": 72, "setup_type": "trend_pullback", "entry_type": "market", "entry": 100.0, "entry_zone": [99.0, 100.5],
         "stop_loss": 98.0, "invalidation": 98.5, "targets": [{"label": "TP1", "price": 106.0, "rr": 3.0, "basis": "swing_high"},
                                                               {"label": "TP2", "price": 109.0, "rr": 4.5, "basis": "pdh"}],
         "risk_reward": 3.0, "risk_atr": 1.2, "cost_r": 0.02, "blocked": [], "conditions": ["Enter BUY near 100", "Invalid if 1H closes below 98.5"],
         "reasons_for": ["4H trend bullish"], "reasons_against": [], "confirm_tf": "15m", "confirm_used": "15m",
         "bias": [{"timeframe": "4H", "label": "Bullish", "direction": 1}, {"timeframe": "1D", "label": "Bullish", "direction": 1}],
         "validation": UNVALID, "summary": "BUY 1H trend pullback: 72/100"}
    p.update(over)
    return p


def call(p=None, **kw):
    return signal_call(p or plan(), "XAUUSD", **kw)


def test_valid_entry_conditions_give_enter_only_for_validated_rules():
    c = call(plan(validation=VALID), price_now=100.2)
    assert c["decision"] == ENTER and c["label"] == "ENTER" and c["entry_mode"] == "immediate" and c["direction"] == "BUY"
    assert c["levels"]["stop_loss"] == 98.0 and [t["price"] for t in c["levels"]["targets"]] == [106.0, 109.0]
    lim = call(plan(validation=VALID, state="SETUP_DEVELOPING", instruction="PLACE LIMIT ORDER", entry_type="limit"), price_now=101.5)
    assert lim["decision"] == ENTER and lim["entry_mode"] == "conditional"


def test_unvalidated_setup_is_wait_never_enter_and_levels_only_in_experimental_mode():
    c = call(price_now=100.2)
    assert c["decision"] == WAIT and c["label"] == "WAIT — UNVALIDATED SETUP" and c["levels"] is None and c["hypothetical"] is None
    assert "not recommend entering" in c["headline"] and "out-of-sample" in c["next_condition"]
    x = call(price_now=100.2, experimental=True)
    assert x["decision"] == WAIT and x["levels"] is None
    assert x["hypothetical"]["label"] == "HYPOTHETICAL — UNVALIDATED" and x["hypothetical"]["stop_loss"] == 98.0
    assert "EXECUTE NOW" not in str({k: x[k] for k in ("label", "headline", "next_condition")})


def test_missing_timeframe_data_is_never_assumed_aligned():
    c = call(plan(bias=[{"timeframe": "4H", "label": "Bullish", "direction": 1}, {"timeframe": "1D", "label": "unavailable", "direction": None}],
                  validation=VALID), price_now=100.2)
    assert c["decision"] == NO_TRADE and "1D" in c["headline"] and "not assumed aligned" in c["headline"]
    conf = call(plan(confirm_used="1H", validation=VALID), price_now=100.2)  # confirmation fell back to the setup timeframe
    assert conf["decision"] == NO_TRADE and "15m" in conf["headline"]
    assert conf["alignment"]["confirmation"]["status"] == "unavailable"


def test_contradictory_timeframe_trends_are_no_trade():
    c = call(plan(bias=[{"timeframe": "4H", "label": "Bullish", "direction": 1}, {"timeframe": "1D", "label": "Bearish", "direction": -1}],
                  validation=VALID, score=95), price_now=100.2)
    assert c["decision"] == NO_TRADE and "Higher-timeframe agreement" in c["headline"] and "against a BUY" in c["headline"]
    assert any(h["agrees"] is False for h in c["alignment"]["higher"]) and "1D conflicts" in c["alignment"]["summary"]


@pytest.mark.parametrize("blocked,name", [
    ("structural stop is 3.1 ATR from entry (maximum 2.5 ATR for intraday)", "Stop-loss"),
    ("no structural target at >= 2.0R (furthest: swing high at 1.22R)", "Reward:risk"),
    ("spread 0.9 would cost 0.31R of the risk (limit 0.2R for intraday)", "Transaction costs")])
def test_failed_mandatory_rule_is_no_trade_even_with_a_high_score(blocked, name):
    c = call(plan(state="WATCHLIST", instruction="NO TRADE", blocked=[blocked], score=99, validation=VALID), price_now=100.2)
    assert c["decision"] == NO_TRADE and c["label"] == "NO TRADE — CONDITION FAILED" and c["headline"].startswith(name)
    assert c["failed_checks"][0]["name"] == name and c["next_condition"]


def test_stale_or_missing_data_is_no_trade_without_levels():
    for status, word in (("stale", "stale"), ("insufficient_data", "Not enough"), ("unavailable", "unavailable")):
        c = call(plan(status=status, reason="latest 1H candle is 9 bars old", validation=VALID), price_now=100.2)
        assert c["decision"] == NO_TRADE and c["label"] == "NO TRADE — DATA" and word.lower() in c["headline"].lower()
        assert c["levels"] is None and c["hypothetical"] is None


def test_already_triggered_entry_with_a_tracked_trade_is_wait_not_a_second_entry():
    tr = {"id": 7, "status": "open", "direction": "BUY", "entry_price": 100.0, "fill_price": 100.1, "stop_loss": 98.0, "take_profit": 106.0,
          "invalidation": 98.5, "last_price": 101.0, "last_close": 100.9}
    c = call(plan(validation=VALID), price_now=101.0, open_trade=tr)
    assert c["decision"] == WAIT and c["label"] == "WAIT — TRADE OPEN" and c["trade"]["action"] == "HOLD"


def test_missed_entry_zone_is_no_trade_never_chase():
    c = call(plan(validation=VALID), price_now=100.0 + 0.31 * 2.0 + 0.01)
    assert c["decision"] == NO_TRADE and c["label"] == "NO TRADE — ENTRY MISSED" and "never chase" in c["headline"]
    beyond_tp = call(plan(validation=VALID, state="SETUP_DEVELOPING", instruction="WAIT FOR CONFIRMATION", entry_type="limit"), price_now=106.5)
    assert beyond_tp["label"] == "NO TRADE — TARGET ALREADY REACHED"
    beyond_sl = call(plan(validation=VALID), price_now=97.5)
    assert beyond_sl["label"] == "NO TRADE — PRICE BEYOND STOP"


@pytest.mark.parametrize("price,close,label", [(97.9, 99.0, "EXIT — STOP-LOSS HIT"), (106.2, 106.0, "EXIT — TARGET REACHED"),
                                               (99.0, 98.2, "EXIT — SETUP INVALIDATED")])
def test_exit_only_for_a_tracked_trade_with_an_exit_condition(price, close, label):
    tr = {"id": 3, "status": "open", "direction": "BUY", "entry_price": 100.0, "fill_price": 100.0, "stop_loss": 98.0, "take_profit": 106.0,
          "invalidation": 98.5, "last_price": price, "last_close": close}
    c = call(price_now=None, open_trade=tr)
    assert c["decision"] == EXIT and c["label"] == label and c["trade"]["trade_id"] == 3 and c["exit_price"] == price


def test_no_active_trade_means_no_exit_or_hold():
    assert manage_trade(None) is None and manage_trade({"status": "closed"}) is None
    c = call(price_now=97.0)  # price beyond the stop, but nothing is tracked: no EXIT is invented
    assert c["decision"] != EXIT and c["trade"] is None
    pend = manage_trade({"id": 1, "status": "pending", "direction": "SELL", "entry_price": 50.0, "stop_loss": 52.0, "take_profit": 44.0,
                         "invalidation": 51.5, "last_price": 49.0})
    assert pend["action"] == WAIT and "fill" in pend["reason"]


def test_trade_invalidation_and_expiry_of_the_technical_setup_are_no_trade():
    inv = call(plan(state="TRADE_INVALIDATED", instruction="NO TRADE", previous={"side": "BUY", "reason": "a 1H candle closed below 98.5"}))
    assert inv["decision"] == NO_TRADE and inv["label"] == "NO TRADE — SETUP INVALIDATED" and "98.5" in inv["headline"]
    exp = call(plan(state="TRADE_EXPIRED", instruction="NO TRADE", previous={"side": "BUY", "reason": "TP1 106 was reached"}))
    assert exp["label"] == "NO TRADE — SETUP EXPIRED"


def test_waits_say_exactly_what_they_wait_for():
    conf = call(plan(state="WAITING_FOR_CONFIRMATION", instruction="WAIT FOR CONFIRMATION",
                     conditions=["A bullish BOS/CHoCH on 15m, or a bullish rejection candle at the zone", "No 1H close below 98.5"]), price_now=100.1)
    assert conf["label"] == "WAIT — CONFIRMATION PENDING" and conf["next_condition"].startswith("A bullish BOS/CHoCH on 15m")
    assert conf["invalidation"] == "A 1H candle closing below 98.5" and conf["watch"]["zone"] == [99.0, 100.5]
    closed = call(plan(state="WAITING_FOR_CONFIRMATION", instruction="WAIT FOR CONFIRMATION",
                       conditions=["Market is closed: re-check after the open (spreads widen at the open)"]), price_now=100.1)
    assert closed["label"] == "WAIT — MARKET CONDITIONS"
    price = call(plan(state="SETUP_DEVELOPING", instruction="WAIT FOR CONFIRMATION", entry_type="limit",
                      conditions=["Price retraces into the demand zone 99.0-100.5"]), price_now=102.0)
    assert price["label"] == "WAIT — PRICE NOT AT ENTRY ZONE" and "retraces" in price["next_condition"]
    dev = call(plan(state="WATCHLIST", instruction="NO TRADE", score=52, reasons_against=[
        "Liquidity sweep missing: none", "Reward:risk ≥ 2 with a clear path missing: TP1 at 2.3R, but a band sits in the way"]), price_now=100.1)
    assert dev["label"] == "WAIT — SETUP DEVELOPING" and "60/100 (now 52/100)" in dev["next_condition"]
    assert dev["next_condition"].endswith(": Liquidity sweep, Reward:risk ≥ 2 with a clear path")  # check names survive their own colons
    none = call(plan(state="NO_SETUP", instruction="NO TRADE", side=None, entry=None, score=None, reason="no zone ahead"))
    assert none["decision"] == NO_TRADE and none["direction"] == "NONE" and "no zone ahead" in none["headline"]


def test_no_failed_mandatory_condition_can_ever_produce_enter():
    rng = random.Random(7)
    techs = ["none", "developing", "awaiting_price", "awaiting_confirmation", "confirmed", "invalidated", "expired"]
    for _ in range(3000):
        checks = [Check(f"c{k}", rng.random() > 0.3, "x") for k in range(rng.randint(0, 4))]
        trade = rng.choice([None, {"id": 1, "status": "open", "direction": "BUY", "entry_price": 100.0, "stop_loss": 98.0,
                                   "take_profit": 106.0, "invalidation": 98.5, "last_price": rng.uniform(96, 108), "last_close": 99.0}])
        i = DecisionInput(symbol="X", timeframe="1H", data_status=rng.choice(["ok", "ok", "stale", "insufficient"]), technical=rng.choice(techs),
                          direction=rng.choice([1, -1]), entry_mode=rng.choice(["market", "limit"]), entry=100.0, stop=98.0,
                          targets=[{"label": "TP1", "price": 106.0, "rr": 3.0}], checks=checks, price_now=rng.choice([None, rng.uniform(96, 108)]),
                          validation=rng.choice([VALID, UNVALID]), open_trade=trade, experimental=rng.random() < 0.5)
        c = decide(i)
        assert c["decision"] in (ENTER, WAIT, EXIT, NO_TRADE)
        assert c["label"].startswith(c["decision"]) and c["headline"] and c["next_condition"]  # always says what comes next
        if c["decision"] == ENTER:
            assert all(k.passed for k in checks) and i.data_status == "ok" and i.technical == "confirmed" and i.validation is VALID
            assert trade is None and c["levels"] is not None
        else:
            assert c["levels"] is None  # entry levels are never shown as a recommendation without ENTER
        if c["decision"] == EXIT:
            assert trade is not None
        if c["hypothetical"] is not None:
            assert i.experimental and c["decision"] != ENTER


def test_instrument_call_prefers_exit_then_enter_then_the_most_concrete_wait():
    a = {"decision": WAIT, "wait_kind": "developing", "score": 90}
    b = {"decision": WAIT, "wait_kind": "unvalidated", "score": 61}
    c = {"decision": NO_TRADE, "wait_kind": None, "score": 99}
    assert rank([a, b, c]) is b and rank([c, {"decision": EXIT, "score": 0}])["decision"] == EXIT and rank([]) is None
    held = {"decision": WAIT, "wait_kind": "trade_open", "score": None}  # a tracked paper trade to manage comes before any new WAIT
    assert rank([a, b, held, c]) is held and rank([held, {"decision": ENTER, "score": 70}])["decision"] == ENTER


def test_opportunity_and_prediction_adapters_follow_the_same_rules():
    o = {"symbol": "XAUUSD", "setup_timeframe": "4H", "status": "entry_triggered", "direction": "BUY", "side": "BUY", "entry_low": 99.0,
         "entry_high": 101.0, "stop_loss": 98.0, "take_profit_1": 106.0, "take_profit_2": None, "take_profit_3": None, "invalidation": 98.5,
         "risk_reward": 3.0, "validation_status": "untested", "evidence_score": 64.2, "setup_type": "trend_pullback", "wait_reasons": []}
    assert opportunity_call(o)["label"] == "WAIT — UNVALIDATED SETUP"
    assert opportunity_call({**o, "validation_status": "validated"})["decision"] == ENTER
    assert opportunity_call({**o, "status": "waiting_for_confirmation"})["label"] == "WAIT — CONFIRMATION PENDING"
    assert opportunity_call({**o, "status": "none", "direction": "WAIT", "side": None, "wait_reasons": ["no setup"]})["decision"] == NO_TRADE
    p = {"symbol": "BTCUSDT", "timeframe": "1H", "decision": "SELL", "entry_low": 99.0, "entry_high": 101.0, "stop_loss": 103.0,
         "take_profit": [94.0], "risk_reward": 2.0, "invalidation_level": 102.5, "data_quality_score": 1.0, "warnings": []}
    assert prediction_call(p)["label"] == "WAIT — UNVALIDATED SETUP" and prediction_call(p)["levels"] is None
    w = prediction_call({**p, "decision": "WAIT"}, wait_reasons=["confluence -0.17 is below the +/-0.35 threshold"])
    assert w["decision"] == NO_TRADE and "confluence" in w["headline"]


def test_stored_explanations_never_leak_levels_without_enter_or_experimental_mode():
    text = "BUY setup on X 1H (analytical confluence +0.55).\nPlan: entry 103.5-104.5, stop 101, targets 110, R:R 2.00.\nAnalysis only."
    p = {"symbol": "X", "timeframe": "1H", "decision": "BUY", "entry_low": 103.5, "entry_high": 104.5, "stop_loss": 101.0,
         "take_profit": [110.0], "risk_reward": 2.0, "invalidation_level": 101.5, "data_quality_score": 1.0, "warnings": []}
    hidden = redact_explanation(text, prediction_call(p))
    assert "101" not in hidden and "withheld" in hidden and "WAIT — UNVALIDATED SETUP" in hidden and hidden.startswith("BUY setup")
    assert redact_explanation(text, prediction_call(p, experimental=True)) == text  # hypothetical levels are shown, so is the plan line
    assert redact_explanation(None, prediction_call(p)) is None
