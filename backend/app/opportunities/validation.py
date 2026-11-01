"""Strategy-validation status lookup.

Validation results are produced by `python -m app.research.run_opportunity_validation` (walk-forward replay of the exact
setup rules on stored candles, with costs and baselines, recorded as reproducible experiments) and exported to
app/data/opportunity_validation.json so production and local runs read the same measured numbers.

Status meaning (decided by `classify`, never by hand):
  validated : out-of-sample net expectancy CI entirely above 0, p < 0.05, >= 2/3 of folds positive, >= 100 OOS trades,
              and better than random entries through the same execution model.
  negative  : out-of-sample 95% bootstrap CI entirely below 0 (the rules LOSE money after costs).
  no_edge   : tested, but not distinguishable from zero or too few trades to conclude.
  untested  : no out-of-sample test exists for this instrument / style / timeframe.
"""
import json
from pathlib import Path

VALIDATION_PATH = Path(__file__).resolve().parents[1] / "data" / "opportunity_validation.json"
MIN_OOS_TRADES = 100


def classify(oos: dict, sig: dict, fold_positive_share: float | None, random_expectancy: float | None) -> tuple[str, str]:
    n = oos.get("n_trades", 0)
    if n < MIN_OOS_TRADES or "boot_ci95" not in sig:
        return "no_edge", f"only {n} out-of-sample trades (< {MIN_OOS_TRADES}): no conclusion possible"
    lo, hi = sig["boot_ci95"]
    mean = oos["expectancy_r"]
    if hi < 0:
        return "negative", f"out-of-sample expectancy {mean:+.3f} R, 95% CI [{lo:+.3f}, {hi:+.3f}] entirely below zero"
    beats_random = random_expectancy is None or mean > random_expectancy
    if lo > 0 and sig["p_edge_gt_0"] < 0.05 and (fold_positive_share or 0) >= 2 / 3 and beats_random:
        return "validated", f"out-of-sample expectancy {mean:+.3f} R, 95% CI [{lo:+.3f}, {hi:+.3f}], p={sig['p_edge_gt_0']:.3f}"
    return "no_edge", f"out-of-sample expectancy {mean:+.3f} R, 95% CI [{lo:+.3f}, {hi:+.3f}]: not distinguishable from zero"


def load_validation(path: Path | None = None) -> dict:
    p = path or VALIDATION_PATH
    if not p.exists():
        return {"meta": {}, "results": {}}
    return json.loads(p.read_text(encoding="utf8"))


def strategy_validation(symbol: str, style: str, timeframe: str, path: Path | None = None) -> dict:
    store = load_validation(path)
    r = store.get("results", {}).get(symbol, {}).get(style, {}).get(timeframe)
    if not r:
        return {"status": "untested", "summary": f"No out-of-sample validation exists for {symbol} {style} on {timeframe}",
                "experiment_id": None}
    return {"status": r["status"], "summary": r["summary"], "experiment_id": r.get("experiment_id"), "oos": r.get("oos"),
            "dev": r.get("dev"), "baselines": r.get("baselines"), "cost_round_trip_frac": r.get("cost_round_trip_frac"),
            "snapshot_id": r.get("snapshot_id"), "period": r.get("period")}


def validation_overview(path: Path | None = None) -> list[dict]:
    store = load_validation(path)
    rows = []
    for sym, styles in store.get("results", {}).items():
        for style, tfs in styles.items():
            for tf, r in tfs.items():
                rows.append({"symbol": sym, "style": style, "timeframe": tf, **r})
    return rows
