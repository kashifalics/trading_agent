"""Screenshot -> extraction -> (market-data match | extracted bars) -> the SAME analytical pipeline."""
import time
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chart_vision.extraction import (
    AxisCalibration,
    extract_candles,
    fit_axis,
    to_ohlc,
)
from app.chart_vision.ocr import (
    AxisLabel,
    ocr_available,
    parse_chart_title,
    read_price_axis,
    read_title_text,
)
from app.chart_vision.preprocessing import (
    candle_color_masks,
    chart_region,
    load_bgr,
    normalize_size,
)
from app.chart_vision.upload import StoredImage
from app.chart_vision.validation import match_to_market, quality_score
from app.core.jsonutil import to_jsonable
from app.database.base import utcnow
from app.database.models import Analysis, ChartExtraction, Instrument, Screenshot
from app.market_data.bars import Bars
from app.market_data.ingestion.service import load_candles, resolve_mapping
from app.services.analysis_service import execute_analysis, prediction_for_analysis
from app.services.data_service import tf_step


@dataclass
class CalibrationPoint:
    y: float  # pixel row in the ORIGINAL screenshot
    price: float


def analyze_screenshot(session: Session, user_id: int, stored: StoredImage, symbol: str | None = None,
                       timeframe: str | None = None, points: list[CalibrationPoint] | None = None) -> dict:
    shot = Screenshot(user_id=user_id, filename=stored.filename, content_type=stored.content_type, sha256=stored.sha256,
                      size_bytes=stored.size_bytes, width=stored.width, height=stored.height, storage_path=stored.path)
    session.add(shot)
    session.flush()

    raw = load_bgr(stored.path)
    img, scale = normalize_size(raw)
    ex = extract_candles(img)
    warnings = list(ex.warnings)
    ocr_ok = ocr_available()
    if not ocr_ok:
        warnings.append("Tesseract OCR is not installed: instrument, timeframe and price axis were NOT read from the image.")

    green, red = candle_color_masks(img)
    region = chart_region(green, red)
    det_symbol = det_tf = None
    cal: AxisCalibration | None = None
    if ocr_ok:
        det_symbol, det_tf, notes = parse_chart_title(read_title_text(img))
        warnings += notes
        if region:
            cal = fit_axis(read_price_axis(img, region[2]), "ocr", min_points=3)
    if points:
        user_cal = fit_axis([AxisLabel(p.y * scale, p.price) for p in points], "user", min_points=2)
        if user_cal:
            cal = user_cal
        else:
            warnings.append("supplied calibration points were rejected (need >=2 distinct rows with price falling downwards)")
    if symbol and det_symbol and symbol.upper() != det_symbol:
        warnings.append(f"The chart title reads {det_symbol} but you specified {symbol.upper()}; analysing {symbol.upper()} as instructed. "
                        f"Clear the instrument field to use the one detected in the image.")
    symbol = (symbol or det_symbol or "").upper() or None
    timeframe = timeframe or det_tf
    if cal is None:
        warnings.append("Price axis not calibrated: absolute prices (entry/stop/target) are unavailable. "
                        "Provide two (pixel row, price) calibration points to enable them.")

    q = quality_score(ex, cal, ocr_ok, symbol, timeframe)
    ohlc = to_ohlc(ex, cal, img.shape[0])
    row = ChartExtraction(
        screenshot_id=shot.id, user_id=user_id, status="extracted", ocr_available=ocr_ok, detected_symbol=det_symbol,
        detected_timeframe=det_tf, price_calibrated=cal is not None, calibration=cal.to_dict() if cal else None,
        candles=to_jsonable(ohlc[-300:]), quality_score=q["score"], quality_breakdown=q["breakdown"], warnings=warnings)
    session.add(row)
    session.commit()

    result = {"extraction_id": row.id, "screenshot_id": shot.id, "status": "extracted", "symbol": symbol,
              "timeframe": timeframe, "n_candles": len(ohlc), "price_calibrated": cal is not None,
              "quality": q, "warnings": warnings, "analysis_id": None, "prediction_id": None}
    inst = session.scalar(select(Instrument).where(Instrument.canonical_symbol == symbol)) if symbol else None
    if not q["usable"] or inst is None or timeframe is None:
        row.status = "needs_input"
        why = []
        if not q["usable"]:
            why.append("extraction quality too low to analyse")
        if inst is None or timeframe is None:
            why.append("instrument and timeframe must be identified (pass symbol and timeframe)")
        warnings.append("Not analysed: " + "; ".join(why))
        row.warnings = warnings
        session.commit()
        result.update(status="needs_input", warnings=warnings)
        return result

    bars, price_cal, extra, match, provider_label = _build_bars(session, inst, timeframe, ohlc, cal is not None)
    row.market_match = to_jsonable(match)
    a = Analysis(user_id=user_id, instrument_id=inst.id, timeframe=timeframe, source="screenshot", status="running",
                 params={"symbol": symbol, "timeframe": timeframe, "use_ml": False, "min_rr": 1.5, "horizon_bars": 24,
                         "screenshot_id": shot.id, "lookback_bars": len(bars)}, started_at=utcnow())
    session.add(a)
    session.commit()
    try:
        execute_analysis(session, a, bars_override=bars, price_calibrated=price_cal, source="screenshot",
                         extra_warnings=warnings + extra, provider_label=provider_label)
        a.status = "completed"
    except Exception as exc:  # AppError or unexpected
        session.rollback()
        a = session.get(Analysis, a.id)
        a.status, a.error = "failed", getattr(exc, "message", f"internal error ({exc.__class__.__name__})")
    a.completed_at = utcnow()
    row.analysis_id = a.id
    row.status = "analysed" if a.status == "completed" else "failed"
    session.commit()
    pred = prediction_for_analysis(session, a.id)
    result.update(status=row.status, analysis_id=a.id, prediction_id=pred.id if pred else None, market_match=match,
                  data_source="provider_candles" if match else "extracted_from_pixels", warnings=warnings + extra)
    return result


