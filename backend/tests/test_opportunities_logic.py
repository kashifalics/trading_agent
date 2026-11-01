"""Unit tests for the Trade Opportunities analytical modules: detectors, setup rules, scoring, ranking, analogues, validation."""
import numpy as np
import pytest

from app.core.events import Event
from app.feature_engineering.indicators import atr as atr_fn
from app.market_data.bars import Bars
from app.market_structure.swings import Swing, find_swings
from app.opportunities import config as cfg
from app.opportunities.analogue import build_context, setup_analogues
from app.opportunities.scoring import ScoreInputs, score_setup
from app.opportunities.service import rank_rows
from app.opportunities.setup import Bias, Concepts, generate_setup
from app.opportunities.validation import classify, strategy_validation
from app.price_action.engine import PriceActionResult, analyze_price_action
from app.price_action.levels import (
    BreakoutParams,
    LevelParams,
    detect_breakouts,
    detect_levels,
    detect_trendlines,
)

PROF = cfg.PROFILES["swing"]


def bars_from(rows):
    a = np.array(rows, float)
    return Bars.from_arrays(a[:, 0], a[:, 1], a[:, 2], a[:, 3], step=3600)


def wave(highs, lows, n_each=8, base=100.0):
    """Zig-zag bars whose swing highs/lows hit the given prices exactly (a distinct peak bar and trough bar per cycle)."""
    rows, px = [], base
    for hi, lo in zip(highs, lows):
        path = list(np.linspace(px, hi, n_each)) + list(np.linspace(hi, lo, n_each))[1:]
        start = len(rows)
        for a, b in zip(path[:-1], path[1:]):
            rows.append([a, max(a, b) + 0.05, min(a, b) - 0.05, b])
        rows[start + n_each - 2][1] = hi  # peak bar: its high is the swing high ...
        rows[start + n_each - 1][1] = hi - 0.2  # ... and the bars around it are lower
        rows[-1][2] = lo  # trough bar: its low is the swing low
        px = lo
    return bars_from(rows)


# ----------------------------------------------------------------------------------------------- S/R, trendlines
def test_support_resistance_needs_repeated_touches_and_is_causal():
    b = wave([110, 110.1, 109.9, 110.05], [100, 101, 102, 103])
    atr = atr_fn(b.h, b.l, b.c)
    sw = find_swings(b)
    lv = detect_levels(b, sw, atr)
    res = [e for e in lv if e.low <= 110.1 and e.high >= 109.9]
    assert res and res[0].meta["touches"] >= 3 and res[0].kind in ("resistance", "support")
    only_one = detect_levels(b, [s for s in sw if s.kind == "high"][:1], atr)
    assert only_one == []  # a single swing is not a level
    # no look-ahead: levels known at bar k are identical whether or not later bars exist
    k = len(b) - 20
    full = detect_levels(b, sw, atr, as_of=k)
    cut = detect_levels(b.upto(k + 1), [s for s in find_swings(b.upto(k + 1))], atr_fn(b.h[:k + 1], b.l[:k + 1], b.c[:k + 1]))
    assert [(round(e.low, 6), round(e.high, 6), e.meta["touches"]) for e in full] == \
           [(round(e.low, 6), round(e.high, 6), e.meta["touches"]) for e in cut]


def test_trendline_requires_three_touches_and_dies_when_closed_through():
    b = wave([115, 117, 119, 121], [100, 102, 104, 106])  # rising lows 100,102,104,106 on a straight line
    atr = atr_fn(b.h, b.l, b.c)
    sw = find_swings(b)
    tl = [e for e in detect_trendlines(b, sw, atr) if e.kind == "trendline_support"]
    assert tl and tl[0].meta["touches"] >= 3 and tl[0].meta["slope"] > 0
    # force a close far below the line after the touches: the line must be rejected
    c = b.c.copy()
    c[-3:] = c[-3:] - 8
    broken = Bars(b.t, b.o, b.h, b.l, c, b.v, b.step)
    assert not [e for e in detect_trendlines(broken, sw, atr) if e.kind == "trendline_support"]


