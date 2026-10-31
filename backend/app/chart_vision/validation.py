"""Extraction-quality scoring and matching of extracted candles against stored provider candles."""
import numpy as np

from app.chart_vision.extraction import AxisCalibration, Extraction


def quality_score(ex: Extraction, cal: AxisCalibration | None, ocr_ok: bool, symbol: str | None,
                  timeframe: str | None) -> dict:
    n = len(ex.candles)
    parts = {
        "candle_count": float(min(1.0, n / 40)),
        "spacing_regularity": ex.regularity,
        "detection_ratio": ex.detected_ratio,
        "body_resolution": ex.body_resolution,
        "price_calibration": (cal.r2 if cal and cal.n_points > 2 else 0.8 if cal else 0.0),
        "instrument_identified": 1.0 if symbol and timeframe else 0.5 if symbol or timeframe else 0.0,
    }
    weights = {"candle_count": .15, "spacing_regularity": .15, "detection_ratio": .2, "body_resolution": .15,
               "price_calibration": .25, "instrument_identified": .10}
    score = sum(parts[k] * weights[k] for k in parts)
    return {"score": round(float(score), 3), "breakdown": parts, "ocr_available": ocr_ok,
            "usable": bool(n >= 20 and ex.body_resolution >= 0.8 and score >= 0.45)}


def match_to_market(extracted_close: np.ndarray, extracted_range: np.ndarray, market_close: np.ndarray,
                    market_range: np.ndarray, min_corr: float = 0.98) -> dict | None:
    """Slide the extracted window over provider candles; compare z-normalised close and range series.
    A match is only reported when BOTH correlate >= min_corr (price-scale independent)."""
    n, m = len(extracted_close), len(market_close)
    if n < 20 or m < n:
        return None
    ec = (extracted_close - extracted_close.mean()) / (extracted_close.std() or 1)
    er = (extracted_range - extracted_range.mean()) / (extracted_range.std() or 1)
    best = None
    for s in range(0, m - n + 1):
        wc, wr = market_close[s:s + n], market_range[s:s + n]
        if wc.std() == 0 or wr.std() == 0:
            continue
        cc = float(np.mean(ec * (wc - wc.mean()) / wc.std()))
        cr = float(np.mean(er * (wr - wr.mean()) / wr.std()))
        score = min(cc, cr)
        if best is None or score > best["score"]:
            best = {"start": s, "end": s + n - 1, "close_corr": cc, "range_corr": cr, "score": score}
    return best if best and best["score"] >= min_corr else None
