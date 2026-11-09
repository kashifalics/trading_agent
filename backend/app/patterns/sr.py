"""Family F: support / resistance events beyond the platform's breakout, retest and failed breakout (registered in platform.py)."""
import numpy as np

from app.feature_engineering.indicators import ema
from app.market_data.bars import Bars
from app.patterns.candles import _roll_max, _roll_min, _sh
from app.patterns.ctx import ChunkCtx
from app.patterns.registry import Hits, Points, spec
from app.price_action.levels import detect_levels

F = "F"
LEVEL_STEP = 200
spec(id="support_rejection", family=F, name="Support Rejection", direction="bullish",
     definition="price trades into a support band (2+ clustered confirmed swings, known before the candle) and closes back above it, "
                "lower wick >= 40% of range, not more than 0.5 ATR through the band", invalidation="the lower of the candle low and the band low")
spec(id="resistance_rejection", family=F, name="Resistance Rejection", direction="bearish",
     definition="mirror of support rejection at a resistance band", invalidation="the higher of the candle high and the band high")
spec(id="multi_touch_rejection", family=F, name="Multiple-Touch Level Rejection", direction="both",
     definition="a support / resistance rejection at a band with 3 or more swing touches", invalidation="beyond the band and the candle")
for step, nm in ((10, "Round Number ($10)"), (50, "Round Number ($50)"), (100, "Psychological Level ($100)")):
    spec(id=f"round{step}_reaction", family=F, name=f"{nm} Reaction", direction="both",
         definition=f"price arrives at a multiple of ${step}{' (not of a larger round step)' if step < 100 else ''} from more than 0.1 ATR "
                    "away, trades through it and closes back on its original side; direction away from the level",
         invalidation="the candle's extreme")
spec(id="round_placebo_reaction", family=F, name="Placebo Level Reaction ($10 grid offset by $5)", direction="both",
     definition="the round-number rule applied to levels at $5, $15, $25 ...: the comparison that shows whether round numbers matter",
     invalidation="the candle's extreme")
spec(id="range_boundary_rejection", family=F, name="Range Boundary Rejection", direction="both",
     definition="the candle trades to or beyond the previous 50-candle high (low) and closes more than 0.1 ATR back inside",
     invalidation="the candle's extreme")
spec(id="range_midpoint_cross", family=F, name="Range Midpoint Cross", direction="both",
     definition="close crosses the midpoint of the previous 50-candle range", invalidation="the extreme of the last 3 candles")
spec(id="ema_bounce", family=F, name="Dynamic Support / Resistance (EMA50) Bounce", direction="both",
     definition="EMA50 rising (falling) over 5 candles, the candle trades through it and closes back on the trend side, after 3 closes "
                "on that side", invalidation="the candle's extreme")
for pid, nm, why in (
    ("horizontal_sr", "Horizontal Support / Horizontal Resistance / Major Swing Zone", "levels are states; they are traded through "
     "support_rejection, resistance_rejection, breakout, retest and failed_breakout"),
    ("sr_flip", "Support-to-Resistance / Resistance-to-Support Flip", "identical to retest (family F, platform)"),
    ("false_breakdown", "False Breakdown", "identical to failed_breakout of a support"),
    ("confluence_zone", "Confluence Zone", "a combination (level overlapping a zone): studied in the combination phase"),
):
    spec(id=pid, family=F, name=nm, direction="both", definition="-", status="scoped_out", reason=why)


def detect(ctx: ChunkCtx) -> Hits:
    H = Hits()
    P = Points()
    n = ctx.n
    o, h, lo, c, a = ctx.o, ctx.h, ctx.l, ctx.c, ctx.atr
    b = Bars(ctx.t, o, h, lo, c, ctx.v, ctx.step)
    rng = np.where(h - lo > 0, h - lo, np.nan)
    lw = (np.minimum(o, c) - lo) / rng
    uw = (h - np.maximum(o, c)) / rng
    for w in range(LEVEL_STEP, n, LEVEL_STEP):
        end = min(n, w + LEVEL_STEP)
        for lv in detect_levels(b, ctx.swings, a, as_of=w - 1):
            blo, bhi = lv.low, lv.high
            k = np.arange(w, end)
            if lv.kind == "support":
                m = (lo[k] <= bhi) & (c[k] > bhi) & (lo[k] >= blo - 0.5 * a[k]) & (lw[k] >= 0.4) & (c[k - 1] > bhi)
                d, stop = 1, np.minimum(lo[k], blo)
            else:
                m = (h[k] >= blo) & (c[k] < blo) & (h[k] <= bhi + 0.5 * a[k]) & (uw[k] >= 0.4) & (c[k - 1] < blo)
                d, stop = -1, np.maximum(h[k], bhi)
            hit = np.flatnonzero(m)
            if len(hit):
                j = hit[0]  # first rejection per band and window
                P.put("support_rejection" if d > 0 else "resistance_rejection", int(k[j]), d, float(stop[j]))
                if (lv.meta.get("touches") or 0) >= 3:
                    P.put("multi_touch_rejection", int(k[j]), d, float(stop[j]))
    pc = _sh(c, 1)
    with np.errstate(invalid="ignore"):
        for name, step, off in (("round", 10, 0.0), ("round_placebo_reaction", 10, 5.0)):
            below = np.floor((pc - off) / step) * step + off  # nearest grid level under the previous close
            above = np.ceil((pc - off) / step) * step + off
            bull = (pc > below + 0.1 * a) & (lo <= below) & (c > below)
            bear = (pc < above - 0.1 * a) & (h >= above) & (c < above)
            if name == "round":
                for lvl, m, d, st in ((below, bull, 1, lo), (above, bear, -1, h)):
                    r100 = np.isclose(np.mod(lvl, 100), 0) | np.isclose(np.mod(lvl, 100), 100)
                    r50 = ~r100 & (np.isclose(np.mod(lvl, 50), 0) | np.isclose(np.mod(lvl, 50), 50))
                    H.add("round100_reaction", m & r100, d, st)
                    H.add("round50_reaction", m & r50, d, st)
                    H.add("round10_reaction", m & ~r100 & ~r50, d, st)
            else:
                H.add(name, bull, 1, lo)
                H.add(name, bear, -1, h)
        hi50, lo50 = _sh(_roll_max(h, 50), 1), _sh(_roll_min(lo, 50), 1)
        H.add("range_boundary_rejection", (h >= hi50) & (c < hi50 - 0.1 * a), -1, h)
        H.add("range_boundary_rejection", (lo <= lo50) & (c > lo50 + 0.1 * a), 1, lo)
        mid = (hi50 + lo50) / 2
        lo3, hi3 = _roll_min(lo, 3), _roll_max(h, 3)
        H.add("range_midpoint_cross", (pc < mid) & (c >= mid), 1, lo3)
        H.add("range_midpoint_cross", (pc > mid) & (c <= mid), -1, hi3)
        e50 = ema(c, 50)
        e5 = _sh(e50, 5)
        above3 = (_sh(c, 1) > _sh(e50, 1)) & (_sh(c, 2) > _sh(e50, 2)) & (_sh(c, 3) > _sh(e50, 3))
        below3 = (_sh(c, 1) < _sh(e50, 1)) & (_sh(c, 2) < _sh(e50, 2)) & (_sh(c, 3) < _sh(e50, 3))
        H.add("ema_bounce", (e50 > e5) & (lo <= e50) & (c >= e50) & above3, 1, lo)
        H.add("ema_bounce", (e50 < e5) & (h >= e50) & (c <= e50) & below3, -1, h)
    H.extend(P.flush(Hits()))
    return H
