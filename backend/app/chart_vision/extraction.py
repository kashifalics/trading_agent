"""Candle extraction from pixels + price-axis calibration.

All values derive from detected pixels; nothing is guessed. If the price axis cannot be calibrated the
output is reported in pixel space only (price_calibrated=False)."""
from collections import Counter
from dataclasses import asdict, dataclass

import cv2
import numpy as np

from app.chart_vision.ocr import AxisLabel
from app.chart_vision.preprocessing import candle_color_masks


@dataclass
class PixelCandle:
    x: float
    y_high: float
    y_low: float
    y_open: float | None
    y_close: float | None
    bullish: bool
    body_resolved: bool


@dataclass
class Extraction:
    candles: list[PixelCandle]
    spacing: float | None
    regularity: float
    detected_ratio: float
    body_resolution: float
    warnings: list[str]
    image_size: tuple[int, int]


@dataclass
class AxisCalibration:
    a: float  # price = a * y + b
    b: float
    r2: float
    n_points: int
    source: str  # ocr | user

    def price(self, y: float) -> float:
        return self.a * y + self.b

    def to_dict(self) -> dict:
        return asdict(self)


def fit_axis(points: list[AxisLabel], source: str, min_points: int = 2, min_r2: float = 0.999) -> AxisCalibration | None:
    """Least-squares linear price axis from (y_pixel, price) pairs. Rejects non-monotonic / noisy fits."""
    if len(points) < min_points:
        return None
    y = np.array([p.y for p in points])
    v = np.array([p.value for p in points])
    if np.ptp(y) < 20 or np.ptp(v) <= 0:
        return None
    a, b = np.polyfit(y, v, 1)
    if a >= 0:  # price must fall as y (downwards) increases
        return None
    pred = a * y + b
    ss_res, ss_tot = float(((v - pred) ** 2).sum()), float(((v - v.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    if len(points) > 2 and r2 < min_r2:
        return None
    return AxisCalibration(float(a), float(b), float(r2), len(points), source)


def extract_candles(img: np.ndarray) -> Extraction:
    green, red = candle_color_masks(img)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
    raw: list[PixelCandle] = []
    for mask, bullish in ((green, True), (red, False)):
        m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, k)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if h < 4 or w > 60 or h > img.shape[0] * 0.9:
                continue
            comp = (labels[y:y + h, x:x + w] == i)
            widths = comp.sum(axis=1)
            maxw = int(widths.max())
            body_rows = np.nonzero(widths >= max(2, 0.6 * maxw))[0] if maxw >= 3 else np.array([])
            if len(body_rows):
                top, bot = float(y + body_rows.min()), float(y + body_rows.max())
                yo, yc = (bot, top) if bullish else (top, bot)
                resolved = True
            else:
                yo = yc = None
                resolved = False
            cols = np.nonzero(comp.sum(axis=0) > 0)[0]
            raw.append(PixelCandle(float(x + (cols.min() + cols.max()) / 2), float(y), float(y + h - 1), yo, yc,
                                   bullish, resolved))
    warnings: list[str] = []
    # Drop volume-pane bars: many components sharing one baseline row and no wicks.
    if len(raw) >= 10:
        bottoms = Counter(round(c.y_low) for c in raw)
        base, cnt = bottoms.most_common(1)[0]
        if cnt >= 0.4 * len(raw):
            flat = [c for c in raw if abs(c.y_low - base) <= 1]
            if np.mean([c.y_low - c.y_high for c in flat]) < img.shape[0] * 0.25:
                raw = [c for c in raw if abs(c.y_low - base) > 1]
                warnings.append(f"ignored {len(flat)} volume-like bars sharing one baseline")
    raw.sort(key=lambda c: c.x)
    if len(raw) < 5:
        return Extraction(raw, None, 0.0, 0.0, 0.0, warnings + ["fewer than 5 candles detected"], (img.shape[1], img.shape[0]))
    xs = np.array([c.x for c in raw])
    gaps = np.diff(xs)
    spacing = float(np.median(gaps[gaps > 1])) if (gaps > 1).any() else None
    if spacing:
        mult = gaps / spacing
        regularity = float(np.mean(np.abs(mult - np.round(np.maximum(mult, 1))) < 0.25))
        expected = (xs[-1] - xs[0]) / spacing + 1
        ratio = float(min(1.0, len(raw) / expected))
    else:
        regularity, ratio = 0.0, 0.0
    if ratio < 0.85:
        warnings.append(f"only {ratio:.0%} of expected candle positions detected (hollow/coloured differently or overlapped)")
    body_res = float(np.mean([c.body_resolved for c in raw]))
    if body_res < 0.8:
        warnings.append("candles too thin to separate body from wick; open/close not reliable (zoom in)")
    return Extraction(raw, spacing, regularity, ratio, body_res, warnings, (img.shape[1], img.shape[0]))


def to_ohlc(ex: Extraction, cal: AxisCalibration | None, image_height: int) -> list[dict]:
    """Candles left->right. Calibrated -> real prices; otherwise 'pixel units' (image_height - y), flagged."""
    conv = (lambda y: cal.price(y)) if cal else (lambda y: float(image_height - y))
    out = []
    for c in ex.candles:
        if not c.body_resolved:
            continue
        o, cl = conv(c.y_open), conv(c.y_close)
        h, lo = conv(c.y_high), conv(c.y_low)
        out.append({"x": c.x, "open": o, "high": max(h, lo, o, cl), "low": min(h, lo, o, cl), "close": cl,
                    "bullish": c.bullish})
    return out
