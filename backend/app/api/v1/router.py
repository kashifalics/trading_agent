from fastapi import APIRouter

from app.api.v1.routes import (
    analysis,
    backtesting,
    charts,
    health,
    market,
    models,
    patterns,
    predictions,
    watchlists,
)

api_router = APIRouter()
for module in (health, market, analysis, charts, predictions, backtesting, patterns, models, watchlists):
    api_router.include_router(module.router)