def _build_bars(session: Session, inst: Instrument, timeframe: str, ohlc: list[dict], calibrated: bool):
    """Prefer exact provider candles when the screenshot window matches stored data; else use extracted bars."""
    extra: list[str] = []
    step = tf_step(timeframe)
    ec = np.array([c["close"] for c in ohlc])
    er = np.array([c["high"] - c["low"] for c in ohlc])
    try:
        _, prov, _ = resolve_mapping(session, inst.canonical_symbol)
        candles = load_candles(session, inst.id, prov.id, timeframe, limit=3000, complete_only=True)
    except Exception:
        prov, candles = None, []
    if prov is not None and len(candles) >= len(ohlc) + 10:
        mb = Bars.from_candles(candles, step)
        m = match_to_market(ec, er, mb.c, mb.h - mb.l)
        if m:
            bars = mb.upto(m["end"] + 1)
            extra.append(f"Screenshot window matched stored {prov.code} candles (correlation {m['score']:.3f}); analysis uses "
                         f"exact provider OHLC as of the screenshot's last candle, not pixel estimates.")
            return bars, True, extra, m, prov.code
        extra.append("No matching window found in stored provider candles; using values extracted from pixels.")
    t_end = int(time.time())
    n = len(ohlc)
    t = t_end - (n - 1 - np.arange(n)) * step
    bars = Bars(t.astype(np.int64), np.array([c["open"] for c in ohlc]), np.array([c["high"] for c in ohlc]),
                np.array([c["low"] for c in ohlc]), ec, np.full(n, np.nan), step)
    extra.append("Candle timestamps were not read from the time axis; they are placeholders ending at upload time.")
    if not calibrated:
        extra.append("Values are in pixel units (no price calibration).")
    return bars, calibrated, extra, None, "screenshot"