def test_breakout_retest_and_failed_breakout():
    base = [(100, 100.4, 99.6, 100)] * 3
    swings_zone = [(100, 110.1, 99.9, 109.9), (109.9, 110.2, 105, 106), (106, 110.1, 105, 109.9), (109.9, 110.1, 105, 106),
                   (106, 110.05, 105, 109.95), (109.95, 110, 105, 106)]
    # clean break above ~110 at bar k, then a retest that holds
    brk = [(106, 113, 105.9, 112.5), (112.5, 112.8, 110.0, 111.5), (111.5, 113, 111, 112.9)]
    b = bars_from(base + swings_zone * 2 + brk)
    atr = np.full(len(b), 2.0)
    lv = Event("resistance", "bearish", idx=14, ts=int(b.t[14]), price=110.0, low=109.9, high=110.1, start_idx=3, start_ts=int(b.t[3]),
               meta={"touches": 4, "second_confirm_idx": 8})
    ev = detect_breakouts(b, [lv], atr, BreakoutParams(break_atr=0.25))
    kinds = [e.kind for e in ev]
    assert "breakout" in kinds and "retest" in kinds and "failed_breakout" not in kinds
    # same breakout, but price closes back under the band within 5 bars -> failed
    fail = [(106, 113, 105.9, 112.5), (112.5, 112.6, 108, 108.5)]
    b2 = bars_from(base + swings_zone * 2 + fail)
    ev2 = detect_breakouts(b2, [lv], np.full(len(b2), 2.0))
    assert [e.kind for e in ev2][:2] == ["breakout", "failed_breakout"]
    # a level whose 2nd touch is not yet confirmed at the breakout bar is ignored (information not available then)
    late = Event("resistance", "bearish", idx=60, ts=0, price=110.0, low=109.9, high=110.1, start_idx=3, start_ts=0,
                 meta={"touches": 2, "second_confirm_idx": 500})
    assert detect_breakouts(b, [late], atr) == []


# ----------------------------------------------------------------------------------------------- setup rules (controlled PA)
def _pa(b: Bars, trend: int, zones=(), swings=(), candles=(), breaks=(), sweeps=(), equal=(), atr_val=2.0) -> PriceActionResult:
    n = len(b)
    return PriceActionResult(atr=np.full(n, atr_val), swings=list(swings), trend=np.full(n, trend, dtype=np.int8), bias=trend, candles=list(candles),
                             breaks=list(breaks), equal_levels=list(equal), sweeps=list(sweeps), fvgs=[], order_blocks=list(zones), breakers=[],
                             zones=[], premium_discount=None)


def _flat_bars(n=80, price=105.0, last=None):
    rows = [(price, price + 0.5, price - 0.5, price)] * n
    if last:
        rows[-1] = last
    return bars_from(rows)


def _ob(low, high, idx=40, direction="bullish"):
    return Event("order_block", direction, idx=idx, ts=1_700_000_000 + idx * 3600, low=low, high=high, price=(low + high) / 2, status="unmitigated",
                 evidence="test zone")


def _sw(idx, kind, price, n=80):
    return Swing(idx, kind, price, min(idx + 3, n - 1))


def test_buy_setup_is_structural_and_waits_for_confirmation():
    b = _flat_bars()
    swings = [_sw(10, "low", 99.0), _sw(30, "high", 118.0), _sw(50, "high", 126.0), _sw(60, "high", 140.0)]
    pa = _pa(b, 1, zones=[_ob(101.0, 103.0)], swings=swings)
    out = generate_setup(b, pa, Concepts([], [], []), Bias(1, 0.8, False, [{"timeframe": "1D", "direction": 1, "note": "bullish"}]), PROF, 0.0002)
    s = out.setup
    assert s and s.direction == "BUY" and s.status == "waiting_for_confirmation"
    assert (s.entry_low, s.entry_high, s.entry_ref) == (101.0, 103.0, 103.0)  # structural zone, upper edge = first contact
    assert s.stop_loss < 101.0 and abs(s.invalidation - 99.0) < 1e-9 or abs(s.invalidation - 101.0) < 1e-9
    assert s.targets[0]["price"] == 118.0 and s.targets[0]["basis"] == "swing_high" and s.risk_reward >= PROF.min_rr
    assert s.targets[0]["price"] < s.targets[1]["price"] < s.targets[2]["price"]  # TP1 < TP2 < TP3, all structural
    assert any("entry zone" in c for c in s.conditions)


