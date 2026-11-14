"""Strategy engine v2 (docs/engine_v2/DESIGN.md) on synthetic candles (TEST FIXTURES ONLY): indicators, regime classifier, the six
strategies' triggers and rejections, plan rules across tick sizes, selector conflicts, sessions across DST, risk, H8 derivation."""
from datetime import datetime, timezone

import numpy as np
import pytest

from app.feature_engineering.indicators import (
    adx,
    bollinger_width,
    efficiency_ratio,
    trailing_percentile,
)
from app.market_data.bars import Bars
from app.strategy_engine.config import GROUPS, RESEARCH_STATUS
from app.strategy_engine.context import TFData
from app.strategy_engine.plan import build_plan, round_to
from app.strategy_engine.regime import Regime, classify
from app.strategy_engine.risk import RiskLimits, check, exposure, position_size
from app.strategy_engine.selector import evaluate_timeframe
from app.strategy_engine.service import derive_8h
from app.strategy_engine.sessions import session_info
from app.strategy_engine.strategies import STRATEGIES
from app.strategy_engine.strategies.base import Candidate

T0 = 1_700_000_000 - (1_700_000_000 % 3600)


def bars(o, h, lo, c, step: int = 3600) -> Bars:
    n = len(c)
    return Bars(t=np.arange(n, dtype=np.int64) * step + T0, o=np.asarray(o, float), h=np.asarray(h, float), l=np.asarray(lo, float),
                c=np.asarray(c, float), v=np.zeros(n), step=step)


def from_closes(c, wick: float = 0.3, step: int = 3600) -> Bars:
    c = np.asarray(c, float)
    prev = np.r_[c[0], c[:-1]]
    o = prev + 0.2 * (c - prev)  # opens a little inside the move, so turning points are strict highs/lows (as in real candles)
    return bars(o, np.maximum(o, c) + wick, np.minimum(o, c) - wick, c, step)


def noise(n: int, seed: int = 1, scale: float = 0.4, drift: float = 0.0, start: float = 100.0):
    rng = np.random.default_rng(seed)
    return start + np.cumsum(rng.normal(drift, scale, n))


def td(b: Bars, levels: dict | None = None) -> TFData:
    return TFData.build("1H", b, levels=levels)


TREND_UP = Regime("TRENDING", 1, None, "uptrend")
TREND_DN = Regime("TRENDING", -1, None, "downtrend")
RANGE = Regime("RANGING", 0, None, "range")
UNKNOWN = Regime("UNKNOWN", 0, "transitional", "transitional")
INTRADAY = GROUPS["intraday"]


# ------------------------------------------------------------------ indicators and regimes
def test_indicators_measure_trend_noise_and_compression():
    up = np.linspace(100, 160, 200) + np.sin(np.arange(200)) * 0.3
    b = from_closes(up)
    a, pdi, mdi = adx(b.h, b.l, b.c)
    assert a[-1] > 25 and pdi[-1] > mdi[-1]
    assert efficiency_ratio(np.linspace(1, 2, 50))[-1] == pytest.approx(1.0)
    flat = np.r_[noise(150, scale=2.0), 100 + np.sin(np.arange(60)) * 0.05]
    bw = bollinger_width(flat)
    assert trailing_percentile(bw)[-1] <= 0.15  # the quiet end is in the lowest percentiles of its own history
    assert np.isnan(adx(b.h[:10], b.l[:10], b.c[:10])[0]).all()  # never invented on a short history


