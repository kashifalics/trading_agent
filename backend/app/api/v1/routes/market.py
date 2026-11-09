import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    AppError,
    NotFoundError,
    ProviderNotConfigured,
    UnsupportedError,
)
from app.core.security import get_current_user
from app.database.models import (
    DataCoverage,
    DataProvider,
    Instrument,
    ProviderInstrument,
    User,
)
from app.database.session import get_session
from app.market_data.ingestion.service import (
    coverage_dict,
    get_instrument,
    ingest_candles,
    load_candles,
    resolve_mapping,
)
from app.market_data.registry import get_provider
from app.market_data.timeframes import TIMEFRAME_ORDER, TIMEFRAMES
from app.schemas.common import Page
from app.schemas.market import (
    CandleOut,
    CandlesResponse,
    CoverageOut,
    InstrumentOut,
    MappingOut,
    ProbeRequest,
    QuoteOut,
    SyncRequest,
    TimeframeOut,
)
from app.services.audit import audit
from app.services.data_service import trading_hours_only as filter_closed

router = APIRouter(prefix="/market", tags=["market"])
_quote_cache: dict[str, tuple[float, QuoteOut]] = {}
MAX_QUOTE_SYMBOLS = 20


def _instrument_out(session: Session, inst: Instrument) -> InstrumentOut:
    rows = session.execute(select(ProviderInstrument, DataProvider).join(DataProvider).where(
        ProviderInstrument.instrument_id == inst.id)).all()
    maps = [MappingOut(provider=p.code, provider_symbol=pi.provider_symbol, exchange=pi.exchange, market_kind=pi.market_kind,
                       status=pi.status, notes=pi.notes) for pi, p in rows]
    out = InstrumentOut.model_validate(inst)
    out.mappings = maps
    out.supported = any(m.status != "unsupported" for m in maps)
    return out


@router.get("/instruments", response_model=list[InstrumentOut])
def instruments(all: bool = Query(False, description="include instruments outside FOCUS_SYMBOLS"),
                session: Session = Depends(get_session)):
    focus = get_settings().focus_list
    rows = session.scalars(select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.id)).all()
    return [_instrument_out(session, i) for i in rows if all or not focus or i.canonical_symbol in focus]


@router.get("/timeframes", response_model=list[TimeframeOut])
def timeframes():
    from app.market_data.binance.provider import BinanceProvider
    from app.market_data.twelve_data.provider import TwelveDataProvider

    native = {"binance": set(BinanceProvider.native_timeframes), "twelve_data": set(TwelveDataProvider.native_timeframes)}
    return [TimeframeOut(code=c, label=TIMEFRAMES[c].label, seconds=TIMEFRAMES[c].seconds, months=TIMEFRAMES[c].months,
                         native_on=[p for p, s in native.items() if c in s]) for c in TIMEFRAME_ORDER]


@router.get("/candles", response_model=CandlesResponse)
def candles(symbol: str, timeframe: str, provider: str | None = None, limit: int = Query(500, ge=1, le=5000),
            start: datetime | None = None, end: datetime | None = None, include_incomplete: bool = False,
            trading_hours_only: bool = Query(True, description="hide candles stamped inside the market closure"),
            session: Session = Depends(get_session)):
    if timeframe not in TIMEFRAMES:
        raise AppError(f"Unsupported timeframe '{timeframe}'", details={"supported": TIMEFRAME_ORDER})
    inst, prov, _ = resolve_mapping(session, symbol, provider)
    fetch = limit if (inst.calendar == "continuous" or not trading_hours_only) else int(limit * 1.25) + 5
    rows = load_candles(session, inst.id, prov.id, timeframe, start=start, end=end, limit=fetch,
                        complete_only=not include_incomplete)
    if trading_hours_only:
        rows = filter_closed(rows, inst.calendar)[-limit:]
    return CandlesResponse(
        symbol=inst.canonical_symbol, timeframe=timeframe, provider=prov.code, price_precision=inst.price_precision,
        count=len(rows), candles=[CandleOut(time=int(c.ts.timestamp()), open=float(c.open), high=float(c.high),
                                            low=float(c.low), close=float(c.close),
                                            volume=None if c.volume is None else float(c.volume), complete=c.complete,
                                            origin=c.origin) for c in rows])


@router.get("/coverage", response_model=list[CoverageOut])
def coverage(symbol: str | None = None, session: Session = Depends(get_session)):
    q = select(DataCoverage, Instrument, DataProvider).join(Instrument, DataCoverage.instrument_id == Instrument.id) \
        .join(DataProvider, DataCoverage.provider_id == DataProvider.id)
    if symbol:
        q = q.where(Instrument.canonical_symbol == symbol.upper())
    return [CoverageOut(**coverage_dict(c, i, p)) for c, i, p in session.execute(q.order_by(Instrument.canonical_symbol))]


