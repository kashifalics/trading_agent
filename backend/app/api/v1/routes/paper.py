from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.models import User
from app.database.session import get_session
from app.paper import service, stats
from app.services.audit import audit

router = APIRouter(prefix="/paper", tags=["paper trading"])
STATUS_PATTERN = r"^(pending|open|closed|cancelled|missed|expired|skipped|live|finished|unfilled|all)$"


class AccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    risk_pct: float | None = Field(None, gt=0, le=5, description="% of the balance risked per trade")
    max_open_positions: int | None = Field(None, ge=1, le=50)
    max_daily_loss_pct: float | None = Field(None, gt=0, le=50)


class AccountReset(AccountUpdate):
    start_balance: float | None = Field(None, gt=0, le=1_000_000_000)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/summary")
def paper_summary(session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Paper account, forward-test statistics, equity curves, breakdowns, open/pending trades and worker status."""
    return stats.summary(session)


@router.get("/trades")
def paper_trades(status: str | None = Query(None, pattern=STATUS_PATTERN), symbol: str | None = Query(None, pattern=r"^[A-Za-z0-9]{3,12}$"),
                 timeframe: str | None = Query(None, pattern=r"^[0-9]{1,2}[mHDWM]$"), limit: int = Query(100, ge=1, le=500),
                 offset: int = Query(0, ge=0), session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Recorded signals and their simulated outcome, newest first."""
    return service.list_trades(session, status, symbol, timeframe, limit, offset)


@router.get("/trades/{trade_id}")
def paper_trade(trade_id: int = Path(..., ge=1), session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """One paper trade with the plan exactly as it was shown when the signal was recorded (checklist, reasons, targets)."""
    return service.get_trade(session, trade_id)


@router.get("/account")
def paper_account(session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    from app.core.jsonutil import to_jsonable

    acc = service.active_account(session)
    session.commit()
    return to_jsonable(service.account_out(session, acc))


@router.patch("/account")
def paper_account_update(body: AccountUpdate, request: Request, session: Session = Depends(get_session),
                         user: User = Depends(get_current_user)) -> dict:
    """Change the risk rules of the active paper account (applies to signals recorded from now on)."""
    out = service.update_account(session, body.model_dump(exclude_none=True))
    audit(session, user.id, "paper.account.update", "paper_account", out["id"], _ip(request), body.model_dump(exclude_none=True))
    return out


@router.post("/account/reset")
def paper_account_reset(body: AccountReset, request: Request, session: Session = Depends(get_session),
                        user: User = Depends(get_current_user)) -> dict:
    """Start a new paper account. The recorded signals and the forward-test record are kept."""
    out = service.reset_account(session, body.model_dump(exclude_none=True))
    audit(session, user.id, "paper.account.reset", "paper_account", out["id"], _ip(request), body.model_dump(exclude_none=True))
    return out


@router.post("/run")
def paper_run(request: Request, sync: bool = Query(True, description="fetch due candles from keyless providers first"),
              session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Run one paper-trading cycle now (the background loop does this automatically every PAPER_TRADING_INTERVAL_SECONDS)."""
    res = service.run_cycle(sync=sync)
    audit(session, user.id, "paper.run", None, None, _ip(request), {"sync": sync, "duration_s": res.get("duration_s")})
    return res