def test_regime_classifier_labels_each_condition_and_says_unknown_when_it_cannot_tell():
    up = from_closes(np.linspace(100, 180, 220) + np.sin(np.arange(220)) * 0.4)
    r = classify(td(up))
    assert r.label == "TRENDING" and r.direction == 1 and r.criteria and all(c["met"] for c in r.criteria)
    dn = from_closes(np.linspace(180, 100, 220) + np.sin(np.arange(220)) * 0.4)
    assert (classify(td(dn)).label, classify(td(dn)).direction) == ("TRENDING", -1)
    short = classify(td(from_closes(noise(100))))
    assert short.label == "UNKNOWN" and short.subtype == "insufficient_data"
    rng_ = 100 + 3 * np.sin(np.arange(260) / 3.0) + noise(260, seed=4, scale=0.05) - 100
    assert classify(td(from_closes(rng_ + 100))).label in ("RANGING", "UNKNOWN")  # never TRENDING on a sideways market
    shock = np.r_[noise(200, seed=2, scale=0.3)]
    sb = from_closes(shock)
    sb.h[-1] = sb.c[-2] + 15  # a 15-point candle after 0.3-point moves
    assert classify(td(sb)).label == "HIGH_VOLATILITY"
    calm = np.r_[noise(170, seed=3, scale=2.0), noise(60, seed=5, scale=0.02, start=100)]
    cb = from_closes(calm, wick=0.02)
    assert classify(td(cb)).label in ("CONSOLIDATING", "RANGING")


# ------------------------------------------------------------------ plan rules
def _cand(d: int, entry: float, inval: float, mode: str = "market", status: str = "ready", targets=None, idx=None) -> Candidate:
    return Candidate("breakout_retest", d, status, mode, entry, None, inval, idx, "test trigger", ["r"], [], targets)


@pytest.mark.parametrize("precision,price", [(2, 4000.0), (5, 1.1), (1, 52000.0), (3, 87.5)])
def test_plans_are_on_the_tick_grid_with_stops_and_targets_on_the_correct_side(precision, price):
    n = 150
    c = price * (1 + np.linspace(0, 0.002, n))
    b = from_closes(c, wick=price * 0.0004)
    t = td(b)
    a = float(t.atr[-1])
    for d in (1, -1):
        entry = float(b.c[-1])
        plan, why = build_plan(_cand(d, entry, entry - d * 1.0 * a), t, group=INTRADAY, precision=precision, spread=price * 0.00002,
                               price_now=entry)
        assert plan is not None, why
        tick = 10.0 ** -precision
        levels = [plan["stop_loss"], plan["entry"]] + [x["price"] for x in plan["targets"]]
        assert all(abs(v / tick - round(v / tick)) < 1e-6 for v in levels)  # every price is on the tick grid
        assert all((levels[k + 1] - levels[k]) * d > 0 for k in range(len(levels) - 1))  # SL < entry < TP1 < TP2 < TP3 (mirrored)
        assert [x["label"] for x in plan["targets"]] == ["TP1", "TP2", "TP3"] and all(x["rr"] > 0 for x in plan["targets"])
        assert plan["targets"][0]["rr"] >= 1.5 - 1e-9 and plan["entry_status"] == "READY"
        assert (plan["entry"] - plan["stop_loss"]) * d == pytest.approx(plan["risk"])


def test_plan_rules_reject_instead_of_repairing():
    b = from_closes(np.linspace(100, 101, 150), wick=0.2)
    t = td(b)
    a, e = float(t.atr[-1]), float(b.c[-1])
    _, why = build_plan(_cand(1, e, e + 0.5), t, group=INTRADAY, precision=2, spread=0.01, price_now=e)
    assert "not beyond the stop" in why  # a BUY whose invalidation is above the entry
    _, why = build_plan(_cand(1, e, e - 0.1 * a), t, group=INTRADAY, precision=2, spread=0.0, price_now=e)
    assert "too tight" in why
    _, why = build_plan(_cand(1, e, e - 10 * a), t, group=INTRADAY, precision=2, spread=0.0, price_now=e)
    assert "too wide" in why
    _, why = build_plan(_cand(1, e, e - 1.0 * a), t, group=INTRADAY, precision=2, spread=0.5 * a, price_now=e)
    assert "would cost" in why  # spread larger than the intraday limit of 0.20R
    _, why = build_plan(_cand(1, e, e - 1.0 * a, targets=[(e + 0.5 * a, "range midpoint")]), t, group=INTRADAY, precision=2, spread=0.0,
                        price_now=e)
    assert "offers only" in why  # TP1 below 1.5R is never shown


