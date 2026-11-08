"""python -m app.historical download|build|report [--symbols EURUSD,XAUUSD] [--interval 1.0]   (docs/HISTORICAL_DATA.md)"""
import argparse
from datetime import datetime
from pathlib import Path

from app.historical import build as builder
from app.historical.config import INSTRUMENTS, REPORTS
from app.historical.download import download

DOC = Path(__file__).resolve().parents[3] / "docs" / "reports" / "HISTORICAL_COVERAGE.md"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.historical")
    ap.add_argument("command", choices=("download", "build", "report", "all"))
    ap.add_argument("--symbols", default=",".join(INSTRUMENTS))
    ap.add_argument("--interval", type=float, default=1.0, help="minimum seconds between Dukascopy requests")
    ap.add_argument("--force", action="store_true", help="rebuild normalized files even if unchanged")
    a = ap.parse_args()
    symbols = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    if a.command in ("download", "all"):
        log(f"download summary: {download(symbols, min_interval=a.interval, log=log)}")
    if a.command in ("build", "all"):
        for s in symbols:
            r = builder.build(s, log=log, force=a.force)
            log(f"{s}: coverage {r['coverage_pct']}%, {r['material_gaps']} material gaps")
    if a.command in ("report", "build", "all"):
        md = builder.report_markdown(symbols)
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "coverage.md").write_text(md, encoding="utf8")
        DOC.parent.mkdir(parents=True, exist_ok=True)
        DOC.write_text(md, encoding="utf8")
        log(f"report written: {DOC}")


if __name__ == "__main__":
    main()
