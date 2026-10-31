"""Historical analogue search: past bars whose feature profile resembles the query bar."""
from dataclasses import dataclass, field

import numpy as np

from app.feature_engineering.labels import Labels
from app.historical_engine.forward_returns import summarize_forward_returns
from app.historical_engine.mfe_mae import summarize_excursions
from app.historical_engine.similarity import knn, robust_scale_params, scale
from app.historical_engine.stats import freq
from app.market_data.bars import Bars

MIN_OBSERVATIONS = 30


@dataclass
class AnalogueConfig:
    k: int = 50
    min_separation: int = 12  # bars between picked analogues
    min_library: int = 200
    min_observations: int = MIN_OBSERVATIONS


@dataclass
class AnalogueResult:
    query_idx: int
    n_library: int
    n_obs: int
    sufficient: bool
    reason: str | None = None
    neighbors: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"query_idx": self.query_idx, "n_library": self.n_library, "n_obs": self.n_obs,
                "sufficient": self.sufficient, "reason": self.reason, "stats": self.stats,
                "note": "Similarity ranks resemblance only; it is not a probability."}


def find_analogues(b: Bars, X: np.ndarray, labels: Labels, query_idx: int | None = None,
                   cfg: AnalogueConfig | None = None) -> AnalogueResult:
    """Library = bars j with j + horizon <= query_idx (outcome fully known at the query time), finite features.
    Scaling uses library rows only, so nothing from after the query influences the match."""
    cfg = cfg or AnalogueConfig()
    q = len(b) - 1 if query_idx is None else query_idx
    H = labels.cfg.horizon
    qvec = X[q]
    if not np.all(np.isfinite(qvec)):
        return AnalogueResult(q, 0, 0, False, "query bar features not yet defined (warm-up)")
    cand = np.arange(0, max(0, q - H + 1))
    cand = cand[labels.valid[cand] & np.all(np.isfinite(X[cand]), axis=1)] if len(cand) else cand
    if len(cand) < cfg.min_library:
        return AnalogueResult(q, int(len(cand)), 0, False,
                              f"only {len(cand)} comparable historical bars (< {cfg.min_library})")
    lib = X[cand]
    med, sc = robust_scale_params(lib)
    picks = knn(scale(qvec, med, sc), scale(lib, med, sc), cand, cfg.k, cfg.min_separation)
    idx = np.array([p[0] for p in picks])
    n = len(idx)
    long_k = int((labels.long_result[idx] == 1).sum())
    short_k = int((labels.short_result[idx] == 1).sum())
    base_long = int((labels.long_result[cand] == 1).sum())
    base_short = int((labels.short_result[cand] == 1).sum())
    stats = {
        "horizon_bars": H, "tp_atr": labels.cfg.tp_atr, "sl_atr": labels.cfg.sl_atr,
        "long_tp_before_sl": freq(long_k, n), "short_tp_before_sl": freq(short_k, n),
        "base_rate_long": freq(base_long, len(cand)), "base_rate_short": freq(base_short, len(cand)),
        "timeout_or_ambiguous": freq(int(((labels.long_result[idx] == 0) & (labels.short_result[idx] == 0)).sum()), n),
        "forward_return": summarize_forward_returns(labels, idx),
        "excursions": summarize_excursions(labels, idx),
        "mean_similarity": float(np.mean([p[2] for p in picks])),
        "kind": "historical_frequency (not a calibrated probability)",
    }
    neighbors = [{"idx": int(i), "ts": int(b.t[i]), "similarity": s, "distance": d,
                  "forward_return_atr": _f(labels.fwd_ret_atr[i]), "mfe_atr": _f(labels.mfe_atr[i]),
                  "mae_atr": _f(labels.mae_atr[i]), "long_tp_before_sl": bool(labels.long_result[i] == 1),
                  "short_tp_before_sl": bool(labels.short_result[i] == 1)} for i, d, s in picks]
    return AnalogueResult(q, int(len(cand)), n, n >= cfg.min_observations,
                          None if n >= cfg.min_observations else f"only {n} analogues (< {cfg.min_observations})",
                          neighbors, stats)


def _f(x) -> float | None:
    return None if x is None or np.isnan(x) else float(x)