def test_entry_status_follows_the_price():
    b = from_closes(np.linspace(100, 101, 150), wick=0.2)
    t = td(b)
    a, e = float(t.atr[-1]), float(b.c[-1])
    kw = dict(group=INTRADAY, precision=2, spread=0.0)
    risk = 1.1 * a
    assert build_plan(_cand(1, e, e - a), t, price_now=e + 0.2 * risk, **kw)[0]["entry_status"] == "READY"
    assert build_plan(_cand(1, e, e - a), t, price_now=e + 0.6 * risk, **kw)[0]["entry_status"] == "ENTRY MISSED"  # never chased
    assert build_plan(_cand(1, e, e - a), t, price_now=e - 2 * risk, **kw)[0]["entry_status"] == "INVALIDATED"
    lim = _cand(1, e - 0.5 * a, e - 1.5 * a, "limit", "pending", idx=t.last)
    assert build_plan(lim, t, price_now=e, **kw)[0]["entry_status"] == "WAITING FOR ENTRY"
    old = _cand(1, e - 0.5 * a, e - 1.5 * a, "limit", "pending", idx=t.last - 40)
    assert build_plan(old, t, price_now=e, **kw)[0]["entry_status"] == "EXPIRED"
    stop = _cand(1, e + 0.5 * a, e - a, "stop", "pending", idx=t.last)
    p, _ = build_plan(stop, t, price_now=e, **kw)
    assert p["entry_status"] == "WAITING FOR ENTRY" and p["entry"] == pytest.approx(round_to(e + 0.5 * a + 0.01, 0.01, "up"))


def test_targets_without_structure_are_labelled_risk_objectives():
    b = from_closes(np.linspace(100, 110, 150), wick=0.05)  # a straight climb: no swing highs above the last close
    t = td(b)
    a, e = float(t.atr[-1]), float(b.c[-1])
    p, why = build_plan(_cand(1, e, e - a), t, group=INTRADAY, precision=2, spread=0.0, price_now=e)
    assert p is not None, why
    assert [x["basis"] for x in p["targets"]] == ["risk objective 2R", "risk objective 3R", "risk objective 5R"]


# ------------------------------------------------------------------ strategies
def _box_then_break(retest_last: bool = True, fail: bool = False, travel: float = 0.0) -> Bars:
    rng = np.random.default_rng(7)
    n = 150
    c = 100 + rng.uniform(-0.8, 0.8, n)
    o = np.r_[100, c[:-1]]
    h, lo = np.maximum(o, c) + 0.2, np.minimum(o, c) - 0.2
    o, h, lo, c = list(o), list(h), list(lo), list(c)
    box_hi = max(h[-20:])
    o += [box_hi - 0.3]
    c += [box_hi + 1.5]
    h += [box_hi + 1.6]
    lo += [box_hi - 0.4]  # breakout candle: strong body, close well beyond the box
    o += [c[-1]]
    c += [box_hi + 1.2 + travel]
    h += [box_hi + 1.7 + travel]
    lo += [box_hi + 1.0]
    if fail:
        o += [c[-1]]
        c += [box_hi - 0.5]
        h += [c[-2]]
        lo += [box_hi - 0.7]
    elif retest_last:
        o += [c[-1]]
        c += [box_hi + 0.6]
        h += [c[-2] + 0.1]
        lo += [box_hi + 0.05]  # touches the level, closes above it
    return bars(o, h, lo, c)


def test_breakout_retest_ready_pending_false_breakout_and_no_chase():
    s = STRATEGIES["breakout_retest"]
    ready = s.evaluate(td(_box_then_break()), UNKNOWN, None, 1)
    assert ready.status == "ready" and ready.entry_mode == "market" and ready.invalidation < ready.entry
    pending = s.evaluate(td(_box_then_break(retest_last=False)), UNKNOWN, None, 1)
    assert pending.status == "pending" and pending.entry_mode == "limit"
    failed = s.evaluate(td(_box_then_break(fail=True)), UNKNOWN, None, 1)
    assert failed.status == "rejected" and "false breakout" in failed.missing[0]
    far = s.evaluate(td(_box_then_break(retest_last=False, travel=4.0)), UNKNOWN, None, 1)
    assert far.status == "rejected" and "travelled" in far.missing[0]
    assert s.evaluate(td(_box_then_break()), UNKNOWN, None, -1).status != "ready"  # no SELL from a bullish breakout


