"""Quantitative evaluation of a strategy on a stored dataset: costs, folds, regimes, baselines, significance.

Everything here is a pure function of (stored candles, spec). Specs are JSON, so every run is an Experiment that
can be re-executed (`app.research.reproduce`). Nothing is tuned: strategy parameters are the library defaults.
"""
import math
from datetime import datetime, timezone

import numpy as np
from scipy import stats
from sqlalchemy.orm import Session

from app.backtesting.engine import BacktestConfig, BacktestResult, run_backtest
from app.backtesting.strategies import STRATEGIES, Signal
from app.feature_engineering.indicators import atr as atr_fn
from app.market_data.bars import Bars
from app.market_data.ingestion.service import load_candles, resolve_mapping
from app.market_structure.bos import detect_structure_breaks
from app.market_structure.swings import find_swings
from app.ml_engine.evaluation import trade_metrics
from app.research.experiments import dataset_snapshot
from app.services.data_service import tf_step

# Percent units. fee = % of notional per side; spread = full spread as % of price; slippage = % of price per market/stop fill.
COST_SCENARIOS: dict[str, dict] = {
    "zero_cost": {},
    "optimistic": {"commission_pct": 0.075, "spread_pct": 0.001, "slippage_pct": 0.005},
    "base": {"commission_pct": 0.10, "spread_pct": 0.002, "slippage_pct": 0.01},
    "stress": {"commission_pct": 0.10, "spread_pct": 0.01, "slippage_pct": 0.03},
}
DETERMINISTIC = {"decision_engine", "ma_cross"}
_memo: dict[tuple, dict] = {}


def round_trip_cost_frac(scenario: str) -> float:
    c = COST_SCENARIOS[scenario]
    return 2 * (c.get("commission_pct", 0) + c.get("slippage_pct", 0)) / 100 + c.get("spread_pct", 0) / 100


def load_series(session: Session, symbol: str, provider: str | None, timeframe: str, expected_snapshot: str | None = None):
    inst, prov, _ = resolve_mapping(session, symbol, provider)
    candles = load_candles(session, inst.id, prov.id, timeframe, complete_only=True)
    bars = Bars.from_candles(candles, tf_step(timeframe))
    snap = dataset_snapshot(session, inst.id, prov.id, timeframe, inst.canonical_symbol, prov.code)
    if expected_snapshot and snap["snapshot_id"] != expected_snapshot:
        raise ValueError(f"dataset changed: snapshot {snap['snapshot_id']} != expected {expected_snapshot}")
    return inst, prov, bars, snap


class MemoStrategy:
    """Signals depend only on bars[:i+1], so they are identical across cost scenarios: compute each once."""

    def __init__(self, inner, store: dict):
        self.inner, self.store = inner, store
        self.name, self.warmup = inner.name, inner.warmup

    def signal(self, bars: Bars) -> Signal | None:
        k = len(bars)
        if k not in self.store:
            self.store[k] = self.inner.signal(bars)
        return self.store[k]


def iso(t) -> str:
    return datetime.fromtimestamp(int(t), tz=timezone.utc).isoformat()


def regime_arrays(bars: Bars) -> dict[str, np.ndarray]:
    a = atr_fn(bars.h, bars.l, bars.c)
    pct = a / bars.c
    _, trend = detect_structure_breaks(bars, find_swings(bars))
    ok = pct[np.isfinite(pct)]
    q1, q2 = np.percentile(ok, [33.3, 66.7])
    vol = np.where(~np.isfinite(pct), -1, np.where(pct <= q1, 0, np.where(pct <= q2, 1, 2)))
    sma200 = np.convolve(bars.c, np.ones(200) / 200, mode="full")[: len(bars)]
    sma200[:199] = np.nan
    return {"vol": vol, "trend": trend, "above_sma200": np.where(np.isfinite(sma200), bars.c > sma200, -1).astype(int),
            "vol_edges": np.array([q1, q2])}


def _tm(trades: list[dict]) -> dict:
    """Trade-level metrics in R (net of costs) plus holding period and cash P&L."""
    if not trades:
        return {"n_trades": 0}
    R = np.array([t["r_multiple"] for t in trades])
    m = trade_metrics(R)
    m["avg_bars_held"] = float(np.mean([t["bars_held"] for t in trades]))
    m["sum_pnl_cash"] = float(sum(t["pnl"] for t in trades))
    m["total_costs_cash"] = float(sum(t["costs"] for t in trades))
    return m


