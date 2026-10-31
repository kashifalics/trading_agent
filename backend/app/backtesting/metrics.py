import math

import numpy as np


def backtest_metrics(trades: list[dict], equity: np.ndarray, initial: float, step_seconds: int,
                     bars_total: int) -> dict:
    n = len(trades)
    if n == 0:
        return {"n_trades": 0, "final_equity": float(equity[-1]) if len(equity) else initial,
                "total_return_pct": 0.0, "note": "no trades were generated"}
    pnl = np.array([t["pnl"] for t in trades])
    r = np.array([t["r_multiple"] for t in trades])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    peak = np.maximum.accumulate(equity)
    dd = (peak - equity) / peak
    rets = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([])
    per_year = 365.25 * 86400 / step_seconds
    sharpe = float(rets.mean() / rets.std(ddof=1) * math.sqrt(per_year)) if len(rets) > 2 and rets.std(ddof=1) > 0 else None
    streak = best = 0
    for p in pnl:
        streak = streak + 1 if p <= 0 else 0
        best = max(best, streak)
    sd = float(r.std(ddof=1)) if n > 1 else None
    return {
        "n_trades": n, "final_equity": float(equity[-1]), "total_return_pct": float((equity[-1] / initial - 1) * 100),
        "win_rate": float((pnl > 0).mean()),
        "profit_factor": float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() < 0 else None,
        "expectancy_cash": float(pnl.mean()), "expectancy_r": float(r.mean()),
        "expectancy_r_ci": [float(r.mean() - 1.96 * sd / math.sqrt(n)), float(r.mean() + 1.96 * sd / math.sqrt(n))] if sd else None,
        "avg_win": float(wins.mean()) if len(wins) else None, "avg_loss": float(losses.mean()) if len(losses) else None,
        "max_drawdown_pct": float(dd.max() * 100), "sharpe_annualized": sharpe,
        "sharpe_note": "computed on per-bar equity changes over bars present in the data; approximate for markets with closures",
        "total_costs": float(sum(t["costs"] for t in trades)), "longest_losing_streak": int(best),
        "avg_bars_in_trade": float(np.mean([t["bars_held"] for t in trades])),
        "exposure_pct": float(sum(t["bars_held"] for t in trades) / max(1, bars_total) * 100),
        "exits": {k: sum(1 for t in trades if t["exit_reason"] == k) for k in {t["exit_reason"] for t in trades}},
    }
