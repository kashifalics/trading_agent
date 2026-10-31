import numpy as np

from app.candlestick.detectors import detect_candlestick_patterns
from app.feature_engineering.indicators import atr
from app.market_data.bars import Bars
from app.market_structure.bos import detect_structure_breaks
from app.market_structure.liquidity import detect_equal_levels, detect_liquidity_sweeps
from app.market_structure.swings import find_swings
from app.price_action.engine import analyze_price_action
from app.price_action.fvg import detect_fvg
from app.price_action.premium_discount import premium_discount
from app.price_action.supply_demand import detect_supply_demand


def ohlc(rows):
    a = np.array(rows, float)
    return Bars.from_arrays(a[:, 0], a[:, 1], a[:, 2], a[:, 3])


def from_closes(closes, pad=0.1):
    c = np.array(closes, float)
    return Bars.from_arrays(c, c + pad, c - pad, c)


def kinds(events, idx=None):
    return [e.kind for e in events if idx is None or e.idx == idx]


# ---------- candlesticks ----------
def test_bullish_and_bearish_engulfing():
    b = ohlc([(10, 10.2, 9.4, 9.5), (9.4, 10.6, 9.3, 10.5), (10.5, 10.6, 9.0, 9.1)])
    ev = detect_candlestick_patterns(b)
    assert any(e.kind == "bullish_engulfing" and e.idx == 1 for e in ev)
    bear = [e for e in ev if e.kind == "bearish_engulfing"]
    assert bear and bear[0].idx == 2 and bear[0].start_idx == 1


def test_hammer_requires_prior_decline_and_shooting_star_advance():
    down = [(20 - i + 0.5, 20 - i + 0.6, 20 - i - 0.6, 20 - i - 0.5 + 0.5 - 0.5) for i in range(7)]
    hammer = (14.0, 14.35, 12.8, 14.3)
    ev = detect_candlestick_patterns(ohlc(down + [hammer]))
    assert [e.idx for e in ev if e.kind == "hammer"] == [7]
    # same candle with no prior decline: not a hammer under default parameters
    flat = [(14, 14.5, 13.5, 14)] * 7
    assert not [e for e in detect_candlestick_patterns(ohlc(flat + [hammer])) if e.kind == "hammer"]
    up = [(10 + i, 10 + i + 0.6, 10 + i - 0.6, 10 + i + 0.5) for i in range(7)]
    star = (17.0, 18.6, 16.95, 16.7)
    ev = detect_candlestick_patterns(ohlc(up + [star]))
    assert [e.idx for e in ev if e.kind == "shooting_star"] == [7]


def test_doji_pin_inside_outside():
    b = ohlc([(10, 11, 9, 10.01), (10, 10.2, 8.0, 10.1), (10, 10.15, 9.0, 9.5), (9.4, 11, 8.5, 10.8)])
    ev = detect_candlestick_patterns(b)
    assert any(e.kind == "doji" and e.idx == 0 for e in ev)
    pin = [e for e in ev if e.kind == "pin_bar"]
    assert pin and pin[0].direction == "bullish"
    assert any(e.kind == "inside_bar" and e.idx == 2 for e in ev)
    outside = [e for e in ev if e.kind == "outside_bar"]
    assert outside and outside[0].idx == 3 and outside[0].direction == "bullish"


def test_morning_and_evening_star():
    m = ohlc([(20, 20.2, 14.8, 15), (14.5, 14.9, 14.2, 14.6), (14.8, 18.7, 14.7, 18.5)])
    ev = detect_candlestick_patterns(m)
    ms = [e for e in ev if e.kind == "morning_star"]
    assert ms and ms[0].start_idx == 0 and ms[0].direction == "bullish"
    e = ohlc([(15, 20.2, 14.8, 20), (20.5, 20.8, 20.1, 20.4), (20.2, 20.3, 16.3, 16.5)])
    assert any(x.kind == "evening_star" for x in detect_candlestick_patterns(e))


# ---------- market structure ----------
PATH = [10, 11, 12, 13, 14, 13, 12, 11, 10.5, 11.5, 12.5, 13.5, 15, 14, 13, 12, 11, 10, 9, 8, 9, 9.5, 10, 10.5, 11]


def test_swings_labels_and_confirmation_delay():
    sw = find_swings(from_closes(PATH), 3, 3)
    highs = [s for s in sw if s.kind == "high"]
    assert [s.idx for s in highs] == [4, 12] and [s.label for s in highs] == [None, "HH"]
    assert all(s.confirm_idx == s.idx + 3 for s in sw)
    lows = [s for s in sw if s.kind == "low"]
    assert [s.idx for s in lows] == [8, 19] and lows[1].label == "LL"


def test_bos_then_choch():
    b = from_closes(PATH)
    ev, trend = detect_structure_breaks(b, find_swings(b))
    assert [(e.kind, e.direction, e.idx) for e in ev] == [("BOS", "bullish", 12), ("CHoCH", "bearish", 17)]
    assert trend[12] == 1 and trend[17] == -1 and trend[5] == 0


