from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.jsonutil import to_jsonable
from app.core.security import get_current_user
from app.database.models import (
    Analysis,
    Instrument,
    Prediction,
    PredictionEvidence,
    User,
)
from app.database.session import get_session
from app.decision.adapters import prediction_call
from app.historical_engine.stats import wilson_interval
from app.jobs.tasks import dispatch
from app.schemas.analysis import (
    AnalysisRunRequest,
    EvidenceOut,
    PredictionDetail,
    PredictionOut,
)
from app.schemas.common import JobAccepted, Page
from app.services.analysis_service import create_analysis
from app.services.audit import audit
from app.services.prediction_service import refresh_outcomes

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _out(session: Session, p: Prediction, cls=PredictionOut, experimental: bool = False, wait_reasons: list[str] | None = None):
    o = cls.model_validate(p)
    o.symbol = session.get(Instrument, p.instrument_id).canonical_symbol
    o.call = to_jsonable(prediction_call(o.model_dump(), wait_reasons=wait_reasons, experimental=experimental))
    return o


@router.post("/run", response_model=JobAccepted, status_code=202)
def run(req: AnalysisRunRequest, request: Request, background: BackgroundTasks, session: Session = Depends(get_session),
        user: User = Depends(get_current_user)):
    """Runs the full analysis pipeline as a background job; the prediction is created when it completes
    (poll /analysis/{id}, then fetch /predictions?analysis_id=)."""
    a = create_analysis(session, user.id, req.model_dump())
    audit(session, user.id, "prediction.run", "analysis", a.id, request.client.host if request.client else None,
          {"symbol": req.symbol, "timeframe": req.timeframe})
    dispatch("analysis", background, a.id)
    return JobAccepted(id=a.id, status=a.status, poll_url=f"/api/v1/analysis/{a.id}")


@router.get("", response_model=Page[PredictionOut])
def list_predictions(symbol: str | None = None, decision: str | None = None, outcome: str | None = None,
                     analysis_id: int | None = None, limit: int = Query(25, ge=1, le=200), offset: int = Query(0, ge=0),
                     experimental: bool = False, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    q = select(Prediction).where(Prediction.user_id == user.id)
    if symbol:
        q = q.join(Instrument, Prediction.instrument_id == Instrument.id).where(Instrument.canonical_symbol == symbol.upper())
    if decision:
        q = q.where(Prediction.decision == decision.upper())
    if outcome:
        q = q.where(Prediction.outcome == outcome)
    if analysis_id:
        q = q.where(Prediction.analysis_id == analysis_id)
    total = session.scalar(select(func.count()).select_from(q.subquery()))
    rows = session.scalars(q.order_by(Prediction.id.desc()).limit(limit).offset(offset)).all()
    return Page(items=[_out(session, p, experimental=experimental) for p in rows], total=total, limit=limit, offset=offset)


@router.get("/stats")
def stats(session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Tracked outcomes of this user's predictions (independent of backtests)."""
    rows = session.execute(select(Prediction, Instrument.canonical_symbol).join(
        Instrument, Prediction.instrument_id == Instrument.id).where(Prediction.user_id == user.id)).all()
    by_decision: dict = {}
    by_outcome: dict = {}
    per: dict = {}
    for p, sym in rows:
        by_decision[p.decision] = by_decision.get(p.decision, 0) + 1
        by_outcome[p.outcome] = by_outcome.get(p.outcome, 0) + 1
        s = per.setdefault(sym, {"total": 0, "BUY": 0, "SELL": 0, "WAIT": 0, "tp_hit": 0, "sl_hit": 0, "r": []})
        s["total"] += 1
        s[p.decision] += 1
        if p.outcome in ("tp_hit", "sl_hit"):
            s[p.outcome] += 1
            if p.outcome_meta and p.outcome_meta.get("r_multiple") is not None:
                s["r"].append(p.outcome_meta["r_multiple"])
    tp, sl = by_outcome.get("tp_hit", 0), by_outcome.get("sl_hit", 0)
    ci = wilson_interval(tp, tp + sl)
    for s in per.values():
        r = s.pop("r")
        s["avg_r"] = sum(r) / len(r) if r else None
    return {
        "total": len(rows), "by_decision": by_decision, "by_outcome": by_outcome,
        "resolved": tp + sl, "tp_first_rate": tp / (tp + sl) if tp + sl else None,
        "tp_first_ci": list(ci) if ci else None, "per_instrument": per,
        "note": "Small samples are not evidence of edge. Resolved = TP or SL reached after fill.",
    }


@router.post("/refresh-outcomes")
def refresh(session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    return {"updated": refresh_outcomes(session, user.id)}


@router.get("/{prediction_id}", response_model=PredictionDetail)
def get_prediction(prediction_id: int, experimental: bool = False, session: Session = Depends(get_session),
                   user: User = Depends(get_current_user)):
    p = session.get(Prediction, prediction_id)
    if not p or p.user_id != user.id:
        raise NotFoundError("Prediction not found")
    a0 = session.get(Analysis, p.analysis_id)
    waits = (((a0.result or {}).get("decision") or {}).get("wait_reasons") or []) if a0 else []
    out = _out(session, p, PredictionDetail, experimental=experimental, wait_reasons=waits)
    out.evidence = [EvidenceOut.model_validate(e) for e in session.scalars(
        select(PredictionEvidence).where(PredictionEvidence.prediction_id == p.id).order_by(PredictionEvidence.id))]
    a = session.get(Analysis, p.analysis_id)
    d = ((a.result or {}).get("decision") or {}) if a else {}
    out.confidence = d.get("confidence")
    out.wait_reasons = d.get("wait_reasons", [])
    return out