def _sweep_series(shift: bool) -> tuple[Bars, dict]:
    rng = np.random.default_rng(3)
    c = list(100 + np.cumsum(rng.normal(0, 0.15, 140)))
    path = [c[-1] + x for x in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 2.6, 2.2, 1.8, 1.5, 1.9, 2.3, 2.7)]  # rally, dip (swing low), rally
    c += path
    o = [c[0]] + c[:-1]
    h = [max(a, b) + 0.1 for a, b in zip(o, c)]
    lo = [min(a, b) - 0.1 for a, b in zip(o, c)]
    lo[140 + 9] -= 0.3  # the dip candle: a strictly lower low, so it is a swing low
    hi_level = max(h[:-2])
    o += [c[-1]]
    c += [hi_level - 0.3]
    h += [hi_level + 0.6]
    lo += [hi_level - 0.5]  # sweep: trades above the high, closes back below
    if shift:
        o += [c[-1]]
        swing_low = min(c[-8:])
        c += [swing_low - 0.4]
        h += [o[-1] + 0.1]
        lo += [swing_low - 0.5]  # the close breaks the last swing low: market-structure shift
    return bars(o, h, lo, c), {"pdh": hi_level, "pd_end": T0}


def test_a_liquidity_sweep_alone_is_never_a_trade():
    s = STRATEGIES["sweep_reversal"]
    b, lv = _sweep_series(shift=False)
    c = s.evaluate(td(b, lv), UNKNOWN, None, -1)
    assert c.status == "forming" and "a sweep alone is not a trade" in c.missing[0]
    b, lv = _sweep_series(shift=True)
    c = s.evaluate(td(b, lv), UNKNOWN, None, -1)
    assert c.status == "ready" and c.entry_mode == "market" and c.invalidation > c.entry  # SELL: stop side above
    assert s.evaluate(td(b, lv), Regime("HIGH_VOLATILITY"), None, -1).status == "rejected"


def test_the_shift_must_break_the_swing_that_led_into_the_sweep():
    s = STRATEGIES["sweep_reversal"]
    b, lv = _sweep_series(shift=True)
    t = td(b, lv)
    c = s.evaluate(t, UNKNOWN, None, -1)
    sweep_hi = float(max(b.h[-3:]))
    shift_level = float(c.reasons[1].split("beyond the swing ")[1])
    assert shift_level < sweep_hi  # a SELL's shift level is a swing low below the swept high, never one above it


def test_the_previous_day_level_is_never_used_before_that_day_has_closed():
    s = STRATEGIES["sweep_reversal"]
    b, lv = _sweep_series(shift=True)
    late = {**lv, "pd_end": int(b.t[-1]) + 10 * 3600}  # the day closes after the last candle: its high is not known yet
    t = TFData.build("1H", b, levels=late)
    c = s.evaluate(t, UNKNOWN, None, -1)
    assert not any("previous day" in r for r in c.reasons)
    daily = TFData.build("1D", b, levels={**lv, "pd_end": int(b.t[0])})  # on daily candles the "previous day" is the candle itself
    assert not any("previous day" in r for r in s.evaluate(daily, UNKNOWN, None, -1).reasons)


def _uptrend_pullback(trigger: bool) -> Bars:
    c, x = [], 100.0
    for _ in range(40):  # zig-zag uptrend: higher highs and higher lows
        for step in (0.9, 0.8, 0.7, -0.6, -0.5):
            x += step
            c.append(x)
    for step in (0.9, 0.8, 0.7, -0.8, -0.8, -0.7, 0.6):  # a new high, a pullback to EMA20, a weak bounce
        x += step
        c.append(x)
    if trigger:
        c.append(x + 1.5)  # momentum returns: a close above the prior candle
    return from_closes(c, wick=0.15)


