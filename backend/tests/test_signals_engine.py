"""Signal engine: market read, trade plan (entry / stop / targets / must-pass rules), 100-point score, entry states, live downgrades,
causality (no future candles from any timeframe) and the plan lifecycle."""
from datetime import datetime, timezone

import numpy as np
import pytest

from app.core.events import Event
from app.feature_engineering.indicators import atr as atr_fn
from app.market_data.bars import Bars
from app.market_structure.swings import Swing
from app.opportunities.rules_strategy import resample
from app.opportunities.setup import Concepts
from app.price_action.engine import PriceActionResult
from app.signals import config as cfg
from app.signals.context import as_of, classify_direction, in_active_session, period_levels, period_sweeps, read_tf
from app.signals.engine import Frame, _decide, evaluate_instrument, evaluate_timeframe, live_adjust, overall_bias
from app.signals.lifecycle import apply_lifecycle, what_happened
from app.signals.plan import build_plan
from app.signals.scoring import score_plan
from tests.conftest import make_candles

INTRA = cfg.GROUPS["intraday"]
N = 200


def flat(n: int = N, px: float = 100.0) -> Bars:
    """Flat candles: every bar 99.5-100.5, close 100 -> ATR exactly 1.0 (TEST FIXTURE ONLY)."""
    return Bars.from_arrays(np.full(n, px), np.full(n, px + 0.5), np.full(n, px - 0.5), np.full(n, px), step=3600)


def pa_of(b: Bars, **kw) -> PriceActionResult:
    base = dict(atr=atr_fn(b.h, b.l, b.c), swings=[], trend=np.zeros(len(b), np.int8), bias=0, candles=[], breaks=[], equal_levels=[],
                sweeps=[], fvgs=[], order_blocks=[], breakers=[], zones=[], premium_discount=None)
    base.update(kw)
    return PriceActionResult(**base)


def ev(b: Bars, kind: str, direction: str, idx: int, **kw) -> Event:
    return Event(kind=kind, direction=direction, idx=idx, ts=int(b.t[idx]), **kw)


def sh(price: float, idx: int = 120) -> Swing:
    return Swing(idx, "high", price, idx + 3, "HH")


def sl_(price: float, idx: int = 120) -> Swing:
    return Swing(idx, "low", price, idx + 3, "LL")


def cx(levels=(), trendlines=(), breakouts=()) -> Concepts:
    return Concepts(list(levels), list(trendlines), list(breakouts))


def bull_ob(b: Bars, low: float = 99.0, high: float = 99.6, idx: int = 150) -> Event:
    return ev(b, "order_block", "bullish", idx, low=low, high=high, price=(low + high) / 2, status="fresh", evidence="test OB")


# --------------------------------------------------------------------------------------------- market read
def test_direction_classes_follow_the_documented_truth_table():
    assert classify_direction(1, 1, 1) == "strong_bullish"
    assert classify_direction(-1, -1, -1) == "strong_bearish"
    assert classify_direction(1, 1, 0) == "bullish" and classify_direction(1, 0, 0) == "bullish" and classify_direction(1, 0, 1) == "bullish"
    assert classify_direction(1, -1, 1) == "transitioning" and classify_direction(1, 0, -1) == "transitioning"
    assert classify_direction(0, -1, 0) == "bearish"
    assert classify_direction(0, 0, 1) == "ranging"


def test_read_tf_on_trending_data():
    up = make_candles(400, datetime(2024, 1, 1, tzinfo=timezone.utc), 3600, base=100, seed=3, drift=0.35, vol=0.5)
    b = Bars.from_candles(up, 3600)
    from app.price_action.engine import analyze_price_action

    r = read_tf("1H", b, analyze_price_action(b))
    assert r["direction"] == 1 and r["class"] in ("bullish", "strong_bullish")
    assert r["observation"] and r["last_close"] == pytest.approx(b.c[-1])


