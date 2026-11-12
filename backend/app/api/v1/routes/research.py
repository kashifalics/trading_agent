from fastapi import APIRouter, Depends, Response

from app.core.security import get_current_user
from app.database.models import User
from app.gold_research import dashboard

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/gold")
def gold_research(user: User = Depends(get_current_user)) -> Response:
    """Gold Research dashboard: dataset, frozen split, pattern study, market scenarios and model status. Historical research only."""
    return Response(dashboard.load_bytes(), media_type="application/json")
