"""Family B: market structure events beyond the platform's BOS / CHoCH (registered in platform.py)."""
import numpy as np

from app.market_data.bars import Bars
from app.market_structure.bos import detect_structure_breaks
from app.patterns.ctx import ChunkCtx
from app.patterns.registry import Hits, Points, spec

B = "B"
spec(id="higher_low", family=B, name="Higher Low (confirmed)", direction="bullish",
     definition="a swing low (3/3) above the previous swing low, at the candle that confirms it", invalidation="the swing low")
spec(id="lower_high", family=B, name="Lower High (confirmed)", direction="bearish",
     definition="a swing high (3/3) below the previous swing high, at the candle that confirms it", invalidation="the swing high")
spec(id="higher_high", family=B, name="Higher High (confirmed)", direction="neutral",
     definition="a swing high above the previous swing high, at its confirmation", invalidation="none (structure label, not traded alone)")
spec(id="lower_low", family=B, name="Lower Low (confirmed)", direction="neutral",
     definition="a swing low below the previous swing low, at its confirmation", invalidation="none (structure label, not traded alone)")
spec(id="internal_bos", family=B, name="Internal Structure Break", direction="both",
     definition="break of structure on internal swings (2 left / 2 right)", invalidation="origin of the breaking move")
spec(id="external_bos", family=B, name="External Structure Break", direction="both",
     definition="break of structure on external swings (5 left / 5 right)", invalidation="origin of the breaking move")
spec(id="market_structure_shift", family=B, name="Market Structure Shift", direction="both",
     definition="a CHoCH followed within 20 candles by a BOS in the same direction (event at the BOS)",
     invalidation="origin of the BOS move")
spec(id="failed_bos", family=B, name="Failed Break of Structure", direction="both",
     definition="within 1-5 candles of a BOS/CHoCH a close back beyond the broken level; direction is against the break",
     invalidation="the extreme reached after the break")
spec(id="structural_reclaim", family=B, name="Structural Reclaim", direction="both",
     definition="6-20 candles after a BOS/CHoCH a close back beyond the broken level; direction is against the break",
     invalidation="the extreme reached after the break")
spec(id="swing_failure", family=B, name="Swing Failure", direction="both",
     definition="a candle trades beyond the MOST RECENT confirmed swing high (low) and closes back inside",
     invalidation="the candle's extreme")
spec(id="failed_swing", family=B, name="Failed Swing (failure swing)", direction="both",
     definition="a lower high (higher low) is confirmed and price then closes below the last swing low (above the last swing high) "
                "within 30 candles", invalidation="the lower high (higher low)")
for pid, nm, why in (
    ("trend_continuation", "Trend Continuation", "identical to BOS in the direction of the prevailing structure"),
    ("trend_reversal", "Trend Reversal", "identical to CHoCH; the confirmed version is market_structure_shift"),
    ("structural_transition", "Structural Transition", "identical to market_structure_shift"),
    ("double_top_b", "Double Top / Double Bottom / Triple Top / Triple Bottom", "implemented once in family G (chart patterns)"),
    ("rounded_b", "Rounded Bottom / Rounded Top", "implemented in family G"),
    ("htf_consolidation", "Higher-Timeframe Consolidation", "a multi-timeframe state; studied in the multi-timeframe phase"),
    ("ltf_reversal", "Lower-Timeframe Reversal", "a multi-timeframe relation; studied in the multi-timeframe phase"),
    ("trend_exhaustion", "Trend Exhaustion", "implemented in family J (momentum exhaustion, climax reversal)"),
    ("compression_expansion_b", "Compression Before Expansion / Range Expansion / Range Contraction", "implemented in family J"),
):
    spec(id=pid, family=B, name=nm, direction="both", definition="-", status="scoped_out", reason=why)


def _breaks(ctx: ChunkCtx, swings) -> list:
    b = Bars(ctx.t, ctx.o, ctx.h, ctx.l, ctx.c, ctx.v, ctx.step)
    return detect_structure_breaks(b, swings)[0]


