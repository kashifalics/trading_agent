"""Phase 7: the one-time final test on the sealed period (brief Part 11). Analysis only.

    python -m app.gold_research preregister   writes docs/research/{SYMBOL}_preregistration.json (commit it before the test)
    python -m app.gold_research final-test    refuses unless that file is committed and unchanged; then evaluates ONCE

Pre-registration fixes, before any final-test data is read: the hypotheses (the patterns that passed validation, with their
trigger and main setting), the models (challengers that passed the validation gate, by SHA-256), the pass criteria, the
multiple-testing family (Holm over all pre-registered pattern hypotheses), the primary cost scenario, the split and raw-data hashes
and the git commit. Every result is reported, failures included. Running it a second time is allowed only to fix a bug, and the
report then says the test set is no longer untouched (the seal log records every read).
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.gold_research import ml, study
from app.gold_research import stats as Stt
from app.historical.config import REPO_ROOT, TF_SECONDS
from app.historical.split import SPLIT_DIR, load_split

CRITERIA = {"alpha": 0.05, "family": "Holm over all pre-registered pattern hypotheses",
            "pattern_pass": "edge versus matched controls > 0 (Holm p < alpha) AND mean R after spread > 0 (p < alpha), >= 100 trades",
            "model_pass": "Brier skill > 0, ECE <= 0.05, selected trades' expectancy 95% CI above 0 (same gate as validation)",
            "costs": "Dukascopy bid/ask spread of each trade (primary); $0.30 spread and $0.10/side slippage reported as scenarios"}


def prereg_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_preregistration.json"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()


def preregister(symbol: str, log=print) -> dict:
    val = json.loads((study.out_dir(symbol) / "validation.json").read_text())
    hyps = [{k: r.get(k) for k in ("tf", "pattern", "direction", "trigger", "flag", "entry", "stage")} | {"validation_verdict": r["verdict"]}
            for r in val["rows"] if r["verdict"].startswith("CONFIRMED")]
    models = []
    mdir = ml.models_dir(symbol)
    for meta_p in sorted(mdir.glob("*/meta.json")) if mdir.exists() else []:
        meta = json.loads(meta_p.read_text())
        if (meta.get("validation") or {}).get("passed_gate"):
            models.append({"version": meta["version"], "tf": meta["tf"], "sha256": meta["sha256"]})
    sp = load_split(symbol)
    doc = {"symbol": symbol, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "main_setting": {"target_r": study.PRIMARY_TARGET, "hold_candles": study.PRIMARY_HOLD, "stop": "structural + 0.1 ATR"},
           "pattern_hypotheses": hyps, "models": models, "criteria": CRITERIA, "split_sha256": sp["sha256"],
           "raw_manifest_sha256": sp.get("raw_manifest_sha256"), "candidates_sha256": val.get("candidates_sha256"),
           "git_commit": _git("rev-parse", "HEAD"),
           "note": "Nothing in the final-test period has been read when this file is written. If nothing passed validation, the "
                   "final test still runs to report that the validated set is empty."}
    doc["sha256"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    p = prereg_path(symbol)
    if p.exists():
        raise RuntimeError(f"{p.name} already exists; a pre-registration is written once")
    p.write_text(json.dumps(doc, indent=1), encoding="utf8")
    log(f"pre-registration written: {p} ({len(hyps)} pattern hypotheses, {len(models)} models). Commit it, then run final-test.")
    return doc


def _committed(path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    tracked = bool(_git("ls-files", rel))
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=REPO_ROOT).returncode == 0
    return tracked and clean


def run_final_test(symbol: str, log=print, i_understand_this_is_once: bool = False) -> dict:
    p = prereg_path(symbol)
    if not p.exists():
        raise RuntimeError("no pre-registration: run `preregister` and commit the file first")
    if not _committed(p):
        raise RuntimeError(f"{p.name} is not committed (or was changed after committing); commit it before the final test")
    if not i_understand_this_is_once:
        raise RuntimeError("the final test reads the sealed period; pass --confirm-final-test to run it")
    pre = json.loads(p.read_text())
    body = {k: v for k, v in pre.items() if k != "sha256"}
    if hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != pre["sha256"]:
        raise RuntimeError("pre-registration content does not match its hash")
    seal_log = SPLIT_DIR / f"{symbol}_seal_log.md"
    previous_runs = seal_log.read_text(encoding="utf8").count("FINAL TEST RUN") if seal_log.exists() else 0
    with seal_log.open("a", encoding="utf8") as f:
        f.write(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | FINAL TEST RUN #{previous_runs + 1} (pre-registration "
                f"{pre['sha256'][:12]}) | {_git('rev-parse', '--short', 'HEAD')} |\n")
    tfs = sorted({h["tf"] for h in pre["pattern_hypotheses"]} | {m["tf"] for m in pre["models"]})
    for tf in tfs:
        study.run_timeframe(symbol, tf, "test", final_test=True)
    rows = []
    frames = dict(study.load_frames(symbol, tfs, "test", log, final_test=True)) if tfs else {}
    for h in pre["pattern_hypotheses"]:
        tr, pool = frames[h["tf"]]
        d = 1 if h["direction"] == "long" else -1
        g = tr.filter((pl.col("pattern") == (h.get("trigger") or h["pattern"])) & (pl.col("direction") == d))
        if h.get("flag"):
            g = g.filter(pl.col(h["flag"]))
        prim = study._with_ctrl(g, pool, study.PRIMARY_TARGET, study.PRIMARY_HOLD)
        e = study._edge(prim, h["tf"], study.PRIMARY_HOLD)
        r = prim["r"].to_numpy()
        risk, spread = prim["risk_px"].to_numpy(), prim["spread_entry"].to_numpy()
        cl = Stt.cluster_ids(prim["entry_ts"].to_numpy(), study.PRIMARY_HOLD * TF_SECONDS[h["tf"]])
        scen = {k: Stt.clustered_mean(v[np.isfinite(v)], cl[np.isfinite(v)])["mean"] for k, v in
                (("broker_0.30", r + (spread - study.BROKER_SPREAD) / risk), ("slippage_0.10_per_side", r - 0.20 / risk))}
        rows.append({**h, "test": e, "cost_scenarios": scen, "max_drawdown_r": Stt.drawdown_r(r[np.isfinite(r)])})
    ok = [r for r in rows if r["test"].get("n", 0) >= 100]
    for r, hp in zip(ok, Stt.holm(np.array([r["test"]["p_edge"] for r in ok]))):
        r["holm_p"] = float(hp)
    for r in rows:
        t = r["test"]
        r["passed"] = bool(t.get("n", 0) >= 100 and r.get("holm_p", 1) < CRITERIA["alpha"] and t["edge"] > 0 and t["mean_r"] > 0
                           and t["p_profit"] < CRITERIA["alpha"])
    models = [{**m, "result": ml.validate_model(symbol, m["version"], log, segment="test", final_test=True)} for m in pre["models"]]
    out = {"symbol": symbol, "run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run_number": previous_runs + 1,
           "untouched": previous_runs == 0, "preregistration_sha256": pre["sha256"], "patterns": rows, "models": models}
    (study.out_dir(symbol) / "final_test.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf8")
    (REPO_ROOT / "docs" / "reports" / f"{symbol}_FINAL_TEST.md").write_text(render(out, pre), encoding="utf8")
    log(f"final test written: {sum(r['passed'] for r in rows)}/{len(rows)} pattern hypotheses passed")
    return out


def render(out: dict, pre: dict) -> str:
    sp = load_split(out["symbol"])
    f = lambda x, d=2: "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:+.{d}f}"  # noqa: E731
    L = [f"# {out['symbol']} final test", "",
         f"_Run {out['run']} (run #{out['run_number']}). Period {sp['test']['start'][:10]} onward, never read before this run._", "",
         "**The test set is untouched.**" if out["untouched"] else
         "**WARNING: this is not the first final-test run, so the test set is no longer untouched; earlier runs are in the seal log.**", "",
         f"Pre-registration SHA-256 `{out['preregistration_sha256'][:16]}`, committed before this run. Criteria: {CRITERIA['pattern_pass']}; "
         f"{CRITERIA['family']}; costs: {CRITERIA['costs']}.", "", "## Pattern hypotheses (every result, failures included)", ""]
    if not out["patterns"]:
        L.append("No pattern passed validation, so there was nothing to test: the validated set is empty.")
    else:
        L += ["| TF | Pattern | Dir | Trades | Win % | Mean R | Edge | Holm p | $0.30 spread | $0.10 slip/side | Max DD (R) | Passed |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in out["patterns"]:
            t = r["test"]
            L.append(f"| {r['tf']} | {r['pattern']} | {r['direction']} | {t.get('n', 0):,} | {100 * t.get('win_rate', 0):.0f} | "
                     f"{f(t.get('mean_r'))} | {f(t.get('edge'))} | {r.get('holm_p', float('nan')):.4f} | {f(r['cost_scenarios']['broker_0.30'])} | "
                     f"{f(r['cost_scenarios']['slippage_0.10_per_side'])} | {r['max_drawdown_r']:.1f} | {'yes' if r['passed'] else 'no'} |")
    L += ["", "## Models", ""]
    if not out["models"]:
        L.append("No model passed the validation gate, so none was tested.")
    for m in out["models"]:
        res = m["result"]
        L.append(f"* {m['version']}: {'passed' if res['passed_gate'] else 'did not pass'} ({', '.join(res['gate_failures']) or 'all criteria met'}); "
                 f"ROC-AUC {res['metrics'].get('roc_auc', float('nan')):.3f}, Brier skill {res['metrics'].get('brier_skill', float('nan')):+.4f}, "
                 f"ECE {res['metrics'].get('ece', float('nan')):.3f}.")
    L += ["", "Analysis only. A pass here is evidence, not a guarantee; live results are tracked separately by paper trading."]
    return "\n".join(L) + "\n"
