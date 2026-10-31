"""Breaker blocks: an order block that FAILED (a bar closed through its far edge) flips polarity.

A bullish OB invalidated by a close below its low becomes a bearish breaker over the same zone
(and vice-versa). Known at the invalidating bar.
"""
from app.core.events import Event
from app.market_data.bars import Bars


def detect_breaker_blocks(b: Bars, order_blocks: list[Event]) -> list[Event]:
    n = len(b)
    out: list[Event] = []
    for ob in order_blocks:
        if ob.status != "invalidated" or ob.meta.get("status_idx") is None:
            continue
        m = ob.meta["status_idx"]
        direction = "bearish" if ob.direction == "bullish" else "bullish"
        status = "active"
        for q in range(m + 1, n):  # breaker fails if price closes back through the original OB
            if direction == "bearish" and b.c[q] > ob.high or direction == "bullish" and b.c[q] < ob.low:
                status = "invalidated"
                break
        out.append(Event(
            kind="breaker_block", direction=direction, idx=m, ts=int(b.t[m]), low=ob.low, high=ob.high,
            price=ob.price, start_idx=ob.start_idx, start_ts=ob.start_ts, status=status,
            evidence=f"{ob.direction} order block at {ob.low:.6g}-{ob.high:.6g} failed; zone flips {direction}",
            meta={"origin_ob_idx": ob.start_idx},
        ))
    return out
