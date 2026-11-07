"""Signal-engine configuration: timeframe chains, groups, score weights, thresholds and costs (docs/SIGNAL_ENGINE.md).

Everything that shapes a published number lives here so it can be inspected, tested and changed in ONE place. The values were
set a priori (not fitted to outcomes). Bump CONFIG_VERSION whenever anything here changes: it is stored with every replay run.
"""
from dataclasses import asdict, dataclass

from app.core.config import get_settings

CONFIG_VERSION = "2026-11-07.1"

SIGNAL_TFS = ("1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "1D", "1W", "1M", "3M", "6M", "12M")


@dataclass(frozen=True)
class Group:
    key: str
    label: str
    min_rr: float  # TP1 must offer at least this reward:risk
    min_stop_atr: float
    max_stop_atr: float
    max_cost_r: float  # round-trip spread may consume at most this share of the risk
    confirm_bars: int  # window (setup-TF bars) for touches / confirmations
    expiry_bars: int  # an actionable plan is valid for this many setup-TF bars
    max_stale_bars: int  # freshness limit of the setup timeframe
    session_filter: bool  # London/New York session check applies


GROUPS: dict[str, Group] = {
    "scalping": Group("scalping", "Scalping", 2.0, 0.5, 2.5, 0.25, 3, 12, 3, True),
    "intraday": Group("intraday", "Intraday", 2.0, 0.6, 3.0, 0.20, 4, 16, 4, True),
    "swing": Group("swing", "Swing", 2.0, 0.75, 4.0, 0.15, 4, 20, 3, False),
    "position": Group("position", "Position", 2.0, 0.75, 4.0, 0.10, 3, 12, 2, False),
}


@dataclass(frozen=True)
class Chain:
    setup: str
    bias: tuple[str, ...]  # (intermediate, higher) timeframes that set the directional context
    confirm: str  # lower timeframe that must confirm the entry
    group: str


CHAINS: dict[str, Chain] = {c.setup: c for c in (
    Chain("1m", ("15m", "1H"), "1m", "scalping"),
    Chain("3m", ("15m", "1H"), "1m", "scalping"),
    Chain("5m", ("1H", "4H"), "1m", "scalping"),
    Chain("15m", ("1H", "4H"), "5m", "intraday"),
    Chain("30m", ("4H", "1D"), "5m", "intraday"),
    Chain("1H", ("4H", "1D"), "15m", "intraday"),
    Chain("2H", ("4H", "1D"), "15m", "intraday"),
    Chain("4H", ("1D", "1W"), "1H", "swing"),
    Chain("1D", ("1W", "1M"), "4H", "swing"),
    Chain("1W", ("1M", "3M"), "1D", "position"),
    Chain("1M", ("3M", "12M"), "1W", "position"),
    Chain("3M", ("12M",), "1M", "position"),
    Chain("6M", ("12M",), "1M", "position"),
    Chain("12M", (), "3M", "position"),
)}

# 100-point confluence score: factor -> maximum points. See docs/SIGNAL_ENGINE.md.
FACTORS: dict[str, int] = {
    "htf_alignment": 20, "market_structure": 20, "liquidity": 15, "entry_zone": 15, "ltf_confirmation": 15, "risk_reward": 10,
    "session_volatility": 5,
}
assert sum(FACTORS.values()) == 100
FACTOR_LABELS = {
    "htf_alignment": "Higher-timeframe alignment", "market_structure": "Market structure", "liquidity": "Liquidity event",
    "entry_zone": "Entry-zone quality", "ltf_confirmation": "Lower-timeframe confirmation", "risk_reward": "Risk-to-reward",
    "session_volatility": "Session and volatility",
}
POINTS = {
    "htf_each": 10, "structure_class": 10, "fresh_break": 10, "sweep_and_break": 15, "sweep_only": 8, "at_zone": 7, "discount_premium": 4,
    "zone_confluence": 4, "ltf_structure": 8, "rejection_candle": 7, "rr_at_min": 5, "rr_full": 10, "volatility": 3, "session": 2,
}
THRESHOLDS = {"signal": 60, "preferred": 70, "watch": 40}

PARAMS = {
    "lookback_bars": 500,  # candles per timeframe handed to the engine (live and replay alike)
    "min_setup_bars": 120,
    "min_bias_bars": 60,
    "zone_max_age_bars": 300,
    "max_approach_atr": 1.5,  # a zone this close (ATR) ahead of price supports a limit plan
    "at_zone_tolerance_atr": 0.5,  # after a touch, price may be this far beyond the zone's near edge for a market entry
    "touch_window_mult": 2,  # touch must be within confirm_bars * this
    "sweep_window_mult": 3,  # sweeps / sweep-breaks must be within confirm_bars * this
    "stop_buffer_atr": 0.25,
    "protect_swing_atr": 1.0,
    "min_target_gap_atr": 0.5,
    "obstacle_block_rr": 1.0,  # a strong opposing level closer than this (R) blocks the plan; further (but before TP1) costs the R:R points
    "fresh_break_bars": 20,
    "retest_max_age_bars": 30,
    "retest_band_atr": 0.15,
    "confluence_atr": 0.5,
    "vol_pct_low": 0.15,
    "vol_pct_high": 0.90,
    "session_start_utc": 7,
    "session_end_utc": 20,
    "abnormal_spread_mult": 3.0,
    "ema_period": 50,
    "ema_slope_bars": 10,
}
# Overall instrument bias: weighted vote of timeframe classes (macro first).
OVERALL_WEIGHTS = {"1W": 3, "1D": 3, "4H": 2, "1H": 2, "15m": 1, "5m": 1}
GROUP_TFS = {"Short-term": ("1m", "3m", "5m"), "Intraday": ("15m", "30m", "1H", "2H"), "Swing": ("4H", "1D"), "Long-term": ("1W", "1M")}

# Round-trip spread in PRICE units (what the user's broker charges); anything not listed pays DEFAULT_SPREAD_FRAC of price.
DEFAULT_SPREAD_FRAC = 0.0002
STATE_ORDER = {"ENTRY_READY": 5, "WAITING_FOR_CONFIRMATION": 4, "SETUP_DEVELOPING": 3, "WATCHLIST": 2, "TRADE_INVALIDATED": 1,
               "TRADE_EXPIRED": 1, "NO_SETUP": 0}
PROBABILITY_NOTE = "Win probability: not yet statistically validated"
SCORE_LABEL = "Confluence score (setup quality, not a win probability)"


def _pairs(raw: str) -> dict[str, str]:
    out = {}
    for part in (raw or "").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            if k.strip() and v.strip():
                out[k.strip().upper()] = v.strip()
    return out


def spreads() -> dict[str, float]:
    out = {}
    for k, v in _pairs(get_settings().signal_spreads).items():
        try:
            out[k] = float(v)
        except ValueError:
            continue
    return out


def spread_for(symbol: str, price: float) -> float:
    """Round-trip spread in price units for this instrument."""
    sp = spreads().get(symbol.upper())
    return sp if sp is not None else DEFAULT_SPREAD_FRAC * float(price)


def provider_override(symbol: str) -> str | None:
    v = _pairs(get_settings().signal_provider_overrides).get(symbol.upper())
    return v.lower() if v else None


def config_payload() -> dict:
    return {"version": CONFIG_VERSION, "groups": {k: asdict(v) for k, v in GROUPS.items()},
            "chains": {k: asdict(v) for k, v in CHAINS.items()}, "factors": FACTORS, "factor_labels": FACTOR_LABELS, "points": POINTS,
            "thresholds": THRESHOLDS, "params": PARAMS, "spreads": spreads(), "default_spread_frac": DEFAULT_SPREAD_FRAC,
            "overall_weights": OVERALL_WEIGHTS, "score_label": SCORE_LABEL, "probability_note": PROBABILITY_NOTE}
