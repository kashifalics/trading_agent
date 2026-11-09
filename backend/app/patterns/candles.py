"""Family A: the 48 candlestick patterns of the brief, vectorized. Patterns are context-free here; their location, structure,
regime and session are studied as conditions afterwards (a candlestick alone is never a signal)."""
import warnings

import numpy as np

from app.patterns.registry import Hits, spec

S = "body >= 5% of range"


def _reg() -> None:
    A = "A"
    for d, nm in ((1, "Bullish"), (-1, "Bearish")):
        k = "bull" if d > 0 else "bear"
        spec(id=f"marubozu_{k}", family=A, name=f"{nm} Marubozu", direction=nm.lower(),
             definition=f"{'bullish' if d > 0 else 'bearish'} body >= 90% of range and range >= 1 ATR")
        spec(id=f"pin_bar_{k}", family=A, name=f"{nm} Pin Bar", direction=nm.lower(),
             definition=f"{'lower' if d > 0 else 'upper'} wick >= 66% of range, body <= 33% of range, opposite wick <= 20% of range")
        spec(id=f"rejection_{k}", family=A, name=f"{nm} Rejection Candle", direction=nm.lower(),
             definition=f"{'lower' if d > 0 else 'upper'} wick >= 50% of range, close in the {'top' if d > 0 else 'bottom'} 40% of the range, "
                        f"and the candle made a new {'low' if d > 0 else 'high'} versus the previous 5 candles")
        spec(id=f"engulfing_{k}", family=A, name=f"{nm} Engulfing", direction=nm.lower(),
             definition=f"{'bearish' if d > 0 else 'bullish'} candle then a {'bullish' if d > 0 else 'bearish'} candle whose body covers "
                        "the previous body and is larger")
        spec(id=f"harami_{k}", family=A, name=f"{nm} Harami", direction=nm.lower(),
             definition=f"long {'bearish' if d > 0 else 'bullish'} candle (body >= 60% of range) then a smaller "
                        f"{'bullish' if d > 0 else 'bearish'} body inside its body")
        spec(id=f"tweezer_{'bottom' if d > 0 else 'top'}", family=A, name=f"Tweezer {'Bottom' if d > 0 else 'Top'}", direction=nm.lower(),
             definition=f"two candles with {'lows' if d > 0 else 'highs'} within 0.05 ATR, the first {'bearish' if d > 0 else 'bullish'}, "
                        f"the second {'bullish' if d > 0 else 'bearish'}, after a prior {'decline' if d > 0 else 'advance'}")
        spec(id=f"outside_bar_{k}", family=A, name=f"{nm} Outside Bar", direction=nm.lower(),
             definition=f"high above and low below the previous candle, {'bullish' if d > 0 else 'bearish'} close")
        spec(id=f"inside_bar_{k}", family=A, name=f"{nm} Inside Bar", direction=nm.lower(),
             definition=f"high below and low above the previous candle, {'bullish' if d > 0 else 'bearish'} body",
             invalidation=f"beyond the mother candle's {'low' if d > 0 else 'high'}")
        star = "morning" if d > 0 else "evening"
        spec(id=f"{star}_star", family=A, name=f"{star.title()} Star", direction=nm.lower(),
             definition=f"long {'bearish' if d > 0 else 'bullish'} candle (body >= 50% of range), a small body (<= 30% of the first body), "
                        f"then a {'bullish' if d > 0 else 'bearish'} candle closing beyond the first body's midpoint")
        spec(id=f"{star}_doji_star", family=A, name=f"{star.title()} Doji Star", direction=nm.lower(),
             definition=f"as the {star} star, with a doji (body <= 10% of range) as the middle candle")
        spec(id="three_white_soldiers" if d > 0 else "three_black_crows", family=A,
             name="Three White Soldiers" if d > 0 else "Three Black Crows", direction=nm.lower(),
             definition=f"three {'bullish' if d > 0 else 'bearish'} candles, each closing {'higher' if d > 0 else 'lower'}, each opening "
                        "inside the previous body, bodies >= 50% of range, adverse wick <= 30% of range")
        spec(id=f"three_inside_{'up' if d > 0 else 'down'}", family=A, name=f"Three Inside {'Up' if d > 0 else 'Down'}", direction=nm.lower(),
             definition=f"a {nm.lower()} harami followed by a candle closing beyond the first candle's open")
        spec(id=f"three_outside_{'up' if d > 0 else 'down'}", family=A, name=f"Three Outside {'Up' if d > 0 else 'Down'}", direction=nm.lower(),
             definition=f"a {nm.lower()} engulfing followed by a candle closing beyond the engulfing close")
        spec(id="rising_three_methods" if d > 0 else "falling_three_methods", family=A,
             name="Rising Three Methods" if d > 0 else "Falling Three Methods", direction=nm.lower(),
             definition=f"long {'bullish' if d > 0 else 'bearish'} candle, three small candles (body <= 50% of the first) inside its range, "
                        f"then a {'bullish' if d > 0 else 'bearish'} candle closing beyond the first close")
        spec(id=f"strong_{k}_sequence", family=A, name=f"Consecutive Strong {nm} Candles", direction=nm.lower(),
             definition=f"first candle completing three consecutive {'bullish' if d > 0 else 'bearish'} candles with body >= 60% of range "
                        "and range >= 0.8 ATR")
    for pid, nm, dfn in (
        ("hammer", "Hammer", "lower wick >= 2x body, upper wick <= 15% of range, " + S + ", after a prior decline"),
        ("inverted_hammer", "Inverted Hammer", "upper wick >= 2x body, lower wick <= 15% of range, " + S + ", after a prior decline"),
        ("dragonfly_doji", "Dragonfly Doji", "body <= 10% of range, upper wick <= 10%, lower wick >= 60% of range"),
        ("piercing", "Piercing Pattern", "long bearish candle then a bullish candle opening at or below its close and closing above its "
                                         "body midpoint but below its open"),
    ):
        spec(id=pid, family=A, name=nm, direction="bullish", definition=dfn)
    for pid, nm, dfn in (
        ("hanging_man", "Hanging Man", "hammer shape (lower wick >= 2x body, upper <= 15% of range) after a prior advance"),
        ("shooting_star", "Shooting Star", "upper wick >= 2x body, lower wick <= 15% of range, " + S + ", after a prior advance"),
        ("gravestone_doji", "Gravestone Doji", "body <= 10% of range, lower wick <= 10%, upper wick >= 60% of range"),
        ("dark_cloud_cover", "Dark Cloud Cover", "long bullish candle then a bearish candle opening at or above its close and closing below its "
                                                 "body midpoint but above its open"),
    ):
        spec(id=pid, family=A, name=nm, direction="bearish", definition=dfn)
    for pid, nm, dfn in (
        ("long_legged_doji", "Long-Legged Doji", "body <= 10% of range, both wicks >= 30% of range, range >= 1 ATR"),
        ("doji", "Standard Doji", "body <= 10% of range and not a dragonfly, gravestone or long-legged doji"),
        ("narrow_range", "Narrow-Range Candle (NR7)", "smallest range of the last 7 candles"),
        ("compression", "Multi-Candle Compression", "first candle completing 4 candles each with range < 0.6 ATR and a combined range "
                                                    "<= 1.2 ATR"),
    ):
        spec(id=pid, family=A, name=nm, direction="neutral", definition=dfn, invalidation="none (no direction; not traded alone)")
    for pid, nm, dfn in (
        ("displacement", "Strong Displacement Candle", "body >= 70% of range and range >= 2 ATR; direction of the body"),
        ("wide_range", "Wide-Range Candle", "range >= 1.8 ATR with the close in the top third (bullish) or bottom third (bearish)"),
        ("kicker", "Kicker Pattern", "long candle (body >= 60% of range) followed by a long opposite candle that opens at or beyond the "
                                     "first candle's open"),
        ("three_bar_reversal", "Three-Bar Reversal", "middle candle makes the lowest low (highest high) of three and the third candle "
                                                     "closes above its high (below its low)"),
        ("three_bar_continuation", "Three-Bar Continuation", "a directional candle, an inside candle, then a close beyond the first "
                                                             "candle's extreme in the same direction"),
        ("exhaustion_sequence", "Exhaustion Candle Sequence", "four consecutive higher (lower) closes followed by a candle with range >= "
                                                              "1.8 ATR closing in its bottom (top) third; direction is the reversal"),
    ):
        spec(id=pid, family=A, name=nm, direction="both", definition=dfn)


