"""python -m app.gold_research.exp6 rescore --symbol XAUUSD [--tfs M5,M15] | prereg | develop | confirm | report [--log FILE]"""
import argparse
from datetime import datetime
from pathlib import Path

from app.gold_research.exp5 import run as R5
from app.gold_research.exp6 import run
from app.gold_research.exp6.rescore import verdicts


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.gold_research.exp6")
    ap.add_argument("command", choices=("rescore", "prereg", "develop", "confirm", "report"))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--tfs", default=",".join(R5.TFS))
    ap.add_argument("--log", type=Path)
    a = ap.parse_args()

    def log(msg: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
        print(line, flush=True)
        if a.log:
            with a.log.open("a", encoding="utf8") as f:
                f.write(line + "\n")

    if a.command == "rescore":  # verdicts only (no outcome); one file per timeframe; resumable; parallel processes allowed
        out = run.out_dir(a.symbol)
        out.mkdir(parents=True, exist_ok=True)
        for tf in a.tfs.split(","):
            p = out / f"verdicts_{tf}.parquet"
            if p.exists():
                log(f"{a.symbol} {tf}: verdicts exist, kept")
                continue
            v = verdicts(a.symbol, tf, "validation", log)
            v.write_parquet(p, compression="zstd")
            log(f"{a.symbol} {tf}: {v.height:,} signals re-scored, all reproduced")
    elif a.command == "prereg":
        run.prereg(log)
    elif a.command == "develop":
        run.develop(log)
    elif a.command == "confirm":
        run.confirm(log)
    else:
        from app.gold_research.exp6 import report
        log(f"report written: {report.write()}")


if __name__ == "__main__":
    main()