def test_as_of_and_previous_period_levels_use_complete_candles_only():
    d = Bars.from_arrays([10, 11, 12], [12, 13, 14], [9, 10, 11], [11, 12, 13], t0=0, step=86400)
    cut = as_of(d, 2 * 86400)  # at the end of day 2 only days 0 and 1 are complete
    assert len(cut) == 2
    lv = period_levels(cut, None)
    assert lv["pdh"] == 13 and lv["pdl"] == 10
    b = Bars.from_arrays([11, 11], [11.5, 11.2], [9.5, 10.5], [10.6, 10.9], step=3600)  # first bar wicks under PDL 10 and closes back above
    sw = period_sweeps(b, lv, 0)
    assert sw and sw[0]["direction"] == "bullish" and sw[0]["label"] == "previous day low"


def test_session_window():
    assert in_active_session(int(datetime(2026, 1, 5, 7, 0, tzinfo=timezone.utc).timestamp()))
    assert not in_active_session(int(datetime(2026, 1, 5, 20, 0, tzinfo=timezone.utc).timestamp()))
    assert not in_active_session(int(datetime(2026, 1, 5, 3, 0, tzinfo=timezone.utc).timestamp()))


# --------------------------------------------------------------------------------------------- trade plan
def test_market_buy_at_order_block_has_structural_stop_and_targets():
    b = flat()
    pa = pa_of(b, order_blocks=[bull_ob(b)], swings=[sh(103.0), sh(104.5, 130)], trend=np.ones(N, np.int8))
    p, why = build_plan(b, pa, cx(), 1, INTRA, 0.0, {}, [])
    assert why is None and p is not None
    assert p.entry_type == "market" and p.at_zone and p.entry == 100.0
    assert p.stop_loss == pytest.approx(99.0 - 0.25) and p.invalidation == 99.0
    assert [t["price"] for t in p.targets] == [103.0, 104.5]
    assert p.rr == pytest.approx(3.0 / 1.25) and not p.blocked
    assert p.setup_type == "trend_pullback"


def test_zone_ahead_gives_a_limit_plan_at_its_near_edge():
    b = flat()
    pa = pa_of(b, order_blocks=[bull_ob(b, 98.5, 99.1)], swings=[sh(103.0)])
    p, _ = build_plan(b, pa, cx(), 1, INTRA, 0.0, {}, [])
    assert p.entry_type == "limit" and not p.at_zone and p.entry == 99.1
    assert p.stop_loss == pytest.approx(98.25) and p.rr == pytest.approx((103.0 - 99.1) / 0.85)


def test_no_logical_entry_location_means_no_plan():
    b = flat()
    pa = pa_of(b, order_blocks=[bull_ob(b, 96.0, 97.0)], swings=[sh(103.0)])
    p, why = build_plan(b, pa, cx(), 1, INTRA, 0.0, {}, [])
    assert p is None and "no logical entry location" in why


def test_strong_obstacle_blocks_close_and_penalises_further():
    b = flat()
    near = ev(b, "resistance", "bearish", 140, low=100.6, high=100.7, price=100.65, status="active", meta={"touches": 3})
    p, _ = build_plan(b, pa_of(b, order_blocks=[bull_ob(b)], swings=[sh(103.0)]), cx([near]), 1, INTRA, 0.0, {}, [])
    assert p.blocked and "no room" in p.blocked[0]
    far = ev(b, "resistance", "bearish", 140, low=101.9, high=102.0, price=101.95, status="active", meta={"touches": 3})
    p, _ = build_plan(b, pa_of(b, order_blocks=[bull_ob(b)], swings=[sh(103.0)]), cx([far]), 1, INTRA, 0.0, {}, [])
    assert not p.blocked and p.obstacle and p.obstacle["price"] == 101.9 and p.targets[0]["price"] == 103.0


def test_must_pass_rules_block_wide_stops_costly_spreads_and_missing_targets():
    b = flat()
    wide, _ = build_plan(b, pa_of(b, order_blocks=[bull_ob(b, 96.5, 99.6)], swings=[sh(110.0)]), cx(), 1, INTRA, 0.0, {}, [])
    assert any("structural stop" in x for x in wide.blocked)
    costly, _ = build_plan(b, pa_of(b, order_blocks=[bull_ob(b)], swings=[sh(103.0)]), cx(), 1, INTRA, 0.5, {}, [])
    assert any("spread" in x for x in costly.blocked) and costly.cost_r == pytest.approx(0.4)
    short, _ = build_plan(b, pa_of(b, order_blocks=[bull_ob(b)], swings=[sh(101.5)]), cx(), 1, INTRA, 0.0, {}, [])
    assert any("no structural target" in x for x in short.blocked)


