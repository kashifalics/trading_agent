from fastapi import APIRouter

from app.api.v1.routes import (
    analysis,
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

api_router = APIRouter()
for module in (health, market, analysis, charts, predictions, backtesting, patterns, signals, paper, opportunities, models, watchlists, research):
    api_router.include_router(module.router)
