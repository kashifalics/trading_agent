"""Market regime labels: causal and sensible on synthetic paths (TEST FIXTURES ONLY)."""
from datetime import datetime, timezone

import numpy as np

from app.feature_engineering.indicators import atr as atr_fn
from app.gold_research import regimes


def series(c, seed=0):
    rng = np.random.default_rng(seed)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0.1, 0.5, len(c))
    lo = np.minimum(o, c) - rng.uniform(0.1, 0.5, len(c))
    t = int(datetime(2020, 1, 6, tzinfo=timezone.utc).timestamp()) + 3600 * np.arange(len(c))
    return t, o, h, lo, c, atr_fn(h, lo, c, 14)


def test_regimes_are_causal():
    rng = np.random.default_rng(3)
    c = 1500 + np.cumsum(rng.normal(0, 1, 3000))
    t, o, h, lo, c, a = series(c)
    full = regimes.compute(t, o, h, lo, c, a, trend_struct=np.zeros(3000, np.int8))
    k = 1800
    part = regimes.compute(t[:k], o[:k], h[:k], lo[:k], c[:k], a[:k], trend_struct=np.zeros(k, np.int8))
    for k, v in full.items():
        assert (np.asarray(v)[:1800] == np.asarray(part[k])).all(), k


def test_regime_labels_follow_the_price_path():
    n = 1500
    up = 1500 + 2.0 * np.arange(n) + np.random.default_rng(1).normal(0, 0.3, n)
    flat = 1500 + np.random.default_rng(2).normal(0, 0.3, n)
    r_up = regimes.compute(*series(up), trend_struct=np.ones(n, np.int8))
    r_flat = regimes.compute(*series(flat), trend_struct=np.zeros(n, np.int8))
    assert (r_up["trend_regime"][300:] == "strong_bullish").mean() > 0.9
    assert (r_flat["trend_regime"][300:] == "none").mean() > 0.8
    assert set(r_flat["range_regime"][300:]) <= {"tight_range", "balanced_range", "wide_range", "volatile_range", "trending"}
    assert set(r_up["vol_level"][1300:]) <= {"very_low", "low", "normal", "high", "extreme", "unknown"}
