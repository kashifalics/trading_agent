from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.jsonutil import to_jsonable
from app.core.security import get_current_user
from app.database.models import Instrument, MarketScan, TradeOpportunity, User
from app.database.session import get_session
from app.jobs.tasks import dispatch
from app.opportunities import service
from app.opportunities.config import profile_config
from app.opportunities.scanner import create_scan
from app.schemas.common import Page
from app.services.audit import audit

router = APIRouter(prefix="/opportunities", tags=["opportunities"])
Style = Literal["scalping", "intraday", "swing", "long_term"]


class ScanRequest(BaseModel):
    symbols: list[str] | None = Field(None, max_length=10, description="Defaults to OPPORTUNITY_SYMBOLS")
    refresh_data: bool = Field(False, description="Sync stale timeframes first (spends provider quota). Default: stored candles only.")


class ScanAccepted(BaseModel):
    id: int
    status: str
    poll_url: str
    deduplicated: bool


@router.post("/scan", response_model=ScanAccepted, status_code=202)
def start_scan(req: ScanRequest, request: Request, background: BackgroundTasks, session: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    """Queue a full multi-timeframe scan. If a scan is already queued/running it is returned instead (deduplication)."""
    scan, dup = create_scan(session, user.id, req.model_dump(), "manual")
    if not dup:
        audit(session, user.id, "opportunities.scan", "market_scan", scan.id, request.client.host if request.client else None,
              {"symbols": req.symbols, "refresh_data": req.refresh_data})
        dispatch("scan", background, scan.id)
    return ScanAccepted(id=scan.id, status=scan.status, poll_url=f"/api/v1/opportunities/scans/{scan.id}", deduplicated=dup)


@router.get("/summary")
def summary(experimental: bool = False, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Everything the Trade Opportunities page needs in one call: scan status/freshness, best per style, consolidated ranking.
    Every row carries its call (ENTER / WAIT / EXIT / NO TRADE); `experimental` attaches hypothetical levels of unvalidated setups."""
    return service.summary(session, experimental=experimental)


@router.get("/config")
def config(user: User = Depends(get_current_user)) -> dict:
    """The exact weights, thresholds and profiles in force (the scoring methodology is configurable and documented)."""
    return to_jsonable(profile_config())


@router.get("/validation")
def validation(session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    return service.validation_payload(session, user.id)


@router.get("/scans", response_model=Page[dict])
def scans(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), session: Session = Depends(get_session),
          user: User = Depends(get_current_user)):
    total = session.scalar(select(func.count()).select_from(MarketScan))
    rows = session.scalars(select(MarketScan).order_by(MarketScan.id.desc()).limit(limit).offset(offset)).all()
    items = [to_jsonable({"id": s.id, "status": s.status, "trigger": s.trigger, "created_at": s.created_at, "started_at": s.started_at,
                          "finished_at": s.finished_at, "summary": s.summary, "config_version": s.config_version, "error": s.error})
             for s in rows]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/scans/{scan_id}")
def scan_detail(scan_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    s = session.get(MarketScan, scan_id)
    if not s:
        raise NotFoundError("Scan not found")
    return to_jsonable({"id": s.id, "status": s.status, "trigger": s.trigger, "params": s.params, "created_at": s.created_at,
                        "started_at": s.started_at, "finished_at": s.finished_at, "summary": s.summary, "instruments": s.instruments,
                        "config_version": s.config_version, "code_version": s.code_version, "error": s.error})


@router.get("/timeframes")
def timeframes(symbol: str, scan_id: int | None = None, session: Session = Depends(get_session),
               user: User = Depends(get_current_user)) -> dict:
    """Independent per-timeframe analysis (status, structure, zones, levels) from the latest (or a given) scan."""
    scan = session.get(MarketScan, scan_id) if scan_id else service.latest_scan(session)
    if not scan:
        raise NotFoundError("No completed scan yet. Start one with POST /opportunities/scan.")
    return {"scan_id": scan.id, "symbol": symbol.upper(), "timeframes": service.timeframe_rows(session, symbol, scan.id)}


@router.get("", response_model=Page[dict])
def list_opportunities(symbol: str | None = None, style: Style | None = None, direction: Literal["BUY", "SELL", "WAIT"] | None = None,
                       status: str | None = None, actionable_only: bool = False, headline_only: bool = True,
                       scope: Literal["latest", "all"] = "latest", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                       experimental: bool = False, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """Opportunities of the latest completed scan (default) or the whole history (`scope=all`), ranked."""
    q = select(TradeOpportunity, Instrument.canonical_symbol).join(Instrument, Instrument.id == TradeOpportunity.instrument_id)
    if scope == "latest":
        scan = service.latest_scan(session)
        if not scan:
            return Page(items=[], total=0, limit=limit, offset=offset)
        q = q.where(TradeOpportunity.last_scan_id == scan.id)
    if symbol:
        q = q.where(Instrument.canonical_symbol == symbol.upper())
    if style:
        q = q.where(TradeOpportunity.style == style)
    if direction:
        q = q.where(TradeOpportunity.direction == direction)
    if status:
        q = q.where(TradeOpportunity.status == status)
    if headline_only:
        q = q.where(TradeOpportunity.is_headline.is_(True))
    if actionable_only:
        q = q.where(TradeOpportunity.direction.in_(("BUY", "SELL")))
    rows = [service.opp_out(o, sym, experimental=experimental) for o, sym in session.execute(q).all()]
    ranked = service.rank_rows(rows)
    return Page(items=ranked[offset: offset + limit], total=len(ranked), limit=limit, offset=offset)


@router.get("/{opportunity_id}")
def opportunity_detail(opportunity_id: int, experimental: bool = False, session: Session = Depends(get_session),
                       user: User = Depends(get_current_user)) -> dict:
    row = session.execute(select(TradeOpportunity, Instrument.canonical_symbol).join(Instrument, Instrument.id == TradeOpportunity.instrument_id)
                          .where(TradeOpportunity.id == opportunity_id)).first()
    if not row:
        raise NotFoundError("Opportunity not found")
    o, sym = row
    out = service.opp_out(o, sym, detail=True, experimental=experimental)
    out["status_history"] = service.status_history(session, o.id)
    out["style_profile"] = profile_config()["profiles"][o.style]
    return out
