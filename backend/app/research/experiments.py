"""Experiment registry: dataset snapshot + configuration + code/library versions + results, so a run can be repeated."""
import hashlib
import platform
import time
from datetime import datetime, timezone
from decimal import Decimal
from importlib import metadata
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jsonutil import to_jsonable
from app.database.models import Candle as CandleRow
from app.database.models import Experiment

APP_DIR = Path(__file__).resolve().parents[1]
CODE_PACKAGES = ("backtesting", "ml_engine", "feature_engineering", "price_action", "market_structure", "candlestick",
                 "prediction", "historical_engine", "multi_timeframe", "research", "opportunities")


def _q(x) -> str:
    return format(Decimal(str(x)).quantize(Decimal("0.00000001")), "f")


def dataset_snapshot(session: Session, instrument_id: int, provider_id: int, timeframe: str, symbol: str,
                     provider: str, start: datetime | None = None, end: datetime | None = None,
                     complete_only: bool = True) -> dict:
    """Content hash of the exact candles an experiment used. Same stored data => same snapshot_id, on any machine."""
    q = select(CandleRow.ts, CandleRow.open, CandleRow.high, CandleRow.low, CandleRow.close, CandleRow.volume).where(
        CandleRow.instrument_id == instrument_id, CandleRow.provider_id == provider_id, CandleRow.timeframe == timeframe)
    if complete_only:
        q = q.where(CandleRow.is_complete.is_(True))
    if start:
        q = q.where(CandleRow.ts >= start)
    if end:
        q = q.where(CandleRow.ts <= end)
    h = hashlib.sha256()
    n, first, last = 0, None, None
    for r in session.execute(q.order_by(CandleRow.ts)):
        h.update(f"{r.ts.isoformat()}|{_q(r.open)}|{_q(r.high)}|{_q(r.low)}|{_q(r.close)}|"
                 f"{'' if r.volume is None else _q(r.volume)}\n".encode())
        n += 1
        first = first or r.ts
        last = r.ts
    return {"symbol": symbol, "provider": provider, "timeframe": timeframe, "complete_only": complete_only,
            "first_ts": first.isoformat() if first else None, "last_ts": last.isoformat() if last else None,
            "n_candles": n, "snapshot_id": h.hexdigest()[:16], "hash": "sha256(ts|o|h|l|c|v, 8dp) of ordered candles"}


def code_version() -> dict:
    """Hash of the source that produces results + versions of the numerical libraries."""
    h = hashlib.sha256()
    for pkg in CODE_PACKAGES:
        for f in sorted((APP_DIR / pkg).rglob("*.py")):
            h.update(f.relative_to(APP_DIR).as_posix().encode())
            h.update(f.read_bytes().replace(b"\r\n", b"\n"))
    libs = {}
    for lib in ("numpy", "pandas", "scikit-learn", "lightgbm", "xgboost", "scipy"):
        try:
            libs[lib] = metadata.version(lib)
        except metadata.PackageNotFoundError:  # pragma: no cover
            libs[lib] = None
    return {"source_sha256": h.hexdigest()[:16], "python": platform.python_version(), "libs": libs,
            "note": "project is not a git repository; source hash identifies the exact analysis code"}


def record_experiment(session: Session, kind: str, name: str, dataset: dict, config: dict, results: dict,
                      duration_s: float | None = None) -> Experiment:
    e = Experiment(kind=kind, name=name, dataset=to_jsonable(dataset), config=to_jsonable(config),
                   code_version=code_version(), results=to_jsonable(results), duration_s=duration_s)
    session.add(e)
    session.commit()
    return e


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.elapsed = time.perf_counter() - self.t0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
