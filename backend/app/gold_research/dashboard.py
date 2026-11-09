"""Gold Research dashboard data (brief Part 17): one small JSON assembled from the stored research outputs, bundled in app/data so
the hosted backend can serve it without the 2 GB history. Every figure is labelled with the segment it comes from; final-test
figures are never included before the one-time final test."""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.gold_research import study
from app.gold_research.report import merged_discovery
from app.historical.config import REPORTS
from app.historical.split import load_split

DASHBOARD = Path(__file__).resolve().parents[1] / "data" / "gold_research_dashboard.json"
SCENARIO_COLS = ("trend_regime", "vol_level", "session", "structural_regime", "range_regime")


def _json(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def build(symbol: str = "XAUUSD") -> dict:
    cov = _json(REPORTS / f"{symbol}_coverage.json") or {}
    tfc = _json(REPORTS / f"{symbol}_timeframe_check.json") or {}
    xc = _json(REPORTS / f"{symbol}_dukascopy_crosscheck.json")
    try:
        sp = load_split(symbol)
    except RuntimeError:
        sp = None
    dataset = {
        "source": cov.get("source"), "price": "bid and ask", "first_traded_minute": cov.get("first_traded_minute"),
        "last_minute": (cov.get("timeframes", {}).get("M1") or {}).get("latest"), "m1_candles": cov.get("clean_rows"),
        "traded_coverage_pct": cov.get("coverage_pct"), "material_gaps": cov.get("material_gaps"),
        "material_gap_minutes": cov.get("material_gap_minutes"), "filler_minutes_removed": cov.get("quiet_minutes"),
        "invalid_candles": cov.get("invalid_candles"), "duplicates": cov.get("duplicates"),
        "timeframes": {tf: {**v, "identical_to_m1_rebuild": (tfc.get(tf) or {}).get("identical")} for tf, v in cov.get("timeframes", {}).items()},
        "dukascopy_crosscheck": (xc or {}).get("summary"),
    }
    split = None if sp is None else {"train": {"start": sp["train"]["start"], "end": sp["train"]["end_exclusive"]},
                                     "validation": {"start": sp["validation"]["start"], "end": sp["validation"]["end_exclusive"]},
                                     "test": {"start": sp["test"]["start"], "sealed": True}, "sha256": sp["sha256"]}
    disc = merged_discovery(symbol) if (study.out_dir(symbol)).exists() else None
    val = _json(study.out_dir(symbol) / "validation.json")
    patterns, scenarios = None, None
    if disc:
        rows = [r for r in disc["rows"] if r["primary"].get("n", 0)]
        vmap = {(r["tf"], r["pattern"], r["direction"]): r for r in (val or {}).get("rows", [])}

        def compact(r):
            p = r["primary"]
            v = vmap.get((r["tf"], r["pattern"], r["direction"]))
            return {"tf": r["tf"], "pattern": r["pattern"], "direction": r["direction"], "family": r["family"], "entry": r["entry"],
                    "trades": p.get("n"), "win_rate": p.get("win_rate"), "mean_r": p.get("mean_r"), "edge": p.get("edge"),
                    "edge_se": p.get("edge_se"), "profit_factor": p.get("profit_factor"), "q": r.get("q"), "status": r["status"],
                    "stage": r.get("stage", 1), "smallest_detectable_edge": r.get("mde"),
                    "validation": None if v is None else {"trades": v["validation"].get("n"), "mean_r": v["validation"].get("mean_r"),
                                                          "edge": v["validation"].get("edge"), "verdict": v["verdict"]}}
        tested = [r for r in rows if "q" in r]
        ranked = sorted(tested, key=lambda r: r["primary"]["edge"])
        fams: dict[str, dict] = {}
        for r in rows:
            f = fams.setdefault(r["family"], {"tests": 0, "candidates": 0, "patterns": set()})
            f["tests"] += "q" in r
            f["candidates"] += r["status"] == "candidate"
            f["patterns"].add(r["pattern"])
        patterns = {"segment": "training", "main_test": disc.get("primary"), "stages": disc.get("stages", 1), "tests": len(tested),
                    "candidates": [compact(r) for r in rows if r["status"] == "candidate"],
                    "best": [compact(r) for r in ranked[-10:][::-1]], "worst": [compact(r) for r in ranked[:10]],
                    "by_family": {k: {"tests": v["tests"], "candidates": v["candidates"], "patterns": len(v["patterns"])} for k, v in fams.items()},
                    "status_counts": {s: sum(1 for r in rows if r["status"] == s) for s in {r["status"] for r in rows}},
                    "all": [compact(r) for r in tested]}
        scenarios = {"segment": "training", "note": "descriptive: average result of all single-pattern trades in each condition; "
                                                    "never used to select anything"}
        for col in SCENARIO_COLS:
            agg: dict[str, list] = {}
            for r in rows:
                for k, x in ((r.get("by") or {}).get(col) or {}).items():
                    if x.get("n") and x.get("mean_r") is not None:
                        a = agg.setdefault(k, [0, 0.0, 0.0])
                        a[0] += x["n"]
                        a[1] += x["n"] * x["mean_r"]
                        a[2] += x["n"] * (x.get("edge") or 0.0)
            scenarios[col] = {k: {"trades": n, "mean_r": s / n, "edge": e / n} for k, (n, s, e) in sorted(agg.items()) if n}
    ml = _json(study.out_dir(symbol) / "ml_training.json")
    models = None
    if ml:
        models = {"segment": "training (purged walk-forward, out-of-fold)", "label": ml.get("label_primary"), "tfs": {}}
        for tf, r in ml["tfs"].items():
            best = r["models"][r["best_kind"]]
            meta = _json(study.out_dir(symbol) / "models" / r["challenger"] / "meta.json") or {}
            champ = _json(study.out_dir(symbol) / "models" / f"champion_{tf}.json")
            models["tfs"][tf] = {
                "rows": r["rows"], "features": len(r["features"]), "best_kind": r["best_kind"],
                "comparison": {k: {m: v["oof"].get(m) for m in ("roc_auc", "pr_auc", "brier_skill", "log_loss", "ece")}
                               for k, v in r["models"].items()},
                "calibrated": {m: best["oof_calibrated"].get(m) for m in ("roc_auc", "brier_skill", "ece")},
                "top_decile": (best["oof_calibrated"].get("selection") or {}).get("top_decile"),
                "shuffled_label_auc": r["shuffled_label_check"].get("roc_auc"), "challenger": r["challenger"],
                "validation": meta.get("validation"), "champion": (champ or {}).get("version")}
    status = {"pattern_study": "training discovery done" if disc else "not run yet", "validation": "done" if val else "not run yet",
              "models": "trained (challengers only)" if ml else "not trained yet", "final_test": "sealed (not run)"}
    out = {"symbol": symbol, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": status, "dataset": dataset,
           "split": split, "patterns": patterns, "scenarios": scenarios, "models": models,
           "disclaimer": "Historical research and backtest output, analysis only. Training figures find candidates; only validation "
                         "confirms them; the final test is sealed. The confluence score is not a win probability."}
    DASHBOARD.write_text(json.dumps(out, default=float), encoding="utf8")
    return out


def load() -> dict:
    if not DASHBOARD.exists():
        return {"available": False, "status": {"pattern_study": "not run yet"}}
    return {"available": True, **json.loads(DASHBOARD.read_text(encoding="utf8"))}