def test_price_discovery_target_is_a_labelled_volatility_multiple():
    b = flat()
    p, _ = build_plan(b, pa_of(b, order_blocks=[bull_ob(b)]), cx(), 1, INTRA, 0.0, {}, [])
    assert p.targets[0]["basis"] == "volatility_multiple" and p.targets[0]["price"] == pytest.approx(100.0 + 2.0 * 1.25)
    assert any("price discovery" in w for w in p.warnings)


def test_failed_zone_is_not_traded():
    b = flat()
    b.c[-3], b.l[-3] = 98.9, 98.8  # a close below the zone low after the touch
    p, why = build_plan(b, pa_of(b, order_blocks=[bull_ob(b)], swings=[sh(103.0)]), cx(), 1, INTRA, 0.0, {}, [])
    assert p is None and "zone failed" in why


def test_sell_mirror_and_sweep_entry_without_zone():
    b = flat()
    ob = ev(b, "order_block", "bearish", 150, low=100.4, high=101.0, price=100.7, status="fresh", evidence="test OB")
    p, _ = build_plan(b, pa_of(b, order_blocks=[ob], swings=[sl_(97.0)]), cx(), -1, INTRA, 0.0, {}, [])
    assert p.direction == "SELL" and p.stop_loss == pytest.approx(101.25) and p.targets[0]["price"] == 97.0 and p.rr == pytest.approx(2.4)
    sweep = ev(b, "liquidity_sweep", "bullish", N - 3, price=99.3, low=99.0, high=100.2, evidence="test sweep")
    choch = ev(b, "CHoCH", "bullish", N - 2, price=100.3)
    p, _ = build_plan(b, pa_of(b, sweeps=[sweep], breaks=[choch], swings=[sh(103.0)]), cx(), 1, INTRA, 0.0, {}, [])
    assert p.poi is None and p.setup_type == "liquidity_sweep_reversal" and p.invalidation == 99.0 and p.entry_type == "market"


# --------------------------------------------------------------------------------------------- score
def _read(d: int, label: str = "Bullish") -> dict:
    return {"direction": d, "label": label, "structure": "HH/HL", "observation": "test"}


def test_full_confluence_scores_100_and_every_factor_respects_its_maximum():
    b = flat()
    pa = pa_of(b, order_blocks=[bull_ob(b)], swings=[sh(105.5)], trend=np.ones(N, np.int8))
    p, _ = build_plan(b, pa, cx(), 1, INTRA, 0.0, {}, [])
    sweep = {"label": "swing low", "price": 99.2, "break": ev(b, "CHoCH", "bullish", N - 2, price=100.3)}
    sc = score_plan(plan=p, setup_tf="1H", group=INTRA, bias=[("4H", _read(1)), ("1D", _read(1))], setup_read=_read(1),
                    fresh_break={"text": "x"}, sweep=sweep, zone_pos=0.3, confluence="support band", ltf_break={"text": "x"},
                    rejection={"text": "x"}, confirm_tf="15m", atr_pct=0.5, session_ok=True)
    assert sc["score"] == 100 and sc["met"] == sc["total"]
    assert all(f["points"] <= f["max"] for f in sc["factors"]) and sum(f["max"] for f in sc["factors"]) == 100


