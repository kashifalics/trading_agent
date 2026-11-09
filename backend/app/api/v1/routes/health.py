from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.chart_vision.ocr import ocr_available
from app.core.config import get_settings
from app.database.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    s = get_settings()
    try:
        session.execute(text("SELECT 1"))
        db = "ok"
    except Exception:
        db = "error"
    redis_state = "not_configured"
    if s.redis_url:
        try:
            import redis

            redis.from_url(s.redis_url, socket_connect_timeout=1).ping()
            redis_state = "ok"
        except Exception:
            redis_state = "error"
    return {
        "status": "ok" if db == "ok" else "degraded", "version": "0.1.0", "env": s.app_env,
        "time": datetime.now(timezone.utc).isoformat(),
        "components": {"database": db, "redis": redis_state, "job_backend": s.job_backend,
                       "ocr_tesseract": ocr_available(), "llm": s.llm_provider,
                       "twelve_data_key_configured": bool(s.twelve_data_api_key)},
        "mode": "analysis_only",
        "auth_required": s.auth_required,
    }
