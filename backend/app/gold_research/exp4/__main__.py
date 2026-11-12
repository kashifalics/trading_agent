"""python -m app.gold_research.exp4 gate|simulate|develop|report [--tfs M5,M15] [--log FILE]   (analysis only)

Order: gate (counts only) -> commit the pre-registration -> simulate -> develop -> report. simulate and develop refuse to run
without the pre-registration file."""
import argparse
from datetime import datetime
from pathlib import Path

from app.gold_research.exp4 import report, run

LOG: Path | None = None


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] exp4 {msg}"
    print(line, flush=True)
    if LOG:
        with LOG.open("a", encoding="utf8") as f:
            f.write(line + "\n")


def main() -> None:
    global LOG
    ap = argparse.ArgumentParser(prog="python -m app.gold_research.exp4")
    ap.add_argument("command", choices=("gate", "simulate", "develop", "report"))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--tfs", default=None, help="default: the pre-registered timeframes with a test to run")
    ap.add_argument("--log", type=Path)
    a = ap.parse_args()
    LOG = a.log
    if a.command == "gate":
        run.gate(a.symbol, log=log)
    elif a.command == "simulate":
        pre = run.load_preregistration(a.symbol)
        tfs = [t.strip().upper() for t in a.tfs.split(",")] if a.tfs else sorted({t["tf"] for t in pre["tests"] if t["status"] == "run"},
                                                                                  key=run.TFS.index)
        for tf in tfs:
            run.simulate_tf(a.symbol, tf, log=log)
    elif a.command == "develop":
        s = run.develop(a.symbol, log=log)
        log(f"{s['tests_run']} tests run, {len(s['candidates'])} training candidates: {s['candidates']}")
        report.write(a.symbol, log=log)
    else:
        report.write(a.symbol, log=log)


if __name__ == "__main__":
    main()