@router.get("/providers")
def providers(session: Session = Depends(get_session)) -> list[dict]:
    out = []
    for p in session.scalars(select(DataProvider)):
        meta, status = None, "no_adapter"
        try:
            adapter = get_provider(p.code)
            meta = adapter.get_provider_metadata()
            status = "configured" if adapter.is_configured() else "needs_api_key"
        except NotFoundError:
            pass
        maps = session.execute(select(ProviderInstrument, Instrument).join(Instrument).where(
            ProviderInstrument.provider_id == p.id)).all()
        out.append({
            "code": p.code, "name": p.name, "requires_api_key": p.requires_api_key, "status": status,
            "free_plan": meta.free_plan if meta else None, "licensing": meta.licensing if meta else None,
            "docs_url": meta.docs_url if meta else (p.meta or {}).get("docs"),
            "signup_url": meta.signup_url if meta else None, "note": (p.meta or {}).get("note"),
            "instruments": [{"symbol": i.canonical_symbol, "provider_symbol": pi.provider_symbol, "status": pi.status,
                             "market_kind": pi.market_kind, "notes": pi.notes} for pi, i in maps],
        })
    return out


@router.get("/quotes", response_model=list[QuoteOut])
def quotes(symbols: str | None = Query(None, description="comma separated; default all active"),
           session: Session = Depends(get_session)):
    known = set(session.scalars(select(Instrument.canonical_symbol)))
    names = [s.strip().upper() for s in symbols.split(",") if s.strip()][:MAX_QUOTE_SYMBOLS] if symbols else \
        [i.canonical_symbol for i in session.scalars(select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.id))
         if not get_settings().focus_list or i.canonical_symbol in get_settings().focus_list]
    out: list[QuoteOut] = []
    for sym in dict.fromkeys(names):
        if sym not in known:  # answered without a provider call and never cached, so arbitrary names cannot grow the cache
            out.append(QuoteOut(symbol=sym[:32], status="error", message=f"Unknown instrument '{sym[:32]}'"))
            continue
        cached = _quote_cache.get(sym)
        if cached and time.monotonic() - cached[0] < 5:
            out.append(cached[1])
            continue
        try:
            inst, prov, pi = resolve_mapping(session, sym)
            q = get_provider(prov.code).get_latest_quote(pi.provider_symbol)
            res = QuoteOut(symbol=sym, status="ok", price=float(q.price), bid=None if q.bid is None else float(q.bid),
                           ask=None if q.ask is None else float(q.ask), time=q.ts, provider=prov.code,
                           message=f"Last known price ({q.ts:%Y-%m-%d %H:%M}Z): market closed or quote stale, not a live price" if q.is_delayed else None,
                           delayed=bool(q.is_delayed))
        except UnsupportedError as exc:
            res = QuoteOut(symbol=sym, status="unsupported", message=exc.message)
        except ProviderNotConfigured as exc:
            res = QuoteOut(symbol=sym, status="not_configured", message=exc.message)
        except NotFoundError as exc:
            res = QuoteOut(symbol=sym, status="error", message=exc.message)
        except AppError as exc:
            res = QuoteOut(symbol=sym, status="error", message=exc.message)
        except Exception:
            res = QuoteOut(symbol=sym, status="error", message="quote request failed")
        _quote_cache[sym] = (time.monotonic(), res)
        out.append(res)
    return out


@router.post("/sync")
def sync(req: SyncRequest, request: Request, session: Session = Depends(get_session),
         user: User = Depends(get_current_user)) -> dict:
    """Pull candles from the provider and upsert (idempotent). May take a few seconds."""
    if req.timeframe not in TIMEFRAMES:
        raise AppError(f"Unsupported timeframe '{req.timeframe}'")
    inst, prov, pi = resolve_mapping(session, req.symbol, req.provider)
    res = ingest_candles(session, get_provider(prov.code), inst, prov, pi, req.timeframe, bars=req.bars)
    audit(session, user.id, "market.sync", "instrument", inst.canonical_symbol,
          request.client.host if request.client else None, {"timeframe": req.timeframe, "bars": req.bars})
    return res.to_dict()


@router.post("/coverage/probe")
def probe(req: ProbeRequest, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Ask the provider what it can actually serve for this symbol/timeframe on the current plan."""
    inst, prov, pi = resolve_mapping(session, req.symbol, req.provider)
    return get_provider(prov.code).check_data_coverage(pi.provider_symbol, req.timeframe)


@router.get("/instruments/{symbol}", response_model=InstrumentOut)
def instrument(symbol: str, session: Session = Depends(get_session)):
    return _instrument_out(session, get_instrument(session, symbol))


__all__ = ["router", "timezone", "Page"]
