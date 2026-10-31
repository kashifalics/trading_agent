"""Research runner. Usage (from backend/, DATABASE_URL points at the research database):

  python -m app.research.run_milestone backfill  [--days 1200]
  python -m app.research.run_milestone quality
  python -m app.research.run_milestone backtest  --tf 1H        # 4 cost scenarios + baselines, stored as experiments
  python -m app.research.run_milestone ml        --tf 1H
  python -m app.research.run_milestone report
Everything is stored in the `experiments` table; `report` renders markdown from stored experiments only.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.database.init_db import init_db
from app.database.models import Experiment
from app.database.session import session_scope
from app.market_data.ingestion.backfill import backfill_candles
from app.market_data.ingestion.service import resolve_mapping
from app.market_data.registry import get_provider
from app.research import reports
from app.research.data_quality import compute_quality, render_markdown
from app.research.experiments import Timer, record_experiment
from app.research.ml_eval import ALGOS, rule_engine_in_window, run_ml_experiment
from app.research.strategy_eval import (
    compute_baselines,
    load_series,
    run_backtest_experiment,
)

SYMBOL, PROVIDER = "BTCUSDT", "binance"
TFS = ("1H", "4H")
REPORT_DIR = Path(__file__).resolve().parents[3] / "docs" / "reports"
BT_BASE = {"symbol": SYMBOL, "provider": PROVIDER, "n_folds": 6}
BT_PARAMS = {"risk_pct": 1.0, "max_bars_in_trade": 200, "eval_every": 1}


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def cmd_backfill(days: int) -> None:
    with session_scope() as s:
        inst, prov, pi = resolve_mapping(s, SYMBOL, PROVIDER)
        provider = get_provider(PROVIDER)
        start = datetime.now(timezone.utc) - timedelta(days=days)
        for tf in TFS:
            log(f"backfill {SYMBOL} {tf} from {start.date()}")
            run = backfill_candles(s, provider, inst, prov, pi, tf, start,
                                   progress=lambda p: log(f"  window {p['window']} from {p['from'][:16]} stored={p['stored']}"))
            log(f"  -> run #{run.id} {run.status}: requests={run.requests} stored={run.stored} missing {run.missing_before}->{run.missing_after}")


def cmd_quality() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with session_scope() as s:
        inst, prov, _ = resolve_mapping(s, SYMBOL, PROVIDER)
        qs = [compute_quality(s, inst, prov, tf) for tf in TFS]
    (REPORT_DIR / "BTCUSDT_DATA_QUALITY.md").write_text(render_markdown(qs), encoding="utf8")
    for q in qs:
        log(f"{q['timeframe']}: status={q['status']} candles={q.get('complete_count')} missing={q.get('missing_count')} coverage={q.get('coverage_pct')}%")


def cmd_backtest(tf: str) -> None:
    for scenario in ("zero_cost", "optimistic", "base", "stress"):
        spec = {**BT_BASE, "timeframe": tf, "strategy": "decision_engine", "strategy_params": {}, "cost_scenario": scenario,
                "backtest": BT_PARAMS}
        with Timer() as t, session_scope() as s:
            res, snap = run_backtest_experiment(s, spec)
        with session_scope() as s:
            e = record_experiment(s, "backtest", f"bt:{tf}:decision_engine:{scenario}", {**snap}, {"spec": {**spec, "expected_snapshot": snap["snapshot_id"]}},
                                  res, t.elapsed)
        m = res["metrics"]
        log(f"bt {tf} {scenario}: trades={res['n_trades']} PF={m.get('profit_factor')} E[R]={m.get('expectancy_r')} ret={m.get('total_return_pct')}% exp#{e.id} ({t.elapsed:.0f}s)")
    spec = {**BT_BASE, "timeframe": tf, "strategy": "decision_engine", "backtest": BT_PARAMS}
    with Timer() as t, session_scope() as s:
        bl = compute_baselines(s, spec, "base")
        snap = load_series(s, SYMBOL, PROVIDER, tf)[3]
    with session_scope() as s:
        e = record_experiment(s, "baseline", f"baselines:{tf}:base", snap, {"spec": {**spec, "expected_snapshot": snap["snapshot_id"]}, "scenario": "base"}, bl, t.elapsed)
    log(f"baselines {tf}: exp#{e.id} ({t.elapsed:.0f}s)")


def cmd_ml(tf: str) -> None:
    for algo in ALGOS:
        for cost_name, scenario in (("gross", "zero_cost"), ("base", "base")):
            spec = {"symbol": SYMBOL, "provider": PROVIDER, "timeframe": tf, "algorithm": algo,
                    "label": {"horizon": 24, "tp_atr": 2.0, "sl_atr": 1.0}, "n_splits": 5, "threshold": 0.45,
                    "cost_scenario": scenario}
            with Timer() as t, session_scope() as s:
                rep, snap = run_ml_experiment(s, spec, register=(cost_name == "base"))
            with session_scope() as s:
                e = record_experiment(s, "ml", f"ml:{tf}:{algo}:{cost_name}", snap, {"spec": {**spec, "expected_snapshot": snap["snapshot_id"]}}, rep, t.elapsed)
            tr = rep.get("oos_trades", {})
            log(f"ml {tf} {algo} {cost_name}: brier_skill={rep.get('brier_skill')} trades={tr.get('n_trades')} E[R]={tr.get('expectancy_r')} status={rep['status']} exp#{e.id} ({t.elapsed:.0f}s)")


def _latest(s, name: str) -> Experiment:
    e = s.scalars(select(Experiment).where(Experiment.name == name).order_by(Experiment.id.desc()).limit(1)).first()
    if e is None:
        raise SystemExit(f"missing experiment '{name}' - run the earlier steps first")
    return e


def cmd_report() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    cmd_quality()
    ctx = {"quality": {}, "snap": {}, "bt": {}, "bl": {}, "ml": {}, "exp_ids": []}
    with session_scope() as s:
        inst, prov, _ = resolve_mapping(s, SYMBOL, PROVIDER)
        for tf in TFS:
            ctx["quality"][tf] = compute_quality(s, inst, prov, tf)
            scen, ids = {}, {}
            for sc in ("zero_cost", "optimistic", "base", "stress"):
                e = _latest(s, f"bt:{tf}:decision_engine:{sc}")
                scen[sc], ids[sc] = e.results, e.id
                snap = e.dataset
            be = _latest(s, f"baselines:{tf}:base")
            ids["baselines"] = be.id
            ctx["bt"][tf], ctx["bl"][tf], ctx["snap"][tf] = scen, be.results, snap["snapshot_id"]
            ctx["exp_ids"] += list(ids.values())
            (REPORT_DIR / f"BTCUSDT_BACKTEST_{tf}.md").write_text(
                reports.render_backtest(tf, scen, be.results, snap, ids, 1 if tf == "1H" else 4), encoding="utf8")
            runs, mids = {}, []
            for algo in ALGOS:
                for cost in ("gross", "base"):
                    e = _latest(s, f"ml:{tf}:{algo}:{cost}")
                    runs[(algo, cost)] = e.results
                    mids.append(e.id)
                    msnap = e.dataset
            first_base = runs[("lightgbm", "base")]
            ctx["ml"][tf] = {"runs": runs, "snapshot": msnap, "exp_ids": mids,
                             "rule_engine": rule_engine_in_window(scen["base"]["trades_compact"], first_base.get("oos_start"))}
            ctx["exp_ids"] += mids
    (REPORT_DIR / "BTCUSDT_ML_EVALUATION.md").write_text(reports.render_ml(ctx["ml"]), encoding="utf8")
    (REPORT_DIR / "QUANTITATIVE_VALIDATION_SUMMARY.md").write_text(reports.render_summary(ctx), encoding="utf8")
    log(f"reports written to {REPORT_DIR}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["backfill", "quality", "backtest", "ml", "report"])
    ap.add_argument("--tf", choices=TFS)
    ap.add_argument("--days", type=int, default=1200)
    a = ap.parse_args(argv)
    log(f"database: {get_settings().database_url.split('@')[-1]}")
    init_db()
    if a.cmd == "backfill":
        cmd_backfill(a.days)
    elif a.cmd == "quality":
        cmd_quality()
    elif a.cmd == "backtest":
        for tf in ([a.tf] if a.tf else TFS):
            cmd_backtest(tf)
    elif a.cmd == "ml":
        for tf in ([a.tf] if a.tf else TFS):
            cmd_ml(tf)
    else:
        cmd_report()


if __name__ == "__main__":
    main(sys.argv[1:])
