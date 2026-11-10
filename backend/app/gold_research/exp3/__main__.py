"""python -m app.gold_research.exp3 gate|simulate|develop|report|scope [--tfs H1,H4] [--log FILE]   (analysis only)

Order: gate (counts only) -> commit the pre-registration -> simulate -> develop -> report. simulate and develop refuse to run
without the pre-registration file."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from app.gold_research.exp3 import report, run

LOG: Path | None = None


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] exp3 {msg}"
    print(line, flush=True)
    if LOG:
        with LOG.open("a", encoding="utf8") as f:
            f.write(line + "\n")


def main() -> None:
    global LOG
    ap = argparse.ArgumentParser(prog="python -m app.gold_research.exp3")
    ap.add_argument("command", choices=("gate", "simulate", "develop", "report", "scope"))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--tfs", default=",".join(run.TFS))
    ap.add_argument("--log", type=Path)
    a = ap.parse_args()
    LOG = a.log
    if a.command == "gate":
        run.gate(a.symbol, log=log)
    elif a.command == "simulate":
        for tf in [t.strip().upper() for t in a.tfs.split(",") if t.strip()]:
            log(f"{tf}: simulating")
            run.run_tf(a.symbol, tf, log=log)
    elif a.command == "develop":
        s = run.develop(a.symbol, log=log)
        log(f"{s['tests_run']} tests run, {len(s['candidates'])} candidates: {json.dumps(s['candidates'])}")
        report.write(a.symbol, log=log)
    elif a.command == "scope":
        log(json.dumps(run.verify_scope(a.symbol)))
    else:
        report.write(a.symbol, log=log)


if __name__ == "__main__":
    main()
