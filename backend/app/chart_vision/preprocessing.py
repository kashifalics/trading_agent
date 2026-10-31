import cv2
import numpy as np

MAX_WIDTH = 1800


def load_bgr(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("cannot decode image")
    return img


def normalize_size(img: np.ndarray) -> tuple[np.ndarray, float]:
    """Downscale very wide screenshots; returns (image, scale) where scale = new/old."""
    h, w = img.shape[:2]
    if w <= MAX_WIDTH:
        return img, 1.0
    s = MAX_WIDTH / w
    return cv2.resize(img, (MAX_WIDTH, int(h * s)), interpolation=cv2.INTER_AREA), s


def candle_color_masks(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks of bullish (green/teal) and bearish (red) candle pixels (HSV, OpenCV hue 0-179)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    strong = (s >= 90) & (v >= 90)
    green = strong & (h >= 35) & (h <= 95)
    red = strong & ((h <= 10) | (h >= 170))
    return green, red


def chart_region(green: np.ndarray, red: np.ndarray, margin: int = 12) -> tuple[int, int, int, int] | None:
    """Bounding box (x0, y0, x1, y1) of all candle-coloured pixels = the plot region."""
    ys, xs = np.nonzero(green | red)
    if len(xs) < 50:
        return None
    return (max(0, int(xs.min()) - margin), max(0, int(ys.min()) - margin), int(xs.max()) + margin, int(ys.max()) + margin)
