"""Walk-forward validation of the Trade Opportunities setup rules (every trading style) on stored real candles.

Usage (from backend/, DATABASE_URL points at the research database that holds the candles):
  python -m app.research.run_opportunity_validation run    [--symbols BTCUSDT,XAUUSD] [--styles scalping,swing] [--only swing:4H]
  python -m app.research.run_opportunity_validation export        # -> app/data/opportunity_validation.json (what the scan reads)
  python -m app.research.run_opportunity_validation report        # -> docs/reports/OPPORTUNITY_VALIDATION.md

Protocol (fixed BEFORE any run; no parameter was tuned, defaults come from app/opportunities/config.py):
  * the rules are replayed bar by bar with only past information; entries are market orders at the next open after a FRESH trigger;
  * costs: BTCUSDT 0.10% taker fee + 0.01% slippage per side + 0.002% spread; XAUUSD 0.005% slippage per side + 0.01% spread;
  * the first 60% of each series is "development" (shown, not used for any decision), the last 40% is out-of-sample (OOS);
  * status is decided by app.opportunities.validation.classify from OOS trades only (>= 100 trades, bootstrap CI > 0, p < 0.05,
    >= 2/3 of OOS sub-periods positive, better than random entries through the same execution model);
  * every run is stored as a reproducible experiment (dataset snapshot hash + code hash).
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import select

from app.core.jsonutil import to_jsonable
from app.database.init_db import init_db
from app.database.models import Experiment
from app.database.session import session_scope
from app.ml_engine.evaluation import trade_metrics
from app.opportunities import rules_strategy  # noqa: F401  (registers the strategy)
from app.opportunities.config import CONFIG_VERSION, PROFILES, ROUND_TRIP_COST
from app.opportunities.validation import VALIDATION_PATH, classify
from app.research.experiments import Timer, record_experiment
from app.research.strategy_eval import (
    compute_baselines,
    load_series,
    run_backtest_experiment,
    significance,
)

SYMBOLS = {"BTCUSDT": ("binance", "base"), "XAUUSD": ("twelve_data", "gold_spot")}
MATRIX = {"scalping": ("5m", "15m"), "intraday": ("15m", "1H"), "swing": ("4H", "1D"), "long_term": ("1D", "1W")}
# Most recent complete candles replayed per timeframe (None = all stored). The replay costs ~60 ms per bar, so the fine timeframes use a
# recent window; every experiment records the exact candles it used (snapshot hash).
MAX_BARS = {"5m": 6000, "15m": 8000, "1H": 8000, "4H": None, "1D": None, "1W": None}
OOS_SHARE = 0.4
REPORT = Path(__file__).resolve().parents[3] / "docs" / "reports" / "OPPORTUNITY_VALIDATION.md"


def log(m: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def _epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def _block(trades: list[dict]) -> dict:
    if not trades:
        return {"n_trades": 0}
    m = trade_metrics(np.array([t["r"] for t in trades]))
    m["long"] = _side(trades, "BUY")
    m["short"] = _side(trades, "SELL")
    return m


def _side(trades: list[dict], d: str) -> dict:
    r = np.array([t["r"] for t in trades if t["dir"] == d])
    return {"n_trades": int(len(r)), "expectancy_r": float(r.mean()) if len(r) else None, "win_rate": float((r > 0).mean()) if len(r) else None}


def oos_analysis(net: dict, gross: dict, t_start: float, t_split: float, t_end: float, baselines: dict) -> dict:
    tr = [{**t, "ts": _epoch(t["entry"])} for t in net["trades_compact"]]
    dev, oos = [t for t in tr if t["ts"] < t_split], [t for t in tr if t["ts"] >= t_split]
    edges = np.linspace(t_split, t_end, 5)
    subs = [[t for t in oos if edges[i] <= t["ts"] < edges[i + 1] or (i == 3 and t["ts"] == edges[4])] for i in range(4)]
    pos = [np.mean([t["r"] for t in s]) > 0 for s in subs if s]
    share = (sum(pos) / len(pos)) if pos else None
    sig = significance(np.array([t["r"] for t in oos])) if oos else {"n": 0}
    g = [t for t in gross["trades_compact"] if _epoch(t["entry"]) >= t_split]
    gross_m = trade_metrics(np.array([t["r"] for t in g])) if g else {"n_trades": 0}
    rand = (baselines.get("random_entry_mean_of_seeds") or {}).get("expectancy_r_mean")
    oos_m = _block(oos)
    status, summary = classify(oos_m, sig, share, rand)
    return {"status": status, "summary": summary, "dev": _block(dev), "oos": oos_m, "oos_significance": sig,
            "oos_subperiods": [{"n_trades": len(s), "expectancy_r": float(np.mean([t["r"] for t in s])) if s else None} for s in subs],
            "oos_subperiods_positive_share": share, "oos_gross_zero_cost": {k: gross_m.get(k) for k in ("n_trades", "expectancy_r", "win_rate", "profit_factor")},
            "random_entry_expectancy_r": rand,
            "split": {"start": datetime.fromtimestamp(t_start, tz=timezone.utc).isoformat(), "oos_start": datetime.fromtimestamp(t_split, tz=timezone.utc).isoformat(),
                      "end": datetime.fromtimestamp(t_end, tz=timezone.utc).isoformat(), "oos_share": OOS_SHARE}}


def run_combo(sym: str, style: str, tf: str) -> int:
    provider, scenario = SYMBOLS[sym]
    prof = PROFILES[style]
    with session_scope() as s:
        _, _, bars, snap = load_series(s, sym, provider, tf, max_bars=MAX_BARS[tf])
    spec = {"symbol": sym, "provider": provider, "timeframe": tf, "strategy": "opportunity_rules",
            "strategy_params": {"style": style, "symbol": sym}, "cost_scenario": scenario, "n_folds": 6,
            "max_bars": MAX_BARS[tf], "backtest": {"eval_every": 1, "max_bars_in_trade": 2 * prof.horizon_bars, "risk_pct": 1.0},
            "expected_snapshot": snap["snapshot_id"]}
    base_spec = {k: spec[k] for k in ("symbol", "provider", "timeframe", "backtest", "n_folds", "expected_snapshot", "max_bars")}
    with Timer() as t, session_scope() as s:
        net, _ = run_backtest_experiment(s, spec)
        gross, _ = run_backtest_experiment(s, {**spec, "cost_scenario": "zero_cost"})
        bl = compute_baselines(s, base_spec, scenario)
    split = int(len(bars) * (1 - OOS_SHARE))
    ana = oos_analysis(net, gross, float(bars.t[0]), float(bars.t[split]), float(bars.t[-1]), bl)
    results = {**net, "baselines": bl, "opportunity_oos": ana}
    with session_scope() as s:
        e = record_experiment(s, "backtest", f"opportunity:{style}:{sym}:{tf}", snap, {"spec": spec, "config_version": CONFIG_VERSION,
                                                                                      "cost_round_trip_frac": ROUND_TRIP_COST[sym]}, results, t.elapsed)
        eid = e.id
    o = ana["oos"]
    log(f"{sym} {style:9s} {tf:3s}: trades dev={ana['dev'].get('n_trades')} oos={o.get('n_trades')} E[R] oos={o.get('expectancy_r')} "
        f"gross={ana['oos_gross_zero_cost'].get('expectancy_r')} -> {ana['status']} (exp#{eid}, {t.elapsed:.0f}s)")
    return eid


def cmd_run(symbols: list[str], styles: list[str], only: str | None) -> None:
    for sym in symbols:
        for style in styles:
            for tf in MATRIX[style]:
                if only and only != f"{style}:{tf}":
                    continue
                try:
                    run_combo(sym, style, tf)
                except Exception as exc:  # noqa: BLE001 - report and continue; a missing series must not hide the others
                    log(f"{sym} {style} {tf}: FAILED {exc.__class__.__name__}: {exc}")


def latest() -> dict[tuple, Experiment]:
    out: dict[tuple, Experiment] = {}
    with session_scope() as s:
        for e in s.scalars(select(Experiment).where(Experiment.name.like("opportunity:%")).order_by(Experiment.id)):
            _, style, sym, tf = e.name.split(":")
            out[(sym, style, tf)] = e
        s.expunge_all()
    return out


def cmd_export() -> None:
    res: dict = {}
    for (sym, style, tf), e in latest().items():
        r, a = e.results, e.results["opportunity_oos"]
        m = r["metrics"]
        res.setdefault(sym, {}).setdefault(style, {})[tf] = {
            "experiment_id": e.id, "snapshot_id": e.dataset["snapshot_id"], "status": a["status"], "summary": a["summary"],
            "period": a["split"], "cost_round_trip_frac": e.config["cost_round_trip_frac"], "oos": a["oos"], "dev": a["dev"],
            "oos_significance": a["oos_significance"], "oos_gross_zero_cost": a["oos_gross_zero_cost"],
            "oos_subperiods_positive_share": a["oos_subperiods_positive_share"],
            "full_period": {k: m.get(k) for k in ("n_trades", "total_return_pct", "win_rate", "profit_factor", "expectancy_r", "max_drawdown_pct",
                                                  "sharpe_annualized", "avg_bars_in_trade", "exposure_pct")},
            "baselines": {"random_entry_expectancy_r": a["random_entry_expectancy_r"],
                          "buy_and_hold_return_pct": (r["baselines"].get("buy_and_hold") or {}).get("total_return_pct"),
                          "ma_cross_expectancy_r": (r["baselines"].get("ma_cross_ema20_50") or {}).get("expectancy_r")}}
    out = {"meta": {"generated_at": datetime.now(timezone.utc).isoformat(), "config_version": CONFIG_VERSION,
                    "method": "docs/STRATEGY_VALIDATION.md, docs/reports/OPPORTUNITY_VALIDATION.md", "oos_share": OOS_SHARE}, "results": res}
    VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_PATH.write_text(json.dumps(to_jsonable(out), separators=(",", ":")), encoding="utf8")
    log(f"wrote {VALIDATION_PATH} ({VALIDATION_PATH.stat().st_size / 1024:.0f} KB), {sum(len(t) for s in res.values() for t in s.values())} combinations")


def _f(x, d=3, sign=False) -> str:
    return "n/a" if x is None else f"{x:+.{d}f}" if sign else f"{x:.{d}f}"


def cmd_report() -> None:
    rows = latest()
    L = ["# Trade Opportunities — strategy validation", "",
         f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} from stored experiments; config version `{CONFIG_VERSION}`. "
         "Nothing here was tuned: the rules and thresholds were fixed before the first run._", "",
         "## Method", "",
         "* The setup rules (`app/opportunities/setup.py`, the same function the live scan calls) are replayed bar by bar using only information available at each bar.",
         "* A trade is opened at the **next bar's open** after a *fresh* trigger (confirmation on the latest bar), with the setup's structural stop and first target; the time stop is 2x the style's expected holding.",
         "* Same-bar stop/target ambiguity is resolved against the trade (stop first). One position at a time; 1% of equity risked.",
         "* Costs: BTCUSDT 0.10% taker fee + 0.01% slippage per side + 0.002% spread (0.222% round trip); XAUUSD 0.005% slippage per side + 0.01% spread (0.020% round trip).",
         "* The first 60% of each series is *development* (reported, not used for decisions); the last 40% is *out-of-sample (OOS)*. Status uses OOS trades only.",
         "* **validated** needs >= 100 OOS trades, bootstrap 95% CI of net expectancy above 0, p < 0.05, >= 2/3 of OOS sub-periods positive and better than random entries; **negative** = CI entirely below 0; otherwise **no_edge**.",
         "* Not covered by this replay: the evidence score and the analogue search (they are not entry rules), calendar-month higher-timeframe filters (1W entries have no HTF filter), and non-UTC daily/weekly anchoring.", ""]
    counts: dict[str, int] = {}
    for e in rows.values():
        st = e.results["opportunity_oos"]["status"]
        counts[st] = counts.get(st, 0) + 1
    L += ["## Summary", "", f"{len(rows)} instrument/style/timeframe combinations tested: " + ", ".join(f"**{v} {k}**" for k, v in sorted(counts.items())) + ".", ""]
    for sym in SYMBOLS:
        sel = {k: e for k, e in rows.items() if k[0] == sym}
        if not sel:
            continue
        snap = next(iter(sel.values())).dataset
        L += [f"## {sym}", "", "| Style | TF | Trades dev / OOS | OOS net E[R] (95% CI) | OOS win | OOS PF | OOS gross E[R] | OOS long / short E[R] | Random-entry E[R] | OOS max DD (R) | Net return (full) | Status |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for style in MATRIX:
            for tf in MATRIX[style]:
                e = sel.get((sym, style, tf))
                if not e:
                    L.append(f"| {style} | {tf} | — | not run | | | | | | | | untested |")
                    continue
                a, o = e.results["opportunity_oos"], e.results["opportunity_oos"]["oos"]
                sg = a["oos_significance"]
                ci = f"[{_f(sg['boot_ci95'][0], 2, True)}, {_f(sg['boot_ci95'][1], 2, True)}]" if "boot_ci95" in sg else "n/a"
                lg, sh = o.get("long", {}), o.get("short", {})
                L.append(f"| {style} | {tf} | {a['dev'].get('n_trades', 0)} / {o.get('n_trades', 0)} | {_f(o.get('expectancy_r'), 3, True)} {ci} | "
                         f"{_f(o.get('win_rate'), 2)} | {_f(o.get('profit_factor'), 2)} | {_f(a['oos_gross_zero_cost'].get('expectancy_r'), 3, True)} | "
                         f"{_f(lg.get('expectancy_r'), 2, True)} / {_f(sh.get('expectancy_r'), 2, True)} | {_f(a['random_entry_expectancy_r'], 3, True)} | "
                         f"{_f(o.get('max_drawdown_r'), 1)} | {_f(e.results['metrics'].get('total_return_pct'), 1, True)}% | **{a['status']}** |")
        L += ["", "Experiments: " + ", ".join(f"#{e.id}" for e in sel.values()) + f". Dataset snapshots hash the exact stored candles (e.g. {snap['symbol']} {snap['timeframe']} `{snap['snapshot_id']}`).", ""]
        L += ["<details><summary>Reasons per combination</summary>", ""]
        for (s_, st_, tf_), e in sorted(sel.items()):
            L.append(f"* {st_} {tf_}: {e.results['opportunity_oos']['summary']}")
        L += ["", "</details>", ""]
    L += ["## How to read this", "",
          "* *OOS net E[R]* is the average result per trade in multiples of the risk taken, after costs, on data the rules were never adjusted on. 0 means break-even.",
          "* A wide CI that spans 0 means the data cannot distinguish the rules from a coin flip. With few trades the CI is wide: **\"no_edge\" with a small sample is absence of evidence, not evidence of absence.**",
          "* *Gross* (zero-cost) expectancy shows whether costs alone are the problem. *Random-entry* expectancy is what the same execution model earns with no skill.",
          "* Results on one instrument over a finite history are not a guarantee about the future.", ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L), encoding="utf8")
    log(f"wrote {REPORT}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "export", "report"])
    ap.add_argument("--symbols", default=",".join(SYMBOLS))
    ap.add_argument("--styles", default=",".join(MATRIX))
    ap.add_argument("--only", default=None, help="style:TF, e.g. swing:4H")
    a = ap.parse_args()
    init_db()
    if a.cmd == "run":
        cmd_run(a.symbols.split(","), a.styles.split(","), a.only)
    elif a.cmd == "export":
        cmd_export()
    else:
        cmd_report()


if __name__ == "__main__":
    main()
