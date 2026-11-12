from fastapi import APIRouter, Depends, Path, Query, Request
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
Experimental = Query(False, description="Experimental analysis mode: attach the hypothetical levels of unvalidated technical setups "
                                        "(the call stays WAIT, clearly marked UNVALIDATED)")


@router.get("")
def signals_summary(experimental: bool = Experimental, session: Session = Depends(get_session),
                    user: User = Depends(get_current_user)) -> dict:
    """The call (ENTER / HOLD / WAIT / EXIT / NO TRADE), best plan, active plans and overall bias for every configured instrument."""
    return service.summary(session, experimental=experimental)


@router.get("/config")
def signals_config(user: User = Depends(get_current_user)) -> dict:
    """Timeframe chains, groups, score weights, thresholds and spreads in force (docs/SIGNAL_ENGINE.md)."""
    return to_jsonable(config_payload())


@router.get("/track-record")
def signals_track_record(user: User = Depends(get_current_user)) -> dict:
    """Historical replay of the engine (per instrument x timeframe), including the out-of-sample verdicts."""
    return track_record.load()


@router.get("/{symbol}")
def signal_detail(symbol: str = Symbol, experimental: bool = Experimental, session: Session = Depends(get_session),
                  user: User = Depends(get_current_user)) -> dict:
    """Full top-down analysis of one instrument: the call per timeframe and for the instrument, plans, checklist, reasons, report."""
    return service.analyze_cached(session, symbol, experimental)


@router.post("/{symbol}/sync")
def signal_sync(request: Request, symbol: str = Symbol, experimental: bool = Experimental, session: Session = Depends(get_session),
                user: User = Depends(get_current_user)) -> dict:
    """Fetch the candles that are due from the instrument's provider (keyless providers only), then re-analyse."""
    res = service.sync(session, symbol)
    audit(session, user.id, "signals.sync", "instrument", symbol.upper(), request.client.host if request.client else None,
          {"provider": res.get("provider"), "fetched": res.get("fetched")})
    if res.get("fetched"):  # new candles: analyse them now
        r = service.analyze(session, symbol, experimental=experimental)
        service.remember(r, experimental)
    else:  # nothing new since the last analysis (the paper cycle syncs every instrument each minute)
        r = service.analyze_cached(session, symbol, experimental)
    return {**res, "analysis": r}
