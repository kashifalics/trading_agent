from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.database.models import (
    Analysis,
    HistoricalAnalogue,
    Instrument,
    Prediction,
    User,
)
from app.database.session import get_session
from app.jobs.tasks import dispatch
from app.schemas.analysis import AnalysisOut, AnalysisRunRequest
from app.schemas.common import JobAccepted, Page
from app.services.analysis_service import create_analysis
from app.services.audit import audit

router = APIRouter(prefix="/analysis", tags=["analysis"])


def analysis_out(session: Session, a: Analysis) -> AnalysisOut:
    out = AnalysisOut.model_validate(a)
    out.symbol = session.get(Instrument, a.instrument_id).canonical_symbol
    out.prediction_id = session.scalar(select(Prediction.id).where(Prediction.analysis_id == a.id))
    return out


def get_owned(session: Session, analysis_id: int, user: User) -> Analysis:
    a = session.get(Analysis, analysis_id)
    if not a or a.user_id != user.id:  # same 404 for foreign and missing rows: no existence leak
        raise NotFoundError("Analysis not found")
    return a


@router.post("/run", response_model=JobAccepted, status_code=202)
def run(req: AnalysisRunRequest, request: Request, background: BackgroundTasks, session: Session = Depends(get_session),
        user: User = Depends(get_current_user)):
    a = create_analysis(session, user.id, req.model_dump())
    audit(session, user.id, "analysis.run", "analysis", a.id, request.client.host if request.client else None,
          {"symbol": req.symbol, "timeframe": req.timeframe})
    dispatch("analysis", background, a.id)
    return JobAccepted(id=a.id, status=a.status, poll_url=f"/api/v1/analysis/{a.id}")


@router.get("", response_model=Page[AnalysisOut])
def list_analyses(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), session: Session = Depends(get_session),
                  user: User = Depends(get_current_user)):
    q = select(Analysis).where(Analysis.user_id == user.id)
    total = session.scalar(select(func.count()).select_from(q.subquery()))
    rows = session.scalars(q.order_by(Analysis.id.desc()).limit(limit).offset(offset)).all()
    return Page(items=[analysis_out(session, a) for a in rows], total=total, limit=limit, offset=offset)


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return analysis_out(session, get_owned(session, analysis_id, user))


@router.get("/{analysis_id}/analogues")
def analogues(analysis_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    a = get_owned(session, analysis_id, user)
    rows = session.scalars(select(HistoricalAnalogue).where(HistoricalAnalogue.analysis_id == a.id)
                           .order_by(HistoricalAnalogue.rank)).all()
    summary = (a.result or {}).get("analogues")
    return {
        "analysis_id": a.id, "status": a.status, "summary": summary,
        "note": "Similarity scores rank resemblance only; frequencies describe history, not future probability.",
        "analogues": [{"rank": r.rank, "time": r.matched_ts, "similarity": r.similarity, "horizon_bars": r.horizon_bars,
                       "forward_return_atr": r.forward_return, "mfe_atr": r.mfe_atr, "mae_atr": r.mae_atr,
                       "long_tp_before_sl": r.long_tp_before_sl, "short_tp_before_sl": r.short_tp_before_sl} for r in rows],
    }
