"""Family D: fair value gaps and imbalance beyond the platform's FVG first-mitigation entry (registered in platform.py).

Zone patterns are traded like every zone in the study: a limit order at the zone's near edge, stop beyond its far edge."""

from app.patterns.ctx import ChunkCtx
from app.patterns.registry import Hits, Points, spec

D = "D"
Z = "zone_limit"
FAR = "the far edge of the zone"
spec(id="fvg_formation", family=D, name="FVG Formation (momentum)", direction="both",
     definition="the candle that completes a fair value gap (gap >= 0.1 ATR); traded at the next open in the gap's direction",
     invalidation="the far edge of the gap")
spec(id="inverse_fvg", family=D, name="Inverse FVG (FVG failure)", direction="both", entry=Z,
     definition="a fair value gap that price closes through (beyond its far edge) within 100 candles; the zone flips polarity and is "
                "traded on the first return", invalidation=FAR)
spec(id="consecutive_fvg", family=D, name="Consecutive FVG", direction="both", entry=Z,
     definition="two same-direction fair value gaps on consecutive candles; zone = their union", invalidation=FAR)
spec(id="fvg_with_bos", family=D, name="FVG with BOS", direction="both", entry=Z,
     definition="a fair value gap formed from 3 candles before to 1 candle after a same-direction BOS", invalidation=FAR)
spec(id="fvg_with_choch", family=D, name="FVG with CHoCH", direction="both", entry=Z,
     definition="a fair value gap formed from 3 candles before to 1 candle after a same-direction CHoCH", invalidation=FAR)
spec(id="fvg_after_sweep", family=D, name="FVG after Liquidity Sweep", direction="both", entry=Z,
     definition="a fair value gap formed within 5 candles after a same-direction swing sweep (bullish gap after a sweep of lows)",
     invalidation=FAR)
spec(id="fvg_continuation", family=D, name="FVG Continuation", direction="both", entry=Z,
     definition="a fair value gap in the direction of the prevailing structure trend", invalidation=FAR)
spec(id="fvg_reversal", family=D, name="FVG Reversal", direction="both", entry=Z,
     definition="a fair value gap against the prevailing structure trend", invalidation=FAR)
spec(id="balanced_price_range", family=D, name="Balanced Price Range", direction="both", entry=Z,
     definition="a bullish and a bearish fair value gap within 10 candles whose ranges overlap; zone = the overlap, direction of the "
                "later gap", invalidation=FAR)
spec(id="displacement_imbalance", family=D, name="Displacement Imbalance", direction="both", entry=Z,
     definition="a fair value gap whose middle candle is a displacement candle (range >= 2 ATR, body >= 70% of range)", invalidation=FAR)
for pid, nm, why in (
    ("fvg_mitigation", "FVG Mitigation", "identical to the platform's fvg entry (first return into the gap)"),
    ("fvg_fill_states", "Partial FVG Fill / Full FVG Fill / Unmitigated FVG / Imbalance Repricing",
     "states of a gap, not entry events: used as features (fill fraction, age, distance)"),
    ("nested_fvg", "Nested FVG", "a gap inside a higher-timeframe gap: studied in the multi-timeframe phase"),
    ("htf_ltf_fvg", "Higher-Timeframe FVG / Lower-Timeframe FVG", "multi-timeframe relation: studied in the multi-timeframe phase"),
    ("fvg_failure", "FVG Failure", "identical to inverse_fvg"),
):
    spec(id=pid, family=D, name=nm, direction="both", definition="-", status="scoped_out", reason=why)


def detect(ctx: ChunkCtx) -> Hits:
    P = Points()
    n = ctx.n
    fvgs = sorted(ctx.events.get("fvgs", []), key=lambda e: e.idx)
    breaks = ctx.events.get("breaks", [])
    sweeps = ctx.events.get("sweeps", [])
    for k, e in enumerate(fvgs):
        d = 1 if e.direction == "bullish" else -1
        lo, hi = e.low, e.high
        far = lo if d > 0 else hi
        P.put("fvg_formation", e.idx, d, far)
        for j in range(e.idx + 1, min(n, e.idx + 101)):
            if (d > 0 and ctx.c[j] < lo) or (d < 0 and ctx.c[j] > hi):
                P.put("inverse_fvg", j, -d, hi if d > 0 else lo, lo, hi)
                break
        if k and fvgs[k - 1].idx == e.idx - 1 and fvgs[k - 1].direction == e.direction:
            ulo, uhi = min(lo, fvgs[k - 1].low), max(hi, fvgs[k - 1].high)
            P.put("consecutive_fvg", e.idx, d, ulo if d > 0 else uhi, ulo, uhi)
        for br in breaks:
            if br.direction == e.direction and br.idx - 3 <= e.idx <= br.idx + 1:
                P.put("fvg_with_bos" if br.kind == "BOS" else "fvg_with_choch", e.idx, d, far, lo, hi)
                break
        for sw in sweeps:
            if sw.direction == e.direction and 0 < e.idx - sw.idx <= 5:
                P.put("fvg_after_sweep", e.idx, d, far, lo, hi)
                break
        if ctx.trend is not None and ctx.trend[e.idx] != 0:
            P.put("fvg_continuation" if ctx.trend[e.idx] == d else "fvg_reversal", e.idx, d, far, lo, hi)
        m = e.idx - 1
        rng = ctx.h[m] - ctx.l[m]
        if rng >= 2 * ctx.atr[m] and abs(ctx.c[m] - ctx.o[m]) >= 0.7 * rng:
            P.put("displacement_imbalance", e.idx, d, far, lo, hi)
        for f in fvgs[k + 1:]:
            if f.idx - e.idx > 10:
                break
            if f.direction != e.direction:
                olo, ohi = max(lo, f.low), min(hi, f.high)
                if olo < ohi:
                    fd = 1 if f.direction == "bullish" else -1
                    P.put("balanced_price_range", f.idx, fd, olo if fd > 0 else ohi, olo, ohi)
                    break
    return P.flush(Hits())
