"""Phase 4: pre-registered pattern combinations and multi-timeframe profiles (brief Parts 4K and 8).

Neither needs new simulation: a combination "A then B within N candles" is the subset of B's trades preceded by an A event in the
same direction (or a non-directional A) on the same timeframe, entered and stopped exactly like B; a multi-timeframe variant is the
subset of setup-timeframe trades whose higher-timeframe state at the signal close met a condition. Both are tested with the same
main setting, the same matched controls and in the same multiple-testing family as single patterns.

The lists below were fixed before any result was seen (staged discovery: pairs chosen on trading logic, not mined).
"""
import numpy as np
import polars as pl

from app.feature_engineering.indicators import atr as atr_fn
from app.feature_engineering.indicators import ema
from app.gold_research.events import bars_from_frame
from app.historical.config import TF_SECONDS
from app.historical.store import load_tf
from app.historical.sync import bar_close, last_closed
from app.market_structure.bos import detect_structure_breaks
from app.market_structure.swings import find_swings

# (name, A, B, window in candles): B is the trigger whose entry and stop are used.
PAIRS = [
    ("sweep+choch", "liquidity_sweep", "CHoCH", 10), ("sweep+bos", "liquidity_sweep", "BOS", 10),
    ("sweep+order_block", "liquidity_sweep", "order_block", 10), ("sweep+mss", "liquidity_sweep", "market_structure_shift", 20),
    ("bos+displacement", "BOS", "displacement", 10), ("choch+fvg", "CHoCH", "fvg", 10),
    ("support_rejection+engulfing", "support_rejection", "engulfing_bull", 2),
    ("resistance_rejection+engulfing", "resistance_rejection", "engulfing_bear", 2),
    ("retest+momentum", "retest", "momentum_continuation", 10),
    ("sweep+double_bottom", "liquidity_sweep", "double_bottom", 20), ("sweep+double_top", "liquidity_sweep", "double_top", 20),
    ("equal_highs+displacement", "equal_highs", "displacement", 30), ("equal_lows+displacement", "equal_lows", "displacement", 30),
    ("pdh_sweep+choch", "pd_high_sweep", "CHoCH", 12), ("pdl_sweep+choch", "pd_low_sweep", "CHoCH", 12),
    ("pdh_sweep+engulfing", "pd_high_sweep", "engulfing_bear", 3), ("pdl_sweep+engulfing", "pd_low_sweep", "engulfing_bull", 3),
    ("asia_high_sweep+bos", "asia_high_sweep", "BOS", 12), ("asia_low_sweep+bos", "asia_low_sweep", "BOS", 12),
    ("london_high_sweep+choch", "london_high_sweep", "CHoCH", 24), ("london_low_sweep+choch", "london_low_sweep", "CHoCH", 24),
    ("breaker+fvg", "breaker_block", "fvg", 10), ("failed_breakout+reclaim", "failed_breakout", "structural_reclaim", 20),
    ("compression+sweep", "compression", "liquidity_sweep", 10), ("atr_expansion+bos", "atr_expansion", "BOS", 5),
    ("squeeze+bos", "squeeze_release", "BOS", 5), ("swing_failure+choch", "swing_failure", "CHoCH", 10),
    ("higher_low+bos", "higher_low", "BOS", 10), ("lower_high+bos", "lower_high", "BOS", 10),
    ("pdl_sweep+fvg", "pd_low_sweep", "fvg", 10), ("pdh_sweep+fvg", "pd_high_sweep", "fvg", 10),
    ("grab_reversal+order_block", "grab_reversal", "order_block", 10), ("inside_compression+nr_breakout", "inside_bar_compression", "nr_breakout", 5),
    ("rejection_bull+bos", "rejection_bull", "BOS", 10), ("rejection_bear+bos", "rejection_bear", "BOS", 10),
]

# Brief Part 8: macro context, directional bias, setup, confirmation (execution is the setup timeframe's simulation here).
PROFILES = {
    "scalp": {"context": "H4", "bias": "H1", "setup": "M15", "confirm": "M5"},
    "intraday": {"context": "D1", "bias": "H4", "setup": "H1", "confirm": "M15"},
    "swing": {"context": "W1", "bias": "D1", "setup": "H4", "confirm": "H1"},
}
MTF_PATTERNS = ["BOS", "CHoCH", "market_structure_shift", "liquidity_sweep", "swing_failure", "grab_reversal", "sweep_to_bos", "fvg",
                "order_block", "breaker_block", "demand_zone", "supply_zone", "engulfing_bull", "engulfing_bear", "pin_bar_bull",
                "pin_bar_bear", "pd_high_sweep", "pd_low_sweep", "support_rejection", "resistance_rejection", "retest", "failed_breakout"]
MTF_VARIANTS = ("bias", "bias+context", "full", "counter")
CONFIRM_BARS = 6  # confirmation-timeframe structure break in the trade's direction within this many confirmation candles