def _origin_stop(ctx: ChunkCtx, e) -> float:
    s = e.meta.get("swing_idx", e.idx)
    return float(ctx.l[s:e.idx + 1].min() if e.direction == "bullish" else ctx.h[s:e.idx + 1].max())


def detect(ctx: ChunkCtx) -> Hits:
    H = Hits()
    P = Points()
    n = ctx.n
    for s in ctx.swings:
        if s.label is None or s.confirm_idx >= n:
            continue
        pid, d, st = {"HL": ("higher_low", 1, s.price), "LH": ("lower_high", -1, s.price), "HH": ("higher_high", 0, np.nan),
                      "LL": ("lower_low", 0, np.nan)}[s.label]
        P.put(pid, s.confirm_idx, d, st)
    for pid, sw in (("internal_bos", ctx.swings_int), ("external_bos", ctx.swings_ext)):
        for e in _breaks(ctx, sw):
            if e.kind != "BOS":
                continue
            P.put(pid, e.idx, 1 if e.direction == "bullish" else -1, _origin_stop(ctx, e))
    breaks = ctx.events.get("breaks", [])
    for k, e in enumerate(breaks):
        d = 1 if e.direction == "bullish" else -1
        if e.kind == "CHoCH":  # market structure shift: the next same-direction BOS within 20 candles
            for f in breaks[k + 1:]:
                if f.idx - e.idx > 20:
                    break
                if f.kind == "BOS" and f.direction == e.direction:
                    P.put("market_structure_shift", f.idx, d, _origin_stop(ctx, f))
                    break
        lvl = e.price
        for j in range(e.idx + 1, min(n, e.idx + 21)):
            back = ctx.c[j] < lvl if d > 0 else ctx.c[j] > lvl
            if back:
                ext = ctx.h[e.idx:j + 1].max() if d > 0 else ctx.l[e.idx:j + 1].min()
                P.put("failed_bos" if j - e.idx <= 5 else "structural_reclaim", j, -d, ext)
                break
    # swing failure: the most recent confirmed swing of each kind
    last_h = last_l = None
    by_conf: dict[int, list] = {}
    for s in ctx.swings:
        by_conf.setdefault(s.confirm_idx, []).append(s)
    sf_b, sf_s = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    for i in range(n):
        if last_h is not None and ctx.h[i] > last_h.price and ctx.c[i] < last_h.price:
            sf_s[i] = True
        if last_l is not None and ctx.l[i] < last_l.price and ctx.c[i] > last_l.price:
            sf_b[i] = True
        if last_h is not None and ctx.h[i] > last_h.price:
            last_h = None  # consumed once traded through
        if last_l is not None and ctx.l[i] < last_l.price:
            last_l = None
        for s in by_conf.get(i, []):  # confirmed at the close of i: usable from i + 1
            if s.kind == "high":
                last_h = s
            else:
                last_l = s
    H.add("swing_failure", sf_b, 1, ctx.l)
    H.add("swing_failure", sf_s, -1, ctx.h)
    # failed swing: after a confirmed LH (HL), close beyond the last opposite swing within 30 candles
    lows = sorted((s for s in ctx.swings if s.kind == "low"), key=lambda s: s.confirm_idx)
    highs = sorted((s for s in ctx.swings if s.kind == "high"), key=lambda s: s.confirm_idx)
    for s in ctx.swings:
        if s.label not in ("LH", "HL") or s.confirm_idx >= n:
            continue
        opp = [x for x in (lows if s.label == "LH" else highs) if x.confirm_idx <= s.confirm_idx]
        if not opp:
            continue
        ref = opp[-1].price
        for j in range(s.confirm_idx + 1, min(n, s.confirm_idx + 31)):
            if (s.label == "LH" and ctx.c[j] < ref) or (s.label == "HL" and ctx.c[j] > ref):
                P.put("failed_swing", j, -1 if s.label == "LH" else 1, s.price)
                break
    return P.flush(H)
