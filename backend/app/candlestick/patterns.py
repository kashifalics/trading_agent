"""Parameters and operational definitions of the candlestick patterns.

Notation: body=|close-open|, range=high-low, upper=high-max(open,close), lower=min(open,close)-low.
Every pattern at index i uses bars <= i only.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CandleParams:
    doji_body_ratio: float = 0.10  # Doji: body <= 10% of range
    hammer_wick_mult: float = 2.0  # Hammer/Shooting star: dominant wick >= 2x body
    hammer_opp_wick_ratio: float = 0.15  # opposite wick <= 15% of range
    min_body_ratio: float = 0.05  # body must be >= 5% of range (else it's a doji)
    trend_lookback: int = 5  # hammer needs prior decline, shooting star prior advance
    require_trend: bool = True
    pin_wick_ratio: float = 0.66  # Pin bar: dominant wick >= 66% of range
    pin_body_ratio: float = 0.33  # ... body <= 33% of range
    pin_opp_wick_ratio: float = 0.20
    star_body_ratio: float = 0.30  # Morning/Evening star: middle body <= 30% of first body
    first_body_ratio: float = 0.50  # first candle body >= 50% of its range
    min_range: float = 1e-12


PATTERN_DEFINITIONS = {
    "bullish_engulfing": "Bearish bar followed by a bullish bar whose body fully covers the prior body and is larger.",
    "bearish_engulfing": "Bullish bar followed by a bearish bar whose body fully covers the prior body and is larger.",
    "hammer": "Lower wick >= 2x body, upper wick <= 15% of range, body >= 5% of range, after a decline.",
    "shooting_star": "Upper wick >= 2x body, lower wick <= 15% of range, body >= 5% of range, after an advance.",
    "doji": "Body <= 10% of the bar range.",
    "pin_bar": "One wick >= 66% of range, body <= 33% of range, opposite wick <= 20% of range.",
    "morning_star": "Long bearish bar, small-bodied bar (<=30% of first body), bullish bar closing above the first bar's midpoint.",
    "evening_star": "Long bullish bar, small-bodied bar (<=30% of first body), bearish bar closing below the first bar's midpoint.",
    "inside_bar": "High below prior high and low above prior low.",
    "outside_bar": "High above prior high and low below prior low.",
}
