"""Out-of-sample evaluation: probability quality and cost-aware trade simulation."""
import math

import numpy as np

from app.feature_engineering.labels import Labels


def multiclass_brier(P: np.ndarray, y: np.ndarray) -> float:
    onehot = np.eye(P.shape[1])[y]
    return float(((P - onehot) ** 2).sum(axis=1).mean())


def log_loss(P: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(P[np.arange(len(y)), y], 1e-9, 1)).mean())


def calibration_curve(p: np.ndarray, event: np.ndarray, bins: int = 10) -> dict:
    edges = np.linspace(0, 1, bins + 1)
    out, ece, n = [], 0.0, len(p)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if m.sum() == 0:
            continue
        mp, obs = float(p[m].mean()), float(event[m].mean())
        out.append({"bin_low": float(lo), "bin_high": float(hi), "mean_predicted": mp, "observed": obs, "n": int(m.sum())})
        ece += m.sum() / n * abs(mp - obs)
    return {"bins": out, "ece": float(ece)}


def trade_metrics(R: np.ndarray) -> dict:
    n = len(R)
    if n == 0:
        return {"n_trades": 0}
    wins, losses = R[R > 0], R[R <= 0]
    gross_w, gross_l = float(wins.sum()), float(-losses.sum())
    eq = np.cumsum(R)
    dd = float((np.maximum.accumulate(np.concatenate([[0], eq])) - np.concatenate([[0], eq])).max())
    sd = float(R.std(ddof=1)) if n > 1 else float("nan")
    mean = float(R.mean())
    half = 1.96 * sd / math.sqrt(n) if n > 1 else float("nan")
    return {
        "n_trades": int(n), "win_rate": float((R > 0).mean()),
        "profit_factor": (gross_w / gross_l) if gross_l > 0 else None,
        "expectancy_r": mean, "expectancy_r_ci_low": mean - half if n > 1 else None,
        "expectancy_r_ci_high": mean + half if n > 1 else None,
        "max_drawdown_r": dd, "total_r": float(R.sum()),
        "sharpe_per_trade": (mean / sd) if sd and sd > 0 else None,
        "avg_win_r": float(wins.mean()) if len(wins) else None,
        "avg_loss_r": float(losses.mean()) if len(losses) else None,
    }


def simulate_directions(dirs: np.ndarray, rows: np.ndarray, labels: Labels, atr: np.ndarray, spread: float = 0.0,
                        price: np.ndarray | None = None, cost_frac: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Trade a per-row direction (+1 long, -1 short, 0 none) with the triple-barrier outcome of each row.

    Non-overlapping: a new trade waits for the previous label window to end. R multiples are net of costs:
    `spread` (price units) and `cost_frac` (round-trip fraction of price: 2*fee + 2*slippage + spread) are both
    converted to R by dividing by the stop distance (sl_atr * ATR). Returns (R, indices into `rows`)."""
    rr = labels.cfg.tp_atr / labels.cfg.sl_atr
    R, taken = [], []
    busy_until = -1
    for j, bar in enumerate(rows):
        d = int(dirs[j])
        if d == 0 or bar <= busy_until:
            continue
        res = labels.long_result[bar] if d == 1 else labels.short_result[bar]
        a = atr[j]
        r = rr if res == 1 else -1.0 if res == -1 else float(np.clip(d * labels.fwd_ret_atr[bar] / labels.cfg.sl_atr, -1, rr))
        cost = spread + (cost_frac * price[j] if price is not None else 0.0)
        r -= cost / (labels.cfg.sl_atr * a)
        R.append(r)
        taken.append(j)
        busy_until = int(labels.t1[bar]) if res != 0 else bar + labels.cfg.horizon
    return np.array(R), np.array(taken, dtype=int)


def simulate_signals(P: np.ndarray, rows: np.ndarray, labels: Labels, atr: np.ndarray, spread: float,
                     threshold: float = 0.45, margin: float = 0.10, price: np.ndarray | None = None,
                     cost_frac: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Long if P(long TP first) >= threshold and leads P(short) by `margin` (mirror for short)."""
    p_s, p_l = P[:, 0], P[:, 2]
    dirs = np.where((p_l >= threshold) & (p_l - p_s >= margin), 1, np.where((p_s >= threshold) & (p_s - p_l >= margin), -1, 0))
    return simulate_directions(dirs, rows, labels, atr, spread, price, cost_frac)


def regime_breakdown(R: np.ndarray, taken: np.ndarray, atr_pct: np.ndarray, trend: np.ndarray) -> dict:
    if not len(R):
        return {}
    out: dict = {}
    vol = atr_pct[taken]
    q1, q2 = np.percentile(atr_pct, [33.3, 66.7])
    for name, m in (("low_vol", vol <= q1), ("mid_vol", (vol > q1) & (vol <= q2)), ("high_vol", vol > q2)):
        out[name] = trade_metrics(R[m])
    tr = trend[taken]
    for name, v in (("uptrend", 1), ("downtrend", -1), ("no_structure", 0)):
        out[name] = trade_metrics(R[tr == v])
    return out


def validation_status(report: dict) -> tuple[str, list[str]]:
    """Minimum evidence bar. Passing does NOT prove a model works live; failing => research only."""
    reasons = []
    ov = report.get("oos_trades", {})
    if report.get("n_oos_rows", 0) < 1000:
        reasons.append(f"only {report.get('n_oos_rows', 0)} out-of-sample rows (< 1000)")
    if ov.get("n_trades", 0) < 100:
        reasons.append(f"only {ov.get('n_trades', 0)} out-of-sample trades (< 100)")
    lo = ov.get("expectancy_r_ci_low")
    if lo is None or lo <= 0:
        reasons.append("net expectancy (after spread) not significantly > 0")
    if (report.get("brier_skill") or -1) <= 0:
        reasons.append("no Brier skill vs class-prior baseline")
    if (report.get("calibration", {}).get("ece") or 1) > 0.08:
        reasons.append("calibration error (ECE) > 0.08")
    base = report.get("baselines") or {}
    best = max((b.get("expectancy_r") for b in base.values() if b.get("n_trades", 0) >= 30 and b.get("expectancy_r") is not None),
               default=None)
    if best is not None and (ov.get("expectancy_r") is None or ov["expectancy_r"] <= best):
        reasons.append(f"does not beat the best simple baseline (baseline expectancy {best:+.3f}R vs model "
                       f"{(ov.get('expectancy_r') or 0):+.3f}R)")
    pos = report.get("folds_positive_expectancy")
    if pos is None or pos < 0.6:
        reasons.append("expectancy positive in < 60% of walk-forward folds")
    return ("passed_minimum_checks" if not reasons else "research_only"), reasons
