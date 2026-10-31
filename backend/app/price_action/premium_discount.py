"""Premium/discount of the current dealing range (last confirmed swing high & swing low)."""
from app.core.events import Event
from app.market_data.bars import Bars
from app.market_structure.swings import Swing, confirmed


def premium_discount(b: Bars, swings: list[Swing], band: float = 0.05) -> Event | None:
    """Position of the last close in [swing low, swing high]: >0.5+band premium, <0.5-band discount."""
    n = len(b)
    if n == 0:
        return None
    c = confirmed(swings, n - 1)
    highs = [s for s in c if s.kind == "high"]
    lows = [s for s in c if s.kind == "low"]
    if not highs or not lows:
        return None
    hi, lo = highs[-1], lows[-1]
    if hi.price <= lo.price:
        return None
    pos = (float(b.c[-1]) - lo.price) / (hi.price - lo.price)
    zone = "premium" if pos > 0.5 + band else "discount" if pos < 0.5 - band else "equilibrium"
    return Event(
        kind="premium_discount", direction="bearish" if zone == "premium" else "bullish" if zone == "discount" else "neutral",
        idx=n - 1, ts=int(b.t[-1]), price=(hi.price + lo.price) / 2, low=lo.price, high=hi.price,
        start_idx=min(hi.idx, lo.idx), start_ts=int(b.t[min(hi.idx, lo.idx)]), status=zone,
        evidence=f"close at {pos:.0%} of range {lo.price:.6g}-{hi.price:.6g} ({zone}); equilibrium {(hi.price + lo.price) / 2:.6g}",
        params={"band": band}, meta={"position": pos, "outside_range": pos < 0 or pos > 1},
    )