_reg()


def _sh(x: np.ndarray, k: int) -> np.ndarray:
    out = np.full_like(x, np.nan, dtype=float)
    if k < len(x):
        out[k:] = x[:len(x) - k]
    return out


def _shb(m: np.ndarray, k: int) -> np.ndarray:
    """Boolean shift: m[i - k], False before the start."""
    out = np.zeros(len(m), dtype=bool)
    if k < len(m):
        out[k:] = m[:len(m) - k]
    return out


def _onset(m: np.ndarray) -> np.ndarray:
    return m & ~np.r_[False, m[:-1]]


def _roll_min(x: np.ndarray, w: int) -> np.ndarray:
    """Minimum of x[i-w+1 .. i] (NaN at the start)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmin(np.stack([_sh(x, k) for k in range(w)]), axis=0)


def _roll_max(x: np.ndarray, w: int) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmax(np.stack([_sh(x, k) for k in range(w)]), axis=0)


def detect(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, atr: np.ndarray) -> Hits:  # noqa: E741
    H = Hits()
    with np.errstate(invalid="ignore", divide="ignore"):
        B, R = np.abs(c - o), h - l
        U, W = h - np.maximum(o, c), np.minimum(o, c) - l
        R = np.where(R > 0, R, np.nan)
        bull, bear = c > o, c < o
        dn = _sh(c, 1) < _sh(c, 6)
        up = _sh(c, 1) > _sh(c, 6)
        p = {k: _sh(x, 1) for k, x in (("o", o), ("h", h), ("l", l), ("c", c), ("B", B), ("R", R))}
        pbull, pbear = p["c"] > p["o"], p["c"] < p["o"]
        lo2, hi2 = np.fmin(l, p["l"]), np.fmax(h, p["h"])
        lo3, hi3 = _roll_min(l, 3), _roll_max(h, 3)
        a = atr

        H.add("marubozu_bull", bull & (B >= 0.9 * R) & (R >= a), 1, l)
        H.add("marubozu_bear", bear & (B >= 0.9 * R) & (R >= a), -1, h)
        ham = (B >= 0.05 * R) & (W >= 2 * B) & (U <= 0.15 * R)
        inv = (B >= 0.05 * R) & (U >= 2 * B) & (W <= 0.15 * R)
        H.add("hammer", ham & dn, 1, l)
        H.add("hanging_man", ham & up, -1, h)
        H.add("inverted_hammer", inv & dn, 1, l)
        H.add("shooting_star", inv & up, -1, h)
        H.add("pin_bar_bull", (B <= 0.33 * R) & (W >= 0.66 * R) & (U <= 0.2 * R), 1, l)
        H.add("pin_bar_bear", (B <= 0.33 * R) & (U >= 0.66 * R) & (W <= 0.2 * R), -1, h)
        doji = B <= 0.1 * R
        dfly = doji & (U <= 0.1 * R) & (W >= 0.6 * R)
        grav = doji & (W <= 0.1 * R) & (U >= 0.6 * R)
        ll = doji & (U >= 0.3 * R) & (W >= 0.3 * R) & (R >= a)
        H.add("dragonfly_doji", dfly, 1, l)
        H.add("gravestone_doji", grav, -1, h)
        H.add("long_legged_doji", ll, 0, np.nan)
        H.add("doji", doji & ~dfly & ~grav & ~ll, 0, np.nan)
        prev5_lo, prev5_hi = _roll_min(_sh(l, 1), 5), _roll_max(_sh(h, 1), 5)
        H.add("rejection_bull", (W >= 0.5 * R) & (c >= l + 0.6 * R) & (l < prev5_lo), 1, l)
        H.add("rejection_bear", (U >= 0.5 * R) & (c <= h - 0.6 * R) & (h > prev5_hi), -1, h)
        disp = (B >= 0.7 * R) & (R >= 2 * a)
        H.add("displacement", disp & bull, 1, l)
        H.add("displacement", disp & bear, -1, h)
        wide = R >= 1.8 * a
        H.add("wide_range", wide & (c >= h - R / 3), 1, l)
        H.add("wide_range", wide & (c <= l + R / 3), -1, h)
        H.add("narrow_range", R <= _roll_min(R, 7), 0, np.nan)

        H.add("engulfing_bull", pbear & bull & (o <= p["c"]) & (c >= p["o"]) & (B > p["B"]), 1, lo2)
        H.add("engulfing_bear", pbull & bear & (o >= p["c"]) & (c <= p["o"]) & (B > p["B"]), -1, hi2)
        long_prev = p["B"] >= 0.6 * p["R"]
        hb = pbear & long_prev & bull & (np.maximum(o, c) <= p["o"]) & (np.minimum(o, c) >= p["c"]) & (B < p["B"])
        hs = pbull & long_prev & bear & (np.maximum(o, c) <= p["c"]) & (np.minimum(o, c) >= p["o"]) & (B < p["B"])
        H.add("harami_bull", hb, 1, lo2)
        H.add("harami_bear", hs, -1, hi2)
        mid_prev = (p["o"] + p["c"]) / 2
        H.add("piercing", pbear & long_prev & bull & (o <= p["c"]) & (c > mid_prev) & (c < p["o"]), 1, lo2)
        H.add("dark_cloud_cover", pbull & long_prev & bear & (o >= p["c"]) & (c < mid_prev) & (c > p["o"]), -1, hi2)
        dn1, up1 = _sh(c, 2) < _sh(c, 7), _sh(c, 2) > _sh(c, 7)
        H.add("tweezer_bottom", (np.abs(l - p["l"]) <= 0.05 * a) & pbear & bull & dn1, 1, lo2)
        H.add("tweezer_top", (np.abs(h - p["h"]) <= 0.05 * a) & pbull & bear & up1, -1, hi2)
        outside = (h > p["h"]) & (l < p["l"])
        inside = (h < p["h"]) & (l > p["l"])
        H.add("outside_bar_bull", outside & bull, 1, l)
        H.add("outside_bar_bear", outside & bear, -1, h)
        H.add("inside_bar_bull", inside & bull, 1, p["l"])
        H.add("inside_bar_bear", inside & bear, -1, p["h"])
        H.add("kicker", pbear & long_prev & bull & (B >= 0.6 * R) & (o >= p["o"]), 1, lo2)
        H.add("kicker", pbull & long_prev & bear & (B >= 0.6 * R) & (o <= p["o"]), -1, hi2)

        q = {k: _sh(x, 2) for k, x in (("o", o), ("h", h), ("l", l), ("c", c), ("B", B), ("R", R))}
        qbull, qbear = q["c"] > q["o"], q["c"] < q["o"]
        long_q = q["B"] >= 0.5 * q["R"]
        small_mid = p["B"] <= 0.3 * q["B"]
        doji_mid = p["B"] <= 0.1 * p["R"]
        mid_q = (q["o"] + q["c"]) / 2
        ms = qbear & long_q & bull & (c > mid_q)
        es = qbull & long_q & bear & (c < mid_q)
        H.add("morning_star", ms & small_mid, 1, lo3)
        H.add("evening_star", es & small_mid, -1, hi3)
        H.add("morning_doji_star", ms & doji_mid, 1, lo3)
        H.add("evening_doji_star", es & doji_mid, -1, hi3)
        good_b = (B >= 0.5 * R) & (p["B"] >= 0.5 * p["R"]) & (q["B"] >= 0.5 * q["R"])
        tws = (bull & pbull & qbull & (c > p["c"]) & (p["c"] > q["c"]) & (o >= p["o"]) & (o <= p["c"]) & (p["o"] >= q["o"]) & (p["o"] <= q["c"])
               & good_b & (U <= 0.3 * R) & (_sh(U, 1) <= 0.3 * p["R"]))
        tbc = (bear & pbear & qbear & (c < p["c"]) & (p["c"] < q["c"]) & (o <= p["o"]) & (o >= p["c"]) & (p["o"] <= q["o"]) & (p["o"] >= q["c"])
               & good_b & (W <= 0.3 * R) & (_sh(W, 1) <= 0.3 * p["R"]))
        H.add("three_white_soldiers", tws, 1, lo3)
        H.add("three_black_crows", tbc, -1, hi3)
        H.add("three_inside_up", _shb(hb, 1) & (c > q["o"]), 1, lo3)
        H.add("three_inside_down", _shb(hs, 1) & (c < q["o"]), -1, hi3)
        eb = pbear & bull & (o <= p["c"]) & (c >= p["o"]) & (B > p["B"])
        es2 = pbull & bear & (o >= p["c"]) & (c <= p["o"]) & (B > p["B"])
        H.add("three_outside_up", _shb(eb, 1) & bull & (c > p["c"]), 1, lo3)
        H.add("three_outside_down", _shb(es2, 1) & bear & (c < p["c"]), -1, hi3)
        f = {k: _sh(x, 4) for k, x in (("o", o), ("h", h), ("l", l), ("c", c), ("B", B), ("R", R))}
        inside3 = np.ones(len(c), dtype=bool)
        for k in (1, 2, 3):
            inside3 &= (_sh(h, k) <= f["h"]) & (_sh(l, k) >= f["l"]) & (_sh(B, k) <= 0.5 * f["B"])
        lo5, hi5 = _roll_min(l, 5), _roll_max(h, 5)
        H.add("rising_three_methods", (f["c"] > f["o"]) & (f["B"] >= 0.6 * f["R"]) & inside3 & bull & (c > f["c"]), 1, lo5)
        H.add("falling_three_methods", (f["c"] < f["o"]) & (f["B"] >= 0.6 * f["R"]) & inside3 & bear & (c < f["c"]), -1, hi5)
        H.add("three_bar_reversal", (p["l"] < q["l"]) & (p["l"] < l) & (c > p["h"]), 1, lo3)
        H.add("three_bar_reversal", (p["h"] > q["h"]) & (p["h"] > h) & (c < p["l"]), -1, hi3)
        p_inside = (p["h"] <= q["h"]) & (p["l"] >= q["l"])
        H.add("three_bar_continuation", qbull & p_inside & (c > q["h"]), 1, lo3)
        H.add("three_bar_continuation", qbear & p_inside & (c < q["l"]), -1, hi3)
        small = R < 0.6 * a
        comp = small & _sh(small.astype(float), 1).astype(bool) & _sh(small.astype(float), 2).astype(bool) & \
            _sh(small.astype(float), 3).astype(bool) & ((_roll_max(h, 4) - _roll_min(l, 4)) <= 1.2 * a)
        H.add("compression", _onset(np.nan_to_num(comp).astype(bool)), 0, np.nan)
        strong = (B >= 0.6 * R) & (R >= 0.8 * a)
        sb = strong & bull
        ss = strong & bear
        seq_b = sb & _shb(sb, 1) & _shb(sb, 2)
        seq_s = ss & _shb(ss, 1) & _shb(ss, 2)
        H.add("strong_bull_sequence", _onset(seq_b), 1, lo3)
        H.add("strong_bear_sequence", _onset(seq_s), -1, hi3)
        upc = c > _sh(c, 1)
        dnc = c < _sh(c, 1)
        run_up = _shb(upc, 1) & _shb(upc, 2) & _shb(upc, 3) & _shb(upc, 4)
        run_dn = _shb(dnc, 1) & _shb(dnc, 2) & _shb(dnc, 3) & _shb(dnc, 4)
        H.add("exhaustion_sequence", run_up & wide & (c <= l + R / 3), -1, h)
        H.add("exhaustion_sequence", run_dn & wide & (c >= h - R / 3), 1, l)
    return H


def detect_ctx(ctx) -> Hits:
    return detect(ctx.o, ctx.h, ctx.l, ctx.c, ctx.atr)