def test_trend_pullback_needs_trend_pullback_and_recovery():
    s = STRATEGIES["trend_pullback"]
    waiting = s.evaluate(td(_uptrend_pullback(trigger=False)), TREND_UP, None, 1)
    assert waiting.status == "forming" and "momentum recovery" in waiting.missing[0]  # pullback seen, recovery missing: no plan
    t = td(_uptrend_pullback(trigger=True))
    c = s.evaluate(t, TREND_UP, None, 1)
    assert c.status == "ready" and c.entry_mode == "market", c.missing
    assert c.invalidation < c.entry and any("pullback to" in r for r in c.reasons)
    assert s.evaluate(t, RANGE, None, 1).status == "rejected"  # never outside a trend
    assert s.evaluate(t, TREND_UP, TREND_DN, 1).status == "rejected"  # context timeframe trending the other way
    assert s.evaluate(t, TREND_DN, None, -1).status == "rejected"  # structure is bullish: no SELL pullback


def test_momentum_continuation_refuses_exhausted_moves():
    s = STRATEGIES["momentum_continuation"]
    c = list(np.linspace(100, 130, 200) + np.sin(np.arange(200)) * 0.3)
    c += [c[-1] + 12]  # one huge candle far from EMA20
    out = s.evaluate(td(from_closes(c, wick=0.2)), TREND_UP, None, 1)
    assert out.status in ("rejected", "forming") and out.entry is None


def _range_top_rejection() -> Bars:
    n = 200
    while not 1.0 <= ((n - 1) / 2.5) % (2 * np.pi) <= 1.3:  # end while price is rising toward the top of the range
        n += 1
    b = from_closes(list(100 + 2.5 * np.sin(np.arange(n) / 2.5)), wick=0.2)
    o, h, lo, c = list(b.o), list(b.h), list(b.l), list(b.c)
    top = max(h[-50:])
    o.append(top - 1.0)
    c.append(top - 1.2)
    h.append(top - 0.05)
    lo.append(top - 1.3)  # reaches the range high, closes back inside with a long upper wick
    return bars(o, h, lo, c)


def test_range_reversion_only_inside_a_range_and_only_after_a_rejection():
    s = STRATEGIES["range_reversion"]
    t = td(_range_top_rejection())
    assert s.evaluate(t, TREND_UP, None, -1).missing[0].startswith("disabled outside a RANGING regime (now trending up)")
    out = s.evaluate(t, RANGE, None, -1)
    assert out.status == "ready" and out.entry_mode == "market", out.missing
    assert out.invalidation > out.entry and [n for _, n in out.targets] == ["range midpoint", "75% across the range", "opposite range boundary"]
    assert all(px < out.entry for px, _ in out.targets)
    no_reject = td(from_closes(list(100 + 2.5 * np.sin(np.arange(200) / 2.5)), wick=0.2))
    assert s.evaluate(no_reject, RANGE, None, -1).status in ("forming", "rejected")  # mid-range or no rejection candle: no trade


def _compression_then_expansion() -> Bars:
    rng = np.random.default_rng(9)
    c = list(100 + np.cumsum(rng.normal(0, 1.5, 180)))
    c = [x - c[-1] + 100 for x in c]
    c += list(100 + np.sin(np.arange(25)) * 0.05)
    b = from_closes(c, wick=0.6)
    o, h, lo, cc = list(b.o), list(b.h), list(b.l), list(b.c)
    for k in range(180, len(cc)):  # tight candles: the compression
        h[k], lo[k] = max(o[k], cc[k]) + 0.03, min(o[k], cc[k]) - 0.03
    o.append(100.0)
    cc.append(103.0)
    h.append(103.1)
    lo.append(99.95)  # the expansion candle
    return bars(o, h, lo, cc)


