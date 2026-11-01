"""Reference-data seeding, candle ingestion (idempotent upsert), loading and coverage tracking."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, UnsupportedError
from app.database.base import utcnow
from app.database.models import Candle as CandleRow
from app.database.models import (
    DataCoverage,
    DataProvider,
    Instrument,
    ProviderInstrument,
)
from app.market_data.aggregation.aggregate import aggregate_candles
from app.market_data.base import MarketDataProvider
from app.market_data.calendars import get_calendar
from app.market_data.coverage.gaps import find_gaps
from app.market_data.normalization.normalize import normalize_candles
from app.market_data.registry import SEED_INSTRUMENTS, SEED_MAPPINGS, SEED_PROVIDERS
from app.market_data.timeframes import (
    SessionAnchor,
    approx_seconds,
    bucket_start,
    get_timeframe,
    plan_timeframe,
)
from app.market_data.types import Candle

MAX_BARS_PER_CALL = 100_000
CHUNK = 500


def seed_reference_data(session: Session) -> None:
    providers = {p.code: p for p in session.scalars(select(DataProvider))}
    for spec in SEED_PROVIDERS:
        if spec["code"] not in providers:
            p = DataProvider(**spec)
            session.add(p)
            providers[spec["code"]] = p
    insts = {i.canonical_symbol: i for i in session.scalars(select(Instrument))}
    for spec in SEED_INSTRUMENTS:
        if spec["canonical_symbol"] not in insts:
            i = Instrument(**spec)
            session.add(i)
            insts[spec["canonical_symbol"]] = i
    session.flush()
    existing = {(m.provider_id, m.instrument_id) for m in session.scalars(select(ProviderInstrument))}
    for sym, prov, psym, exch, kind, status, notes in SEED_MAPPINGS:
        key = (providers[prov].id, insts[sym].id)
        if key not in existing:
            session.add(ProviderInstrument(provider_id=key[0], instrument_id=key[1], provider_symbol=psym,
                                           exchange=exch, market_kind=kind, status=status, notes=notes))
    session.commit()


def anchor_for(inst: Instrument) -> SessionAnchor:
    return SessionAnchor.from_strings(inst.session_tz, inst.session_open)


def get_instrument(session: Session, canonical: str) -> Instrument:
    inst = session.scalar(select(Instrument).where(Instrument.canonical_symbol == canonical.upper()))
    if not inst:
        raise NotFoundError(f"Unknown instrument '{canonical}'")
    return inst


def resolve_mapping(session: Session, canonical: str, provider_code: str | None = None
                    ) -> tuple[Instrument, DataProvider, ProviderInstrument]:
    inst = get_instrument(session, canonical)
    q = select(ProviderInstrument, DataProvider).join(DataProvider).where(ProviderInstrument.instrument_id == inst.id)
    if provider_code:
        q = q.where(DataProvider.code == provider_code)
    rows = session.execute(q).all()
    if not rows:
        raise NotFoundError(f"No provider mapping for {canonical}")
    rank = {"active": 0, "unverified": 1, "unsupported": 2}
    pi, prov = sorted(rows, key=lambda r: rank.get(r[0].status, 9))[0]
    if pi.status == "unsupported":
        raise UnsupportedError(f"{canonical} is unsupported until a data source is configured. {pi.notes or ''}".strip(),
                               details={"instrument": canonical, "provider": prov.code})
    return inst, prov, pi


def _upsert(session: Session, rows: list[dict]) -> None:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover
        raise NotImplementedError(dialect)
    keys = ["provider_id", "instrument_id", "timeframe", "ts"]
    update_cols = ["open", "high", "low", "close", "volume", "volume_type", "is_complete", "origin",
                   "source_meta", "ingested_at"]
    for i in range(0, len(rows), CHUNK):
        stmt = insert(CandleRow).values(rows[i:i + CHUNK])
        stmt = stmt.on_conflict_do_update(index_elements=keys, set_={c: stmt.excluded[c] for c in update_cols})
        session.execute(stmt)
    session.commit()


def store_candles(session: Session, instrument_id: int, provider_id: int, timeframe: str,
                  candles: list[Candle]) -> int:
    now = utcnow()
    rows = [dict(instrument_id=instrument_id, provider_id=provider_id, timeframe=timeframe, ts=c.ts, open=c.open,
                 high=c.high, low=c.low, close=c.close, volume=c.volume, volume_type=c.volume_type,
                 is_complete=c.complete, origin=c.origin, source_meta=c.meta or None, ingested_at=now)
            for c in candles]
    if rows:
        _upsert(session, rows)
    return len(rows)


def load_candles(session: Session, instrument_id: int, provider_id: int, timeframe: str,
                 start: datetime | None = None, end: datetime | None = None, limit: int | None = None,
                 complete_only: bool = True) -> list[Candle]:
    q = select(CandleRow).where(CandleRow.instrument_id == instrument_id, CandleRow.provider_id == provider_id,
                                CandleRow.timeframe == timeframe)
    if complete_only:
        q = q.where(CandleRow.is_complete.is_(True))
    if start:
        q = q.where(CandleRow.ts >= start)
    if end:
        q = q.where(CandleRow.ts < end)
    if limit:  # most recent `limit` rows, returned ascending
        q = q.order_by(CandleRow.ts.desc()).limit(limit)
        rows = list(reversed(session.scalars(q).all()))
    else:
        rows = session.scalars(q.order_by(CandleRow.ts)).all()
    return [Candle(ts=r.ts, open=Decimal(r.open), high=Decimal(r.high), low=Decimal(r.low), close=Decimal(r.close),
                   volume=None if r.volume is None else Decimal(r.volume), complete=r.is_complete,
                   volume_type=r.volume_type, origin=r.origin, meta=r.source_meta or {}) for r in rows]


@dataclass
class IngestResult:
    instrument: str
    provider: str
    timeframe: str
    plan: str
    fetched: int = 0
    stored: int = 0
    rejected: int = 0
    duplicates: int = 0
    misaligned: int = 0  # candles whose open time is off the timeframe grid (rejected, never stored)
    aggregated_from: str | None = None
    coverage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def ingest_candles(session: Session, provider: MarketDataProvider, inst: Instrument, prov: DataProvider,
                   pi: ProviderInstrument, timeframe: str, bars: int = 1000, start: datetime | None = None,
                   end: datetime | None = None) -> IngestResult:
    tf = get_timeframe(timeframe)
    bars = max(1, min(bars, MAX_BARS_PER_CALL))
    plan = plan_timeframe(timeframe, set(provider.native_timeframes))
    if plan is None:
        raise UnsupportedError(f"{prov.code} cannot serve {timeframe} natively or by aggregation")
    kind, fetch_tf = plan
    fetch = get_timeframe(fetch_tf)
    result = IngestResult(inst.canonical_symbol, prov.code, timeframe, kind,
                          aggregated_from=fetch_tf if kind == "aggregate" else None)
    now = datetime.now(timezone.utc)
    mult = 1 if kind == "native" else int(approx_seconds(tf) / approx_seconds(fetch)) + 1
    fetch_bars = min(bars * mult, MAX_BARS_PER_CALL * 5)
    if start is None and end is None:
        start = now - timedelta(seconds=approx_seconds(fetch) * fetch_bars)
    try:
        raw = provider.get_candles(pi.provider_symbol, fetch_tf, start=start, end=end)
        clean, report = normalize_candles(raw)
        if kind == "native":  # a provider whose native grid differs from ours (e.g. DST-shifted 4H) must not be stored as-is
            anchor = anchor_for(inst)
            on_grid = [c for c in clean if bucket_start(c.ts, get_timeframe(fetch_tf), anchor) == c.ts]
            result.misaligned = len(clean) - len(on_grid)
            clean = on_grid
        result.fetched, result.rejected, result.duplicates = len(raw), len(report.rejected), report.duplicates
        result.stored = store_candles(session, inst.id, prov.id, fetch_tf, clean)
        if kind == "aggregate":
            base = load_candles(session, inst.id, prov.id, fetch_tf, start=start, end=end, complete_only=False)
            base = [c for c in base if get_calendar(inst.calendar).is_open(c.ts)]  # never aggregate closed-market quotes
            agg = aggregate_candles(base, fetch_tf, timeframe, anchor_for(inst), inst.calendar)
            result.stored += store_candles(session, inst.id, prov.id, timeframe, agg)
            refresh_coverage(session, inst, prov, fetch_tf, status="ok")
        result.coverage = refresh_coverage(session, inst, prov, timeframe, status="ok")
    except Exception as exc:
        refresh_coverage(session, inst, prov, timeframe, status="error", error=str(exc)[:500])
        raise
    return result


def refresh_coverage(session: Session, inst: Instrument, prov: DataProvider, timeframe: str,
                     status: str | None = None, error: str | None = None) -> dict:
    ts = list(session.scalars(select(CandleRow.ts).where(
        CandleRow.instrument_id == inst.id, CandleRow.provider_id == prov.id, CandleRow.timeframe == timeframe,
        CandleRow.is_complete.is_(True)).order_by(CandleRow.ts)))
    gaps = find_gaps(ts, timeframe, inst.calendar, anchor_for(inst)) if ts else []
    cov = session.scalar(select(DataCoverage).where(
        DataCoverage.instrument_id == inst.id, DataCoverage.provider_id == prov.id,
        DataCoverage.timeframe == timeframe))
    if not cov:
        cov = DataCoverage(instrument_id=inst.id, provider_id=prov.id, timeframe=timeframe)
        session.add(cov)
    cov.first_ts, cov.last_ts = (ts[0], ts[-1]) if ts else (None, None)
    cov.candle_count, cov.gap_count, cov.gaps = len(ts), len(gaps), gaps[:200]
    if status:
        cov.last_sync_status, cov.last_sync_at = status, utcnow()
        cov.last_error = error
    session.commit()
    return coverage_dict(cov, inst, prov)


def coverage_dict(cov: DataCoverage, inst: Instrument, prov: DataProvider) -> dict:
    return {
        "instrument": inst.canonical_symbol, "provider": prov.code, "timeframe": cov.timeframe,
        "first_ts": cov.first_ts, "last_ts": cov.last_ts, "candle_count": cov.candle_count,
        "gap_count": cov.gap_count, "gaps": cov.gaps or [], "last_sync_at": cov.last_sync_at,
        "last_sync_status": cov.last_sync_status, "last_error": cov.last_error,
    }
