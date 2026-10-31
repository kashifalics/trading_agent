import json

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.chart_vision.upload import validate_and_store
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailed
from app.core.security import get_current_user
from app.database.models import ChartExtraction, User
from app.database.session import get_session
from app.market_data.timeframes import TIMEFRAMES
from app.services.audit import audit
from app.services.chart_service import CalibrationPoint, analyze_screenshot

router = APIRouter(prefix="/charts", tags=["charts"])


@router.post("/analyze")
async def analyze(request: Request, file: UploadFile = File(...), symbol: str | None = Form(None),
                  timeframe: str | None = Form(None),
                  calibration_points: str | None = Form(None, description='JSON: [{"y": 120, "price": 2350.5}, ...]'),
                  session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    """Upload a chart screenshot. Candles are extracted with computer vision; prices are only reported when the
    price axis could be calibrated (OCR or user-supplied points). Never invents OHLC values."""
    limit = get_settings().max_upload_bytes
    data = await file.read(limit + 1)
    if timeframe and timeframe not in TIMEFRAMES:
        raise ValidationFailed(f"Unsupported timeframe '{timeframe}'")
    points = None
    if calibration_points:
        try:
            points = [CalibrationPoint(float(p["y"]), float(p["price"])) for p in json.loads(calibration_points)]
        except (ValueError, KeyError, TypeError) as exc:
            raise ValidationFailed("calibration_points must be JSON like [{\"y\":120,\"price\":2350.5}]") from exc
        if len(points) > 20:
            raise ValidationFailed("too many calibration points")
    stored = validate_and_store(data, file.filename, user.id)
    audit(session, user.id, "chart.upload", "screenshot", stored.sha256[:12],
          request.client.host if request.client else None, {"bytes": stored.size_bytes})
    return analyze_screenshot(session, user.id, stored, symbol.strip().upper() if symbol else None, timeframe, points)


@router.get("/extractions/{extraction_id}")
def get_extraction(extraction_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    e = session.get(ChartExtraction, extraction_id)
    if not e or e.user_id != user.id:
        raise NotFoundError("Extraction not found")
    return {"id": e.id, "screenshot_id": e.screenshot_id, "analysis_id": e.analysis_id, "status": e.status,
            "ocr_available": e.ocr_available, "detected_symbol": e.detected_symbol,
            "detected_timeframe": e.detected_timeframe, "price_calibrated": e.price_calibrated,
            "calibration": e.calibration, "quality_score": e.quality_score, "quality_breakdown": e.quality_breakdown,
            "market_match": e.market_match, "warnings": e.warnings, "n_candles": len(e.candles or []),
            "candles": e.candles, "created_at": e.created_at}
