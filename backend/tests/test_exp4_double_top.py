"""Experiment 4 detector: identical to the user's pasted loop, mirrored correctly, and free of look-ahead."""
import numpy as np
import pandas as pd

from app.gold_research.exp4.detect import detect


def user_detect_flexible_double_top(df, lookback=20, tolerance_pct=0.0005):
    """The user's pasted reference loop (signal rule only; the levels are replaced by the pre-registered ones)."""
    signals = []
    for i in range(lookback, len(df)):
        window = df.iloc[i - lookback:i]
        peak1_idx = window['high'].idxmax()
        peak1_val = window['high'].max()
        remaining_window = window.loc[peak1_idx:]
        if len(remaining_window) < 5:
            continue
        trough_val = remaining_window['low'].min()
        trough_idx = remaining_window['low'].idxmin()
        post_trough_window = remaining_window.loc[trough_idx:]
        if post_trough_window.empty:
            continue
        peak2_val = post_trough_window['high'].max()
        peak2_idx = post_trough_window['high'].idxmax()
        if abs(peak1_val - peak2_val) <= peak1_val * tolerance_pct and peak2_idx > trough_idx:
            if df['close'].iloc[i] < trough_val:
                signals.append(i)
    return signals


def candles(n: int, seed: int, start: float = 1300.0) -> pd.DataFrame:
    """A valid gold-like random walk (open/close inside high/low), rounded to the cent so equal highs occur."""
    rng = np.random.default_rng(seed)
    c = start + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[start, c[:-1]]
    h = np.maximum(o, c) + rng.exponential(0.6, n)
    lo = np.minimum(o, c) - rng.exponential(0.6, n)
    ix = pd.date_range("2010-01-04", periods=n, freq="15min")
    return pd.DataFrame({"high": h.round(2), "low": lo.round(2), "close": c.round(2)}, index=ix)


def test_vectorised_detector_matches_the_users_loop_exactly():
    total = 0
    for seed in range(6):
        df = candles(1500, seed)
        for lb, tol in ((20, 0.0005), (15, 0.001), (30, 0.002)):
            ref = user_detect_flexible_double_top(df, lb, tol)
            got = detect(df["high"].values, df["low"].values, df["close"].values, side=-1, lookback=lb, tol=tol, dedupe=False)
            assert got["idx"].tolist() == ref, (seed, lb, tol)
            total += len(ref)
    assert total > 50  # the comparison exercised real signals


def test_double_bottom_is_the_mirror_image():
    df = candles(3000, 11).round(0)  # whole dollars: exactly equal extremes are common, so tolerance 0 still finds patterns
    K = 2 * float(df["high"].max()) + 10  # reflect the prices: tops become bottoms, still positive
    top = detect(K - df["low"].values, K - df["high"].values, K - df["close"].values, side=-1, tol=0.0)
    bottom = detect(df["high"].values, df["low"].values, df["close"].values, side=+1, tol=0.0)
    assert bottom["idx"].tolist() == top["idx"].tolist() and len(bottom["idx"]) > 0  # tol 0: equal lows only, scale-free
    assert np.allclose(bottom["level"], K - top["level"])


def test_hand_made_double_top_and_bottom():
    # peak 1 = 20 (position 3), trough low 12 (position 5), peak 2 = 19.99 (position 7); price then drifts above the neckline
    h = np.array([10, 11, 12, 20, 15, 13, 14, 19.99, 16, 15, 14, 14.5, 14, 13.5, 14, 13.8, 13.6, 13.4, 13.2, 13.1, 13.05, 12.5], float)
    lo = h - 1
    c = h - 0.5
    c[-1] = 11.0  # ... until candle 21 closes below the neckline 12
    lo[-1] = 10.5
    r = detect(h, lo, c, side=-1, lookback=20, tol=0.001, dedupe=False)
    assert 21 in r["idx"].tolist()
    k = r["idx"].tolist().index(21)
    assert r["peak1"][k] == 3 and r["peak2"][k] == 7 and r["level"][k] == 20
    rb = detect(-lo + 40, -h + 40, -c + 40, side=+1, lookback=20, tol=0.001, dedupe=False)
    assert 21 in rb["idx"].tolist()


def test_no_look_ahead_signals_only_use_the_past():
    df = candles(2000, 3)
    full = detect(df["high"].values, df["low"].values, df["close"].values, side=-1, dedupe=False)["idx"]
    for cut in (400, 977, 1500):
        part = detect(df["high"].values[:cut], df["low"].values[:cut], df["close"].values[:cut], side=-1, dedupe=False)["idx"]
        assert part.tolist() == full[full < cut].tolist()


def test_one_signal_per_pattern_instance():
    df = candles(3000, 5)
    raw = detect(df["high"].values, df["low"].values, df["close"].values, side=-1, dedupe=False)
    one = detect(df["high"].values, df["low"].values, df["close"].values, side=-1)
    pairs = set(zip(raw["peak1"].tolist(), raw["peak2"].tolist()))
    assert len(one["idx"]) == len(pairs) and one["idx"].tolist() == sorted(one["idx"].tolist())
