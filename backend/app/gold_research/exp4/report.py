"""docs/reports/XAUUSD_EXPERIMENT4.md from the pre-registration and the frozen result (no number is typed by hand)."""
import json

from app.gold_research.exp4 import run


def _f(x, nd=3, sign=True):
    if x is None or x != x:
        return "-"
    return f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"


def write(symbol: str, log=print) -> str:
    pre = run.load_preregistration(symbol)
    res = json.loads(run.result_path(symbol).read_text()) if run.result_path(symbol).exists() else None
    L = [f"# {symbol} experiment 4: the flexible double top / double bottom", "",
         "_Written by `python -m app.gold_research.exp4 report`. Analysis only; nothing here is a trade recommendation._", "",
         "## Question", "",
         "Does the double-top detector pasted on 2026-11-12 (`detect_flexible_double_top`: lookback 20, peaks within 0.05%, sell on a "
         "close below the neckline), and its mirror image for double bottoms, earn money on gold after real costs, beyond what random "
         "entries of the same shape earn?", "",
         "## Method (pre-registered before any outcome was computed)", "",
         f"* Data: Dukascopy 1-minute bid/ask, **training period only** ({pre['segment']}). The sealed final test was not read.",
         f"* Main setting: {pre['main_setting']['entry']}; stop {pre['main_setting']['stop']}; target {pre['main_setting']['target_r']:g}R; "
         f"time stop {pre['main_setting']['hold_candles']} candles; {pre['main_setting']['costs']}.",
         f"* Controls: {pre['main_setting']['controls']}.",
         "* The pasted levels (stop 1.5 ATR beyond the peak, targets 2 and 4 ATR) were not tested: on 2019 M15 their first target was "
         "below 1:1 reward:risk on every signal (median 1:0.47) and the second never reached 1:2.",
         f"* Pre-registration: `docs/research/{symbol}_exp4_preregistration.json` (SHA-256 `{pre['sha256'][:16]}`), written on top "
         f"of commit `{(pre.get('code_commit') or '-')[:7]}` and committed together with the experiment code before any outcome was "
         "computed (see the git history of that file).", "",
         "Pass criteria (all must hold): " + "; ".join(pre["criteria"]) + ".", "", f"_{pre['interpretation']}_", "",
         "## Signal counts (counts only, fixed the test list)", "",
         "| TF | Pattern | Signals in training | Test |", "|---|---|---|---|"]
    for t in pre["tests"]:
        L.append(f"| {t['tf']} | {t['pattern']} | {t['signals']:,} | {t['status']} |")
    if not res:
        L += ["", "_Outcomes not computed yet._"]
    else:
        L += ["", "## Result", "",
              f"**{len(res['candidates'])} of {res['tests_run']} tests passed.** Deflated Sharpe counts "
              f"{res['trials_counted_for_deflated_sharpe']:,} trials (experiments 1-4).", "",
              "| TF | Pattern | Trades | Win % | Mean R (bid/ask) | Mean R ($0.30 spread) | Control R | Edge | q | 1 candle late edge | "
              "Deflated Sharpe | 2003-11 / 2012-20 | Status |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in res["rows"]:
            p, h = r["primary"], r["halves"]
            L.append(f"| {r['tf']} | {r['pattern']} | {r['trades']:,} | {100 * p['win_rate']:.0f} | {_f(p['mean_r'])} | "
                     f"{_f(r['broker_mean_r'])} | {_f(p['ctrl_mean_r'])} | {_f(p['edge'])} | {_f(r['q'], 3, False)} | "
                     f"{_f(r['late'].get('edge'))} | {_f(r['dsr'], 2, False)} | {_f(h.get('2003-2011'), 2)} / {_f(h.get('2012-2020'), 2)} | "
                     f"{r['status']} |")
        L += ["", "Failed criteria per test:", ""]
        for r in res["rows"]:
            bad = [k for k, v in r["checks"].items() if not v]
            L.append(f"* {r['tf']} {r['pattern']}: " + (", ".join(bad) if bad else "none"))
        L += ["", "### Other targets and holding periods (description only; never used to decide)", "",
              "| TF | Pattern | " + " | ".join(next(iter(res["rows"]))["grid"].keys()) + " |",
              "|---|---|" + "---|" * len(next(iter(res["rows"]))["grid"])] if res["rows"] else []
        for r in res["rows"]:
            L.append(f"| {r['tf']} | {r['pattern']} | " + " | ".join(f"{_f(v['mean_r'], 2)}" for v in r["grid"].values()) + " |")
        L += ["", "Cells: mean R per trade after the Dukascopy spread (target R / holding candles).", "",
              "## Cost context", "",
              "| TF | Pattern | Median stop (USD) | Median spread as share of the risk |", "|---|---|---|---|"]
        for r in res["rows"]:
            L.append(f"| {r['tf']} | {r['pattern']} | {r['median_risk_usd']:.2f} | {100 * r['median_spread_r']:.1f}% |")
    L += ["", "## Limitations", "",
          "* Training data only, and it was already examined by experiments 1-3: a pass would be a candidate, not a validated edge.",
          "* M1 was not tested (the study's control pools start at M5).",
          "* The study's gap rule drops trades whose 96-candle window touches a material data gap, including some US-holiday "
          "closures (documented in XAUUSD_PIPELINE_AUDIT.md); kept for comparability with the library's double top.",
          "* The $0.30 scenario replaces the entry spread only (one round trip per trade); no slippage or swap.", ""]
    path = run.report_path(symbol)
    path.write_text("\n".join(L), encoding="utf8")
    log(f"report written: {path}")
    return str(path)
