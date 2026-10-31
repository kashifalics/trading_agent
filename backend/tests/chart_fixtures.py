"""Renders SYNTHETIC chart screenshots for tests only (never presented as market data)."""
import cv2
import numpy as np

BULL_BGR, BEAR_BGR = (154, 166, 38), (80, 83, 239)  # TradingView-like teal / red
BG = (36, 25, 19)


def render_chart(ohlc: list[tuple[float, float, float, float]], width=1200, height=700, spacing=16, body_w=9,
                 with_volume=False, top=60, bottom=60) -> tuple[np.ndarray, dict]:
    """ohlc: (o,h,l,c). Returns (BGR image, info) where info maps price<->y."""
    pmin, pmax = min(c[2] for c in ohlc), max(c[1] for c in ohlc)
    plot_h = height - top - bottom - (120 if with_volume else 0)

    def y_of(p):
        return int(round(top + (pmax - p) / (pmax - pmin) * plot_h))

    img = np.full((height, width, 3), BG, np.uint8)
    for i, (o, h, lo, c) in enumerate(ohlc):
        x = 40 + i * spacing
        col = BULL_BGR if c >= o else BEAR_BGR
        cv2.line(img, (x, y_of(h)), (x, y_of(lo)), col, 1)
        y1, y2 = sorted((y_of(o), y_of(c)))
        cv2.rectangle(img, (x - body_w // 2, y1), (x + body_w // 2, max(y2, y1 + 1)), col, -1)
        if with_volume:
            vh = 10 + (i * 7) % 60
            cv2.rectangle(img, (x - body_w // 2, height - 20 - vh), (x + body_w // 2, height - 20), col, -1)
    info = {"y_of": y_of, "price_of": lambda y: pmax - (y - top) / plot_h * (pmax - pmin), "pmin": pmin, "pmax": pmax,
            "ppy": (pmax - pmin) / plot_h}
    return img, info


def png_bytes(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()
