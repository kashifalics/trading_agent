from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jsonutil import to_jsonable
from app.database.models import SignalRecord
from app.database.session import get_session
from app.strategy_engine import service
from app.strategy_engine.lifecycle import OPEN, record_out

router = APIRouter(prefix="/engine", tags=["strategy engine v2"])
Symbol = Path(..., pattern=r"^[A-Za-z0-9]{3,12}$", description="Canonical instrument symbol, e.g. XAUUSD")


@router.get("")
def engine_summary(session: Session = Depends(get_session)) -> dict:
    """One primary action per instrument (BUY / SELL / WAIT FOR BUY / WAIT FOR SELL / EXIT / NO TRADE), best opportunity first, with
    its trade plan (entry, stop-loss, TP1-TP3), regime, strategy, research status and every timeframe's action in one line."""
    return service.summary(session)


@router.get("/signals")
def engine_signals(symbol: str | None = Query(None, pattern=r"^[A-Za-z0-9]{3,12}$"), open_only: bool = False,
                   limit: int = Query(100, ge=1, le=500), session: Session = Depends(get_session)) -> dict:
    """Signal history and lifecycle (DETECTED ... TP1/TP2/TP3 HIT, STOP LOSS HIT, INVALIDATED, EXPIRED, ENTRY MISSED), newest first.
    Hypothetical signals tracked on 1-minute candles: not paper trades and never orders."""
    q = select(SignalRecord)
    if symbol:
        q = q.where(SignalRecord.symbol == symbol.upper())
    if open_only:
        q = q.where(SignalRecord.status.in_(OPEN))
    rows = session.scalars(q.order_by(SignalRecord.id.desc()).limit(limit)).all()
    return to_jsonable({"items": [record_out(r) for r in rows], "open_statuses": list(OPEN)})


@router.get("/{symbol}")
def engine_detail(symbol: str = Symbol, session: Session = Depends(get_session)) -> dict:
    """Full analysis of one instrument: per timeframe the regime, all six strategies (ready / pending / forming / rejected / not run,
    with the rule that decided), the selected plan, paper-trade management (separate) and the risk check."""
    return service.analyze_cached(session, symbol)
