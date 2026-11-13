"""Renders docs/reports/{SYMBOL}_EXPERIMENT5.md from the frozen result files (every number comes from them)."""
import json

from app.gold_research.exp5 import run
from app.historical.config import REPO_ROOT
from app.strategy_engine.config import STRATEGY_NAMES


def _f(x, d=3, signed=True):
    if x is None:
        return "—"
    try:
        return f"{x:+.{d}f}" if signed else f"{x:.{d}f}"
    except (TypeError, ValueError):
        return "—"


def render(symbol: str) -> str:
    pre = run.load_prereg(symbol)
    dev = json.loads(run.dev_path(symbol).read_text())
    val = json.loads(run.val_path(symbol).read_text()) if run.val_path(symbol).exists() else None
    rows = dev["rows"]
    L = []
    L.append(f"# Experiment 5: strategy engine v2 on {symbol} (owner-approved plan, 2026-11-13)\n")
    L.append("Plan: `docs/engine_v2/EXPERIMENT_PLAN.md`. Pre-registration (counts only, committed before any outcome): "
             f"`docs/research/{symbol}_exp5_preregistration.json` (sha256 `{pre['sha256'][:16]}…`). Development result: "
             f"`docs/research/{symbol}_exp5_development.json`" + (f"; validation result: `docs/research/{symbol}_exp5_validation.json`." if val else "."))
    L.append("\n**The sealed final-test period was not read.** Development used the training segment (2003-05 to 2020-02-07); "
             "validation (2020-02-08 to 2023-06-24) is read only for cells that pass development.\n")
    n_cand = len(dev["candidates"])
    passed = val["passed"] if val else []
    L.append("## Result\n")
    if n_cand == 0:
        L.append(f"**No strategy passed.** Of {len(pre['tests'])} pre-registered cells (6 strategies × 2 directions × 7 timeframes), "
                 f"{dev['tests_run']} had at least 100 development trades and were tested; **none met all development criteria**, so "
                 "nothing was carried to validation and every strategy stays **NOT VALIDATED** in the product.\n")
    else:
        L.append(f"{n_cand} cell(s) passed development and were carried to validation; {len(passed)} passed validation. Passing validation "
                 "is not 'validated' in the product: the plan requires the sealed final test (separate approval) and a frozen paper "
                 "forward test first.\n")
    tot = sum(r["trades"] for r in rows)
    if tot:
        wmean = sum(r["expectancy_r"] * r["trades"] for r in rows) / tot
        pos = [r for r in rows if r["expectancy_r"] > 0]
        longs = sum(1 for r in pos if r["direction"] == "long")
        L.append(f"**In numbers:** {tot:,} simulated trades across the tested cells, a trade-weighted mean of {wmean:+.3f}R per trade after "
                 f"the real spread. {len(pos)} of {len(rows)} cells had a positive mean, {longs} of them on the long side: gold rose "
                 "strongly over the training years, which favours long trades of any rule. No cell kept a positive mean after every "
                 f"pre-registered check; the highest deflated Sharpe probability was {max(r['deflated_sharpe'] for r in rows):.2f} "
                 "(needed: 0.95).\n")
    L.append(f"Trials counted for the deflated Sharpe ratio: {dev['trials_counted_for_deflated_sharpe']} (experiments 1-5). "
             f"CSCV probability of backtest overfitting across the tested cells: {_f((dev.get('pbo') or {}).get('pbo'), 2, False)}.\n")
    L.append("## Development results per tested cell (training segment, after real bid/ask; TP1 full exit, 96-candle horizon)\n")
    L.append("| TF | Strategy | Side | Trades | Win | Avg win | Avg loss | Exp. R | 95% CI | PF | Max DD R | Edge vs random | BH q | DSR | Years + | Status |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: (x["tf"], x["strategy"], x["direction"])):
        ci = r.get("ci95")
        L.append(f"| {r['tf']} | {STRATEGY_NAMES[r['strategy']]} | {r['direction']} | {r['trades']:,} | {_f(r['win_rate'], 2, False)} | "
                 f"{_f(r.get('avg_win_r'), 2)} | {_f(r.get('avg_loss_r'), 2)} | {_f(r['expectancy_r'])} | "
                 f"{'[' + _f(ci[0]) + ', ' + _f(ci[1]) + ']' if ci else '—'} | {_f(r.get('profit_factor'), 2, False)} | "
                 f"{_f(r.get('max_drawdown_r'), 1, False)} | {_f(r.get('edge'))} | {_f(r.get('q'), 3, False)} | {_f(r.get('deflated_sharpe'), 2, False)} | "
                 f"{_f(r.get('positive_year_share'), 2, False)} | {r['status']} |")
    L.append("\nColumns: win = share of trades with R > 0; Exp. R = mean R per trade; CI = cluster-robust 95% interval (weekly clusters); "
             "PF = profit factor; edge = mean R minus the matched random-entry control mean; BH q = Benjamini-Hochberg across the tested "
             "cells; DSR = deflated Sharpe probability; Years + = share of development years with a positive mean.\n")
    L.append("## Robustness (development)\n")
    L.append("| TF | Strategy | Side | Without best year | At 2× spread | 48-candle horizon | Entry one candle late | Optimistic intrabar | Open at horizon |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: (x["tf"], x["strategy"], x["direction"])):
        L.append(f"| {r['tf']} | {STRATEGY_NAMES[r['strategy']]} | {r['direction']} | {_f(r.get('without_best_year'))} | {_f(r.get('at_2x_spread'))} | "
                 f"{_f((r.get('hold_48') or {}).get('expectancy_r'))} | {_f(r.get('late_entry_expectancy_r'))} | {_f(r.get('optimistic_expectancy_r'))} | "
                 f"{_f(r.get('open_at_horizon_share'), 2, False)} |")
    by = {}
    for r in rows:
        for k, v in (r.get("by_regime") or {}).items():
            by.setdefault(k, []).append(v)
    L.append("\n## Regime classifier usefulness (descriptive)\n")
    out = {(d["tf"], d["strategy"], d["direction"]): d for d in dev.get("outside_regime", [])}
    L.append("| TF | Strategy | Side | Inside compatible regimes: exp. R | Outside them: trades | Outside: exp. R |")
    L.append("|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: (x["tf"], x["strategy"], x["direction"])):
        o = out.get((r["tf"], r["strategy"], r["direction"]))
        L.append(f"| {r['tf']} | {STRATEGY_NAMES[r['strategy']]} | {r['direction']} | {_f(r['expectancy_r'])} | "
                 f"{o['outside_regime_trades'] if o else 0} | {_f(o['outside_regime_expectancy_r']) if o else '—'} |")
    not_run = [t for t in pre["tests"] if t["status"] != "run"]
    L.append(f"\n## Cells not tested ({len(not_run)}: fewer than 100 development signals, decided on counts only)\n")
    L.append(", ".join(f"{t['tf']} {STRATEGY_NAMES[t['strategy']]} {t['direction']} ({t['signals']})" for t in not_run) + "\n")
    if val:
        L.append("## Validation (frozen candidates only)\n")
        L.append("| TF | Strategy | Side | Trades | Exp. R | 95% CI | PF | Edge | Holm p | Status |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in val["rows"]:
            ci = r.get("ci95")
            L.append(f"| {r['tf']} | {STRATEGY_NAMES[r['strategy']]} | {r['direction']} | {r.get('trades', 0):,} | {_f(r.get('expectancy_r'))} | "
                     f"{'[' + _f(ci[0]) + ', ' + _f(ci[1]) + ']' if ci else '—'} | {_f(r.get('profit_factor'), 2, False)} | {_f(r.get('edge'))} | "
                     f"{_f(r.get('holm_p'), 3, False)} | {r['status']} |")
    L.append("\n## Method and deviations fixed before any outcome\n")
    for k, v in pre["settings_fixed_before_outcomes"].items():
        L.append(f"- **{k.replace('_', ' ')}**: {v}")
    L.append("\n## Limitations\n")
    L.append("- EURUSD and GBPUSD were not tested: Dukascopy refused or throttled most download requests during the release; the "
             "download resumes and the FX part can run when it completes (same pre-registered rules).")
    L.append("- The training segment was examined by experiments 1-4 (other rules); the deflated Sharpe counts all their trials.")
    L.append("- Slippage beyond the real spread, commission and swap are not in the main result; the 2× spread column is the cost stress test.")
    L.append("- Historical performance, even when positive, does not guarantee future results.")
    return "\n".join(L) + "\n"


def write(symbol: str) -> str:
    p = REPO_ROOT / "docs" / "reports" / f"{symbol}_EXPERIMENT5.md"
    p.write_text(render(symbol), encoding="utf8")
    return str(p)