def test_volatility_expansion_needs_compression_then_expansion_and_never_uses_volume():
    s = STRATEGIES["volatility_expansion"]
    b = _compression_then_expansion()
    b.v[:] = 0  # no volume at all: the rule must not need it
    out = s.evaluate(td(b), UNKNOWN, None, 1)
    # the close is far more than 1 ATR beyond the box, so no chase: a limit entry back at the box high, invalidated at its midpoint
    assert out.status == "pending" and out.entry_mode == "limit", out.missing
    assert out.invalidation < out.entry < float(b.c[-1])
    calm = td(from_closes(list(noise(220, seed=11, scale=0.5)), wick=0.2))
    assert s.evaluate(calm, UNKNOWN, None, 1).status == "forming"  # no expansion candle: nothing


# ------------------------------------------------------------------ selector
def test_selector_never_averages_conflicts_and_names_the_reason():
    t = td(_box_then_break())
    r = evaluate_timeframe(t, "1H", UNKNOWN, None, precision=2, spread=0.0, price_now=float(t.bars.c[-1]))
    assert r["action"] in ("BUY", "WAIT FOR BUY", "NO TRADE")
    if r["action"] != "NO TRADE":
        assert r["plan"] and r["plan_label"] == "UNVALIDATED — HYPOTHETICAL TRADE PLAN" and r["research_status"] == RESEARCH_STATUS[r["strategy"]]
    insufficient = evaluate_timeframe(None, "1H", classify(None), None, precision=2, spread=0.0, price_now=None)
    assert insufficient["action"] == "NO TRADE" and insufficient["technical_status"] == "NO SETUP" and insufficient["plan"] is None
    wild = evaluate_timeframe(t, "1H", Regime("HIGH_VOLATILITY", reason="abnormal"), None, precision=2, spread=0.0, price_now=100.0)
    assert wild["action"] == "NO TRADE" and "abnormal" in wild["headline"]
    closed = evaluate_timeframe(t, "1H", UNKNOWN, None, precision=2, spread=0.0, price_now=float(t.bars.c[-1]), market_open=False)
    assert closed["action"] != "BUY"  # never BUY NOW while the market is closed


# ------------------------------------------------------------------ sessions, risk, H8
def test_sessions_follow_daylight_saving_and_block_rollover_and_weekends():
    summer = session_info(datetime(2026, 7, 15, 7, 30, tzinfo=timezone.utc))  # 08:30 London (BST)
    winter = session_info(datetime(2026, 1, 15, 7, 30, tzinfo=timezone.utc))  # 07:30 London (GMT)
    assert "London" in summer["sessions"] and "London" not in winter["sessions"]
    assert session_info(datetime(2026, 7, 15, 13, 30, tzinfo=timezone.utc))["overlap"] is True
    roll = session_info(datetime(2026, 7, 15, 21, 0, tzinfo=timezone.utc))  # 17:00 New York (EDT)
    assert roll["entry_allowed"] is False and "rollover" in roll["block_reason"]
    assert session_info(datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc))["block_reason"].startswith("market closed")  # Saturday
    assert session_info(datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc), "continuous")["entry_allowed"] is True


def test_position_size_exposure_and_limits():
    assert position_size("XAUUSD", 10_000, 0.5, 4000.0, 3995.0)["lots"] == pytest.approx(0.1)  # $50 / $5 = 10 oz = 0.1 lot
    assert position_size("EURUSD", 10_000, 0.5, 1.1000, 1.0980)["lots"] == pytest.approx(0.25)  # $50 / 0.0020 = 25,000 units
    ex = exposure([{"symbol": "EURUSD", "direction": "BUY", "risk_pct": 0.5}, {"symbol": "GBPUSD", "direction": "BUY", "risk_pct": 0.5}])
    assert ex["USD"] == pytest.approx(-1.0) and ex["EUR"] == pytest.approx(0.5)
    sig = {"direction": "BUY", "plan": {"entry": 1.1, "stop_loss": 1.098, "risk_reward": 2.0}}
    sess = {"entry_allowed": True}
    base = dict(symbol="EURUSD", equity=10_000, peak_equity=10_000, today_pnl_pct=0.0, regime_label="TRENDING", session=sess)
    assert check(sig, open_trades=[], **base)["eligible"] is True
    three = [{"symbol": s, "direction": "BUY", "risk_pct": 0.5} for s in ("GBPUSD", "XAUUSD", "US30")]
    out = check(sig, open_trades=three, **base)
    assert out["eligible"] is False and any("correlated exposure" in x for x in out["blocks"])  # USD would reach -2.0%
    assert not check(sig, open_trades=[], **{**base, "today_pnl_pct": -2.5})["eligible"]
    assert not check(sig, open_trades=[], **{**base, "equity": 8_900})["eligible"]  # 11% drawdown halts new entries
    assert not check({**sig, "plan": {**sig["plan"], "risk_reward": 1.2}}, open_trades=[], **base)["eligible"]
    assert check(sig, open_trades=[], **base, limits=RiskLimits(risk_per_trade_pct=0.5))["size"]["risk_amount"] == 50.0