def test_confirmation_after_touch_triggers_entry_but_a_candle_before_the_touch_does_not():
    last = (104.0, 104.5, 100.5, 104.2)  # last bar trades down into the zone 101-103 and closes back above it
    b = _flat_bars(last=last)
    swings = [_sw(10, "low", 99.0), _sw(30, "high", 118.0), _sw(60, "high", 140.0)]
    eng = Event("bullish_engulfing", "bullish", idx=79, ts=int(b.t[79]), price=104.2, evidence="engulfing")
    pa = _pa(b, 1, zones=[_ob(101.0, 103.0)], swings=swings, candles=[eng])
    s = generate_setup(b, pa, Concepts([], [], []), Bias(1, 0.8, False, []), PROF, 0.0002).setup
    assert s.status == "entry_triggered" and s.trigger_ts == int(b.t[79])
    early = Event("bullish_engulfing", "bullish", idx=60, ts=int(b.t[60]), price=104.2, evidence="engulfing")
    pa2 = _pa(b, 1, zones=[_ob(101.0, 103.0)], swings=swings, candles=[early])
    s2 = generate_setup(b, pa2, Concepts([], [], []), Bias(1, 0.8, False, []), PROF, 0.0002).setup
    assert s2.status == "waiting_for_confirmation"  # confirmation must come at/after the touch


@pytest.mark.parametrize("case", ["htf_opposes", "no_zone", "costs", "stop_too_far", "obstacle", "target_already_hit"])
def test_wait_when_a_requirement_is_missing(case):
    b = _flat_bars()
    swings = [_sw(10, "low", 99.0), _sw(30, "high", 118.0), _sw(60, "high", 140.0)]
    zones, bias, cost = [_ob(101.0, 103.0)], Bias(1, 0.8, False, []), 0.0002
    if case == "htf_opposes":
        bias = Bias(-1, -0.8, False, [])
    elif case == "no_zone":
        zones = [_ob(60.0, 62.0)]
    elif case == "costs":
        cost = 0.02  # 2% round trip against a ~3% stop
    elif case == "stop_too_far":
        zones = [_ob(80.0, 103.0)]
    elif case == "obstacle":
        swings.append(_sw(70, "high", 108.0))
        pa = _pa(b, 1, zones=zones, swings=swings, equal=[Event("equal_highs", "bearish", idx=72, ts=1, price=108.0)])
        out = generate_setup(b, pa, Concepts([], [], []), bias, PROF, cost)
        assert out.setup is None and any("opposing structure" in r for r in out.wait_reasons)
        return
    elif case == "target_already_hit":
        b = _flat_bars(last=(104.0, 119.0, 100.5, 104.2))
    pa = _pa(b, 1, zones=zones, swings=swings)
    out = generate_setup(b, pa, Concepts([], [], []), bias, PROF, cost)
    assert out.setup is None and out.wait_reasons


def test_setup_generation_is_deterministic():
    b = _flat_bars()
    swings = [_sw(10, "low", 99.0), _sw(30, "high", 118.0), _sw(60, "high", 140.0)]
    pa = _pa(b, 1, zones=[_ob(101.0, 103.0)], swings=swings)
    a = generate_setup(b, pa, Concepts([], [], []), Bias(1, 0.8, False, []), PROF, 0.0002).setup
    c = generate_setup(b, pa, Concepts([], [], []), Bias(1, 0.8, False, []), PROF, 0.0002).setup
    assert a == c


# ----------------------------------------------------------------------------------------------- scoring
def _inputs(validation="untested", rr=2.5, conflict=False, analogue=None, quality=None):
    b = _flat_bars()
    swings = [_sw(10, "low", 99.0), _sw(30, "high", 118.0), _sw(60, "high", 140.0)]
    pa = _pa(b, 1, zones=[_ob(101.0, 103.0)], swings=swings)
    s = generate_setup(b, pa, Concepts([], [], []), Bias(1, 0.8, False, []), PROF, 0.0002).setup
    s.risk_reward = rr
    an = analogue or {"available": True, "n_obs": 120, "sample_quality": "moderate", "edge_vs_base": 0.15, "edge_within_noise": False,
                      "tp_first": {"frequency": 0.45}, "base_rate": {"frequency": 0.30}}
    return ScoreInputs(setup=s, bias=Bias(1, 0.9, conflict, [{"timeframe": "1D", "direction": 1, "note": "bullish"}]), profile=PROF, trend=1,
                       recent_break_same_dir=True, zone_position=0.3, poi_touches=None,
                       feats={"ret_10": 1.0, "slope_20": 1.0, "rsi_14": 0.58, "vol_ratio": 1.0, "atr_pct_rank": 0.5},
                       analogue=an, quality=quality or {"score": 1.0, "issues": [], "stale_bars": 0, "gap_count": 0},
                       validation={"status": validation, "summary": validation})


def test_weights_sum_to_one_and_score_is_labelled_not_a_probability():
    assert abs(sum(cfg.WEIGHTS.values()) - 1.0) < 1e-9
    r = score_setup(_inputs())
    assert r["label"] == "Evidence Score — Not Win Probability" and r["calibrated"] is False
    assert 0 <= r["score"] <= 100 and len(r["components"]) == 9
    assert abs(sum(c["points"] for c in r["components"]) - 100 * sum(c["weight"] * c["raw"] for c in r["components"])) < 0.2


