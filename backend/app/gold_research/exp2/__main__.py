"""python -m app.gold_research.exp2 simulate|develop|screen|report|scope [--tfs H4,H8,D1] [--log FILE]   (analysis only)"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from app.gold_research.exp2 import report, run

LOG: Path | None = None


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] exp2 {msg}"
    print(line, flush=True)
    if LOG:
        with LOG.open("a", encoding="utf8") as f:
            f.write(line + "\n")


def main() -> None:
    global LOG
    ap = argparse.ArgumentParser(prog="python -m app.gold_research.exp2")
    ap.add_argument("command", choices=("simulate", "develop", "screen", "report", "scope"))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--tfs", default=",".join(run.TFS))
    ap.add_argument("--log", type=Path)
    a = ap.parse_args()
    LOG = a.log
    if a.command == "simulate":
        for tf in [t.strip().upper() for t in a.tfs.split(",") if t.strip()]:
            run.run_tf(a.symbol, tf, log=log)
    elif a.command == "develop":
        s = run.develop(a.symbol, log=log)
        log(f"{s['tests']} tests with enough trades, {len(s['candidates'])} candidates: {json.dumps(s['candidates'])}")
        report.write(a.symbol, log=log)
    elif a.command == "screen":
        s = run.screen(a.symbol, log=log)
        log(f"screened {len(s['rows'])} candidates: {[(r['tf'], r['setup'], r['direction'], r['verdict']) for r in s['rows']]}")
        report.write(a.symbol, log=log)
    elif a.command == "scope":
        log(json.dumps(run.verify_scope(a.symbol)))
    else:
        report.write(a.symbol, log=log)


if __name__ == "__main__":
    main()
