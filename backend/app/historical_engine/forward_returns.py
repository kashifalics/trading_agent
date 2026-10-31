"""Forward-return summaries of a set of historical bars (ATR-normalised, from Labels)."""
import numpy as np

from app.feature_engineering.labels import Labels
from app.historical_engine.stats import mean_ci


def summarize_forward_returns(labels: Labels, idx: np.ndarray) -> dict:
    r = labels.fwd_ret_atr[idx]
    r = r[~np.isnan(r)]
    if not len(r):
        return {"n": 0}
    q = np.percentile(r, [10, 25, 50, 75, 90])
    return {"n": len(r), "horizon_bars": labels.cfg.horizon, "unit": "ATR",
            "mean_ci": mean_ci(r), "quantiles": dict(zip(["p10", "p25", "p50", "p75", "p90"], map(float, q))),
            "share_positive": float((r > 0).mean())}