def test_h8_is_built_from_complete_4h_pairs_within_the_trading_day():
    day_open = 1_700_000_000 - (1_700_000_000 % 86400) + 22 * 3600  # an FX day opening at 22:00 UTC
    t4 = np.array([day_open + k * 14400 for k in range(6)] + [day_open + 86400 + k * 14400 for k in range(3)], dtype=np.int64)
    b4 = Bars(t=t4, o=np.arange(9.0), h=np.arange(9.0) + 1, l=np.arange(9.0) - 1, c=np.arange(9.0) + 0.5, v=np.ones(9), step=14400)
    b1d = Bars(t=np.array([day_open], dtype=np.int64), o=np.zeros(1), h=np.ones(1), l=np.zeros(1), c=np.ones(1), v=np.ones(1), step=86400)
    b8 = derive_8h(b4, b1d)
    assert len(b8) == 4  # 3 buckets on day 1 + the complete first bucket of day 2; the forming bucket (1 candle) is left out
    assert b8.o[0] == 0.0 and b8.c[0] == 1.5 and b8.h[0] == 2.0 and b8.l[0] == -1.0 and b8.step == 28800


def _prefix(b: Bars, i: int) -> Bars:
    return Bars(t=b.t[:i + 1], o=b.o[:i + 1], h=b.h[:i + 1], l=b.l[:i + 1], c=b.c[:i + 1], v=b.v[:i + 1], step=b.step)


@pytest.mark.parametrize("make", [lambda: from_closes(list(noise(420, seed=21, scale=0.6, drift=0.02)), wick=0.25),
                                  lambda: _box_then_break(), lambda: _uptrend_pullback(trigger=True)])
def test_replaying_history_gives_exactly_what_the_engine_saw_at_the_time(make):
    """No look-ahead: the full-history view at candle i equals the engine run on candles 0..i only (regime, every strategy, every plan)."""
    b = make()
    full = TFData.build("1H", b)
    for i in range(140, len(b), 7):
        past = TFData.build("1H", _prefix(b, i))
        view = full.at(i)
        r_view, r_past = classify(view), classify(past)
        assert (r_view.label, r_view.direction, r_view.subtype) == (r_past.label, r_past.direction, r_past.subtype), i
        for key, s in STRATEGIES.items():
            for d in (1, -1):
                a_, p_ = s.evaluate(view, r_view, None, d), s.evaluate(past, r_past, None, d)
                assert (a_.status, a_.entry_mode, a_.entry, a_.invalidation, a_.missing) == (p_.status, p_.entry_mode, p_.entry, p_.invalidation, p_.missing), (i, key, d)
                if a_.status in ("ready", "pending"):
                    pa_, pp_ = (build_plan(x, y, group=INTRADAY, precision=2, spread=0.05, price_now=None) for x, y in ((a_, view), (p_, past)))
                    assert pa_ == pp_, (i, key, d)


# ---- confirmation layer: strategies tag their checks and report their key candles (CONFIRMATION_DESIGN.md section 6) -------------
EXPECTED_ANCHORS = {"trend_pullback": {"pullback", "trigger"}, "breakout_retest": {"breakout", "retest", "level"},
                    "momentum_continuation": {"displacement", "pullback"}, "range_reversion": {"touch", "boundary"},
                    "sweep_reversal": {"sweep", "level"}, "volatility_expansion": {"expansion", "box_hi", "box_lo"}}