def test_no_lookahead_in_structure_and_swings():
    rng = np.random.default_rng(7)
    c = 100 + np.cumsum(rng.normal(0, 1, 400))
    b = Bars.from_arrays(c, c + rng.uniform(0.1, 0.8, 400), c - rng.uniform(0.1, 0.8, 400), c)
    full_sw = find_swings(b)
    full_ev, full_trend = detect_structure_breaks(b, full_sw)
    for k in (60, 150, 299):
        part = b.upto(k + 1)
        sw = find_swings(part)
        ev, trend = detect_structure_breaks(part, sw)
        known = {(s.idx, s.kind, s.price) for s in full_sw if s.confirm_idx <= k}
        assert {(s.idx, s.kind, s.price) for s in sw if s.confirm_idx <= k} == known
        assert [(e.kind, e.idx) for e in ev] == [(e.kind, e.idx) for e in full_ev if e.idx <= k]
        assert (trend == full_trend[: k + 1]).all()


def test_equal_highs_and_liquidity_sweep():
    closes = [10, 11, 12, 13, 14, 13, 12, 11, 12, 13, 14, 13, 12, 11]
    c = np.array(closes + [13.0], float)
    h, l = c + 0.1, c - 0.1  # noqa: E741
    h[10] = 14.08
    h[14], l[14] = 14.6, 10.9  # wick above both highs, close back below
    b = Bars.from_arrays(c, h, l, c)
    sw = find_swings(b)
    eq = detect_equal_levels(b, sw, atr(b.h, b.l, b.c))
    assert [e.kind for e in eq] == ["equal_highs"] and abs(eq[0].price - 14.09) < 0.02
    sweeps = detect_liquidity_sweeps(b, sw)
    assert sweeps and all(s.direction == "bearish" and s.idx == 14 for s in sweeps)


# ---------- price action ----------
FLAT = [(10, 10.5, 9.7, 10.1)] * 20


def test_fvg_detection_and_fill_status():
    gap = [(10, 10.3, 9.8, 10.2), (10.2, 12.6, 10.1, 12.5), (12.5, 13, 11.0, 12.9)]
    b0 = ohlc(FLAT + gap)
    ev = detect_fvg(b0, atr(b0.h, b0.l, b0.c))
    g = [e for e in ev if e.direction == "bullish"]
    assert g and (g[0].low, g[0].high, g[0].status, g[0].idx) == (10.3, 11.0, "active", 22)
    b1 = ohlc(FLAT + gap + [(12.9, 13, 10.8, 11.2)])
    assert [e.status for e in detect_fvg(b1, atr(b1.h, b1.l, b1.c)) if e.idx == 22] == ["partially_filled"]
    b2 = ohlc(FLAT + gap + [(12.9, 13, 10.8, 11.2), (11.2, 11.3, 10.2, 10.4)])
    assert [e.status for e in detect_fvg(b2, atr(b2.h, b2.l, b2.c)) if e.idx == 22] == ["filled"]


def test_supply_demand_base_impulse():
    base = [(100, 100.3, 99.9, 100.1), (100.1, 100.4, 99.95, 100.0)]
    imp = [(100, 103.1, 99.95, 103)]
    flat = [(100, 100.5, 99.5, 100)] * 18
    b = ohlc(flat + base + imp)
    z = detect_supply_demand(b, atr(b.h, b.l, b.c))
    assert len(z) == 1 and z[0].kind == "demand_zone"
    assert (z[0].low, z[0].high, z[0].start_idx, z[0].idx) == (99.9, 100.4, 18, 20)


OB_ROWS = (
    [(100, 100.5, 99.5, 100)] * 16
    + [(100, 103.3, 99.9, 103), (103, 105.3, 102.9, 105), (105, 105.0, 102.8, 103), (103, 103.1, 100.8, 101),
       (101, 101.1, 98.9, 99), (99, 99.1, 96.2, 96.5), (96.5, 97.3, 96.4, 97.0), (97, 98.3, 96.9, 98),
       (98, 99.3, 97.9, 99), (99, 106.5, 98.9, 106)]
)


def test_order_block_lifecycle_and_breaker():
    def run(extra):
        b = ohlc(OB_ROWS + extra)
        return analyze_price_action(b)

    fresh = run([(106, 107.2, 105.5, 107)])
    ob = [o for o in fresh.order_blocks if o.direction == "bullish"]
    assert ob and (ob[0].start_idx, ob[0].low, ob[0].high, ob[0].idx) == (21, 96.2, 99.1, 25)
    assert ob[0].status == "fresh"
    tested = run([(106, 107.2, 105.5, 107), (107, 107, 98.5, 99)])
    assert [o.status for o in tested.order_blocks if o.direction == "bullish"] == ["tested"]
    broken = run([(106, 107.2, 105.5, 107), (107, 107, 98.5, 99), (99, 99, 94.8, 95)])
    assert [o.status for o in broken.order_blocks if o.direction == "bullish"] == ["invalidated"]
    br = [x for x in broken.breakers if x.direction == "bearish"]
    assert br and (br[0].low, br[0].high, br[0].idx) == (96.2, 99.1, 28)


def test_premium_discount():
    b = from_closes(PATH)
    pd_ = premium_discount(b, find_swings(b))
    assert pd_ is not None and pd_.status == "discount"
    assert abs(pd_.meta["position"] - (11 - 7.9) / (15.1 - 7.9)) < 1e-9
    assert pd_.price == (15.1 + 7.9) / 2


def test_events_carry_time_and_level_references():
    b = ohlc(OB_ROWS)
    res = analyze_price_action(b)
    for e in res.all_events():
        d = e.to_dict()
        assert d["time"] and (e.price is not None or e.low is not None) and e.evidence