def combo_flags(trades: pl.DataFrame, events: pl.DataFrame) -> pl.DataFrame:
    """Adds combo:<name> boolean columns: B trade preceded (same candle allowed) by an A event within the window."""
    idx = trades["idx"].to_numpy()
    d = trades["direction"].to_numpy()
    pat = trades["pattern"].to_numpy()
    cols = {}
    for name, a, b, win in PAIRS:
        flag = np.zeros(trades.height, dtype=bool)
        isb = pat == b
        if isb.any():
            ev = events.filter(pl.col("pattern") == a)
            for dd in (1, -1):
                ai = np.sort(ev.filter((pl.col("direction") == dd) | (pl.col("direction") == 0))["idx"].to_numpy())
                m = isb & (d == dd)
                if len(ai) and m.any():
                    j = idx[m]
                    flag[m] = np.searchsorted(ai, j, side="right") > np.searchsorted(ai, j - win, side="left")
        cols[f"combo:{name}"] = flag
    return trades.with_columns(**{k: pl.Series(v) for k, v in cols.items()})


def tf_state(symbol: str, tf: str, segment: str) -> dict[str, np.ndarray]:
    """Close times, structure trend and the time of the last structure break (with its direction) for one timeframe."""
    df = load_tf(symbol, tf, upto=segment)
    b = bars_from_frame(df, TF_SECONDS[tf])
    breaks, trend = detect_structure_breaks(b, find_swings(b))
    close = bar_close(tf, b.t)
    last_dir = np.zeros(len(b), dtype=np.int8)
    last_t = np.full(len(b), -1, dtype=np.int64)
    bi = np.array([e.idx for e in breaks], dtype=np.int64)
    bd = np.array([1 if e.direction == "bullish" else -1 for e in breaks], dtype=np.int8)
    if len(bi):
        k = np.searchsorted(bi, np.arange(len(b)), side="right") - 1
        ok = k >= 0
        last_dir[ok] = bd[k[ok]]
        last_t[ok] = close[bi[k[ok]]]
    e50 = ema(b.c, 50)
    slope = np.r_[np.full(20, np.nan), (e50[20:] - e50[:-20])] / np.maximum(atr_fn(b.h, b.l, b.c, 14), 1e-9)
    regime = np.select([slope >= 0.3, slope <= -0.3], [1, -1], 0)
    return {"close": close, "trend": trend, "regime": regime, "break_dir": last_dir, "break_close": last_t}


def mtf_flags(trades: pl.DataFrame, tf: str, states: dict[str, dict]) -> pl.DataFrame:
    """Adds mtf:<profile>:<variant> columns for trades of a profile's setup timeframe (all False elsewhere).

    bias          the bias timeframe's structure trend at the signal close equals the trade direction
    bias+context  and the context timeframe's EMA50 slope regime agrees
    full          and the confirmation timeframe's latest structure break (within CONFIRM_BARS of its candles) agrees
    counter       the bias timeframe's trend is AGAINST the trade (countertrend: pullback-or-reversal question)
    """
    sig_close = trades["signal_ts"].to_numpy() + TF_SECONDS[tf]
    d = trades["direction"].to_numpy()
    cols = {}
    for prof, p in PROFILES.items():
        for v in MTF_VARIANTS:
            cols[f"mtf:{prof}:{v}"] = np.zeros(trades.height, dtype=bool)
        if p["setup"] != tf or any(p[k] not in states for k in ("bias", "context", "confirm")):
            continue
        sb, sc, sf = states[p["bias"]], states[p["context"]], states[p["confirm"]]
        ib, ic, i_f = last_closed(sb["close"], sig_close), last_closed(sc["close"], sig_close), last_closed(sf["close"], sig_close)
        tb = np.where(ib >= 0, sb["trend"][np.maximum(ib, 0)], 0)
        rc = np.where(ic >= 0, sc["regime"][np.maximum(ic, 0)], 0)
        fd = np.where(i_f >= 0, sf["break_dir"][np.maximum(i_f, 0)], 0)
        ft = np.where(i_f >= 0, sf["break_close"][np.maximum(i_f, 0)], -1)
        recent = (ft >= 0) & (sig_close - ft <= CONFIRM_BARS * TF_SECONDS[p["confirm"]])
        bias = tb == d
        ctx = rc == d
        cols[f"mtf:{prof}:bias"] = bias
        cols[f"mtf:{prof}:bias+context"] = bias & ctx
        cols[f"mtf:{prof}:full"] = bias & ctx & recent & (fd == d)
        cols[f"mtf:{prof}:counter"] = tb == -d
    return trades.with_columns(**{k: pl.Series(v) for k, v in cols.items()})


def extra_tests(tf: str) -> list[tuple[str, str, str, str]]:
    """(test name, trigger pattern, flag column, family label) for every combination and multi-timeframe test on `tf`."""
    out = [(name, b, f"combo:{name}", "Combination") for name, _a, b, _w in PAIRS]
    for prof, p in PROFILES.items():
        if p["setup"] != tf:
            continue
        for pat in MTF_PATTERNS:
            for v in MTF_VARIANTS:
                out.append((f"{pat}|{prof}:{v}", pat, f"mtf:{prof}:{v}", "Multi-timeframe"))
    return out
