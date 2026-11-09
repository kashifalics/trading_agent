"""Pattern event extraction over long histories (TEST FIXTURES ONLY, never market data): chunking, causality and the chunk cache."""
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.gold_research import events as P
from app.gold_research import sim


def random_walk(n=3000, seed=7):
    rng = np.random.default_rng(seed)
    c = 1500 + np.cumsum(rng.normal(0, 1, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 1, n)
    lo = np.minimum(o, c) - rng.uniform(0, 1, n)
    return o, h, lo, c


def bars(o, h, lo, c, step=300):
    t0 = int(datetime(2010, 1, 4, tzinfo=timezone.utc).timestamp())
    df = pl.DataFrame({"ts": [datetime.fromtimestamp(t0 + i * step, timezone.utc) for i in range(len(c))], "bid_open": o, "bid_high": h,
                       "bid_low": lo, "bid_close": c, "bid_volume": np.ones(len(c))})
    return P.bars_from_frame(df, step)


def _keys(df):
    return {(p, d, i, None if s != s else round(s, 9)) for p, d, i, s in df.select("pattern", "direction", "idx", "stop_level").rows()}


def test_chunked_detection_matches_one_pass_for_local_patterns(monkeypatch):
    b = bars(*random_walk())
    one, _ = P.find_events(b)
    monkeypatch.setattr(P, "CHUNK", 1000)
    monkeypatch.setattr(P, "WARMUP", 300)
    many, _ = P.find_events(b)
    for sel in (pl.col("family") == "candlestick", pl.col("pattern") == "fvg"):
        assert _keys(one.filter(sel)) == _keys(many.filter(sel))
    assert many.height > 1000


def test_no_lookahead_events_before_a_cut_do_not_change_when_future_bars_are_added():
    o, h, lo, c = random_walk()
    cut = 2000
    full, _ = P.find_events(bars(o, h, lo, c))
    part, _ = P.find_events(bars(o[:cut], h[:cut], lo[:cut], c[:cut]))
    early = lambda d: _keys(d.filter(pl.col("idx") < cut - 25))  # noqa: E731
    assert early(full) == early(part)
    assert set(full["pattern"].unique()) >= {"BOS", "fvg", "order_block", "liquidity_sweep", "breakout", "pin_bar_bull", "swing_failure", "failed_bos", "engulfing_bull"}


def test_chunk_cache_resumes_and_is_reused_only_for_identical_data(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "CHUNK", 1000)
    monkeypatch.setattr(P, "WARMUP", 300)
    o, h, lo, c = random_walk()
    first, tr1 = P.find_events(bars(o, h, lo, c), cache_dir=tmp_path)
    files = sorted(tmp_path.glob("chunk_*.parquet"))
    assert len(files) == 3 and len(list(tmp_path.glob("*.trend.npy"))) == 3
    again, tr2 = P.find_events(bars(o, h, lo, c), cache_dir=tmp_path, log=lambda m: seen.append(m)) if (seen := []) == [] else None
    assert sum("cached" in m for m in seen) == 3 and _keys(again) == _keys(first) and (tr1 == tr2).all()
    c2 = c.copy()
    c2[2500] += 50  # different data in the last chunk: that chunk must be recomputed, the first two reused
    seen.clear()
    P.find_events(bars(o, h, lo, c2), cache_dir=tmp_path, log=lambda m: seen.append(m))
    assert sum("cached" in m for m in seen) == 2
    assert sim.HMAX == max(sim.HOLDS)
