"""python -m app.gold_research.exp5 events|gate|develop|validate --symbol XAUUSD [--tfs M5,M15] [--log FILE]"""
import argparse
from datetime import datetime
from pathlib import Path

from app.gold_research.exp5 import run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("events", "gate", "develop", "validate"))
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--tfs", default=",".join(run.TFS))
    ap.add_argument("--log", type=Path)
    a = ap.parse_args()

    def log(msg: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
        print(line, flush=True)
        if a.log:
            with a.log.open("a", encoding="utf8") as f:
                f.write(line + "\n")

    if a.command == "events":  # signals only (no outcomes), one file per timeframe; can run in parallel processes
        out = run.out_dir(a.symbol)
        out.mkdir(parents=True, exist_ok=True)
        for tf in a.tfs.split(","):
            p = out / f"events_{tf}.parquet"
            if p.exists():
                log(f"{tf}: events exist, kept")
                continue
            ev = run.events(a.symbol, tf, "validation", log)
            ev.write_parquet(p, compression="zstd")
            log(f"{tf}: {ev.height:,} signals written")
    elif a.command == "gate":
        run.gate(a.symbol, log)
    elif a.command == "develop":
        run.develop(a.symbol, log)
    else:
        run.validate(a.symbol, log)


if __name__ == "__main__":
    main()
