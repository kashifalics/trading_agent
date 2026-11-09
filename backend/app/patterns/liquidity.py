"""Family C: liquidity events beyond the platform's swing sweep and equal highs/lows (registered in platform.py).

A sweep of a reference level = the FIRST candle of the period that trades beyond the level and closes back inside it. Session
sweeps are measured on timeframes up to H1, previous-day levels up to H4, previous-week up to D1, previous-month up to W1.
"""

from app.market_data.bars import Bars
from app.market_structure.liquidity import detect_liquidity_sweeps
from app.patterns.context import first_touch
from app.patterns.ctx import ChunkCtx
from app.patterns.registry import Hits, Points, spec

C = "C"
LEVEL_SWEEPS = (  # (id stem, name, high attr, low attr, period attr, max candle seconds)
    ("pd", "Previous Day", "pdh", "pdl", "day_id", 4 * 3600),
    ("pw", "Previous Week", "pwh", "pwl", "week_id", 86400),
    ("pm", "Previous Month", "pmh", "pml", "month_id", 7 * 86400),
    ("asia", "Asian Session", "asia_h", "asia_l", "day_id", 3600),
    ("london", "London Session", "london_h", "london_l", "day_id", 3600),
)
for stem, nm, *_ in LEVEL_SWEEPS:
    what = {"pd": "previous New York trading day (17:00-17:00)", "pw": "previous trading week", "pm": "previous calendar month",
            "asia": "latest completed Asian session (19:00-03:00 New York)",
            "london": "latest completed London session (03:00-08:00 New York)"}[stem]
    spec(id=f"{stem}_high_sweep", family=C, name=f"{nm} High Sweep", direction="bearish",
         definition=f"first candle of the period to trade above the {what} high, closing back below it", invalidation="the candle's high")
    spec(id=f"{stem}_low_sweep", family=C, name=f"{nm} Low Sweep", direction="bullish",
         definition=f"first candle of the period to trade below the {what} low, closing back above it", invalidation="the candle's low")
spec(id="internal_sweep", family=C, name="Internal Liquidity Sweep", direction="both",
     definition="sweep of an internal swing (2 left / 2 right) high or low", invalidation="the sweep candle's extreme")
spec(id="external_sweep", family=C, name="External Liquidity Sweep", direction="both",
     definition="sweep of an external swing (5 left / 5 right) high or low", invalidation="the sweep candle's extreme")
spec(id="grab_reversal", family=C, name="Liquidity Grab and Reversal (stop-run reversal)", direction="both",
     definition="a swing sweep followed within 3 candles by a close beyond the sweep candle's opposite extreme",
     invalidation="the sweep extreme")
spec(id="failed_sweep", family=C, name="Failed Liquidity Sweep (sweep and continuation)", direction="both",
     definition="a swing sweep followed within 5 candles by a close beyond the sweep extreme; direction is the original push",
     invalidation="the extreme on the other side since the sweep")
spec(id="sweep_reclaim", family=C, name="Sweep and Reclaim (two-candle)", direction="both",
     definition="a candle closes beyond the most recent confirmed swing and the next candle closes back inside it",
     invalidation="the extreme of the two candles")
spec(id="multiple_sweeps", family=C, name="Multiple Liquidity Sweeps", direction="both",
     definition="a second swing sweep on the same side within 20 candles at a level within 0.3 ATR of the first",
     invalidation="the extreme of both sweeps")
spec(id="sweep_to_bos", family=C, name="Liquidity-Sweep-to-BOS Sequence", direction="both",
     definition="a swing sweep followed within 10 candles by a BOS/CHoCH in the sweep's direction (event at the break)",
     invalidation="the sweep extreme")
for pid, nm, why in (
    ("buy_side_liquidity", "Buy-Side / Sell-Side Liquidity, Swing High / Low Liquidity, Resting Liquidity",
     "levels, not events: used as features (distance to the nearest unswept swing / equal highs) and as sweep reference levels"),
    ("liquidity_pool", "Liquidity Pool Formation / Liquidity Compression", "covered by equal_highs / equal_lows; clustering is a feature"),
    ("inducement", "Inducement", "no objective definition separates it from a minor swing sweep (internal_sweep)"),
    ("stop_run_reversal", "Stop-Run Reversal", "identical to grab_reversal"),
    ("breakout_trap", "Breakout Trap", "identical to failed_breakout (family F)"),
    ("sweep_continuation", "Liquidity Sweep and Continuation", "identical to failed_sweep"),
):
    spec(id=pid, family=C, name=nm, direction="both", definition="-", status="scoped_out", reason=why)


