"""Family J: volatility and momentum events."""
import numpy as np

from app.feature_engineering.indicators import atr as atr_fn
from app.feature_engineering.indicators import rsi
from app.patterns.candles import _roll_max, _roll_min, _sh, _shb
from app.patterns.ctx import ChunkCtx
from app.patterns.registry import Hits, spec

J = "J"
NT = "none (no direction; not traded alone)"
spec(id="atr_expansion", family=J, name="ATR Expansion (volatility expansion)", direction="both",
     definition="ATR14 / ATR100 crosses above 1.3 on a candle with body >= 50% of range; direction of the body",
     invalidation="the candle's extreme")
spec(id="atr_compression", family=J, name="ATR Compression (volatility contraction)", direction="neutral",
     definition="ATR14 / ATR100 crosses below 0.7", invalidation=NT)
spec(id="inside_bar_compression", family=J, name="Inside Bar Compression", direction="neutral",
     definition="first candle completing two consecutive inside candles", invalidation=NT)
spec(id="nr_breakout", family=J, name="Narrow Range Breakout", direction="both",
     definition="the candle after a narrowest-of-7 candle closes beyond its high (low)", invalidation="the narrow candle's other extreme")
spec(id="wide_range_reversal", family=J, name="Wide Range Reversal", direction="both",
     definition="range >= 1.8 ATR against the prior 5-candle move, closing in the top (bottom) third", invalidation="the candle's extreme")
spec(id="momentum_continuation", family=J, name="Momentum Continuation", direction="both",
     definition="close beyond the previous 20-candle high (low) while ATR14 / ATR100 >= 1.1", invalidation="the extreme of the last 5 candles")
spec(id="momentum_exhaustion", family=J, name="Momentum Exhaustion", direction="both",
     definition="RSI14 was above 80 (below 20) within the last 10 candles and now crosses back below 70 (above 30); direction is the "
                "reversal", invalidation="the extreme of the last 10 candles")
spec(id="consecutive_expansion", family=J, name="Consecutive Candle Expansion", direction="both",
     definition="three same-direction candles, each with a larger range than the one before", invalidation="the extreme of the three")
spec(id="failed_momentum_breakout", family=J, name="Failed Momentum Breakout", direction="both",
     definition="a close beyond the previous 20-candle high (low) followed within 3 candles by a close back inside; direction is "
                "against the breakout", invalidation="the extreme since the breakout")
spec(id="squeeze_release", family=J, name="Volatility Squeeze Release", direction="both",
     definition="Bollinger bands (20, 2) inside Keltner bands (+/- 1.5 ATR, same centre) for 5+ candles, then the first candle outside; "
                "direction = close versus the 20-candle mean", invalidation="the extreme of the squeeze")
spec(id="range_to_trend", family=J, name="Range-to-Trend Transition", direction="both",
     definition="the 20-candle efficiency ratio (net move / path length) crosses above 0.5; direction of the net move",
     invalidation="the extreme of the last 10 candles")
spec(id="trend_to_range", family=J, name="Trend-to-Range Transition", direction="neutral",
     definition="the 20-candle efficiency ratio crosses below 0.2", invalidation=NT)
spec(id="parabolic_move", family=J, name="Parabolic Price Movement", direction="neutral",
     definition="first candle completing 5 consecutive closes beyond the Bollinger band (20, 2.5)", invalidation=NT)
spec(id="climax_reversal", family=J, name="Climax Reversal", direction="both",
     definition="range >= 2 ATR and volume in the top 10% of the last 200 candles, after a 20-candle move in one direction, closing "
                "in the opposite third; direction is the reversal", invalidation="the candle's extreme")
spec(id="compression_breakout", family=J, name="Compression Before Expansion", direction="both",
     definition="a multi-candle compression followed within 10 candles by a displacement candle (range >= 2 ATR, body >= 70%); "
                "direction of the displacement", invalidation="the displacement candle's extreme")
