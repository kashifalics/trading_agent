"""OCR (Tesseract) helpers. Everything degrades gracefully when the Tesseract binary is absent."""
import re
import shutil
from dataclasses import dataclass

import cv2
import numpy as np

CANONICAL = {
    "XAUUSD": "XAUUSD", "GOLD": "XAUUSD", "XAU/USD": "XAUUSD",
    "US30": "US30", "DJI": "US30", "DJIA": "US30", "DOW": "US30",
    "BTCUSDT": "BTCUSDT",
    "USOIL": "USOIL", "WTI": "USOIL", "USOUSD": "USOIL",
}
TF_PATTERNS = [
    (r"\b(1|3|5|15|30)\s?(?:m|min)\b", lambda m: f"{m.group(1)}m"),
    (r"\b(1|2|4)\s?(?:h|hr|hour)\b", lambda m: f"{m.group(1)}H"),
    (r"\b1\s?(?:d|day)\b|\bd1\b|\bdaily\b", lambda m: "1D"),
    (r"\b1\s?(?:w|week)\b|\bweekly\b", lambda m: "1W"),
    (r"\b(?:m1|m5|m15|m30)\b", lambda m: m.group(0)[1:] + "m"),
    (r"\bh(1|2|4)\b", lambda m: f"{m.group(1)}H"),
]


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _within_one_edit(a: str, b: str) -> bool:
    """True if a and b differ by at most one substitution/insertion/deletion."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def parse_chart_title(text: str) -> tuple[str | None, str | None, list[str]]:
    """(canonical symbol, timeframe, notes) from OCR'd header text. Exact alias matches only."""
    notes: list[str] = []
    up = text.upper()
    symbol = None
    for token in re.findall(r"[A-Z0-9/!]{2,10}", up):
        if token in CANONICAL:
            symbol = CANONICAL[token]
            break
        if token in ("BTCUSD", "CL1!", "USOILSPOT"):
            notes.append(f"'{token}' is not the same instrument as the configured series; not mapped")
            continue
        # Tolerate ONE OCR slip (e.g. BICUSDT) but only on long tokens; always reported.
        fuzzy = [k for k in CANONICAL if len(k) >= 6 and len(token) >= 6 and _within_one_edit(token, k)]
        if len({CANONICAL[k] for k in fuzzy}) == 1:
            symbol = CANONICAL[fuzzy[0]]
            notes.append(f"OCR read '{token}'; matched to {symbol} (1-character difference) - verify")
            break
    low = text.lower()
    tf = None
    for pat, fn in TF_PATTERNS:
        m = re.search(pat, low)
        if m:
            tf = fn(m)
            break
    return symbol, tf, notes


@dataclass
class AxisLabel:
    y: float
    value: float


def _numbers(img: np.ndarray, psm: int = 6) -> list[tuple[float, float, str]]:
    import pytesseract

    data = pytesseract.image_to_data(img, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789.,",
                                     output_type=pytesseract.Output.DICT)
    out = []
    for i, txt in enumerate(data["text"]):
        t = txt.strip().replace(",", "")
        if not re.fullmatch(r"\d+(\.\d+)?", t):
            continue
        out.append((data["top"][i] + data["height"][i] / 2.0, float(t), t))
    return out


def read_price_axis(img: np.ndarray, plot_right_x: int) -> list[AxisLabel]:
    """OCR the strip right of the plot for numeric labels -> (pixel y, price)."""
    if not ocr_available():
        return []
    strip = img[:, plot_right_x:]
    if strip.shape[1] < 20:
        return []
    big = cv2.resize(cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY), None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    if big.mean() < 127:
        big = 255 - big
    return [AxisLabel(y / 3.0, v) for y, v, _ in _numbers(big)]


def read_title_text(img: np.ndarray) -> str:
    if not ocr_available():
        return ""
    import pytesseract

    top = img[: max(60, img.shape[0] // 8), : img.shape[1] // 2]
    g = cv2.resize(cv2.cvtColor(top, cv2.COLOR_BGR2GRAY), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    if g.mean() < 127:
        g = 255 - g
    return pytesseract.image_to_string(g, config="--psm 6")
