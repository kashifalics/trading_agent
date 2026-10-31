import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.models import (
    DataCoverage,
    DataProvider,
    Instrument,
    ProviderInstrument,
)
from app.market_data.bars import Bars
from app.market_data.coverage.gaps import staleness
from app.market_data.ingestion.service import anchor_for, ingest_candles, load_candles
from app.market_data.registry import get_provider
from app.market_data.timeframes import get_timeframe

log = logging.getLogger(__name__)


def tf_step(code: str) -> int:
    """Nominal seconds per bar. Month-based timeframes use 31 days/month (conservative 'completeness' lag)."""
    tf = get_timeframe(code)
    return tf.seconds if tf.seconds else tf.months * 31 * 86400  # type: ignore[operator]


def ensure_data(session: Session, inst: Instrument, prov: DataProvider, pi: ProviderInstrument, timeframe: str,
                bars_needed: int, auto_sync: bool = True) -> list[str]:
    """Best-effort sync when data is missing or stale. Never raises for provider problems:
    returns warnings and lets analysis proceed on whatever is stored."""
    if not auto_sync:
        return []
    cov = session.scalar(select(DataCoverage).where(
        DataCoverage.instrument_id == inst.id, DataCoverage.provider_id == prov.id, DataCoverage.timeframe == timeframe))
    now = datetime.now(timezone.utc)
    count = cov.candle_count if cov else 0
    stale = staleness(cov.last_ts, timeframe, now, inst.calendar, anchor_for(inst)) if cov and cov.last_ts else None
    recently = cov and cov.last_sync_at and (now - cov.last_sync_at).total_seconds() < 30
    if (count >= bars_needed * 0.9 and stale is not None and stale <= 1) or recently:
        return []
    try:
        ingest_candles(session, get_provider(prov.code), inst, prov, pi, timeframe, bars=bars_needed)
        return []
    except AppError as exc:
        log.warning("auto-sync failed for %s %s: %s", inst.canonical_symbol, timeframe, exc.message)
        return [f"data sync failed ({exc.message}); using previously stored candles"]
    except Exception as exc:  # network etc.
        log.warning("auto-sync error %s", exc)
        return [f"data sync failed ({exc.__class__.__name__}); using previously stored candles"]


def load_bars(session: Session, inst: Instrument, prov: DataProvider, timeframe: str, n: int,
              end: datetime | None = None, start: datetime | None = None) -> Bars:
    candles = load_candles(session, inst.id, prov.id, timeframe, start=start, end=end, limit=n if not start else None,
                           complete_only=True)
    return Bars.from_candles(candles, tf_step(timeframe))


def recent_gap_count(session: Session, inst: Instrument, prov: DataProvider, timeframe: str) -> int:
    cov = session.scalar(select(DataCoverage).where(
        DataCoverage.instrument_id == inst.id, DataCoverage.provider_id == prov.id, DataCoverage.timeframe == timeframe))
    return cov.gap_count if cov else 0