def test_missing_data_scores_zero_and_obstacles_cost_the_rr_points():
    b = flat()
    far = ev(b, "resistance", "bearish", 140, low=101.9, high=102.0, price=101.95, status="active", meta={"touches": 3})
    p, _ = build_plan(b, pa_of(b, order_blocks=[bull_ob(b)], swings=[sh(105.5)]), cx([far]), 1, INTRA, 0.0, {}, [])
    sc = score_plan(plan=p, setup_tf="1H", group=INTRA, bias=[("4H", None), ("1D", None)], setup_read=_read(0, "Ranging"),
                    fresh_break=None, sweep=None, zone_pos=None, confluence=None, ltf_break=None, rejection=None, confirm_tf="15m",
                    atr_pct=None, session_ok=False)
    f = {x["key"]: x for x in sc["factors"]}
    assert f["htf_alignment"]["points"] == 0 and "not assumed" in f["htf_alignment"]["checks"][0]["detail"]
    assert f["risk_reward"]["points"] == 0 and "in the way" in f["risk_reward"]["checks"][0]["detail"]
    assert sc["score"] == 7  # only "entry at a point of interest"


# --------------------------------------------------------------------------------------------- states
def _plan(**kw):
    b = flat()
    p, _ = build_plan(b, pa_of(b, order_blocks=[bull_ob(b, *kw.pop("zone", (99.0, 99.6)))], swings=[sh(105.5)]), cx(), 1, INTRA, 0.0, {}, [])
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def test_entry_states_and_final_instructions():
    at = _plan()
    assert _decide(at, 30, None, None, "1H", "15m")[:2] == ("NO_SETUP", "NO TRADE")
    assert _decide(at, 55, None, None, "1H", "15m")[:2] == ("WATCHLIST", "NO TRADE")
    assert _decide(at, 65, None, None, "1H", "15m")[:2] == ("WAITING_FOR_CONFIRMATION", "WAIT FOR CONFIRMATION")
    assert _decide(at, 65, {"text": "x"}, None, "1H", "15m")[:2] == ("ENTRY_READY", "EXECUTE NOW")
    limit = _plan(zone=(98.5, 99.1))
    assert _decide(limit, 75, None, None, "1H", "15m")[:2] == ("SETUP_DEVELOPING", "PLACE LIMIT ORDER")
    assert _decide(limit, 65, None, None, "1H", "15m")[:2] == ("SETUP_DEVELOPING", "WAIT FOR CONFIRMATION")
    blocked = _plan(blocked=["structural stop too wide"])
    assert _decide(blocked, 90, {"text": "x"}, None, "1H", "15m")[:2] == ("WATCHLIST", "NO TRADE")


def test_live_downgrades_when_market_closed_or_spread_abnormal():
    s, i, c = live_adjust("ENTRY_READY", "EXECUTE NOW", [], True, {"market_open": False}, 0.3)
    assert (s, i) == ("WAITING_FOR_CONFIRMATION", "WAIT FOR CONFIRMATION") and "closed" in c[0]
    s, i, _ = live_adjust("SETUP_DEVELOPING", "PLACE LIMIT ORDER", [], False, {"market_open": True, "live_spread": 2.0}, 0.3)
    assert (s, i) == ("SETUP_DEVELOPING", "WAIT FOR CONFIRMATION")
    assert live_adjust("ENTRY_READY", "EXECUTE NOW", [], True, {"market_open": True, "live_spread": 0.3}, 0.3)[:2] == ("ENTRY_READY", "EXECUTE NOW")


# --------------------------------------------------------------------------------------------- whole engine
def _multi_tf(days: int = 40, seed: int = 7) -> dict[str, Bars]:
    start = datetime(2025, 3, 3, tzinfo=timezone.utc)
    base = Bars.from_candles(make_candles(days * 288, start, 300, base=2000, seed=seed, vol=1.2), 300)  # 5m
    out = {"5m": base}
    for tf, sec in (("15m", 900), ("1H", 3600), ("4H", 14400), ("1D", 86400)):
        out[tf] = resample(base, sec)
    return out


def test_evaluation_never_uses_candles_after_the_setup_close():
    s = _multi_tf()
    k = len(s["1H"]) - 37
    end = int(s["1H"].t[k - 1]) + 3600
    full = {tf: Frame(tf, b) for tf, b in s.items() if tf != "1H"}
    full["1H"] = Frame("1H", s["1H"].upto(k))
    cut = {tf: Frame(tf, as_of(b, end)) for tf, b in s.items()}
    a = evaluate_timeframe("XAUUSD", "1H", full, spread=0.3)
    b = evaluate_timeframe("XAUUSD", "1H", cut, spread=0.3)
    assert a == b and a["status"] == "ok"
    assert a["bias_tfs"] == ["4H", "1D"] and a["confirm_tf"] == "15m"


