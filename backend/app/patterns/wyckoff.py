"""Family H: Wyckoff-style market events.

Every event here is a HYPOTHESIS read from observable price and tick-volume behaviour. None of them is evidence that institutions are
accumulating or distributing; the Wyckoff names only label the shape.

Two causal range definitions are used (candles up to the current one only, swings only once confirmed):

* Band range. At candle i the last 30 candles (i-29..i) have max(high) - min(low) <= 3 x ATR(i): the range is confirmed at i, its
  bounds R_hi / R_lo are frozen from that window, and it stays active until the first close outside [R_lo, R_hi]. A new range can
  only begin after that close (its 30-candle window starts after it). Springs, upthrusts, SOS / SOW, LPS / LPSY and the four range
  states are measured on it.
* Climax range. A selling (buying) climax low (high) and the automatic rally (reaction) swing that follows it, whose price is the
  creek (ice). Secondary tests, the creek breakout and the ice breakdown are measured on it.

Notation: ATR = 14-candle Wilder ATR; a candle's own size is judged against the ATR of the PREVIOUS candle so that it does not
inflate its own yardstick. Volume = Dukascopy tick volume (ctx.v) compared with the 200 candles BEFORE the candle (percentiles with
linear interpolation); with missing or constant volume no climax or preliminary support / supply can qualify. Down trend at candle i:
close below the close 50 candles earlier; up trend mirrored. Swings = the standard 3 left / 3 right swings (ctx.swings).
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.patterns.ctx import ChunkCtx
from app.patterns.registry import Hits, Points, spec

RANGE_N, RANGE_K = 30, 3.0  # band range: candles, width in ATR
TREND_LB, TREND_ATR = 50, 3.0  # prior trend of a range: close vs 50 candles back, at least 3 ATR
VOL_LB, CLIMAX_Q, PS_Q = 200, 90, 80  # volume window and percentiles
CLIMAX_ATR, BREAK_ATR, ST_ATR = 2.0, 1.5, 0.5  # climax candle range, SOS/SOW/creek/ice candle range, secondary-test reach
AR_WINDOW, CLIMAX_LIFE, CLIMAX_CTX = 30, 300, 30  # candles: AR after climax, climax range life, climax before a range window
LPS_WINDOW, PS_GAP = 50, 20  # candles: LPS swing after SOS, spacing of preliminary support / supply

WY = "H"
HYP = "a hypothesis read from price and volume, not evidence of institutional activity"
BAND = ("a band range (the last 30 candles' highest high minus lowest low <= 3 ATR, confirmed at the 30th candle, bounds frozen, "
        "active until the first close outside them)")
STATE = (f"{BAND} confirmed after a prior {{trend}} trend (close of the candle before the window at least 3 ATR {{side}} the close "
         f"50 candles earlier) {{climax}} within the 30 candles before the window or inside it; event at the confirming candle "
         f"(range state, not traded; {HYP})")
SC_DEF = ("a candle with high - low >= 2 ATR on volume above the 90th percentile of the previous 200 candles, in a {trend} trend "
          "(close {side} the close 50 candles back), making the {ext} of the last 50 candles ({what}; " + HYP + ")")

spec(id="wyckoff_accumulation", family=WY, name="Accumulation (range state)", direction="neutral",
     definition=STATE.format(trend="down", side="below", climax="with a selling_climax"), invalidation="none (range state, not traded)")
spec(id="wyckoff_distribution", family=WY, name="Distribution (range state)", direction="neutral",
     definition=STATE.format(trend="up", side="above", climax="with a buying_climax"), invalidation="none (range state, not traded)")
spec(id="wyckoff_reaccumulation", family=WY, name="Trading Range Reaccumulation (range state)", direction="neutral",
     definition=STATE.format(trend="up", side="above", climax="with NO buying_climax (a pause within an advance)"),
     invalidation="none (range state, not traded)")
spec(id="wyckoff_redistribution", family=WY, name="Trading Range Redistribution (range state)", direction="neutral",
     definition=STATE.format(trend="down", side="below", climax="with NO selling_climax (a pause within a decline)"),
     invalidation="none (range state, not traded)")
spec(id="spring", family=WY, name="Spring", direction="bullish",
     definition=f"while {BAND} is active, the first candle that trades below the range low and closes back inside the range "
                f"(R_lo <= close <= R_hi); at most one per range; a candle that also trades above the range high is skipped ({HYP})",
     invalidation="the spring candle's low")
spec(id="upthrust", family=WY, name="Upthrust", direction="bearish",
     definition=f"while {BAND} is active, the first candle that trades above the range high and closes back inside the range "
                f"(R_lo <= close <= R_hi); at most one per range; a candle that also trades below the range low is skipped ({HYP})",
     invalidation="the upthrust candle's high")
spec(id="sign_of_strength", family=WY, name="Sign of Strength (SOS)", direction="bullish",
     definition=f"the close that ends {BAND} upward (first close above R_hi), when that candle's high - low >= 1.5 ATR ({HYP})",
     confirmation="the breakout close", invalidation="the breakout candle's low")
spec(id="sign_of_weakness", family=WY, name="Sign of Weakness (SOW)", direction="bearish",
     definition=f"the close that ends {BAND} downward (first close below R_lo), when that candle's high - low >= 1.5 ATR ({HYP})",
     confirmation="the breakdown close", invalidation="the breakdown candle's high")
spec(id="last_point_of_support", family=WY, name="Last Point of Support (LPS)", direction="bullish",
     definition="after a sign_of_strength, the first swing low (3/3) after the SOS candle: it is an LPS when it lies within 50 "
                "candles of the SOS, above the broken range high, and no close fell back below the range high in between; event at "
                f"the swing's confirmation (3 candles after it) ({HYP})",
     confirmation="the candle that confirms the swing low", invalidation="the swing low")
spec(id="last_point_of_supply", family=WY, name="Last Point of Supply (LPSY)", direction="bearish",
     definition="after a sign_of_weakness, the first swing high (3/3) after the SOW candle: it is an LPSY when it lies within 50 "
                "candles of the SOW, below the broken range low, and no close rose back above the range low in between; event at "
                f"the swing's confirmation (3 candles after it) ({HYP})",
     confirmation="the candle that confirms the swing high", invalidation="the swing high")
spec(id="preliminary_support", family=WY, name="Preliminary Support (PS)", direction="bullish",
     definition="a candle in a down trend (close below the close 50 candles back) that makes the lowest low of the last 50 candles "
                "on volume above the 80th percentile of the previous 200 candles and closes in the upper half of its range, is not a "
                f"selling_climax, and comes at least 20 candles after the previous preliminary support (first support in a decline; {HYP})",
     invalidation="the candle's low")
spec(id="preliminary_supply", family=WY, name="Preliminary Supply (PSY)", direction="bearish",
     definition="a candle in an up trend (close above the close 50 candles back) that makes the highest high of the last 50 candles "
                "on volume above the 80th percentile of the previous 200 candles and closes in the lower half of its range, is not a "
                f"buying_climax, and comes at least 20 candles after the previous preliminary supply (first supply in an advance; {HYP})",
     invalidation="the candle's high")
spec(id="selling_climax", family=WY, name="Selling Climax (SC)", direction="bullish",
     definition=SC_DEF.format(trend="down", side="below", ext="lowest low", what="end-of-decline stopping action"),
     invalidation="the climax candle's low")
spec(id="buying_climax", family=WY, name="Buying Climax (BC)", direction="bearish",
     definition=SC_DEF.format(trend="up", side="above", ext="highest high", what="end-of-advance stopping action"),
     invalidation="the climax candle's high")
spec(id="automatic_rally", family=WY, name="Automatic Rally (AR)", direction="neutral",
     definition="the first swing high (3/3) after a selling_climax: it is the AR when it peaks within 30 candles of the climax and no "
                "close fell below the climax low before its confirmation; event at its confirmation; its high is the creek (top of "
                "the climax range); a newer selling climax restarts the sequence",
     confirmation="the candle that confirms the swing high", invalidation="none (structural marker, not traded)")
spec(id="automatic_reaction", family=WY, name="Automatic Reaction (AR)", direction="neutral",
     definition="the first swing low (3/3) after a buying_climax: it is the automatic reaction when it bottoms within 30 candles of "
                "the climax and no close rose above the climax high before its confirmation; event at its confirmation; its low is "
                "the ice (bottom of the climax range); a newer buying climax restarts the sequence",
     confirmation="the candle that confirms the swing low", invalidation="none (structural marker, not traded)")
spec(id="secondary_test", family=WY, name="Secondary Test (ST)", direction="both",
     definition="after an automatic_rally is confirmed, the first candle whose low comes within 0.5 ATR of (or below) the "
                "selling-climax low and that closes above that low on lower volume than the climax candle (bullish); mirrored after "
                "a buying_climax and automatic_reaction (high within 0.5 ATR of the climax high, close below it: bearish); at most one "
                f"per climax, before the creek / ice is crossed and within 300 candles of the climax ({HYP})",
     invalidation="the lower of the test candle's low and the climax low (bullish) / the higher of the highs (bearish)")
spec(id="creek_breakout", family=WY, name="Creek Breakout (jump across the creek)", direction="bullish",
     definition="after a selling_climax and its automatic_rally (the creek = the AR high), the first close above the creek, within "
                "300 candles of the climax and with no close below the climax low before it, when that candle's high - low >= 1.5 "
                f"ATR; the first close above the creek ends the climax range either way ({HYP})",
     confirmation="the close above the creek", invalidation="the breakout candle's low")
spec(id="ice_breakdown", family=WY, name="Ice Breakdown (fall through the ice)", direction="bearish",
     definition="after a buying_climax and its automatic_reaction (the ice = the reaction low), the first close below the ice, within "
                "300 candles of the climax and with no close above the climax high before it, when that candle's high - low >= 1.5 "
                f"ATR; the first close below the ice ends the climax range either way ({HYP})",
     confirmation="the close below the ice", invalidation="the breakdown candle's high")


def _roll(x: np.ndarray, w: int, fn) -> np.ndarray:
    """fn over the window of the last w values ending at each index (NaN before w values exist)."""
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        out[w - 1:] = fn(sliding_window_view(x, w), axis=1)
    return out


def _by_conf(swings, kind: str, sign: float = 1.0) -> dict[int, list[tuple[int, float]]]:
    """{confirm_idx: [(swing idx, sign * price)]} for one swing kind."""
    out: dict[int, list[tuple[int, float]]] = {}
    for s in swings:
        if s.kind == kind:
            out.setdefault(s.confirm_idx, []).append((s.idx, sign * float(s.price)))
    return out


def _climax(P: Points, d: int, sc: np.ndarray, h, l, c, v, atr_prev, pivots: dict, ar_id: str, brk_id: str) -> None:  # noqa: E741
    """Selling-climax sequence (d = +1): SC -> automatic rally (creek) -> secondary test -> creek breakout. The buying-climax sequence
    is the same logic on negated prices (d = -1: h, l, c replaced by -l, -h, -c), so 'low' always means the climax extreme."""
    seq = None  # [climax idx, climax extreme, climax volume, creek or None, tested]
    for i in range(len(c)):
        if sc[i]:
            seq = [i, l[i], v[i], None, False]  # a newer climax restarts the sequence
            continue
        if seq is None:
            continue
        k, ext, vk, creek, tested = seq
        if c[i] < ext or i - k > CLIMAX_LIFE:
            seq = None  # climax extreme lost (or range too old)
            continue
        if creek is None:
            for s_idx, price in pivots.get(i, ()):
                if s_idx > k:  # the first swing after the climax decides
                    if s_idx - k <= AR_WINDOW:
                        seq[3] = price
                        P.put(ar_id, i, 0, np.nan)
                    else:
                        seq = None
                    break
            continue
        if c[i] > creek:
            if h[i] - l[i] >= BREAK_ATR * atr_prev[i]:
                P.put(brk_id, i, d, d * l[i])
            seq = None
            continue
        if not tested and l[i] <= ext + ST_ATR * atr_prev[i] and c[i] > ext and v[i] < vk:
            P.put("secondary_test", i, d, d * min(l[i], ext))
            seq[4] = True


def _band_ranges(P: Points, ctx: ChunkCtx, atr_prev: np.ndarray, sc: np.ndarray, bc: np.ndarray) -> None:
    n, h, l, c, atr = ctx.n, ctx.h, ctx.l, ctx.c, ctx.atr  # noqa: E741
    hmax, lmin = _roll(h, RANGE_N, np.max), _roll(l, RANGE_N, np.min)
    with np.errstate(invalid="ignore"):
        fits = (hmax - lmin) <= RANGE_K * atr
    lows, highs = _by_conf(ctx.swings, "low"), _by_conf(ctx.swings, "high")
    active = sprung = thrust = False
    r_hi = r_lo = np.nan
    first_ok = RANGE_N - 1  # first candle whose window may hold a new range
    lps = lpsy = None  # pending (breakout candle, broken level)
    for i in range(n):
        if lps is not None and i > lps[0]:
            k, lvl = lps
            if c[i] < lvl:
                lps = None
            else:
                for s_idx, price in lows.get(i, ()):
                    if s_idx > k:
                        if s_idx - k <= LPS_WINDOW and price > lvl:
                            P.put("last_point_of_support", i, 1, price)
                        lps = None
                        break
        if lpsy is not None and i > lpsy[0]:
            k, lvl = lpsy
            if c[i] > lvl:
                lpsy = None
            else:
                for s_idx, price in highs.get(i, ()):
                    if s_idx > k:
                        if s_idx - k <= LPS_WINDOW and price < lvl:
                            P.put("last_point_of_supply", i, -1, price)
                        lpsy = None
                        break
        if active:
            if c[i] > r_hi or c[i] < r_lo:
                if h[i] - l[i] >= BREAK_ATR * atr_prev[i]:
                    if c[i] > r_hi:
                        P.put("sign_of_strength", i, 1, l[i])
                        lps = (i, r_hi)
                    else:
                        P.put("sign_of_weakness", i, -1, h[i])
                        lpsy = (i, r_lo)
                active = False
                first_ok = i + RANGE_N
            else:
                above, below = h[i] > r_hi, l[i] < r_lo
                if below and not above and not sprung:
                    P.put("spring", i, 1, l[i])
                    sprung = True
                if above and not below and not thrust:
                    P.put("upthrust", i, -1, h[i])
                    thrust = True
        elif i >= first_ok and fits[i]:
            active, sprung, thrust = True, False, False
            r_hi, r_lo = hmax[i], lmin[i]
            start = i - RANGE_N + 1
            pre = start - 1  # the candle before the window
            if pre - TREND_LB < 0:
                continue
            move, a = c[pre] - c[pre - TREND_LB], atr[pre]
            ctx_lo = max(0, start - CLIMAX_CTX)
            if move <= -TREND_ATR * a:
                P.put("wyckoff_accumulation" if sc[ctx_lo:i + 1].any() else "wyckoff_redistribution", i, 0, np.nan)
            elif move >= TREND_ATR * a:
                P.put("wyckoff_distribution" if bc[ctx_lo:i + 1].any() else "wyckoff_reaccumulation", i, 0, np.nan)


def detect(ctx: ChunkCtx) -> Hits:
    P = Points()
    n = ctx.n
    if n == 0:
        return Hits()
    h, l, c = (np.asarray(x, dtype=float) for x in (ctx.h, ctx.l, ctx.c))  # noqa: E741
    v = np.asarray(ctx.v, dtype=float)
    atr_prev = np.r_[np.nan, np.asarray(ctx.atr, dtype=float)[:-1]]
    rng = h - l
    c_back = np.r_[np.full(min(n, TREND_LB), np.nan), c[:-TREND_LB]] if n > TREND_LB else np.full(n, np.nan)
    with np.errstate(invalid="ignore"):
        down, up = c < c_back, c > c_back
        new_lo, new_hi = l <= _roll(l, TREND_LB, np.min), h >= _roll(h, TREND_LB, np.max)
        wide = rng >= CLIMAX_ATR * atr_prev
    q80, q90 = np.full(n, np.nan), np.full(n, np.nan)
    cand = np.flatnonzero((down & new_lo) | (up & new_hi))
    cand = cand[cand >= VOL_LB]
    if len(cand):
        win = sliding_window_view(v, VOL_LB)[cand - VOL_LB]  # row = the 200 volumes before the candle
        q80[cand], q90[cand] = np.percentile(win, [PS_Q, CLIMAX_Q], axis=1)
    with np.errstate(invalid="ignore"):
        sc = down & new_lo & wide & (v > q90)
        bc = up & new_hi & wide & (v > q90)
        ps = down & new_lo & (v > q80) & (c - l >= 0.5 * rng) & ~sc
        psy = up & new_hi & (v > q80) & (h - c >= 0.5 * rng) & ~bc
    for i in np.flatnonzero(sc):
        P.put("selling_climax", int(i), 1, l[i])
    for i in np.flatnonzero(bc):
        P.put("buying_climax", int(i), -1, h[i])
    for pid, mask, d, stop in (("preliminary_support", ps, 1, l), ("preliminary_supply", psy, -1, h)):
        last = -PS_GAP
        for i in np.flatnonzero(mask):
            if i - last >= PS_GAP:
                P.put(pid, int(i), d, stop[i])
                last = i
    _climax(P, 1, sc, h, l, c, v, atr_prev, _by_conf(ctx.swings, "high"), "automatic_rally", "creek_breakout")
    _climax(P, -1, bc, -l, -h, -c, v, atr_prev, _by_conf(ctx.swings, "low", -1.0), "automatic_reaction", "ice_breakdown")
    _band_ranges(P, ctx, atr_prev, sc, bc)
    return P.flush(Hits())
