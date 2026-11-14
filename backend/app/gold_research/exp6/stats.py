"""Experiment 6 statistics (EXPERIMENT_6_PLAN.md section 6): the random-filter control, Holm, cluster-robust intervals, cost scenarios."""
import numpy as np

from app.gold_research import stats as Stt

BINANCE_TAKER_FEE = 0.001  # per side (plan section 2: reported scenario for BTCUSDT)


def null_means(r: np.ndarray, keep: np.ndarray, strata: np.ndarray, draws: int = 20_000, seed: int = 6) -> np.ndarray:
    """Mean R of `draws` random filters, each keeping exactly as many trades as `keep` does inside every stratum (sampling without
    replacement). Vectorised per stratum in chunks: random keys, the k smallest by argpartition."""
    r, keep, strata = np.asarray(r, float), np.asarray(keep, bool), np.asarray(strata)
    total_k = int(keep.sum())
    if total_k == 0:
        return np.full(draws, np.nan)
    rng = np.random.default_rng(seed)
    total = np.zeros(draws)
    for s in np.unique(strata):
        m = strata == s
        rs, k = r[m], int(keep[m].sum())
        n = len(rs)
        if k == 0:
            continue
        if k == n:
            total += rs.sum()
            continue
        chunk = max(1, min(500, 2_000_000 // n))
        for a in range(0, draws, chunk):
            b = min(draws, a + chunk)
            keys = rng.random((b - a, n))
            pick = np.argpartition(keys, k - 1, axis=1)[:, :k]
            total[a:b] += rs[pick].sum(axis=1)
    return total / total_k


def random_filter_p(r: np.ndarray, keep: np.ndarray, strata: np.ndarray, draws: int = 20_000, seed: int = 6) -> float:
    """One-sided p: share of random filters (same count per stratum) whose mean R is at least the kept trades' mean."""
    r, keep = np.asarray(r, float), np.asarray(keep, bool)
    if keep.sum() == 0:
        return 1.0
    kept = float(r[keep].mean())
    nulls = null_means(r, keep, strata, draws, seed)
    return float((1 + np.sum(nulls >= kept - 1e-12)) / (draws + 1))


def holm_dict(ps: dict[str, float]) -> dict[str, float]:
    keys = list(ps)
    adj = Stt.holm(np.array([ps[k] for k in keys], dtype=float)) if keys else []
    return {k: float(v) for k, v in zip(keys, adj)}


def cluster_ci(r_kept: np.ndarray, w_kept: np.ndarray, r_dropped: np.ndarray, w_dropped: np.ndarray) -> tuple[float, float]:
    """95% interval of mean(kept) - mean(dropped), each mean with standard errors clustered by week."""
    a, b = Stt.clustered_mean(np.asarray(r_kept, float), np.asarray(w_kept)), Stt.clustered_mean(np.asarray(r_dropped, float), np.asarray(w_dropped))
    diff = a["mean"] - b["mean"]
    se = float(np.sqrt(a["se"] ** 2 + b["se"] ** 2)) if np.isfinite(a["se"]) and np.isfinite(b["se"]) else float("nan")
    return (diff - 1.96 * se, diff + 1.96 * se) if np.isfinite(se) else (float("nan"), float("nan"))


def cost_scenarios(r: np.ndarray, spread_entry: np.ndarray, risk_px: np.ndarray, entry_px: np.ndarray) -> dict[str, np.ndarray]:
    """r_2x: one more spread per trade (doubled costs); r_fee: Binance taker fee 0.1% per side on entry and exit."""
    r, sp, risk, entry = (np.asarray(x, float) for x in (r, spread_entry, risk_px, entry_px))
    return {"r_2x": r - sp / risk, "r_fee": r - 2 * BINANCE_TAKER_FEE * entry / risk}
