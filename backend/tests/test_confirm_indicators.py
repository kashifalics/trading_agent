"""Indicators of the confirmation layer (docs/engine_v2/CONFIRMATION_DESIGN.md section 4): causal, NaN during warm-up."""
import numpy as np
import pytest

from app.feature_engineering.indicators import ema, hist_vol, keltner, macd, mfi, obv, roc, session_vwap, sma, stoch_rsi, valid_from


def _series(n: int = 420, seed: int = 7):
    rng = np.random.default_rng(seed)
    c = 100 + np.cumsum(rng.normal(0, 0.6, n))
    h = c + rng.uniform(0.1, 0.8, n)
    lo = c - rng.uniform(0.1, 0.8, n)
    v = rng.uniform(50, 150, n)
    sid = np.arange(n) // 24  # a new session every 24 candles
    return h, lo, c, v, sid


FNS = {
    "macd_hist": lambda h, lo, c, v, s: macd(c)[2],
    "stoch_k": lambda h, lo, c, v, s: stoch_rsi(c)[0],
    "stoch_d": lambda h, lo, c, v, s: stoch_rsi(c)[1],
    "roc10": lambda h, lo, c, v, s: roc(c, 10),
    "keltner_up": lambda h, lo, c, v, s: keltner(h, lo, c)[1],
    "hv20": lambda h, lo, c, v, s: hist_vol(c, 20),
    "vwap": lambda h, lo, c, v, s: session_vwap(h, lo, c, v, s),
    "obv": lambda h, lo, c, v, s: obv(c, v),
    "mfi14": lambda h, lo, c, v, s: mfi(h, lo, c, v, 14),
    "sma20": lambda h, lo, c, v, s: sma(c, 20),
}


@pytest.mark.parametrize("name", FNS)
def test_indicator_is_causal(name):
    h, lo, c, v, s = _series()
    full = FNS[name](h, lo, c, v, s)
    for k in range(40, 420, 37):
        part = FNS[name](h[:k], lo[:k], c[:k], v[:k], s[:k])
        assert np.allclose(part, full[:k], equal_nan=True, rtol=1e-12, atol=1e-12), (name, k)


@pytest.mark.parametrize("name,first", [("macd_hist", 33), ("stoch_k", 29), ("stoch_d", 31), ("roc10", 10), ("keltner_up", 19),
                                        ("hv20", 20), ("mfi14", 14), ("sma20", 19)])
def test_warm_up_is_nan_until_valid_then_finite(name, first):
    h, lo, c, v, s = _series()
    x = FNS[name](h, lo, c, v, s)
    assert np.isnan(x[:first]).all() and np.isfinite(x[first:]).all(), name


def _ema_ref(x: list[float], n: int) -> list[float]:
    """Independent reference: SMA seed over the first n finite values, then the usual recursion."""
    out, start = [float("nan")] * len(x), next(i for i, v in enumerate(x) if v == v)
    k = 2 / (n + 1)
    prev = sum(x[start:start + n]) / n
    out[start + n - 1] = prev
    for i in range(start + n, len(x)):
        prev = x[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def test_macd_matches_an_independent_reference():
    _, _, c, _, _ = _series(80, seed=11)
    line_ref = [a - b for a, b in zip(_ema_ref(list(c), 12), _ema_ref(list(c), 26))]
    sig_ref = _ema_ref(line_ref, 9)
    line, sig, hist = macd(c)
    assert np.allclose(line, line_ref, equal_nan=True) and np.allclose(sig, sig_ref, equal_nan=True)
    assert np.allclose(hist[33:], (np.array(line_ref) - np.array(sig_ref))[33:])


def test_stoch_rsi_is_between_0_and_100():
    _, _, c, _, _ = _series()
    k, d = stoch_rsi(c)
    assert (k[29:] >= 0).all() and (k[29:] <= 100).all() and (d[31:] >= 0).all() and (d[31:] <= 100).all()


def test_roc_and_keltner_values():
    c = np.arange(1.0, 31.0)
    assert np.isclose(roc(c, 10)[20], 21 / 11 - 1)
    h, lo = c + 1, c - 1
    mid, up, low = keltner(h, lo, c, 20, 10, 2.0)
    assert np.isclose(mid[25], ema(c, 20)[25]) and np.isclose(up[25] - mid[25], mid[25] - low[25])


def test_vwap_resets_at_each_session_and_is_nan_without_volume():
    h = np.array([11.0, 12, 13, 21, 22])
    lo = np.array([9.0, 10, 11, 19, 20])
    c = np.array([10.0, 11, 12, 20, 21])
    v = np.array([1.0, 1, 2, 1, 3])
    s = np.array([0, 0, 0, 1, 1])
    w = session_vwap(h, lo, c, v, s)
    assert np.allclose(w, [10, 10.5, 11.25, 20, 20.75])  # typical price = close here; resets at the new session
    v2 = v.copy()
    v2[1] = np.nan
    w2 = session_vwap(h, lo, c, v2, s)
    assert np.isnan(w2[1:3]).all() and np.allclose(w2[[0, 3, 4]], [10, 20, 20.75])  # a missing volume voids its session only
    assert np.isnan(session_vwap(h, lo, c, np.zeros(5), s)).all()


def test_obv_adds_volume_on_up_closes_and_subtracts_on_down_closes():
    assert obv(np.array([1.0, 2, 1, 1, 3]), np.array([5.0, 2, 3, 4, 1])).tolist() == [0, 2, -1, -1, 0]


def test_mfi_is_100_when_every_candle_rises():
    c = np.arange(1.0, 31.0)
    assert np.allclose(mfi(c + 0.5, c - 0.5, c, np.ones(30), 14)[14:], 100.0)


def test_valid_from_masks_the_warm_up():
    x = valid_from(np.arange(5.0), 2)
    assert np.isnan(x[:2]).all() and x[2:].tolist() == [2.0, 3.0, 4.0]