COMPONENTS = {"regime", "htf", "entry", "structure"}


def _momentum_series() -> TFData:
    rng = np.random.default_rng(1)
    steps = rng.normal(0.15, 0.5, 300)
    steps[np.arange(60, 300, 37)] += 3.0  # a displacement candle now and then
    return td(from_closes(list(100 + np.cumsum(steps)), wick=0.3)).at(246)  # a pending continuation at candle 246


def _live_cases():
    b, lv = _sweep_series(shift=True)
    return [("trend_pullback", td(_uptrend_pullback(trigger=True)), TREND_UP, 1),
            ("breakout_retest", td(_box_then_break()), UNKNOWN, 1),
            ("breakout_retest", td(_box_then_break(retest_last=False)), UNKNOWN, 1),
            ("momentum_continuation", _momentum_series(), TREND_UP, 1),
            ("range_reversion", td(_range_top_rejection()), RANGE, -1),
            ("sweep_reversal", td(b, lv), UNKNOWN, -1),
            ("volatility_expansion", td(_compression_then_expansion()), UNKNOWN, 1)]


def _indices(anchors: dict) -> list[int]:
    out = []
    for v in anchors.values():
        if isinstance(v, (int, np.integer)):
            out.append(int(v))
        elif isinstance(v, list):
            out += [int(x) for x in v]
    return out


@pytest.mark.parametrize("case", range(7))
def test_live_candidates_carry_anchors_inside_the_view(case):
    key, t, reg, d = _live_cases()[case]
    c = STRATEGIES[key].evaluate(t, reg, None, d)
    assert c.status in ("ready", "pending"), c.missing
    assert set(c.anchors) == EXPECTED_ANCHORS[key]
    idx = _indices(c.anchors)
    assert idx and all(0 <= k <= t.last for k in idx)


@pytest.mark.parametrize("case", range(7))
def test_checks_tag_every_reason_with_a_component(case):
    key, t, reg, d = _live_cases()[case]
    c = STRATEGIES[key].evaluate(t, reg, None, d)
    met = [text for comp, ok_, text in c.checks if ok_]
    assert all(r in met for r in c.reasons) and all(comp in COMPONENTS for comp, _, _ in c.checks)
    assert c.reasons == STRATEGIES[key].evaluate(t, reg, None, d).reasons  # reasons unchanged in text and order


def test_rejections_name_the_component_that_failed():
    tp = STRATEGIES["trend_pullback"]
    t = td(_uptrend_pullback(trigger=True))
    assert tp.evaluate(t, RANGE, None, 1).checks == [("regime", False, tp.evaluate(t, RANGE, None, 1).missing[0])]
    assert tp.evaluate(t, TREND_UP, TREND_DN, 1).checks[0][:2] == ("htf", False)
    assert tp.evaluate(td(_uptrend_pullback(trigger=False)), TREND_UP, None, 1).checks[-1][:2] == ("entry", False)
    br = STRATEGIES["breakout_retest"].evaluate(td(_box_then_break(fail=True)), UNKNOWN, None, 1)
    assert br.checks[-1][:2] == ("structure", False)
    b, lv = _sweep_series(shift=True)
    assert STRATEGIES["sweep_reversal"].evaluate(td(b, lv), Regime("HIGH_VOLATILITY"), None, -1).checks[0][:2] == ("regime", False)
    b, lv = _sweep_series(shift=False)
    forming = STRATEGIES["sweep_reversal"].evaluate(td(b, lv), UNKNOWN, None, -1)
    assert ("structure", False) in [x[:2] for x in forming.checks] and ("structure", True) in [x[:2] for x in forming.checks]


def test_find_range_returns_the_established_range_only():
    from app.strategy_engine.strategies.range_reversion import find_range
    t = td(_range_top_rejection())
    rng_ = find_range(t, t.last)
    assert rng_ is not None and rng_[0] < rng_[1] and 0 <= rng_[2] < t.last
    trending = td(from_closes(list(np.linspace(100, 160, 260)), wick=0.2))
    assert find_range(trending, trending.last) is None
