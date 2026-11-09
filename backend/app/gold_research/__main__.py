"""python -m app.gold_research run|discover|validate|report [--symbol XAUUSD] [--tfs M5,...] [--segment train] [--workers 3]

  run       simulate pattern trades and control pools for a segment (train first; validation only after discover froze candidates)
  discover  training statistics -> data/historical/research/{SYMBOL}/discovery.json + frozen docs/research/{SYMBOL}_candidates.json
  validate  validation statistics for the frozen candidates only
  report    docs/reports/PATTERN_STUDY_{SYMBOL}.md from the stored results
  library   docs/PATTERN_LIBRARY.md from the pattern registry
  ml-train     walk-forward models on training trades (M15, H1, H4) -> challengers
  ml-validate  the frozen challenger --version on the validation segment (once) and the promotion gate
  ml-validate-all  every latest challenger on the validation segment
  preregister  freeze the final-test hypotheses (commit the file afterwards)
  final-test   --confirm-final-test: the one-time evaluation on the sealed period
  monitor      recent-performance check (only after the final test; the sealed period is never peeked at)
  promote      --version X --approve: champion pointer, only for a challenger that passed validation
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from app.gold_research import report as rep
from app.gold_research import study

LOG: Path | None = None


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    if LOG:
        with LOG.open("a", encoding="utf8") as f:
            f.write(line + "\n")


def main() -> None:
    global LOG
    ap = argparse.ArgumentParser(prog="python -m app.gold_research")
    ap.add_argument("command", choices=("run", "discover", "validate", "report", "library", "ml-train", "ml-validate", "ml-validate-all", "promote", "preregister", "final-test", "monitor", "audit"))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--tfs", default=",".join(study.STUDY_TFS))
    ap.add_argument("--segment", default="train", choices=("train", "validation"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--source", default="library", choices=("library", "unsup"),
                    help="run: the pattern library, or the frozen unnamed-pattern model (phase 6, H1/H4)")
    ap.add_argument("--version", help="model version (ml-validate, promote)")
    ap.add_argument("--approve", action="store_true", help="explicit approval to promote a validated challenger")
    ap.add_argument("--confirm-final-test", action="store_true", help="explicitly run the one-time final test on the sealed period")
    a = ap.parse_args()
    LOG = a.log
    tfs = [t.strip().upper() for t in a.tfs.split(",") if t.strip()]
    if a.command == "run":
        if a.segment == "validation" and not study.frozen_stages(a.symbol):
            raise SystemExit("validation runs only after `discover` has frozen the candidate list")
        if a.source == "unsup":
            from app.gold_research.unsupervised import UNSUP_TFS
            tfs = [t for t in tfs if t in UNSUP_TFS] if a.tfs != ",".join(study.STUDY_TFS) else list(UNSUP_TFS)
        study.run(a.symbol, tfs, a.segment, workers=a.workers, log=log, log_file=str(LOG) if LOG else None, source=a.source)
    elif a.command == "discover":
        s = study.discover(a.symbol, tfs, log=log)
        log(f"{s['tests']} tests, {len(s['candidates'])} candidates: {json.dumps(s['candidates'])}")
        rep.write(a.symbol, log=log)
    elif a.command == "validate":
        s = study.validate(a.symbol, log=log)
        log(f"validated {len(s['rows'])} candidates")
        rep.write(a.symbol, log=log)
    elif a.command == "ml-train":
        from app.gold_research import ml
        ml_tfs = [t for t in tfs if t in ml.ML_TFS] if a.tfs != ",".join(study.STUDY_TFS) else list(ml.ML_TFS)
        s = ml.train(a.symbol, ml_tfs, log=log)
        log(f"challengers: {[v['challenger'] for v in s['tfs'].values()]}")
    elif a.command == "ml-validate":
        from app.gold_research import ml
        log(f"{ml.validate_model(a.symbol, a.version, log=log)}")
    elif a.command == "ml-validate-all":
        from app.gold_research import ml
        summ = json.loads((study.out_dir(a.symbol) / "ml_training.json").read_text())
        for tf, r in summ["tfs"].items():
            log(f"{tf} {r['challenger']}: {ml.validate_model(a.symbol, r['challenger'], log=log)['passed_gate']}")
        from app.gold_research import dashboard
        dashboard.build(a.symbol)
    elif a.command == "preregister":
        from app.gold_research import final_test
        final_test.preregister(a.symbol, log=log)
    elif a.command == "final-test":
        from app.gold_research import final_test
        final_test.run_final_test(a.symbol, log=log, i_understand_this_is_once=a.confirm_final_test)
    elif a.command == "audit":
        from app.gold_research import audit
        audit.run(a.symbol, log=log)
    elif a.command == "monitor":
        from app.gold_research import final_test
        sealed_runs = (study.SPLIT_DIR / f"{a.symbol}_seal_log.md")
        done = sealed_runs.exists() and "FINAL TEST RUN" in sealed_runs.read_text(encoding="utf8")
        if not done:
            log("monitoring waits for the one-time final test: every day after 2023-06-24 belongs to the sealed test period, so "
                "recent performance cannot be looked at yet without spending the final test.")
        else:
            log("final test done: new days after the freeze date form the forward test. Re-run `run --segment validation` style "
                "evaluation on them with `final-test`-frozen hypotheses, or train challengers with ml-train and compare them with "
                f"the champion; promotion still needs --approve. Pre-registration: {final_test.prereg_path(a.symbol)}")
    elif a.command == "promote":
        from app.gold_research import ml
        log(f"{ml.promote(a.symbol, a.version, approve=a.approve)}")
    elif a.command == "library":
        from app.historical.config import REPO_ROOT
        from app.patterns.registry import library_markdown
        p = REPO_ROOT / "docs" / "PATTERN_LIBRARY.md"
        p.write_text(library_markdown(), encoding="utf8")
        log(f"written: {p}")
    else:
        rep.write(a.symbol, log=log)


if __name__ == "__main__":
    main()
