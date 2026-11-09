"""python -m app.historical download|build|report|all|patterns|patterns-report [--symbols EURUSD,XAUUSD] [--interval 3] [--log FILE]   (docs/HISTORICAL_DATA.md)"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from app.historical import build as builder
from app.historical.config import DATA_ROOT, INSTRUMENTS, REPORTS
from app.historical.download import download

DOC = Path(__file__).resolve().parents[3] / "docs" / "reports" / "HISTORICAL_COVERAGE.md"
LOG_FILE: Path | None = None
# Optional allowlist, one symbol per line: instruments not listed are skipped (exit 0), so the batch file moves on without them.
ONLY_FILE = DATA_ROOT / "only_symbols.txt"


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    if LOG_FILE:
        with LOG_FILE.open("a", encoding="utf8") as f:
            f.write(line + "\n")


def unattended_windows() -> None:
    """Long unattended run on Windows: turn off console QuickEdit (a stray click in the window otherwise freezes the program until a
    key is pressed) and ask Windows not to idle-sleep while this process runs. Does nothing elsewhere."""
    if sys.platform != "win32":
        return
    import ctypes

    k32 = ctypes.windll.kernel32
    handle = k32.GetStdHandle(-10)  # console input
    mode = ctypes.c_uint32()
    if k32.GetConsoleMode(handle, ctypes.byref(mode)):
        k32.SetConsoleMode(handle, (mode.value & ~0x0040) | 0x0080)  # clear ENABLE_QUICK_EDIT_MODE, set ENABLE_EXTENDED_FLAGS
    k32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED


def main() -> None:
    global LOG_FILE
    ap = argparse.ArgumentParser(prog="python -m app.historical")
    ap.add_argument("command", choices=("download", "build", "report", "all", "patterns", "patterns-report"))
    ap.add_argument("--symbols", default=",".join(INSTRUMENTS))
    ap.add_argument("--interval", type=float, default=3.0, help="minimum seconds between Dukascopy requests")
    ap.add_argument("--force", action="store_true", help="rebuild normalized files even if unchanged")
    ap.add_argument("--log", type=Path, help="also append progress to this UTF-8 file")
    ap.add_argument("--tfs", default="M5,M15,M30,H1,H4,D1", help="timeframes for the pattern study")
    ap.add_argument("--workers", type=int, default=3, help="timeframes studied in parallel")
    a = ap.parse_args()
    LOG_FILE = a.log
    if LOG_FILE:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    unattended_windows()
    symbols = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    if ONLY_FILE.exists():
        allowed = {ln.strip().upper() for ln in ONLY_FILE.read_text(encoding="utf8").splitlines() if ln.strip()}
        skipped = [s for s in symbols if s not in allowed]
        if skipped:
            log(f"skipping {', '.join(skipped)}: not listed in {ONLY_FILE} (delete that file to download every instrument)")
        symbols = [s for s in symbols if s in allowed]
        if not symbols:
            return
    if a.command in ("patterns", "patterns-report"):
        from app.historical import study

        tfs = [t.strip().upper() for t in a.tfs.split(",") if t.strip()]
        for s in symbols:
            if a.command == "patterns":
                study.run(s, tfs, workers=a.workers, log=log, log_file=str(LOG_FILE) if LOG_FILE else None)
            else:
                study.report(s, tfs, log=log)
        return
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
