"""Experiment-2 simulator features against a minute-by-minute reference (TEST FIXTURES ONLY: synthetic Brownian M1 paths):
long holding periods, conservative limit fills (must trade through by `through`), stop minute timestamps and target-hit candles."""
from datetime import datetime, timezone

import numpy as np
import pytest

from app.gold_research import nulls, sim
from app.historical.build import resample

HOLDS2 = (20, 60, 120)


@pytest.fixture(scope="module")
def S():
    m1df = nulls.brownian_m1(datetime(2021, 3, 1, tzinfo=timezone.utc), 120, seed=5)
    m1 = nulls.m1_from_frame(m1df)
    return sim.Series.from_frame(resample(m1df, "1h"), "H1", m1)


def reference(S, d, entry_bar, stop, atr, limit, cancel, wait, through, k=2.0):
    m1, p = S.m1, S.m1.point
    bid, ask = m1.bid.astype(float) * p, m1.ask.astype(float) * p
    ex_hi, ex_lo, ex_op = (bid[:, 1], bid[:, 2], bid[:, 0]) if d > 0 else (ask[:, 1], ask[:, 2], ask[:, 0])
    e = None
    for j in range(entry_bar, min(S.n, entry_bar + wait)):
        hit = [m for m in range(S.m1_lo[j], S.m1_hi[j]) if (ask[m, 2] < limit - through if d > 0 else bid[m, 1] > limit + through)]
        if hit:
            f = hit[0]
            op = ask[f, 0] if d > 0 else bid[f, 0]
            e, P, first = j, (min(limit, op) if d > 0 else max(limit, op)), f
            break
        if (S.bc[j] < cancel) if d > 0 else (S.bc[j] > cancel):
            return None
    if e is None:
        return None
    raw = (P - stop) if d > 0 else (stop - P)
    hmax = max(HOLDS2)
    if raw <= 0 or e + hmax > S.n:
        return None
    R = max(raw, sim.MIN_RISK_ATR * atr)
    bar_of = np.searchsorted(S.m1_lo, np.arange(len(m1.ts)), side="right") - 1
    stop_m, hit_bar, fav = None, -1, {}
    for m in range(first, S.m1_hi[e + hmax - 1]):
        adv = ((P - ex_lo[m]) if d > 0 else (ex_hi[m] - P)) / R
        if adv >= 1:
            stop_m = m
            break
        f = -np.inf if m == first else ((ex_hi[m] - P) if d > 0 else (P - ex_lo[m])) / R
        fav[m] = f
        if f >= k and hit_bar < 0:
            hit_bar = int(bar_of[m])
    out = {"stop_ts": int(m1.ts[stop_m]) if stop_m is not None else -1, "hit": hit_bar, "entry_bar": e}
    for h in HOLDS2:
        end = S.m1_hi[e + h - 1]
        out[f"stopped_{h}"] = stop_m is not None and stop_m < end
        vals = [v for mm, v in fav.items() if mm < end]
        out[f"mfe_{h}"] = max(vals) if vals else -np.inf
    return out


def test_long_holds_conservative_fills_exit_candles_match_minute_reference(S):
    rng = np.random.default_rng(9)
    n = 250
    d = rng.choice([-1, 1], n)
    eb = rng.integers(10, S.n - max(HOLDS2) - 40, n)
    near = S.bc[eb - 1] - d * rng.uniform(0.0, 3.0, n)
    far = near - d * rng.uniform(0.5, 3.0, n)
    thr = rng.uniform(0.0, 0.6, n)
    o = sim.Orders(d=d, entry_bar=eb, stop=far - d * 0.3, atr=np.full(n, 3.0), limit=near, cancel=far, wait=20, through=thr)
    res = sim.simulate(S, o, holds=HOLDS2, hit_targets=(2.0,))
    checked = 0
    for i in range(n):
        ref = reference(S, int(d[i]), int(eb[i]), float(far[i] - d[i] * 0.3), 3.0, float(near[i]), float(far[i]), 20, float(thr[i]))
        if ref is None:
            assert not res["simulated"][i]
            continue
        assert res["simulated"][i] and res["fill_bar"][i] == ref["entry_bar"]
        checked += 1
        assert res["hit_2"][i] == ref["hit"], (i, res["hit_2"][i], ref["hit"])
        if ref["stop_ts"] >= 0 and ref["hit"] < 0:
            assert res["stop_ts"][i] == ref["stop_ts"]
        for h in HOLDS2:
            assert res[f"stopped_{h}"][i] == ref[f"stopped_{h}"]
            assert res[f"mfe_{h}"][i] == pytest.approx(ref[f"mfe_{h}"], abs=1e-4)
    assert checked > 80


def test_conservative_fill_never_fills_where_touch_does_not_and_fills_less_often(S):
    rng = np.random.default_rng(2)
    n = 400
    d = rng.choice([-1, 1], n)
    eb = rng.integers(10, S.n - max(HOLDS2) - 40, n)
    near = S.bc[eb - 1] - d * rng.uniform(0.0, 2.0, n)
    far = near - d * 1.5
    base = dict(d=d, entry_bar=eb, stop=far - d * 0.3, atr=np.full(n, 3.0), limit=near, cancel=far, wait=20)
    touch = sim.simulate(S, sim.Orders(**base), holds=HOLDS2)
    cons = sim.simulate(S, sim.Orders(**base, through=np.full(n, 0.3)), holds=HOLDS2)
    t, c = touch["fill_bar"] >= 0, cons["fill_bar"] >= 0
    assert not (c & ~t).any() and c.sum() < t.sum()
    both = c & t
    assert (cons["fill_bar"][both] >= touch["fill_bar"][both]).all()  # never earlier than a touch fill
