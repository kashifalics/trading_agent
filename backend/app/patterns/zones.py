"""Family E: order block and supply/demand variants beyond the platform's order block, breaker and supply/demand zones."""

from app.patterns.ctx import ChunkCtx
from app.patterns.registry import Hits, Points, spec

E = "E"
Z = "zone_limit"
FAR = "the far edge of the zone"
spec(id="order_block_bos", family=E, name="Order Block with BOS", direction="both", entry=Z,
     definition="an order block whose impulse produced a BOS (continuation)", invalidation=FAR)
spec(id="order_block_choch", family=E, name="Order Block with CHoCH", direction="both", entry=Z,
     definition="an order block whose impulse produced a CHoCH (reversal)", invalidation=FAR)
spec(id="order_block_sweep", family=E, name="Order Block with Liquidity Sweep", direction="both", entry=Z,
     definition="an order block whose candle took the lowest low (highest high) of the 20 candles before it", invalidation=FAR)
spec(id="order_block_fvg", family=E, name="Order Block with FVG", direction="both", entry=Z,
     definition="an order block whose impulse left a same-direction fair value gap between the block and the break", invalidation=FAR)
spec(id="strong_demand", family=E, name="Strong Demand Zone", direction="bullish", entry=Z,
     definition="a demand zone whose impulse candle has range >= 2.5 ATR", invalidation="the base low")
spec(id="strong_supply", family=E, name="Strong Supply Zone", direction="bearish", entry=Z,
     definition="a supply zone whose impulse candle has range >= 2.5 ATR", invalidation="the base high")
spec(id="demand_to_supply_flip", family=E, name="Demand-to-Supply Flip", direction="bearish", entry=Z,
     definition="a demand zone that a candle closes below (within 300 candles) becomes supply over the same range", invalidation=FAR)
spec(id="supply_to_demand_flip", family=E, name="Supply-to-Demand Flip", direction="bullish", entry=Z,
     definition="a supply zone that a candle closes above (within 300 candles) becomes demand over the same range", invalidation=FAR)
spec(id="reclaimed_order_block", family=E, name="Reclaimed Order Block", direction="both",
     definition="an order block closed through (it failed) and then, within 20 candles, a close back beyond its near edge in the "
                "original direction", invalidation="the extreme since the failure")
spec(id="rejection_block", family=E, name="Rejection Block", direction="both", entry=Z,
     definition="a confirmed swing low (high) candle whose lower (upper) wick is >= 50% of its range; zone = the wick (low to body)",
     invalidation="the wick extreme")
for pid, nm, why in (
    ("mitigation_block", "Mitigation Block", "a failed block without a new extreme: merged with breaker_block (no separate objective rule)"),
    ("failed_order_block", "Failed Order Block", "identical to the origin of breaker_block"),
    ("ob_mitigation_states", "Mitigated / Unmitigated Order Block", "states, not entry events: used as features (mitigation count, age)"),
    ("sd_reaction", "Bullish / Bearish Supply-Demand Reaction", "identical to the platform's demand_zone / supply_zone entries"),
):
    spec(id=pid, family=E, name=nm, direction="both", definition="-", status="scoped_out", reason=why)


def detect(ctx: ChunkCtx) -> Hits:
    P = Points()
    n = ctx.n
    fvgs = ctx.events.get("fvgs", [])
    for ob in ctx.events.get("obs", []):
        d = 1 if ob.direction == "bullish" else -1
        lo, hi = ob.low, ob.high
        far = lo if d > 0 else hi
        P.put("order_block_choch" if ob.meta.get("break_kind") == "CHoCH" else "order_block_bos", ob.idx, d, far, lo, hi)
        k = ob.meta.get("ob_idx", ob.start_idx)
        if k is not None and k >= 20:
            took = ctx.l[k] < ctx.l[k - 20:k].min() if d > 0 else ctx.h[k] > ctx.h[k - 20:k].max()
            if took:
                P.put("order_block_sweep", ob.idx, d, far, lo, hi)
        if k is not None and any(f.direction == ob.direction and k < f.idx <= ob.idx for f in fvgs):
            P.put("order_block_fvg", ob.idx, d, far, lo, hi)
        fail = None
        for m in range(ob.idx + 1, min(n, ob.idx + 301)):  # causal failure scan (the platform status uses the whole future)
            if (d > 0 and ctx.c[m] < lo) or (d < 0 and ctx.c[m] > hi):
                fail = m
                break
        if fail is not None:
            for j in range(fail + 1, min(n, fail + 21)):
                if (d > 0 and ctx.c[j] > hi) or (d < 0 and ctx.c[j] < lo):
                    ext = ctx.l[fail:j + 1].min() if d > 0 else ctx.h[fail:j + 1].max()
                    P.put("reclaimed_order_block", j, d, ext)
                    break
    for z in ctx.events.get("zones", []):
        d = 1 if z.kind == "demand_zone" else -1
        lo, hi = z.low, z.high
        i = z.idx
        if ctx.h[i] - ctx.l[i] >= 2.5 * ctx.atr[max(i - 1, 0)]:
            P.put("strong_demand" if d > 0 else "strong_supply", i, d, lo if d > 0 else hi, lo, hi)
        for m in range(i + 1, min(n, i + 301)):
            if (d > 0 and ctx.c[m] < lo) or (d < 0 and ctx.c[m] > hi):
                P.put("demand_to_supply_flip" if d > 0 else "supply_to_demand_flip", m, -d, hi if d > 0 else lo, lo, hi)
                break
    for s in ctx.swings:
        i, cf = s.idx, s.confirm_idx
        if cf >= n:
            continue
        rng = ctx.h[i] - ctx.l[i]
        if rng <= 0:
            continue
        if s.kind == "low":
            body_lo = min(ctx.o[i], ctx.c[i])
            if body_lo - ctx.l[i] >= 0.5 * rng:
                P.put("rejection_block", cf, 1, ctx.l[i], ctx.l[i], body_lo)
        else:
            body_hi = max(ctx.o[i], ctx.c[i])
            if ctx.h[i] - body_hi >= 0.5 * rng:
                P.put("rejection_block", cf, -1, ctx.h[i], body_hi, ctx.h[i])
    return P.flush(Hits())