@pytest.mark.parametrize("status,cap", [("untested", 65.0), ("no_edge", 58.0), ("negative", 49.0)])
def test_unvalidated_strategies_cannot_exceed_their_cap(status, cap):
    r = score_setup(_inputs(validation=status))
    assert r["score"] <= cap
    assert r["uncapped_score"] > cap and r["cap"]["applied"] is True  # the raw evidence was strong, validation limited it
    assert r["score"] < cfg.PROFILES["swing"].min_evidence or status != "negative"  # a negative strategy can never be published


def test_validated_strategy_is_not_capped_and_penalties_reduce_the_score():
    good = score_setup(_inputs(validation="validated"))
    assert good["cap"]["applied"] is False and good["score"] > score_setup(_inputs(validation="untested"))["score"]
    bad = score_setup(_inputs(validation="validated", conflict=True, quality={"score": 0.5, "issues": ["x"], "stale_bars": 9, "gap_count": 4},
                                analogue={"available": False, "reason": "none", "n_obs": 0}))
    names = {p["name"] for p in bad["penalties"]}
    assert {"conflicting_timeframes", "stale_data", "missing_candles", "weak_sample"} <= names
    assert bad["score"] < good["score"] - 20


# ----------------------------------------------------------------------------------------------- ranking
def _row(symbol, style, direction, score, val, status="waiting_for_confirmation", side=None, rr=2.0):
    return {"symbol": symbol, "style": style, "direction": direction, "status": status, "evidence_score": score, "validation_status": val,
            "risk_reward": rr, "side": side or direction}


def test_validated_outranks_unvalidated_regardless_of_score_and_wait_is_unranked():
    rows = [_row("BTCUSDT", "swing", "BUY", 64, "untested"), _row("XAUUSD", "swing", "SELL", 56, "validated"),
            _row("XAUUSD", "scalping", "WAIT", None, "untested", status="none"),
            _row("BTCUSDT", "intraday", "WAIT", 40, "untested", status="watchlist", side="BUY")]
    out = rank_rows(rows)
    live = [r for r in out if r["rank"] is not None]
    assert [r["symbol"] for r in live][:2] == ["XAUUSD", "BTCUSDT"] and live[0]["rank"] == 1
    assert next(r for r in out if r["status"] == "none")["rank"] is None
    assert live[-1]["status"] == "watchlist"  # actionable first, then watchlist


def test_same_instrument_same_direction_is_flagged_as_one_exposure():
    out = rank_rows([_row("XAUUSD", "swing", "BUY", 60, "untested"), _row("XAUUSD", "intraday", "BUY", 55, "untested"),
                     _row("BTCUSDT", "swing", "BUY", 50, "untested")])
    by = {(r["symbol"], r["style"]): r for r in out}
    assert by[("XAUUSD", "intraday")]["correlated_with_rank"] == by[("XAUUSD", "swing")]["rank"]
    assert by[("BTCUSDT", "swing")]["correlated_with_rank"] is None


