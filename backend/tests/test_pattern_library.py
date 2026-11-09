"""Pattern library: every registered detector is causal and complete (TEST FIXTURES ONLY: synthetic candles)."""
from datetime import datetime, timezone

import numpy as np
import polars as pl
import pytest

from app.feature_engineering.indicators import atr as atr_fn
from app.gold_research.events import bars_from_frame, find_events
from app.historical.sync import bar_close
from app.patterns import FAMILY_DETECTORS
from app.patterns.context import compute_levels, first_touch
from app.patterns.registry import FAMILIES, REGISTRY, library_markdown


def frame(n=6000, seed=4, step=900):
    rng = np.random.default_rng(seed)
    c = 1800 + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[c[0], c[:-1]] + rng.normal(0, 0.2, n)
    h = np.maximum(o, c) + rng.exponential(0.6, n)
    lo = np.minimum(o, c) - rng.exponential(0.6, n)
    t0 = int(datetime(2015, 1, 5, tzinfo=timezone.utc).timestamp())
    ts = pl.Series([datetime.fromtimestamp(t0 + i * step, timezone.utc) for i in range(n)])
    return pl.DataFrame({"ts": ts, "bid_open": o, "bid_high": h, "bid_low": lo, "bid_close": c, "bid_volume": np.ones(n)}), step


def run(df, step):
    b = bars_from_frame(df, step)
    a = atr_fn(b.h, b.l, b.c, 14)
    lv = compute_levels(df["ts"], bar_close("M15", b.t), b.h, b.l)
    return find_events(b, a, levels=lv)[0]


def keys(df):
    return {(p, d, i, None if s != s else round(s, 6)) for p, d, i, s in df.select("pattern", "direction", "idx", "stop_level").rows()}


@pytest.fixture(scope="module")
def full():
    df, step = frame()
    return df, step, run(df, step)


def test_every_registered_detector_is_causal(full):
    """Events confirmed before a cut must not change when later candles are added (prefix vs full history)."""
    df, step, ev_full = full
    for cut in (2500, 4100):
        ev_part = run(df.head(cut), step)
        early = lambda d: keys(d.filter(pl.col("idx") < cut - 25))  # noqa: E731
        diff = early(ev_full) ^ early(ev_part)
        assert not diff, sorted(diff)[:10]


def test_registered_patterns_fire_and_stops_sit_on_the_right_side(full):
    df, _, ev = full
    implemented = {k for k, s in REGISTRY.items() if s.status == "implemented" and s.family in "ABC"}
    fired = set(ev["pattern"].unique())
    rare = {"pm_high_sweep", "pm_low_sweep", "pw_high_sweep", "pw_low_sweep", "morning_doji_star", "evening_doji_star",
            "three_white_soldiers", "three_black_crows", "rising_three_methods", "falling_three_methods", "kicker", "multiple_sweeps"}
    assert implemented - fired - rare == set(), sorted(implemented - fired - rare)
    h, lo = df["bid_high"].to_numpy(), df["bid_low"].to_numpy()
    d = ev.filter((pl.col("direction") != 0) & pl.col("stop_level").is_not_nan() & (pl.col("entry") == "next_open"))
    i = d["idx"].to_numpy()
    s, dd = d["stop_level"].to_numpy(), d["direction"].to_numpy()
    wrong = np.where(dd > 0, s > h[i] + 1e-9, s < lo[i] - 1e-9)  # a long's stop is never above the confirming candle's high
    assert not wrong.any(), d.filter(pl.Series(wrong)).head(5)


def test_library_document_lists_every_pattern_and_scoped_items_have_reasons():
    md = library_markdown()
    for k, s in REGISTRY.items():
        assert f"`{k}`" in md
        assert s.family in FAMILIES
        if s.status == "scoped_out":
            assert s.reason
    assert len(FAMILY_DETECTORS) >= 3


def test_period_levels_are_point_in_time_and_first_touch_is_once_per_period():
    df, step = frame(3000, step=3600)
    b = bars_from_frame(df, step)
    lv = compute_levels(df["ts"], bar_close("H1", b.t), b.h, b.l)
    lv_cut = compute_levels(df["ts"].head(1500), bar_close("H1", b.t[:1500]), b.h[:1500], b.l[:1500])
    for k in ("pdh", "pwl", "pmh", "asia_h", "london_l"):
        assert np.allclose(getattr(lv, k)[:1500], getattr(lv_cut, k), equal_nan=True), k
    t = first_touch(lv.pdh, b.h, lv.day_id, above=True)
    days = lv.day_id[t]
    assert len(days) == len(np.unique(days))
