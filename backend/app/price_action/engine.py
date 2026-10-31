"""Runs every price-action detector once and bundles the results."""
from dataclasses import dataclass, field

import numpy as np

from app.candlestick.detectors import detect_candlestick_patterns
from app.candlestick.patterns import CandleParams
from app.core.events import Event
from app.feature_engineering.indicators import atr as atr_fn
from app.market_data.bars import Bars
from app.market_structure.bos import detect_structure_breaks
from app.market_structure.liquidity import detect_equal_levels, detect_liquidity_sweeps
from app.market_structure.swings import Swing, find_swings, structure_bias
from app.price_action.breaker_blocks import detect_breaker_blocks
from app.price_action.fvg import detect_fvg
from app.price_action.order_blocks import detect_order_blocks
from app.price_action.premium_discount import premium_discount
from app.price_action.supply_demand import detect_supply_demand


@dataclass
class PriceActionParams:
    swing_left: int = 3
    swing_right: int = 3
    atr_period: int = 14
    candle: CandleParams = field(default_factory=CandleParams)


@dataclass
class PriceActionResult:
    atr: np.ndarray
    swings: list[Swing]
    trend: np.ndarray  # structure trend per bar
    bias: int
    candles: list[Event]
    breaks: list[Event]
    equal_levels: list[Event]
    sweeps: list[Event]
    fvgs: list[Event]
    order_blocks: list[Event]
    breakers: list[Event]
    zones: list[Event]
    premium_discount: Event | None

    def all_events(self) -> list[Event]:
        evs = (self.candles + self.breaks + self.equal_levels + self.sweeps + self.fvgs + self.order_blocks
               + self.breakers + self.zones + ([self.premium_discount] if self.premium_discount else []))
        return sorted(evs, key=lambda e: (e.idx, e.kind))


def analyze_price_action(b: Bars, params: PriceActionParams | None = None) -> PriceActionResult:
    p = params or PriceActionParams()
    a = atr_fn(b.h, b.l, b.c, p.atr_period)
    swings = find_swings(b, p.swing_left, p.swing_right)
    breaks, trend = detect_structure_breaks(b, swings)
    obs = detect_order_blocks(b, breaks, a)
    return PriceActionResult(
        atr=a, swings=swings, trend=trend, bias=structure_bias(swings, len(b) - 1) if len(b) else 0,
        candles=detect_candlestick_patterns(b, p.candle), breaks=breaks,
        equal_levels=detect_equal_levels(b, swings, a), sweeps=detect_liquidity_sweeps(b, swings),
        fvgs=detect_fvg(b, a), order_blocks=obs, breakers=detect_breaker_blocks(b, obs),
        zones=detect_supply_demand(b, a), premium_discount=premium_discount(b, swings),
    )
