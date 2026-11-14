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


# ---- confirmation layer (docs/engine_v2/CONFIRMATION_DESIGN.md section 4) ----------------------------------------------------------
def valid_from(x: np.ndarray, k: int) -> np.ndarray:
    """A copy of x with the first k values set to NaN (an explicit warm-up)."""
    out = np.asarray(x, dtype=float).copy()
    out[:k] = np.nan
    return out


def _ema_valid(x: np.ndarray, n: int) -> np.ndarray:
    """EMA that starts where x becomes finite (seeded with the mean of the first n finite values)."""
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    fin = np.flatnonzero(np.isfinite(x))
    if len(fin) == 0:
        return out
    s = fin[0]
    out[s:] = ema(x[s:], n)
    return out


def sma(x: np.ndarray, n: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        cs = np.cumsum(np.insert(x, 0, 0.0))
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def macd(c: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(MACD line, signal line, histogram). The histogram is valid from index slow + signal - 2."""
    line = ema(c, fast) - ema(c, slow)
    sig = _ema_valid(line, signal)
    return line, sig, line - sig


def stoch_rsi(c: np.ndarray, rsi_n: int = 14, stoch_n: int = 14, k: int = 3, d: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """(%K, %D) on 0-100: where RSI sits in its own range over stoch_n candles, smoothed. A flat RSI range reads 50."""
    r = rsi(c, rsi_n)
    raw = np.full(len(c), np.nan)
    for i in range(rsi_n + stoch_n - 1, len(c)):
        w = r[i - stoch_n + 1:i + 1]
        lo, hi = w.min(), w.max()
        raw[i] = 50.0 if hi == lo else 100 * (r[i] - lo) / (hi - lo)
    kk = np.full(len(c), np.nan)
    s = rsi_n + stoch_n - 1
    if len(c) > s:
        kk[s:] = sma(raw[s:], k)
    dd = np.full(len(c), np.nan)
    s2 = s + k - 1
    if len(c) > s2:
        dd[s2:] = sma(kk[s2:], d)
    return kk, dd


def roc(c: np.ndarray, n: int = 10) -> np.ndarray:
    """Rate of change: c[i] / c[i-n] - 1."""
    c = np.asarray(c, dtype=float)
    out = np.full(len(c), np.nan)
    if len(c) > n:
        with np.errstate(divide="ignore", invalid="ignore"):
            out[n:] = c[n:] / c[:-n] - 1
    return out


def keltner(h: np.ndarray, l: np.ndarray, c: np.ndarray, n_ema: int = 20, n_atr: int = 10,  # noqa: E741
            mult: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(middle = EMA of closes, upper, lower = middle -/+ mult x ATR)."""
    mid = ema(np.asarray(c, dtype=float), n_ema)
    a = atr(np.asarray(h, dtype=float), np.asarray(l, dtype=float), np.asarray(c, dtype=float), n_atr)
    return mid, mid + mult * a, mid - mult * a


def hist_vol(c: np.ndarray, n: int = 20) -> np.ndarray:
    """Standard deviation (sample) of the last n log returns."""
    c = np.asarray(c, dtype=float)
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    r = np.diff(np.log(c))
    w = np.lib.stride_tricks.sliding_window_view(r, n)
    out[n:] = w.std(axis=1, ddof=1)
    return out


def session_vwap(h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray, session_id: np.ndarray) -> np.ndarray:  # noqa: E741
    """Volume-weighted typical price since the start of each session. NaN while the session's volume is zero, and for the rest of a
    session once a candle in it has no volume."""
    tp = (np.asarray(h, float) + np.asarray(l, float) + np.asarray(c, float)) / 3
    v = np.asarray(v, dtype=float)
    out = np.full(len(tp), np.nan)
    pv = vol = 0.0
    bad = False
    for i in range(len(tp)):
        if i == 0 or session_id[i] != session_id[i - 1]:
            pv = vol = 0.0
            bad = False
        if not np.isfinite(v[i]):
            bad = True
        if bad:
            continue
        pv += tp[i] * v[i]
        vol += v[i]
        if vol > 0:
            out[i] = pv / vol
    return out


def obv(c: np.ndarray, v: np.ndarray) -> np.ndarray:
    """On-balance volume from 0: + volume on an up close, - volume on a down close, unchanged on an equal close."""
    c, v = np.asarray(c, float), np.asarray(v, float)
    step = np.r_[0.0, np.sign(np.diff(c)) * v[1:]]
    return np.cumsum(step)


def mfi(h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray, n: int = 14) -> np.ndarray:  # noqa: E741
    """Money Flow Index on 0-100 (volume-weighted RSI of the typical price). 100 when no flow was negative."""
    tp = (np.asarray(h, float) + np.asarray(l, float) + np.asarray(c, float)) / 3
    flow = tp * np.asarray(v, float)
    d = np.r_[0.0, np.diff(tp)]
    pos, neg = np.where(d > 0, flow, 0.0), np.where(d < 0, flow, 0.0)
    out = np.full(len(tp), np.nan)
    for i in range(n, len(tp)):
        p, m = pos[i - n + 1:i + 1].sum(), neg[i - n + 1:i + 1].sum()
        out[i] = 100.0 if m == 0 else 100 - 100 / (1 + p / m)
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