def test_insufficient_and_stale_data_are_reported_not_traded():
    s = _multi_tf(days=3)
    frames = {"1H": Frame("1H", s["1H"].upto(50))}
    r = evaluate_timeframe("XAUUSD", "1H", frames)
    assert r["status"] == "insufficient_data" and r["state"] == "NO_SETUP"
    s = _multi_tf()
    r = evaluate_timeframe("XAUUSD", "1H", {"1H": Frame("1H", s["1H"], stale_bars=9)})
    assert r["status"] == "stale" and r["instruction"] == "NO TRADE"


def test_instrument_evaluation_covers_every_timeframe_and_is_consistent():
    s = _multi_tf()
    res = evaluate_instrument("XAUUSD", {tf: Frame(tf, b) for tf, b in s.items()}, live={"market_open": True})
    assert [p["timeframe"] for p in res["plans"]] == list(cfg.SIGNAL_TFS)
    assert res["overall"]["label"] in ("Bullish", "Bearish", "Mixed") and res["report"]["text"]
    for p in res["plans"]:
        assert p["state"] in cfg.STATE_ORDER and p["instruction"] in ("EXECUTE NOW", "WAIT FOR CONFIRMATION", "PLACE LIMIT ORDER", "NO TRADE")
        if p.get("targets") and p.get("side"):
            d = 1 if p["side"] == "BUY" else -1
            assert d * (p["entry"] - p["stop_loss"]) > 0 and d * (p["targets"][0]["price"] - p["entry"]) > 0
            assert p["score"] is not None and 0 <= p["score"] <= 100
        if p["state"] in ("ENTRY_READY", "WAITING_FOR_CONFIRMATION", "SETUP_DEVELOPING"):
            assert p["score"] >= cfg.THRESHOLDS["signal"] and not p["blocked"] and p["risk_reward"] >= cfg.GROUPS[p["group"]].min_rr


def test_overall_bias_is_macro_weighted():
    rows = {"1W": {"direction": 1, "label": "Bullish"}, "1D": {"direction": 1, "label": "Bullish"}, "5m": {"direction": -1, "label": "Bearish"}}
    o = overall_bias(rows)
    assert o["label"] == "Bullish" and o["groups"]["Short-term"] == "Bearish"


# --------------------------------------------------------------------------------------------- lifecycle
def test_lifecycle_reports_invalidation_and_targets():
    b = Bars.from_arrays([100, 100, 100], [101, 101, 104], [99, 97, 99], [100, 98.5, 103], t0=1000, step=3600)
    prev = {"side": "BUY", "invalidation": 99.0, "tp1": 103.5, "signal_ts": 1000, "valid_until_ts": 10**10, "entry": 100, "stop_loss": 98.75}
    assert what_happened(prev, Frame("1H", b), "1H", 2000)["state"] == "TRADE_INVALIDATED"  # the 98.5 close came before the 104 high
    prev["invalidation"] = 95.0
    assert what_happened(prev, Frame("1H", b), "1H", 2000)["state"] == "TRADE_EXPIRED"
    memory: dict = {}
    live = {"timeframe": "1H", "state": "ENTRY_READY", "setup_key": "BUY:order_block:1", "side": "BUY", "entry": 100, "stop_loss": 98.75,
            "invalidation": 99.0, "signal_ts": 1000, "valid_until_ts": 10**10, "targets": [{"price": 110.0}]}
    apply_lifecycle("XAUUSD", [live], {"1H": Frame("1H", b)}, memory, 2000)
    gone = {"timeframe": "1H", "state": "NO_SETUP", "instruction": "NO TRADE", "reasons_against": []}
    apply_lifecycle("XAUUSD", [gone], {"1H": Frame("1H", b)}, memory, 3000)
    assert gone["state"] == "TRADE_INVALIDATED" and gone["previous"]["side"] == "BUY"
