from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.backtesting.strategies import STRATEGIES
from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.database.models import BacktestRun, BacktestTrade, Instrument, User
from app.database.session import get_session
from app.jobs.tasks import dispatch
from app.schemas.backtest import BacktestOut, BacktestRunRequest, BacktestTradeOut
from app.schemas.common import JobAccepted, Page
from app.services.audit import audit
from app.services.backtest_service import create_backtest

router = APIRouter(prefix="/backtests", tags=["backtesting"])


def _out(session: Session, run: BacktestRun, with_trades: bool) -> BacktestOut:
    o = BacktestOut.model_validate(run)
    o.symbol = session.get(Instrument, run.instrument_id).canonical_symbol
    if with_trades:
        o.trades = [BacktestTradeOut.model_validate(t) for t in session.scalars(
            select(BacktestTrade).where(BacktestTrade.run_id == run.id).order_by(BacktestTrade.id).limit(2000))]
    return o


@router.get("/strategies")
def strategies() -> list[dict]:
    return [{"id": k, "description": (v.__doc__ or "").strip().split("\n")[0]} for k, v in STRATEGIES.items()]


@router.post("/run", response_model=JobAccepted, status_code=202)
def run(req: BacktestRunRequest, request: Request, background: BackgroundTasks, session: Session = Depends(get_session),
        user: User = Depends(get_current_user)):
    params = req.model_dump(mode="json")
    r = create_backtest(session, user.id, params)
    audit(session, user.id, "backtest.run", "backtest", r.id, request.client.host if request.client else None,
          {"symbol": req.symbol, "timeframe": req.timeframe, "strategy": req.strategy})
    dispatch("backtest", background, r.id)
    return JobAccepted(id=r.id, status=r.status, poll_url=f"/api/v1/backtests/{r.id}")


@router.get("", response_model=Page[BacktestOut])
def list_runs(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), session: Session = Depends(get_session),
              user: User = Depends(get_current_user)):
    q = select(BacktestRun).where(BacktestRun.user_id == user.id)
    total = session.scalar(select(func.count()).select_from(q.subquery()))
    rows = session.scalars(q.order_by(BacktestRun.id.desc()).limit(limit).offset(offset)).all()
    return Page(items=[_out(session, r, False) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/{run_id}", response_model=BacktestOut)
def get_run(run_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    r = session.get(BacktestRun, run_id)
    if not r or r.user_id != user.id:
        raise NotFoundError("Backtest not found")
    return _out(session, r, True)
