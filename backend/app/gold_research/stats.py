"""Statistics for pattern trades versus their matched controls (docs/PATTERN_STUDY.md).

* Edge of one trade = its R minus the mean R of matched controls in its stratum.
* Standard errors are clustered on time blocks of max(one week, the holding period), because trades that overlap in time are
  not independent; the uncertainty of the control means is added. p-values are one-sided (edge > 0), t with (clusters - 1) df.
* The minimum detectable effect (80% power at the test's significance level) is reported for every test, so "no edge found"
  can be read as "no edge larger than X".
* Multiple testing: Benjamini-Hochberg across all discovery tests, Holm across all validation tests (one family).
"""
import math

import numpy as np
from scipy import stats

WEEK = 7 * 86400


def cluster_ids(entry_ts: np.ndarray, hold_seconds: float) -> np.ndarray:
    return entry_ts // int(max(WEEK, hold_seconds))


def clustered_mean(x: np.ndarray, clusters: np.ndarray, extra_var: float = 0.0) -> dict:
    """Mean, cluster-robust SE (plus `extra_var` added to the variance of the mean), one-sided p (mean > 0), clusters."""
    n = len(x)
    if n < 3:
        return {"n": n, "mean": float(x.mean()) if n else float("nan"), "se": float("nan"), "p": 1.0, "clusters": 0}
    mu = float(x.mean())
    u, inv = np.unique(clusters, return_inverse=True)
    g = len(u)
    if g < 3:
        return {"n": n, "mean": mu, "se": float("nan"), "p": 1.0, "clusters": g}
    sums = np.bincount(inv, weights=x - mu)
    var = float((sums ** 2).sum()) * g / (g - 1) / n ** 2 + extra_var
    se = math.sqrt(var)
    p = float(stats.t.sf(mu / se, g - 1)) if se > 0 else (0.0 if mu > 0 else 1.0)
    return {"n": n, "mean": mu, "se": se, "p": p, "clusters": g}


def edge_stats(r: np.ndarray, ctrl_mean: np.ndarray, ctrl_var: np.ndarray, ctrl_n: np.ndarray, ctrl_cell: np.ndarray,
               entry_ts: np.ndarray, hold_seconds: float) -> dict:
    ok = np.isfinite(r) & np.isfinite(ctrl_mean)
    r, cm, cv, cn, cell, ts = r[ok], ctrl_mean[ok], ctrl_var[ok], ctrl_n[ok], ctrl_cell[ok], entry_ts[ok]
    n = len(r)
    if n == 0:
        return {"n": 0}
    cl = cluster_ids(ts, hold_seconds)
    # variance of the average control mean: trades that share a stratum share its sampling error (sum over strata of
    # (share of trades)^2 * variance / controls)
    _, first, counts = np.unique(cell, return_index=True, return_counts=True)
    extra = float(((counts / n) ** 2 * np.nan_to_num(cv[first]) / np.maximum(cn[first], 1)).sum())
    e = clustered_mean(r - cm, cl, extra)
    raw = clustered_mean(r, cl)
    return {"n": n, "clusters": e["clusters"], "win_rate": float((r > 0).mean()), "mean_r": raw["mean"], "mean_r_se": raw["se"],
            "p_profit": raw["p"], "ctrl_mean_r": float(cm.mean()), "edge": e["mean"], "edge_se": e["se"], "p_edge": e["p"],
            "profit_factor": float(r[r > 0].sum() / -r[r < 0].sum()) if (r < 0).any() else None}


def mde(se: float, alpha: float, power: float = 0.8) -> float:
    """Smallest true edge this test would detect with the given power at one-sided level alpha."""
    if not np.isfinite(se):
        return float("nan")
    return float((stats.norm.isf(alpha) + stats.norm.ppf(power)) * se)


def bh(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg q-values."""
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, i in zip(range(n, 0, -1), order[::-1]):
        prev = min(prev, p[i] * n / rank)
        q[i] = prev
    return q


def holm(p: np.ndarray) -> np.ndarray:
    """Holm-adjusted p-values."""
    n = len(p)
    out = np.empty(n)
    run = 0.0
    for rank, i in enumerate(np.argsort(p)):
        run = max(run, min(1.0, p[i] * (n - rank)))
        out[i] = run
    return out


def drawdown_r(r: np.ndarray) -> float:
    """Largest peak-to-trough fall of the cumulative R of trades taken in time order (no overlap handling)."""
    if len(r) == 0:
        return 0.0
    c = np.cumsum(r)
    return float((np.maximum.accumulate(np.r_[0.0, c])[1:] - c).max())