def detect(ctx: ChunkCtx) -> Hits:
    H = Hits()
    P = Points()
    n = ctx.n
    L = ctx.levels
    if L is not None:
        for stem, _, hk, lk, pk, max_step in LEVEL_SWEEPS:
            if ctx.step > max_step:
                continue
            hi, lo, pid = getattr(L, hk), getattr(L, lk), getattr(L, pk)
            th = first_touch(hi, ctx.h, pid, above=True)
            tl = first_touch(lo, ctx.l, pid, above=False)
            H.add(f"{stem}_high_sweep", th & (ctx.c < hi), -1, ctx.h)
            H.add(f"{stem}_low_sweep", tl & (ctx.c > lo), 1, ctx.l)
    b = Bars(ctx.t, ctx.o, ctx.h, ctx.l, ctx.c, ctx.v, ctx.step)
    for pid, sw in (("internal_sweep", ctx.swings_int), ("external_sweep", ctx.swings_ext)):
        for e in detect_liquidity_sweeps(b, sw):
            P.put(pid, e.idx, 1 if e.direction == "bullish" else -1, e.low if e.direction == "bullish" else e.high)
    sweeps = sorted(ctx.events.get("sweeps", []), key=lambda e: e.idx)
    breaks = ctx.events.get("breaks", [])
    for k, e in enumerate(sweeps):
        d = 1 if e.direction == "bullish" else -1
        ext = e.low if d > 0 else e.high
        for j in range(e.idx + 1, min(n, e.idx + 4)):  # grab and reversal: close beyond the sweep candle's other side
            if (d > 0 and ctx.c[j] > e.high) or (d < 0 and ctx.c[j] < e.low):
                P.put("grab_reversal", j, d, ext)
                break
        for j in range(e.idx + 1, min(n, e.idx + 6)):  # failed sweep: price goes through the swept extreme after all
            if (d > 0 and ctx.c[j] < e.low) or (d < 0 and ctx.c[j] > e.high):
                other = ctx.h[e.idx:j + 1].max() if d > 0 else ctx.l[e.idx:j + 1].min()
                P.put("failed_sweep", j, -d, other)
                break
        for f in sweeps[k + 1:]:
            if f.idx - e.idx > 20:
                break
            if f.direction == e.direction and abs(f.price - e.price) <= 0.3 * ctx.atr[f.idx]:
                P.put("multiple_sweeps", f.idx, d, min(e.low, f.low) if d > 0 else max(e.high, f.high))
                break
        for br in breaks:
            if br.idx <= e.idx:
                continue
            if br.idx - e.idx > 10:
                break
            if br.direction == e.direction:
                P.put("sweep_to_bos", br.idx, d, ext)
                break
    # two-candle sweep and reclaim of the most recent confirmed swing
    by_conf: dict[int, list] = {}
    for s in ctx.swings:
        by_conf.setdefault(s.confirm_idx, []).append(s)
    last_h = last_l = None
    for i in range(n):
        if i >= 1:
            if last_h is not None and ctx.c[i - 1] > last_h.price and ctx.c[i] < last_h.price:
                P.put("sweep_reclaim", i, -1, max(ctx.h[i - 1], ctx.h[i]))
                last_h = None
            if last_l is not None and ctx.c[i - 1] < last_l.price and ctx.c[i] > last_l.price:
                P.put("sweep_reclaim", i, 1, min(ctx.l[i - 1], ctx.l[i]))
                last_l = None
        if last_h is not None and i >= 1 and ctx.c[i - 1] > last_h.price and ctx.c[i] >= last_h.price:
            last_h = None  # accepted above: no longer a reclaim candidate
        if last_l is not None and i >= 1 and ctx.c[i - 1] < last_l.price and ctx.c[i] <= last_l.price:
            last_l = None
        for s in by_conf.get(i, []):
            if s.kind == "high":
                last_h = s
            else:
                last_l = s
    return P.flush(H)
