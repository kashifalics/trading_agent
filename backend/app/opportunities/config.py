"""Trading-style profiles, evidence-score weights and execution costs.

Everything that shapes a published number lives here so it can be inspected, tested and changed in ONE place. These values
were chosen BEFORE the validation runs and were not tuned to make any result look better (docs/STRATEGY_VALIDATION.md).
Bump `CONFIG_VERSION` whenever anything in this module changes: it is part of every cache key and every stored scan.
"""
from dataclasses import asdict, dataclass

CONFIG_VERSION = "2026-11-02.1"

ALL_TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "1D", "1W", "1M", "3M", "6M", "12M")

# Where a timeframe's higher-timeframe BIAS comes from (first entries are used when available).
BIAS_TFS: dict[str, tuple[str, ...]] = {
    "1m": ("15m", "1H"), "3m": ("15m", "1H"), "5m": ("30m", "1H"), "15m": ("1H", "4H"), "30m": ("1H", "4H"),
    "1H": ("4H", "1D"), "2H": ("4H", "1D"), "4H": ("1D", "1W"), "1D": ("1W", "1M"), "1W": ("1M", "3M"),
    "1M": ("3M", "12M"), "3M": ("12M",), "6M": ("12M",), "12M": (),
}
# Higher timeframes that may be BUILT from a lower stored one when the native series is too short (never invented).
DERIVE_FROM: dict[str, str] = {"3m": "1m", "2H": "1H", "4H": "1H", "1W": "1D", "3M": "1M", "6M": "1M", "12M": "1M"}

# Round-trip execution cost as a fraction of price (same assumptions as the pattern study; see docs/STRATEGY_VALIDATION.md):
# BTC spot = 2 x (0.10% taker fee + 0.01% slippage) + 0.002% spread; gold CFD/spot = spread + slippage only.
ROUND_TRIP_COST: dict[str, float] = {"BTCUSDT": 2 * (0.0010 + 0.0001) + 0.00002, "XAUUSD": 2 * 0.00005 + 0.0001}
DEFAULT_ROUND_TRIP_COST = 0.0004


def round_trip_cost(symbol: str) -> float:
    return ROUND_TRIP_COST.get(symbol, DEFAULT_ROUND_TRIP_COST)


@dataclass(frozen=True)
class StyleProfile:
    key: str
    label: str
    scope: str  # what kind of analysis this is (never a fundamental forecast)
    setup_tfs: tuple[str, ...]  # candidate setup timeframes (priority order)
    horizon_bars: int  # analogue label horizon / expected-holding basis
    tp_atr: float  # analogue triple-barrier take-profit (ATR multiples)
    sl_atr: float
    min_rr: float
    min_stop_atr: float
    max_stop_atr: float
    max_cost_r: float  # round-trip cost may consume at most this many R, else the trade is not viable
    min_evidence: float  # evidence score needed to publish an actionable (BUY/SELL) setup
    expiry_bars: int  # an untriggered setup expires after this many setup-timeframe bars
    confirm_bars: int  # window in which a confirming event must appear
    max_stale_bars: int  # freshness limit in setup-timeframe bars
    min_bars: int  # minimum stored complete bars for the setup timeframe
    needs_native_resolution: bool = False  # scalping must not rest on aggregated candles


PROFILES: dict[str, StyleProfile] = {
    "scalping": StyleProfile(
        "scalping", "Scalping", "Short-term technical setup on 1m-15m candles; minutes to a few hours.",
        ("1m", "3m", "5m", "15m"), horizon_bars=24, tp_atr=1.5, sl_atr=1.0, min_rr=1.5, min_stop_atr=0.5, max_stop_atr=2.5,
        max_cost_r=0.20, min_evidence=55, expiry_bars=12, confirm_bars=3, max_stale_bars=3, min_bars=300,
        needs_native_resolution=True),
    "intraday": StyleProfile(
        "intraday", "Intraday", "Technical setup on 5m-2H candles intended to be closed within the trading day.",
        ("5m", "15m", "30m", "1H", "2H"), horizon_bars=24, tp_atr=2.0, sl_atr=1.0, min_rr=1.8, min_stop_atr=0.6, max_stop_atr=3.0,
        max_cost_r=0.15, min_evidence=55, expiry_bars=16, confirm_bars=4, max_stale_bars=4, min_bars=300),
    "swing": StyleProfile(
        "swing", "Swing", "Technical setup on 1H-1D candles held for days to a few weeks.",
        ("1H", "2H", "4H", "1D"), horizon_bars=24, tp_atr=2.5, sl_atr=1.0, min_rr=2.0, min_stop_atr=0.75, max_stop_atr=4.0,
        max_cost_r=0.10, min_evidence=55, expiry_bars=20, confirm_bars=4, max_stale_bars=4, min_bars=200),
    "long_term": StyleProfile(
        "long_term", "Long-term", "TECHNICAL price-structure view on 1D-12M candles. Not a fundamental or macro-economic forecast.",
        ("1D", "1W", "1M", "3M", "6M", "12M"), horizon_bars=26, tp_atr=3.0, sl_atr=1.0, min_rr=2.0, min_stop_atr=0.75,
        max_stop_atr=4.0, max_cost_r=0.10, min_evidence=55, expiry_bars=12, confirm_bars=3, max_stale_bars=3, min_bars=120),
}
STYLE_ORDER = tuple(PROFILES)

# Evidence-score component weights (sum to 1.0). See docs/TRADE_SCORING_METHODOLOGY.md.
WEIGHTS: dict[str, float] = {
    "htf_alignment": 0.16, "structure_quality": 0.14, "price_action_confirmation": 0.14, "historical_analogues": 0.14,
    "momentum": 0.08, "volatility_suitability": 0.06, "risk_reward": 0.10, "data_quality": 0.08, "strategy_validation": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

# Caps: the score may not exceed what the strategy's measured validation supports.
VALIDATION_CAPS = {"validated": 100.0, "untested": 65.0, "no_edge": 58.0, "negative": 49.0}
# strategy_validation component value (0..1) per status
VALIDATION_COMPONENT = {"validated": 1.0, "untested": 0.25, "no_edge": 0.1, "negative": 0.0}
VALIDATION_RANK = {"validated": 3, "untested": 2, "no_edge": 1, "negative": 0}

PENALTIES = {
    "conflicting_timeframes": 15.0, "stale_data": 10.0, "stale_data_scalping": 25.0, "gaps_per_gap": 2.0, "gaps_max": 10.0,
    "sample_lt_30": 8.0, "sample_lt_100": 4.0, "excessive_volatility": 8.0, "poor_rr": 3.0,
}

SCORE_LABEL = "Evidence Score — Not Win Probability"

# Setup-detection parameters (documented in docs/MULTI_TIMEFRAME_ANALYSIS.md)
SETUP = {"max_approach_atr": 1.5, "zone_max_age_bars": 300, "stop_buffer_atr": 0.25, "sweep_window_mult": 3, "min_target_gap_atr": 0.5}

SCAN_LOOKBACK_BARS = 2500
MIN_STRUCTURE_BARS = 120


def profile_config() -> dict:
    return {"version": CONFIG_VERSION, "profiles": {k: asdict(v) for k, v in PROFILES.items()}, "weights": WEIGHTS,
            "validation_caps": VALIDATION_CAPS, "penalties": PENALTIES, "setup": SETUP, "bias_tfs": BIAS_TFS,
            "round_trip_cost": ROUND_TRIP_COST}
