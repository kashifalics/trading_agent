"""Signal classes, bands, sizing and the analyst report (pure functions, no market data)."""
import pytest

from app.signals import classify as K


def test_classes_and_bands_follow_the_brief():
    assert K.confluence_band(95) == "exceptional" and K.confluence_band(80) == "strong" and K.confluence_band(72) == "preferred"
    assert K.confluence_band(60) == "qualified" and K.confluence_band(55) == "watchlist" and K.confluence_band(49) == "research_only"
    assert K.signal_class({"state": "ENTRY_READY", "score": 75}) == "ENTRY_READY"
    assert K.signal_class({"state": "SETUP_DEVELOPING", "instruction": "PLACE LIMIT ORDER", "score": 72}) == "QUALIFIED_SETUP"
    assert K.signal_class({"state": "SETUP_DEVELOPING", "instruction": "WAIT FOR CONFIRMATION", "score": 63}) == "DEVELOPING_SETUP"
    assert K.signal_class({"state": "WATCHLIST", "score": 45}) == "RESEARCH_CANDIDATE"
    assert K.signal_class({"state": "WATCHLIST", "score": 55}) == "WATCHLIST"
    assert K.signal_class({"state": "NO_SETUP", "score": 20}) == "NO_TRADE"
    assert K.signal_class({"state": "TRADE_INVALIDATED", "score": 70}) == "INVALIDATED"
    assert K.signal_class({"state": "TRADE_EXPIRED", "score": 70}) == "EXPIRED"


def test_position_size_for_gold_risks_about_the_budget():
    ps = K.position_size(10_000, 1.0, entry=2000.0, stop=1995.0)
    assert ps["lots"] == pytest.approx(0.2) and ps["loss_at_stop_usd"] == pytest.approx(100.0)
    assert K.position_size(10_000, 1.0, entry=2000.0, stop=1993.0)["loss_at_stop_usd"] <= 100.0  # rounded down, never above
    assert K.position_size(10_000, 1.0, entry=2000.0, stop=2000.0) is None


def test_report_never_shows_a_probability_and_says_analysis_only():
    plan = {"state": "ENTRY_READY", "instruction": "EXECUTE NOW", "score": 74, "timeframe": "1H", "side": "BUY", "decision": "BUY",
            "zone_kind": "order_block", "setup_type": "trend_pullback", "entry": 2000.0, "stop_loss": 1995.0, "setup_key": "k",
            "targets": [{"price": 2010.0, "rr": 2.0}, {"price": 2015.0, "rr": 3.0}], "reasons_for": ["a"], "reasons_against": ["b"]}
    res = K.enrich("XAUUSD", {"plans": [plan], "best": dict(plan), "timeframes": [], "overall": {"label": "Bullish", "detail": "x"}})
    r = res["analysis_report"]
    assert r["final_decision"] == "ENTRY READY — ANALYSIS ONLY" and r["trade_plan"]["tp2"] == 2015.0
    assert r["model_output"]["estimated_probability"] is None and r["signal_class"] == "ENTRY_READY"
    assert res["plans"][0]["position_size"]["lots"] == pytest.approx(0.2)
