"""Historical analogue evidence for one candidate trade (nearest historical situations in the SAME instrument/timeframe).

Wraps the existing, tested analogue engine (point-in-time feature matrix, robust scaling fitted on library rows only,
library restricted to rows whose outcome was fully known at the query bar, minimum spacing between picks) and adds:
  * direction-specific outcomes (TP-before-SL, MFE, MAE) instead of long-only numbers,
  * forward returns at several horizons (H/4, H/2, H bars) in ATR units,
  * an explicit sample-quality verdict and a comparison against the unconditional base rate.
Similarity ranks resemblance only. The numbers are HISTORICAL FREQUENCIES of similar situations, not the probability that
the current trade will succeed.
"""
from dataclasses import dataclass

import numpy as np

from app.feature_engineering.features import FEATURE_NAMES, compute_features
from app.feature_engineering.labels import LabelConfig, Labels, triple_barrier
from app.historical_engine.analogues import AnalogueConfig, find_analogues
from app.historical_engine.stats import freq, mean_ci
from app.market_data.bars import Bars
from app.opportunities.config import StyleProfile
from app.price_action.engine import PriceActionResult


@dataclass
class AnalogueContext:
    """Features and labels are computed once per (timeframe, label config) and reused by every candidate on that timeframe."""
    X: np.ndarray
    labels: Labels


def build_context(bars: Bars, pa: PriceActionResult, prof: StyleProfile) -> AnalogueContext | None:
    if len(bars) < 100:
        return None
    _, X = compute_features(bars, pa)
    return AnalogueContext(X, triple_barrier(bars, pa.atr, LabelConfig(prof.horizon_bars, prof.tp_atr, prof.sl_atr)))


def sample_quality(n: int) -> str:
    return "insufficient" if n < 30 else "limited" if n < 100 else "moderate"


def _summ(x: np.ndarray) -> dict | None:
    x = x[np.isfinite(x)]
    m = mean_ci(x)
    if not m:
        return None
    return {**m, "median": float(np.median(x)), "pct_positive": float((x > 0).mean())}


def setup_analogues(bars: Bars, pa: PriceActionResult, ctx: AnalogueContext | None, prof: StyleProfile, direction: str | None,
                    symbol: str, timeframe: str, show: int = 12) -> dict:
    base = {"available": False, "direction": direction, "timeframe": timeframe, "symbol": symbol,
            "kind": "historical_frequency (not a probability of the current trade succeeding)", "features_used": FEATURE_NAMES}
    if ctx is None:
        return {**base, "reason": f"only {len(bars)} bars (need >= 100 to build features)", "n_obs": 0, "sample_quality": "insufficient"}
    res = find_analogues(bars, ctx.X, ctx.labels, cfg=AnalogueConfig(k=50, min_separation=12))
    if res.n_obs == 0 or not res.neighbors:
        return {**base, "reason": res.reason, "n_library": res.n_library, "n_obs": 0, "sample_quality": "insufficient"}
    lab, H = ctx.labels, prof.horizon_bars
    hs = sorted({max(1, H // 4), max(1, H // 2), H})
    idx = np.array([nb["idx"] for nb in res.neighbors])
    sign = -1.0 if direction == "SELL" else 1.0
    a = pa.atr[idx]
    entry = bars.o[idx + 1]
    fwd = {f"{h}": _summ(sign * (bars.c[idx + h] - entry) / a) for h in hs}
    mfe = lab.mfe_atr[idx] if sign > 0 else lab.mae_atr[idx]
    mae = lab.mae_atr[idx] if sign > 0 else lab.mfe_atr[idx]
    res_arr = lab.long_result if sign > 0 else lab.short_result
    k_hit = int((res_arr[idx] == 1).sum())
    k_stop = int((res_arr[idx] == -1).sum())
    tp_first = freq(k_hit, len(idx))
    cand = np.arange(0, max(0, res.query_idx - H + 1))
    cand = cand[lab.valid[cand]]
    base_rate = freq(int((res_arr[cand] == 1).sum()), len(cand))
    edge = (tp_first["frequency"] - base_rate["frequency"]) if base_rate["frequency"] is not None else None
    overlaps = bool(tp_first["ci_low"] is not None and base_rate["frequency"] is not None
                    and tp_first["ci_low"] <= base_rate["frequency"] <= tp_first["ci_high"])
    n = len(idx)
    neighbors = []
    for nb in sorted(res.neighbors, key=lambda r: -r["similarity"])[:show]:
        j = nb["idx"]
        neighbors.append({
            "ts": nb["ts"], "similarity": nb["similarity"], "instrument": symbol, "timeframe": timeframe,
            "forward_return_atr": {f"{h}": float(sign * (bars.c[j + h] - bars.o[j + 1]) / pa.atr[j]) for h in hs},
            "mfe_atr": float(lab.mfe_atr[j] if sign > 0 else lab.mae_atr[j]),
            "mae_atr": float(lab.mae_atr[j] if sign > 0 else lab.mfe_atr[j]),
            "outcome": "tp_first" if res_arr[j] == 1 else "sl_first" if res_arr[j] == -1 else "timeout"})
    return {**base, "available": True, "n_library": res.n_library, "n_obs": n, "horizon_bars": H, "horizons": hs,
            "tp_atr": prof.tp_atr, "sl_atr": prof.sl_atr, "tp_first": tp_first, "sl_first": freq(k_stop, n), "base_rate": base_rate,
            "edge_vs_base": edge, "edge_within_noise": overlaps, "forward_return_atr": fwd, "mfe_atr": _summ(mfe), "mae_atr": _summ(mae),
            "mean_similarity": res.stats["mean_similarity"], "sample_quality": sample_quality(n), "neighbors": neighbors,
            "note": (f"{n} nearest historical situations (>= 12 bars apart) whose outcome was already known at the time. "
                     f"A frequency of similar situations is not the probability this trade works. "
                     + ("The difference from the base rate is within sampling noise. " if overlaps else ""))}