spec(id="gap_continuation", family=J, name="Gap (continuation)", direction="both",
     definition="open beyond the previous close by >= 0.5 ATR (weekend or daily-break reopen); direction of the gap",
     invalidation="the previous close")
spec(id="gap_fade", family=J, name="Gap (fade)", direction="both",
     definition="the same gap, traded against its direction", invalidation="the gap candle's extreme")
for pid, nm, why in (("volatility_expansion", "Volatility Expansion / Volatility Contraction", "identical to atr_expansion / "
                      "atr_compression"),):
    spec(id=pid, family=J, name=nm, direction="both", definition="-", status="scoped_out", reason=why)


def _win(x: np.ndarray, w: int, fn) -> np.ndarray:
    """fn over the window x[i-w+1 .. i] (NaN before w candles exist)."""
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        out[w - 1:] = fn(np.lib.stride_tricks.sliding_window_view(x, w), axis=1)
    return out


def _cross_up(x: np.ndarray, lvl: float) -> np.ndarray:
    return (x > lvl) & (_sh(x, 1) <= lvl)


def detect(ctx: ChunkCtx) -> Hits:
    H = Hits()
    o, h, lo, c, a, v = ctx.o, ctx.h, ctx.l, ctx.c, ctx.atr, ctx.v
    n = ctx.n
    with np.errstate(invalid="ignore", divide="ignore"):
        rng = h - lo
        body = np.abs(c - o)
        bull, bear = c > o, c < o
        ratio = a / atr_fn(h, lo, c, 100)
        H.add("atr_expansion", _cross_up(ratio, 1.3) & (body >= 0.5 * rng) & bull, 1, lo)
        H.add("atr_expansion", _cross_up(ratio, 1.3) & (body >= 0.5 * rng) & bear, -1, h)
        H.add("atr_compression", (ratio < 0.7) & (_sh(ratio, 1) >= 0.7), 0, np.nan)
        inside = (h < _sh(h, 1)) & (lo > _sh(lo, 1))
        two = inside & _shb(inside, 1)
        H.add("inside_bar_compression", two & ~_shb(two, 1), 0, np.nan)
        nr7 = rng <= _roll_min(rng, 7)
        pn = _shb(nr7, 1)
        H.add("nr_breakout", pn & (c > _sh(h, 1)), 1, _sh(lo, 1))
        H.add("nr_breakout", pn & (c < _sh(lo, 1)), -1, _sh(h, 1))
        wide = rng >= 1.8 * a
        prior_dn, prior_up = _sh(c, 1) < _sh(c, 6), _sh(c, 1) > _sh(c, 6)
        H.add("wide_range_reversal", wide & prior_dn & bull & (c >= h - rng / 3), 1, lo)
        H.add("wide_range_reversal", wide & prior_up & bear & (c <= lo + rng / 3), -1, h)
        hi20, lo20 = _sh(_roll_max(h, 20), 1), _sh(_roll_min(lo, 20), 1)
        up_brk, dn_brk = c > hi20, c < lo20
        H.add("momentum_continuation", up_brk & (ratio >= 1.1), 1, _roll_min(lo, 5))
        H.add("momentum_continuation", dn_brk & (ratio >= 1.1), -1, _roll_max(h, 5))
        r = rsi(c, 14)
        was_hi = _win(np.nan_to_num(r, nan=50.0), 10, np.max) > 80
        was_lo = _win(np.nan_to_num(r, nan=50.0), 10, np.min) < 20
        H.add("momentum_exhaustion", was_hi & (r < 70) & (_sh(r, 1) >= 70), -1, _roll_max(h, 10))
        H.add("momentum_exhaustion", was_lo & (r > 30) & (_sh(r, 1) <= 30), 1, _roll_min(lo, 10))
        grow = (rng > _sh(rng, 1)) & (_sh(rng, 1) > _sh(rng, 2))
        H.add("consecutive_expansion", grow & bull & _shb(bull, 1) & _shb(bull, 2), 1, _roll_min(lo, 3))
        H.add("consecutive_expansion", grow & bear & _shb(bear, 1) & _shb(bear, 2), -1, _roll_max(h, 3))
        for start in np.flatnonzero((up_brk & ~_shb(up_brk, 1)) | (dn_brk & ~_shb(dn_brk, 1))):  # breakout onsets
            d = 1 if up_brk[start] else -1
            ref = hi20[start] if d > 0 else lo20[start]
            for j in range(start + 1, min(n, start + 4)):
                if (d > 0 and c[j] < ref) or (d < 0 and c[j] > ref):
                    ext = h[start:j + 1].max() if d > 0 else lo[start:j + 1].min()
                    H.add_points("failed_momentum_breakout", [j], [-d], [ext])
                    break
        sma = _win(c, 20, np.mean)
        sd = _win(c, 20, np.std)
        sq = 2 * sd < 1.5 * a  # Bollinger (20, 2) inside Keltner (+/- 1.5 ATR) around the same centre
        sq5 = sq & _shb(sq, 1) & _shb(sq, 2) & _shb(sq, 3) & _shb(sq, 4)
        rel = ~sq & _shb(sq5, 1)
        H.add("squeeze_release", rel & (c > sma), 1, _roll_min(lo, 6))
        H.add("squeeze_release", rel & (c < sma), -1, _roll_max(h, 6))
        path = _win(np.abs(np.r_[0.0, np.diff(c)]), 20, np.sum)
        er = np.abs(c - _sh(c, 20)) / path
        trend_on = _cross_up(er, 0.5)
        H.add("range_to_trend", trend_on & (c > _sh(c, 20)), 1, _roll_min(lo, 10))
        H.add("range_to_trend", trend_on & (c < _sh(c, 20)), -1, _roll_max(h, 10))
        H.add("trend_to_range", (er < 0.2) & (_sh(er, 1) >= 0.2), 0, np.nan)
        out_up = c > sma + 2.5 * sd
        out_dn = c < sma - 2.5 * sd
        p5u = out_up & _shb(out_up, 1) & _shb(out_up, 2) & _shb(out_up, 3) & _shb(out_up, 4)
        p5d = out_dn & _shb(out_dn, 1) & _shb(out_dn, 2) & _shb(out_dn, 3) & _shb(out_dn, 4)
        H.add("parabolic_move", (p5u & ~_shb(p5u, 1)) | (p5d & ~_shb(p5d, 1)), 0, np.nan)
        vq = _sh(_win(np.nan_to_num(v), 200, lambda x, axis: np.percentile(x, 90, axis=axis)), 1)
        big = (rng >= 2 * a) & (v >= vq)
        move_up, move_dn = c > _sh(c, 20), c < _sh(c, 20)
        H.add("climax_reversal", big & move_up & (c <= lo + rng / 3), -1, h)
        H.add("climax_reversal", big & move_dn & (c >= h - rng / 3), 1, lo)
        small = rng < 0.6 * a
        comp = small & _shb(small, 1) & _shb(small, 2) & _shb(small, 3) & ((_roll_max(h, 4) - _roll_min(lo, 4)) <= 1.2 * a)
        recent = np.zeros(n, dtype=bool)
        for k in range(1, 11):
            recent |= _shb(comp, k)
        disp = (rng >= 2 * a) & (body >= 0.7 * rng)
        H.add("compression_breakout", recent & disp & bull, 1, lo)
        H.add("compression_breakout", recent & disp & bear, -1, h)
        pc = _sh(c, 1)
        pa = _sh(a, 1)
        gu, gd = o - pc >= 0.5 * pa, pc - o >= 0.5 * pa
        H.add("gap_continuation", gu, 1, pc)
        H.add("gap_continuation", gd, -1, pc)
        H.add("gap_fade", gu, -1, h)
        H.add("gap_fade", gd, 1, lo)
    return H
