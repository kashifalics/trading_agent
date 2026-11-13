"""Causal indicators: value at index i uses only bars <= i."""
import numpy as np


def true_range(h: np.ndarray, l: np.ndarray, c: np.ndarray) -> np.ndarray:  # noqa: E741
    tr = h - l
    if len(c) > 1:
        pc = c[:-1]
        tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - pc), np.abs(l[1:] - pc)])
    return tr


def atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:  # noqa: E741
    """Wilder ATR. NaN until n bars are available."""
    out = np.full(len(c), np.nan)
    if len(c) < n:
        return out
    tr = true_range(h, l, c)
    out[n - 1] = tr[:n].mean()
    for i in range(n, len(c)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    k = 2.0 / (n + 1)
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    d = np.diff(c)
    gain, loss = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    ag, al = gain[:n].mean(), loss[:n].mean()
    out[n] = 100 - 100 / (1 + ag / al) if al > 0 else 100.0
    for i in range(n + 1, len(c)):
        ag = (ag * (n - 1) + gain[i - 1]) / n
        al = (al * (n - 1) + loss[i - 1]) / n
        out[i] = 100 - 100 / (1 + ag / al) if al > 0 else 100.0
    return out


def rolling_sum(x: np.ndarray, n: int) -> np.ndarray:
    cs = np.cumsum(np.insert(np.nan_to_num(x), 0, 0.0))
    idx = np.arange(len(x))
    return cs[idx + 1] - cs[np.maximum(0, idx + 1 - n)]


def _wilder(x: np.ndarray, n: int, start: int) -> np.ndarray:
    """Wilder smoothing of x from index `start` (seeded with the mean of the first n values)."""
    out = np.full(len(x), np.nan)
    if len(x) < start + n:
        return out
    out[start + n - 1] = x[start:start + n].mean()
    for i in range(start + n, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def adx(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:  # noqa: E741
    """Wilder ADX with +DI and -DI (each NaN until enough bars). Returns (adx, plus_di, minus_di)."""
    m = len(c)
    nan = np.full(m, np.nan)
    if m < 2 * n + 1:
        return nan, nan.copy(), nan.copy()
    up, down = np.zeros(m), np.zeros(m)
    up[1:], down[1:] = h[1:] - h[:-1], l[:-1] - l[1:]
    pdm = np.where((up > down) & (up > 0), up, 0.0)
    mdm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(h, l, c)
    atr_w = _wilder(tr, n, 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        pdi = 100 * _wilder(pdm, n, 1) / atr_w
        mdi = 100 * _wilder(mdm, n, 1) / atr_w
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    dx = np.where(np.isfinite(dx), dx, 0.0)
    first = n  # first index where dx is defined
    out = np.full(m, np.nan)
    if m >= first + n:
        out[first + n - 1] = dx[first:first + n].mean()
        for i in range(first + n, m):
            out[i] = (out[i - 1] * (n - 1) + dx[i]) / n
    return out, pdi, mdi


def bollinger_width(c: np.ndarray, n: int = 20, k: float = 2.0) -> np.ndarray:
    """(upper - lower) / middle of a k-sigma Bollinger band over n closes (population sigma). NaN until n bars."""
    out = np.full(len(c), np.nan)
    for i in range(n - 1, len(c)):
        w = c[i - n + 1:i + 1]
        mid = w.mean()
        if mid != 0:
            out[i] = 2 * k * w.std() / abs(mid)
    return out


def efficiency_ratio(c: np.ndarray, n: int = 20) -> np.ndarray:
    """|close - close n bars ago| / sum of |close-to-close changes| over those n bars (1 = a straight line, ~0 = noise)."""
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    path = rolling_sum(np.abs(np.r_[0.0, np.diff(c)]), n)
    net = np.abs(c[n:] - c[:-n])
    with np.errstate(invalid="ignore", divide="ignore"):
        out[n:] = np.where(path[n:] > 0, net / path[n:], 0.0)
    return out


def trailing_percentile(x: np.ndarray, window: int = 200, min_periods: int = 50) -> np.ndarray:
    """Share of the trailing `window` values (including the current one) that are <= the current value. NaN until min_periods."""
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        if not np.isfinite(x[i]):
            continue
        w = x[max(0, i - window + 1):i + 1]
        w = w[np.isfinite(w)]
        if len(w) >= min_periods:
            out[i] = float((w <= x[i]).mean())
    return out
