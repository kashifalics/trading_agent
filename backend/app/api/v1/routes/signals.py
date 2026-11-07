from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session

from app.core.jsonutil import to_jsonable
from app.core.security import get_current_user
from app.database.models import User
from app.database.session import get_session
from app.services.audit import audit
from app.signals import service, track_record
from app.signals.config import config_payload

router = APIRouter(prefix="/signals", tags=["signals"])
Symbol = Path(..., pattern=r"^[A-Za-z0-9]{3,12}$", description="Canonical instrument symbol, e.g. XAUUSD")


@router.get("")
def signals_summary(session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Best plan, active plans and overall bias for every configured instrument (SIGNAL_SYMBOLS), from stored candles."""
    return service.summary(session)


@router.get("/config")
def signals_config(user: User = Depends(get_current_user)) -> dict:
    """Timeframe chains, groups, score weights, thresholds and spreads in force (docs/SIGNAL_ENGINE.md)."""
    return to_jsonable(config_payload())


@router.get("/track-record")
def signals_track_record(user: User = Depends(get_current_user)) -> dict:
    """Historical replay of the engine (per instrument x timeframe), including the out-of-sample verdicts."""
    return track_record.load()


@router.get("/{symbol}")
def signal_detail(symbol: str = Symbol, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Full top-down analysis of one instrument: per-timeframe plans, checklist, levels, reasons and the analyst report."""
    return service.analyze(session, symbol)


@router.post("/{symbol}/sync")
def signal_sync(request: Request, symbol: str = Symbol, session: Session = Depends(get_session),
                user: User = Depends(get_current_user)) -> dict:
    """Fetch the candles that are due from the instrument's provider (keyless providers only), then re-analyse."""
    res = service.sync(session, symbol)
    audit(session, user.id, "signals.sync", "instrument", symbol.upper(), request.client.host if request.client else None,
          {"provider": res.get("provider"), "fetched": res.get("fetched")})
    return {**res, "analysis": service.analyze(session, symbol)}
