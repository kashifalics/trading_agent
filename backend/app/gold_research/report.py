"""Markdown report of the pattern study, written only from the stored result files (nothing hand-entered)."""
import json

import numpy as np

from app.gold_research import sim, study
from app.historical.split import load_split


def _f(x, d=2, sign=True) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    return f"{x:+.{d}f}" if sign else f"{x:.{d}f}"


def render(symbol: str) -> str:
    o = study.out_dir(symbol)
    disc = json.loads((o / "discovery.json").read_text()) if (o / "discovery.json").exists() else None
    val = json.loads((o / "validation.json").read_text()) if (o / "validation.json").exists() else None
    sp = load_split(symbol)
    L = [f"# {symbol} pattern study", "",
         "_Written by `python -m app.gold_research report` from the stored trade files. Analysis only; nothing here is a trade "
         "recommendation._", "",
         "## Data and split", "",
         "| Segment | From | To (exclusive) | M1 candles | Used for |", "|---|---|---|---|---|",
         f"| Training | {sp['train']['start'][:10]} | {sp['train']['end_exclusive'][:10]} | {sp['train']['m1_rows']:,} | finding candidates |",
         f"| Validation | {sp['validation']['start'][:10]} | {sp['validation']['end_exclusive'][:10]} | {sp['validation']['m1_rows']:,} | confirming them |",
         f"| Final test | {sp['test']['start'][:10]} | open | {sp['test']['m1_rows_when_frozen']:,} at freeze | **sealed**, not read |", "",
         f"Split frozen {sp['created'][:10]} (SHA-256 `{sp['sha256'][:16]}`). Dukascopy 1-minute bid/ask; see XAUUSD_DATA_QUALITY.md.", "",
         "## Method (decided before any result was seen)", "",
         f"* **One main test per pattern, timeframe and direction:** the pattern's natural entry (next open; zones: a limit order at the "
         f"zone's near edge, live for {study.ZONE_WAIT} candles, cancelled by a close through its far edge), its structural stop plus "
         f"{study.STOP_BUFFER_ATR} ATR (at least {sim.MIN_RISK_ATR} ATR), a {study.PRIMARY_TARGET:g}R target and a "
         f"{study.PRIMARY_HOLD}-candle limit.",
         "* **Real execution prices:** longs buy at the ask and sell at the bid, shorts the reverse. Where the order of events inside a "
         "candle matters (fill candle, stop candle) the 1-minute path decides; inside one minute the stop counts first.",
         "* **Edge** = R minus the average R of matched random trades (same entry type and stop size or zone geometry, same New York "
         "session, volatility level, year and segment). This removes gold's uptrend and its daily rhythm.",
         f"* **Training:** Benjamini-Hochberg across every test with at least {study.MIN_N} trades (q < {study.FDR_Q}). Standard errors "
         "are clustered on blocks of max(one week, the holding period).",
         "* **Validation:** only the frozen candidate list, Holm-corrected (alpha 0.05); market entries must keep the edge when entered "
         "one candle later; 'confirmed' also requires a positive average R after the spread.",
         "* Other targets and holding periods are shown for description only and were never used to choose anything.", ""]
    if disc:
        rows = disc["rows"]
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        L += ["## Training result", "",
              f"{disc['tests']} tests with enough trades. " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + ".", ""]
        cands = [r for r in rows if r["status"] == "candidate"]
        if cands:
            L += ["### Candidates sent to validation", "",
                  "| TF | Pattern | Dir | Entry | Trades | Win % | Mean R | Control R | Edge | q | 1-candle-late edge |", "|---|---|---|---|---|---|---|---|---|---|---|"]
            for r in sorted(cands, key=lambda r: r["q"]):
                p, lt = r["primary"], r["late"]
                L.append(f"| {r['tf']} | {r['pattern']} | {r['direction']} | {r['entry']} | {p['n']:,} | {100 * p['win_rate']:.0f} | "
                         f"{_f(p['mean_r'])} | {_f(p['ctrl_mean_r'])} | {_f(p['edge'])} +/- {_f(p['edge_se'], 2, False)} | {r['q']:.4f} | "
                         f"{_f(lt.get('edge'))} |")
            L.append("")
        L += ["### Every test (training, main setting)", "",
              "Smallest detectable edge = the edge this sample would find 80% of the time; 'no edge' means no edge larger than that.", ""]
        for tf in dict.fromkeys(r["tf"] for r in rows):
            L += [f"#### {tf}", "", "| Pattern | Dir | Entry | Trades | Win % | Mean R | Edge | Smallest detectable | q | Status |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
            for r in sorted((r for r in rows if r["tf"] == tf), key=lambda r: (r["pattern"], r["direction"])):
                p = r["primary"]
                if p.get("n", 0) == 0:
                    continue
                L.append(f"| {r['pattern']} | {r['direction']} | {r['entry']} | {p['n']:,} | {100 * p['win_rate']:.0f} | {_f(p['mean_r'])} | "
                         f"{_f(p.get('edge'))} | {_f(r.get('mde'), 2, False)} | {r['q']:.3f} | {r['status']} |" if "q" in r else
                         f"| {r['pattern']} | {r['direction']} | {r['entry']} | {p['n']:,} | - | - | - | - | - | {r['status']} |")
            L.append("")
        share = [r["optimistic_share_changed"] for r in rows if r["primary"].get("n", 0)]
        if share:
            L += [f"Intrabar assumption: if the favourable extreme of the stop minute had come first, {100 * float(np.mean(share)):.2f}% of "
                  "main-test results (average over tests) would change.", ""]
    if val:
        L += ["## Validation result", "", f"Candidate list SHA-256 `{val['candidates_sha256'][:16]}` (frozen before validation was read).", "",
              "| TF | Pattern | Dir | Trades | Win % | Mean R | Edge | Holm p | Late edge | R with $0.30 spread | R with $0.10 slippage/side | Max DD (R) | Verdict |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in val["rows"]:
            v, lt, c = r["validation"], r["late"], r["cost_scenarios"]
            L.append(f"| {r['tf']} | {r['pattern']} | {r['direction']} | {v.get('n', 0):,} | {100 * v.get('win_rate', 0):.0f} | {_f(v.get('mean_r'))} | "
                     f"{_f(v.get('edge'))} | {_f(r.get('holm_p'), 4, False)} | {_f(lt.get('edge'))} | {_f(c['broker_0.30']['mean'])} | "
                     f"{_f(c['slippage_0.10_per_side']['mean'])} | {_f(r['max_drawdown_r'], 1, False)} | {r['verdict']} |")
        L.append("")
    L += ["## Limitations", "",
          "* One data source (Dukascopy); a broker's prices and spreads differ slightly.",
          "* Patterns are the platform's current detectors (Phase 1). The full pattern library, regimes, combinations and multi-timeframe "
          "studies follow in later phases and join the same validation family.",
          "* No news calendar; overnight swap is not charged (scenarios come with the swing-profile study).",
          "* Training and validation numbers are not the final test. The final test is run once, at the end, and reported separately."]
    return "\n".join(L) + "\n"


def export_summary(symbol: str) -> dict:
    """Small JSON for the live engine and the dashboard (bundled in app/data so the hosted backend can serve it): per test, the
    training statistics and, when validation has run, the validation verdict. Never contains final-test figures."""
    o = study.out_dir(symbol)
    disc = json.loads((o / "discovery.json").read_text()) if (o / "discovery.json").exists() else None
    val = json.loads((o / "validation.json").read_text()) if (o / "validation.json").exists() else None
    sp = load_split(symbol)
    rows = []
    vmap = {(r["tf"], r["pattern"], r["direction"]): r for r in (val or {}).get("rows", [])}
    for r in (disc or {}).get("rows", []):
        p = r["primary"]
        if p.get("n", 0) == 0:
            continue
        v = vmap.get((r["tf"], r["pattern"], r["direction"]))
        rows.append({"tf": r["tf"], "pattern": r["pattern"], "direction": r["direction"], "family": r["family"], "entry": r["entry"],
                     "training": {k: p.get(k) for k in ("n", "win_rate", "mean_r", "ctrl_mean_r", "edge", "edge_se", "profit_factor")},
                     "q": r.get("q"), "status": r["status"], "smallest_detectable_edge": r.get("mde"),
                     "validation": None if v is None else {**{k: v["validation"].get(k) for k in ("n", "win_rate", "mean_r", "edge", "edge_se")},
                                                           "holm_p": v.get("holm_p"), "verdict": v["verdict"]}})
    summary = {"symbol": symbol, "generated": (disc or {}).get("generated"),
               "split": {k: {kk: sp[k][kk] for kk in ("start", "end_exclusive") if kk in sp[k]} for k in ("train", "validation")} | {
                   "test": {"start": sp["test"]["start"], "sealed": True}},
               "main_test": {"target_r": study.PRIMARY_TARGET, "hold_candles": study.PRIMARY_HOLD},
               "costs": "Dukascopy bid/ask spread of each trade", "rows": rows,
               "counts": {s_: sum(1 for x in rows if x["status"] == s_) for s_ in ("candidate", "no edge in training", "not enough trades")}}
    from app.signals.classify import DATA
    DATA.write_text(json.dumps(summary, default=float), encoding="utf8")
    return summary


def write(symbol: str, log=print) -> None:
    p = study.report_path(symbol)
    p.write_text(render(symbol), encoding="utf8")
    log(f"report written: {p}")
    if (study.out_dir(symbol) / "discovery.json").exists():
        export_summary(symbol)
        log("live-engine summary written: app/data/gold_research_summary.json")