# ----------------------------------------------------------------------------------------------- analogues
def _random_walk(n=1500, seed=3):
    rng = np.random.default_rng(seed)
    c = 100 + np.cumsum(rng.normal(0, 0.6, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + np.abs(rng.normal(0, 0.3, n))
    lo = np.minimum(o, c) - np.abs(rng.normal(0, 0.3, n))
    return Bars.from_arrays(o, h, lo, c, step=3600)


def test_analogues_are_point_in_time_and_direction_aware():
    b = _random_walk()
    pa = analyze_price_action(b)
    ctx = build_context(b, pa, PROF)
    buy = setup_analogues(b, pa, ctx, PROF, "BUY", "TEST", "1H")
    sell = setup_analogues(b, pa, ctx, PROF, "SELL", "TEST", "1H")
    assert buy["available"] and buy["n_obs"] >= 30 and buy["sample_quality"] in ("limited", "moderate")
    H = PROF.horizon_bars
    last_ts = int(b.t[-1])
    for n in buy["neighbors"]:  # every analogue's outcome window finished before "now": no look-ahead
        assert n["ts"] + (H + 1) * b.step <= last_ts
    key = str(H)
    assert buy["forward_return_atr"][key]["mean"] == pytest.approx(-sell["forward_return_atr"][key]["mean"], abs=1e-9)
    assert buy["mfe_atr"]["mean"] == pytest.approx(sell["mae_atr"]["mean"], abs=1e-9)
    assert buy["tp_first"]["n"] == buy["n_obs"] and "not a probability" in buy["kind"]


def test_analogues_report_insufficient_history_instead_of_inventing_evidence():
    b = _random_walk(80)
    pa = analyze_price_action(b)
    res = setup_analogues(b, pa, build_context(b, pa, PROF), PROF, "BUY", "TEST", "1H")
    assert res["available"] is False and res["sample_quality"] == "insufficient" and res["reason"]


# ----------------------------------------------------------------------------------------------- validation classification
SIG_POS = {"boot_ci95": [0.05, 0.25], "p_edge_gt_0": 0.01}


def test_classify_validation_statuses():
    assert classify({"n_trades": 40, "expectancy_r": 0.4}, SIG_POS, 1.0, 0.0)[0] == "no_edge"  # too few trades, however good it looks
    assert classify({"n_trades": 300, "expectancy_r": -0.2}, {"boot_ci95": [-0.3, -0.1], "p_edge_gt_0": 0.99}, 0.0, -0.1)[0] == "negative"
    assert classify({"n_trades": 300, "expectancy_r": 0.1}, {"boot_ci95": [-0.05, 0.25], "p_edge_gt_0": 0.1}, 0.5, 0.0)[0] == "no_edge"
    assert classify({"n_trades": 300, "expectancy_r": 0.15}, SIG_POS, 0.8, 0.0)[0] == "validated"
    assert classify({"n_trades": 300, "expectancy_r": 0.15}, SIG_POS, 0.5, 0.0)[0] == "no_edge"  # unstable across folds
    assert classify({"n_trades": 300, "expectancy_r": 0.15}, SIG_POS, 0.8, 0.30)[0] == "no_edge"  # not better than random entries


def test_missing_validation_is_untested_never_validated(tmp_path):
    assert strategy_validation("XAUUSD", "swing", "4H", tmp_path / "missing.json")["status"] == "untested"
    assert strategy_validation("XAUUSD", "swing", "4H")["status"] != "validated"  # nothing shipped may claim validation without evidence


def test_profiles_are_sane():
    for p in cfg.PROFILES.values():
        assert p.min_rr >= 1.0 and p.min_stop_atr < p.max_stop_atr and 0 < p.max_cost_r < 1 and set(p.setup_tfs) <= set(cfg.ALL_TIMEFRAMES)
    assert cfg.PROFILES["long_term"].scope.lower().find("not a fundamental") >= 0
    assert LevelParams().min_touches == 2


# ----------------------------------------------------------------------------------------------- validation replay helpers
def test_resample_builds_only_completed_buckets_with_correct_ohlc():
    from app.opportunities.rules_strategy import resample

    n = 10
    o = np.arange(n, dtype=float)
    b = Bars.from_arrays(o, o + 2, o - 1, o + 0.5, t0=0, step=3600)
    h = resample(b, 4 * 3600)  # buckets [0-3], [4-7], and a still-forming [8-9]
    assert len(h) == 2 and list(h.t) == [0, 4 * 3600]
    assert h.o[0] == 0 and h.c[0] == 3.5 and h.h[0] == 5 and h.l[0] == -1  # first open, last close, max high, min low of bars 0..3
    assert h.h[1] == 9 and h.l[1] == 3 and h.c[1] == 7.5  # the forming bucket's bars 8-9 never leak into bucket 1
    assert len(resample(b.upto(7), 4 * 3600)) == 1  # at 7 bars the second bucket is incomplete


def test_oos_analysis_uses_only_trades_after_the_split_and_never_validates_small_samples():
    from datetime import datetime, timezone

    from app.research.run_opportunity_validation import oos_analysis

    def trades(n, r, start):
        return [{"entry": datetime.fromtimestamp(start + i * 3600, tz=timezone.utc).isoformat(), "dir": "BUY" if i % 2 else "SELL", "r": r, "pnl": r, "reason": "target"}
                for i in range(n)]

    t0, split, end = 0, 10_000_000, 20_000_000
    net = {"trades_compact": trades(50, -1.0, 0) + trades(30, 1.0, split)}  # terrible development period, great OOS period (only 30 trades)
    a = oos_analysis(net, {"trades_compact": []}, t0, split, end, {"random_entry_mean_of_seeds": {"expectancy_r_mean": -0.2}})
    assert a["dev"]["n_trades"] == 50 and a["oos"]["n_trades"] == 30 and a["oos"]["expectancy_r"] == 1.0
    assert a["status"] == "no_edge" and "30" in a["summary"]  # 30 trades can never validate, however good they look
