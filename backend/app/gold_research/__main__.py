"""python -m app.gold_research run|discover|validate|report [--symbol XAUUSD] [--tfs M5,...] [--segment train] [--workers 3]

  run       simulate pattern trades and control pools for a segment (train first; validation only after discover froze candidates)
  discover  training statistics -> data/historical/research/{SYMBOL}/discovery.json + frozen docs/research/{SYMBOL}_candidates.json
  validate  validation statistics for the frozen candidates only
  report    docs/reports/PATTERN_STUDY_{SYMBOL}.md from the stored results
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
    ap.add_argument("command", choices=("run", "discover", "validate", "report"))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--tfs", default=",".join(study.STUDY_TFS))
    ap.add_argument("--segment", default="train", choices=("train", "validation"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--log", type=Path)
    a = ap.parse_args()
    LOG = a.log
    tfs = [t.strip().upper() for t in a.tfs.split(",") if t.strip()]
    if a.command == "run":
        if a.segment == "validation" and not study.candidates_path(a.symbol).exists():
            raise SystemExit("validation runs only after `discover` has frozen the candidate list")
        study.run(a.symbol, tfs, a.segment, workers=a.workers, log=log, log_file=str(LOG) if LOG else None)
    elif a.command == "discover":
        s = study.discover(a.symbol, tfs, log=log)
        log(f"{s['tests']} tests, {len(s['candidates'])} candidates: {json.dumps(s['candidates'])}")
        rep.write(a.symbol, log=log)
    elif a.command == "validate":
        s = study.validate(a.symbol, log=log)
        log(f"validated {len(s['rows'])} candidates")
        rep.write(a.symbol, log=log)
    else:
        rep.write(a.symbol, log=log)


if __name__ == "__main__":
    main()
