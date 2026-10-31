"""Trade-plan construction: entry zone, stop (invalidation), targets, risk/reward."""
from dataclasses import dataclass, field

import numpy as np

from app.core.events import Event
from app.market_data.bars import Bars
from app.market_structure.swings import Swing, confirmed

MIN_STOP_ATR, MAX_STOP_ATR, STOP_BUFFER_ATR = 0.75, 4.0, 0.25


@dataclass
class TradePlan:
    direction: str  # BUY | SELL
    entry_low: float
    entry_high: float
    entry_ref: float
    stop_loss: float
    invalidation: float
    targets: list[float]
    risk_reward: float
    target_basis: str
    warnings: list[str] = field(default_factory=list)


def build_trade_plan(b: Bars, direction: str, atr: float, swings: list[Swing], zones: list[Event],
                     min_rr: float = 1.5) -> tuple[TradePlan | None, str | None]:
    """Returns (plan, None) or (None, reason). Pure function of data up to the last bar."""
    if not np.isfinite(atr) or atr <= 0:
        return None, "ATR unavailable"
    n = len(b)
    px = float(b.c[-1])
    long_ = direction == "BUY"
    sw = confirmed(swings, n - 1)
    warnings: list[str] = []

    # Point of interest: nearest unmitigated same-side zone within 1.5 ATR of price -> limit entry.
    side = "bullish" if long_ else "bearish"
    poi = None
    for z in zones:
        if z.direction != side or z.status in ("filled", "invalidated", "broken") or z.low is None or z.high is None:
            continue
        dist = (px - z.high) if long_ else (z.low - px)
        inside = z.low <= px <= z.high
        if inside or (0 < dist <= 1.5 * atr):
            if poi is None or abs(z.idx - n) < abs(poi.idx - n):
                poi = z
    if poi is not None and not (poi.low <= px <= poi.high):
        e_low, e_high = poi.low, poi.high
        ref = poi.high if long_ else poi.low
    elif poi is not None:
        e_low, e_high, ref = poi.low, poi.high, px
    else:
        e_low, e_high, ref = px - 0.1 * atr, px + 0.1 * atr, px

    if long_:
        anchors = [s.price for s in sw if s.kind == "low" and s.price < ref]
        base = max(anchors[-3:]) if anchors else ref - 1.5 * atr  # most recent protective lows
        if poi is not None:
            base = min(base, poi.low)
        inval = base
        stop = base - STOP_BUFFER_ATR * atr
        risk = ref - stop
    else:
        anchors = [s.price for s in sw if s.kind == "high" and s.price > ref]
        base = min(anchors[-3:]) if anchors else ref + 1.5 * atr
        if poi is not None:
            base = max(base, poi.high)
        inval = base
        stop = base + STOP_BUFFER_ATR * atr
        risk = stop - ref
    if risk < MIN_STOP_ATR * atr:
        stop = ref - MIN_STOP_ATR * atr if long_ else ref + MIN_STOP_ATR * atr
        risk = MIN_STOP_ATR * atr
        warnings.append("stop widened to minimum distance (0.75 ATR)")
    if risk > MAX_STOP_ATR * atr:
        return None, f"invalidation level is {risk / atr:.1f} ATR away (> {MAX_STOP_ATR})"

    # Targets: opposing swing levels that give >= min_rr, else fixed multiples.
    if long_:
        lv = sorted(s.price for s in sw if s.kind == "high" and s.price > ref + min_rr * risk)
        closer = [s.price for s in sw if s.kind == "high" and ref < s.price <= ref + min_rr * risk]
    else:
        lv = sorted((s.price for s in sw if s.kind == "low" and s.price < ref - min_rr * risk), reverse=True)
        closer = [s.price for s in sw if s.kind == "low" and ref - min_rr * risk <= s.price < ref]
    if closer:
        warnings.append(f"opposing swing level at {closer[0]:.6g} sits before {min_rr}R")
    sign = 1 if long_ else -1
    if lv:
        targets, basis = lv[:2], "opposing_swing_levels"
    else:
        targets, basis = [ref + sign * 2.0 * risk, ref + sign * 3.0 * risk], "fixed_multiple"
    rr = abs(targets[0] - ref) / risk
    if rr < min_rr:
        return None, f"risk/reward {rr:.2f} below minimum {min_rr}"
    return TradePlan(direction, e_low, e_high, ref, stop, inval, targets, rr, basis, warnings), None