def significance(R: np.ndarray, seed: int = 0, n_boot: int = 5000) -> dict:
    n = len(R)
    if n < 10:
        return {"n": n, "note": "too few trades for inference"}
    t_pos = stats.ttest_1samp(R, 0.0, alternative="greater")
    t_neg = stats.ttest_1samp(R, 0.0, alternative="less")
    rng = np.random.default_rng(seed)
    boots = rng.choice(R, size=(n_boot, n), replace=True).mean(axis=1)
    return {"n": n, "mean_r": float(R.mean()), "t_stat": float(t_pos.statistic), "p_edge_gt_0": float(t_pos.pvalue),
            "p_edge_lt_0": float(t_neg.pvalue), "boot_ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}


def verdict(sig: dict, fold_positive_share: float | None, n_trades: int) -> str:
    if n_trades < 100 or "boot_ci95" not in sig:
        return "INSUFFICIENT TRADES (< 100): no conclusion possible"
    lo, hi = sig["boot_ci95"]
    if lo > 0 and sig["p_edge_gt_0"] < 0.05 and (fold_positive_share or 0) >= 2 / 3:
        return "POSITIVE net expectancy (CI > 0, p < 0.05, ≥ 2/3 of folds positive) — still requires out-of-time confirmation"
    if hi < 0:
        return "NEGATIVE net expectancy: 95% bootstrap CI entirely below 0"
    return "NO EVIDENCE OF EDGE: net expectancy not distinguishable from zero (or not stable across folds)"


def analyze_backtest(res: BacktestResult, bars: Bars, warmup: int, n_folds: int = 6) -> dict:
    trades = res.trades
    idx = {iso(t): i for i, t in enumerate(bars.t)}
    reg = regime_arrays(bars)
    sig_i = np.array([idx[t["signal_ts"]] for t in trades], dtype=int) if trades else np.array([], dtype=int)
    edges = np.linspace(warmup, len(bars), n_folds + 1).astype(int)
    folds = []
    for k in range(n_folds):
        sel = [t for t, i in zip(trades, sig_i) if edges[k] <= i < edges[k + 1]]
        folds.append({"fold": k + 1, "start": iso(bars.t[edges[k]]), "end": iso(bars.t[edges[k + 1] - 1]), **_tm(sel)})
    pos_share = (sum(1 for f in folds if f.get("expectancy_r", -1) > 0) / sum(1 for f in folds if f["n_trades"] > 0)
                 if any(f["n_trades"] for f in folds) else None)

    def by(mask_fn):
        return _tm([t for t, i in zip(trades, sig_i) if mask_fn(t, i)])

    regimes = {
        "volatility": {name: by(lambda t, i, v=v: reg["vol"][i] == v) for v, name in enumerate(["low", "mid", "high"])},
        "structure_trend": {name: by(lambda t, i, v=v: reg["trend"][i] == v) for v, name in ((1, "up"), (-1, "down"), (0, "none"))},
        "vs_sma200": {"above": by(lambda t, i: reg["above_sma200"][i] == 1), "below": by(lambda t, i: reg["above_sma200"][i] == 0)},
    }
    R = np.array([t["r_multiple"] for t in trades])
    sig = significance(R)
    m = res.metrics
    return {
        "metrics": {k: v for k, v in m.items() if k not in ("exits", "sharpe_note")},
        "exits": m.get("exits"), "n_trades": len(trades), "skipped_signals": res.skipped_signals,
        "overall": _tm(trades), "by_direction": {"long": by(lambda t, i: t["direction"] == "BUY"),
                                                 "short": by(lambda t, i: t["direction"] == "SELL")},
        "by_regime": regimes, "vol_terciles_atr_pct": [float(x) for x in reg["vol_edges"]],
        "folds": folds, "folds_positive_share": pos_share, "significance": sig,
        "verdict": verdict(sig, pos_share, len(trades)),
        "period": {"start": iso(bars.t[warmup]), "end": iso(bars.t[-1]), "bars": int(len(bars) - warmup)},
        "trades_compact": [{"entry": t["entry_ts"], "dir": t["direction"], "r": t["r_multiple"], "pnl": t["pnl"],
                            "reason": t["exit_reason"]} for t in trades],
    }


def run_backtest_experiment(session: Session, spec: dict) -> tuple[dict, dict]:
    """spec: symbol, provider, timeframe, strategy, strategy_params, cost_scenario, backtest (overrides), n_folds,
    expected_snapshot. Returns (results, dataset_snapshot)."""
    inst, prov, bars, snap = load_series(session, spec["symbol"], spec.get("provider"), spec["timeframe"],
                                         spec.get("expected_snapshot"))
    inner = STRATEGIES[spec["strategy"]](**spec.get("strategy_params", {}))
    strat = inner
    if spec["strategy"] in DETERMINISTIC:
        key = (snap["snapshot_id"], spec["strategy"], repr(sorted(spec.get("strategy_params", {}).items())))
        strat = MemoStrategy(inner, _memo.setdefault(key, {}))
    cfg = BacktestConfig(**{**COST_SCENARIOS[spec.get("cost_scenario", "base")], **spec.get("backtest", {})})
    res = run_backtest(bars, strat, cfg)
    out = analyze_backtest(res, bars, strat.warmup, spec.get("n_folds", 6))
    out["config"] = res.config
    return out, snap


# ------------------------------------------------------------------ baselines (vectorised, same cost model)
def _side_cost(scenario: str) -> float:
    c = COST_SCENARIOS[scenario]
    return (c.get("commission_pct", 0) + c.get("slippage_pct", 0) + c.get("spread_pct", 0) / 2) / 100


def _curve_metrics(equity: np.ndarray, step: int, initial: float) -> dict:
    peak = np.maximum.accumulate(equity)
    rets = np.diff(equity) / equity[:-1]
    per_year = 365.25 * 86400 / step
    sharpe = float(rets.mean() / rets.std(ddof=1) * math.sqrt(per_year)) if rets.std(ddof=1) > 0 else None
    return {"total_return_pct": float((equity[-1] / initial - 1) * 100), "max_drawdown_pct": float(((peak - equity) / peak).max() * 100),
            "sharpe_annualized": sharpe}


def buy_and_hold(bars: Bars, start_idx: int, scenario: str, initial: float = 10_000.0) -> dict:
    side = _side_cost(scenario)
    entry = bars.o[start_idx + 1] * (1 + side)
    units = initial / entry
    eq = np.full(len(bars) - start_idx - 1, 0.0)
    eq[:] = units * bars.c[start_idx + 1:]
    eq[-1] = units * bars.c[-1] * (1 - side)  # liquidation cost at the end
    eq = np.concatenate([[initial], eq])
    return {**_curve_metrics(eq, bars.step, initial), "n_trades": 1, "exposure_pct": 100.0}


def sma_trend_long_flat(bars: Bars, start_idx: int, scenario: str, n: int = 200, initial: float = 10_000.0) -> dict:
    """Long when the previous close is above SMA(n), otherwise flat; executed at the next open."""
    side = _side_cost(scenario)
    c, o = bars.c, bars.o
    sma = np.convolve(c, np.ones(n) / n, mode="full")[: len(c)]
    want = np.where(np.arange(len(c)) >= n - 1, c > sma, False)  # decided at the close of bar i
    eq, cur, entries, in_bars = [initial], initial, 0, 0
    for j in range(start_idx + 2, len(c)):
        hold_prev, hold_now = bool(want[j - 2]), bool(want[j - 1])
        if hold_prev and hold_now:
            r = c[j] / c[j - 1] - 1
        elif hold_prev and not hold_now:
            r = (o[j] / c[j - 1] - 1) - side
        elif hold_now:
            r = (c[j] / o[j] - 1) - side
            entries += 1
        else:
            r = 0.0
        in_bars += hold_now
        cur *= 1 + r
        eq.append(cur)
    return {**_curve_metrics(np.array(eq), bars.step, initial), "n_trades": entries, "exposure_pct": 100 * in_bars / max(1, len(eq))}


def engine_baselines(session: Session, base_spec: dict, scenario: str, seeds: int = 10) -> dict:
    """ma_cross and random-entry through the SAME execution model and cost scenario."""
    out = {}
    s = {**base_spec, "strategy": "ma_cross", "strategy_params": {}, "cost_scenario": scenario}
    r, _ = run_backtest_experiment(session, s)
    out["ma_cross_ema20_50"] = {k: r["metrics"].get(k) for k in ("n_trades", "win_rate", "profit_factor", "expectancy_r", "total_return_pct",
                                                                  "max_drawdown_pct", "sharpe_annualized")}
    rand = []
    for seed in range(seeds):
        s = {**base_spec, "strategy": "random_entry", "strategy_params": {"p": 0.02, "seed": seed}, "cost_scenario": scenario}
        r, _ = run_backtest_experiment(session, s)
        rand.append({k: r["metrics"].get(k) for k in ("n_trades", "expectancy_r", "total_return_pct", "max_drawdown_pct")})
    ret = [x["total_return_pct"] for x in rand if x["total_return_pct"] is not None]
    out["random_entry_mean_of_seeds"] = {
        "seeds": seeds, "n_trades_mean": float(np.mean([x["n_trades"] for x in rand])),
        "expectancy_r_mean": float(np.mean([x["expectancy_r"] for x in rand if x["expectancy_r"] is not None])),
        "return_pct_mean": float(np.mean(ret)), "return_pct_min": float(np.min(ret)), "return_pct_max": float(np.max(ret)),
        "max_drawdown_pct_mean": float(np.mean([x["max_drawdown_pct"] for x in rand if x["max_drawdown_pct"] is not None]))}
    return out


def compute_baselines(session: Session, base_spec: dict, scenario: str = "base") -> dict:
    inst, prov, bars, snap = load_series(session, base_spec["symbol"], base_spec.get("provider"), base_spec["timeframe"],
                                         base_spec.get("expected_snapshot"))
    warm = STRATEGIES["decision_engine"]().warmup
    res = {"no_trade": {"total_return_pct": 0.0, "max_drawdown_pct": 0.0, "n_trades": 0, "sharpe_annualized": None},
           "buy_and_hold": buy_and_hold(bars, warm, scenario),
           "sma200_trend_long_flat": sma_trend_long_flat(bars, warm, scenario)}
    res.update(engine_baselines(session, base_spec, scenario))
    return res
