from fastapi import APIRouter, Depends

from app.api.v1.routes import (
    analysis,
    auth,
    backtesting,
    charts,
    health,
    market,
    models,
    opportunities,
    paper,
    patterns,
    predictions,
    research,
    signals,
    watchlists,
)
from app.core.security import get_current_user

# Only the health check is public. Every other router requires a valid X-API-Key whenever AUTH_REQUIRED=true (mandatory in production);
# applying it at router level means a new endpoint cannot be added without authentication by accident. With AUTH_REQUIRED=false (local
# development) the dependency maps anonymous calls to the single local user, as before.
PUBLIC = (health,)
PROTECTED = (auth, market, analysis, charts, predictions, backtesting, patterns, signals, paper, opportunities, models, watchlists, research)

api_router = APIRouter()
for module in PUBLIC:
    api_router.include_router(module.router)
for module in PROTECTED:
    api_router.include_router(module.router, dependencies=[Depends(get_current_user)])
