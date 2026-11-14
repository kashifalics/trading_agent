"""python -m app.historical download|build|report|all|verify|crosscheck|quality|split|m1store|foundation [--symbols EURUSD,XAUUSD] [--interval 3] [--log FILE]   (docs/HISTORICAL_DATA.md)"""
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


def dukascopy_only(symbols: list[str]) -> list[str]:
    """The Dukascopy downloader never gets an instrument from another source (BTCUSDT comes from the Binance archive)."""
    return [s for s in symbols if INSTRUMENTS.get(s) is None or INSTRUMENTS[s].source == "dukascopy"]


def main() -> None:
    global LOG_FILE
    ap = argparse.ArgumentParser(prog="python -m app.historical")
    ap.add_argument("command", choices=("download", "build", "report", "all", "verify", "crosscheck", "quality", "split", "m1store",
                                        "foundation", "update", "download-binance"))
    ap.add_argument("--symbols", default=",".join(INSTRUMENTS))
    ap.add_argument("--interval", type=float, default=3.0, help="minimum seconds between Dukascopy requests")
    ap.add_argument("--force", action="store_true", help="rebuild normalized files even if unchanged")
    ap.add_argument("--log", type=Path, help="also append progress to this UTF-8 file")
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
    if a.command == "download-binance":
        from app.historical import binance_archive
        for s in symbols:
            if INSTRUMENTS[s].source == "binance":
                log(f"binance archive summary: {binance_archive.download(s, log=log)}")
        return
    if a.command == "update":
        # Continuous update: new days only (the downloader resumes), then rebuild, re-verify and refresh the M1 store.
        # The frozen split never moves: new days belong to the sealed final-test period (then to the forward paper test).
        from app.historical import store
        log(f"download summary: {download(dukascopy_only(symbols), min_interval=a.interval, log=log)}")
        for s in symbols:
            r = builder.build(s, log=log, force=a.force)
            log(f"{s}: coverage {r['coverage_pct']}%, {r['material_gaps']} material gaps")
            bad = [tf for tf, v in builder.verify_timeframes(s, log=lambda m: None).items() if not v["identical"]]
            log(f"{s}: timeframe check {'passed' if not bad else 'FAILED for ' + ', '.join(bad)}")
            store.build_m1_store(s, log=log)
        md = builder.report_markdown(symbols)
        DOC.write_text(md, encoding="utf8")
        log(f"report written: {DOC}")
        return
    if a.command in ("verify", "crosscheck", "quality", "split", "m1store", "foundation"):
        from app.historical import quality, reference, split, store

        steps = ("verify", "crosscheck", "quality", "split", "m1store") if a.command == "foundation" else (a.command,)
        for s in symbols:
            for step in steps:
                if step == "verify":
                    builder.verify_timeframes(s, log=log)
                elif step == "crosscheck":
                    log(f"{s}: Dukascopy cross-check {reference.cross_check(s, log=log)['summary']}")
                elif step == "quality":
                    quality.report(s, log=log)
                elif step == "split":
                    split.freeze_split(s, log=log)
                else:
                    store.build_m1_store(s, log=log)
        return
    if a.command in ("download", "all"):
        log(f"download summary: {download(dukascopy_only(symbols), min_interval=a.interval, log=log)}")
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
