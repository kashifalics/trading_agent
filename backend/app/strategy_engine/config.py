"""Frozen parameters of strategy engine v2 (docs/engine_v2/DESIGN.md). Changing any value is a new experiment, not a tweak."""
from dataclasses import dataclass

ENGINE_VERSION = "v2-2026-11-13.1"

# Signal timeframes, in display order. 8H is built from complete 4H candles (two per bucket, same trading day).
SIGNAL_TFS = ("1m", "3m", "5m", "15m", "30m", "1H", "4H", "8H", "1D", "1W", "1M")


@dataclass(frozen=True)
class Group:
    key: str
    label: str
    min_stop_atr: float
    max_stop_atr: float
    max_cost_r: float  # the round-trip spread may use at most this share of the risk
    pending_expiry_bars: int  # a pending plan expires after this many signal-TF candles
    rank: int  # tie-break between timeframes: lower ranks first (costs weigh more on short timeframes)


GROUPS = {
    "scalping": Group("scalping", "Scalping", 0.5, 3.0, 0.25, 12, 3),
    "intraday": Group("intraday", "Intraday", 0.5, 3.0, 0.20, 16, 1),
    "swing": Group("swing", "Swing", 0.5, 4.0, 0.15, 20, 0),
    "position": Group("position", "Position", 0.5, 4.0, 0.10, 12, 2),
}


@dataclass(frozen=True)
class Chain:
    tf: str
    context: str | None  # regime and direction
    trigger: str | None  # lower-timeframe confirmation (reported, not required)
    group: str


CHAINS = {c.tf: c for c in (
    Chain("1m", "15m", None, "scalping"), Chain("3m", "30m", "1m", "scalping"), Chain("5m", "1H", "1m", "scalping"),
    Chain("15m", "1H", "5m", "intraday"), Chain("30m", "4H", "5m", "intraday"), Chain("1H", "4H", "15m", "intraday"),
    Chain("4H", "1D", "1H", "swing"), Chain("8H", "1D", "1H", "swing"), Chain("1D", "1W", "4H", "swing"),
    Chain("1W", "1M", "1D", "position"), Chain("1M", None, "1W", "position"),
)}

MIN_BARS = 120  # fewer complete candles: regime UNKNOWN (insufficient data), no strategy runs

REGIME = {
    "atr_pct_abnormal": 0.95, "shock_bar_atr": 3.0,
    "trend_adx": 25.0, "trend_er": 0.30, "trend_slope_atr": 0.5,
    "consol_bbw_pct": 0.20, "consol_adx": 20.0,
    "range_adx": 20.0, "range_er": 0.25, "range_span_min_atr": 3.0, "range_span_max_atr": 12.0,
}

STOP_BUFFER_ATR = 0.1
CHASE_R = 0.3  # a market setup is READY only while price is within 0.3R of the entry
MAX_ENTRY_DISTANCE_ATR = 5.0
READY_EXPIRY_BARS = 2
TARGETS = {"tp1_min_r": 1.5, "tp1_max_r": 4.0, "tp1_default_r": 2.0, "tp2_max_r": 6.0, "tp2_default_r": 3.0, "tp3_max_r": 10.0,
           "tp3_default_r": 5.0, "min_gap_r": 0.75}

STRATEGY_NAMES = {
    "trend_pullback": "Trend-following pullback",
    "breakout_retest": "Breakout and retest",
    "momentum_continuation": "Momentum continuation",
    "range_reversion": "Range mean reversion",
    "sweep_reversal": "Liquidity-sweep reversal",
    "volatility_expansion": "Volatility expansion",
}
# Duplicate market events keep the most specific strategy (DESIGN section 7)
SPECIFICITY = ("sweep_reversal", "breakout_retest", "volatility_expansion", "trend_pullback", "momentum_continuation", "range_reversion")

COMPATIBLE = {
    "TRENDING": ("trend_pullback", "breakout_retest", "momentum_continuation", "sweep_reversal"),
    "RANGING": ("breakout_retest", "range_reversion", "sweep_reversal"),
    "CONSOLIDATING": ("breakout_retest", "volatility_expansion"),
    "UNKNOWN": ("breakout_retest", "sweep_reversal", "volatility_expansion"),  # transitional only; insufficient data runs nothing
    "HIGH_VOLATILITY": (),
}

# Research status per strategy, from Experiment 5 (docs/reports/XAUUSD_EXPERIMENT5.md, 2026-11-13): 51 pre-registered cells tested on
# 17 years of gold, none passed. Tested and failed = NOT VALIDATED; never enough signals to test = INSUFFICIENT EVIDENCE.
RESEARCH_STATUS = {
    "trend_pullback": "NOT VALIDATED", "breakout_retest": "NOT VALIDATED", "momentum_continuation": "NOT VALIDATED",
    "sweep_reversal": "NOT VALIDATED", "volatility_expansion": "NOT VALIDATED", "range_reversion": "INSUFFICIENT EVIDENCE",
}
RESEARCH_NOTE = ("Experiment 5 tested these strategies on 17 years of gold (pre-registered, real bid/ask costs, matched random "
                 "controls, multiple-testing correction): none passed (docs/reports/XAUUSD_EXPERIMENT5.md). Every plan is a hypothetical "
                 "trade plan with no verified edge and no win probability.")
PLAN_LABEL_UNVALIDATED = "UNVALIDATED — HYPOTHETICAL TRADE PLAN"
PLAN_LABEL_VALIDATED = "VALIDATED TRADE PLAN"

# ---- confirmation layer (docs/engine_v2/CONFIRMATION_DESIGN.md) ----------------------------------------------------------------------
# What the candle volume is, in the customer's words (design section 3). Spot FX, gold, US30 and oil have no market-wide volume.
VOLUME_LABELS = {"base": "Exchange volume (Binance only)", "tick": "Tick volume (broker)", "venue": "Venue volume (Dukascopy)",
                 "none": "No volume"}
VOLUME_RULES = {"weeks": 20, "min_samples": 4, "min_nonzero": 0.95, "max_run": 10, "window": 2000}
# VSA bar measures and events (design section 5). Fixed for Experiment 6: never tuned on data.
VSA_T = {"wide": 1.2, "narrow": 0.6, "top": 0.67, "bottom": 0.33, "low": 0.7, "high": 1.5, "ultra": 2.5, "prior_n": 8,
         "prior_atr": 2.0, "confirm_n": 3, "test_n": 10, "test_atr": 0.3, "absorb_n": 5, "absorb_atr": 1.0, "level_n": 50}

# Contract size per lot, for position sizing (risk.py)
CONTRACT_SIZE = {"XAUUSD": 100.0, "EURUSD": 100_000.0, "GBPUSD": 100_000.0, "US30": 1.0, "USOIL": 1_000.0, "BTCUSDT": 1.0}
# Currency legs for exposure checks: (base, quote). A BUY is +base -quote.
LEGS = {"XAUUSD": ("XAU", "USD"), "EURUSD": ("EUR", "USD"), "GBPUSD": ("GBP", "USD"), "US30": ("US30", "USD"),
        "USOIL": ("OIL", "USD"), "BTCUSDT": ("BTC", "USD")}
