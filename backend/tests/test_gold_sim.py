"""Gold research simulator against a slow minute-by-minute reference (TEST FIXTURES ONLY: synthetic Brownian M1 paths)."""
from datetime import datetime, timezone

import numpy as np
import polars as pl
import pytest

from app.gold_research import controls as C
from app.gold_research import nulls, sim
from app.gold_research import stats as Stt
from app.historical.build import resample


@pytest.fixture(scope="module")
def world():
    m1df = nulls.brownian_m1(datetime(2021, 3, 1, tzinfo=timezone.utc), 60, seed=11)
    m1 = nulls.m1_from_frame(m1df)
    h1 = resample(m1df, "1h")
    return m1df, m1, sim.Series.from_frame(h1, "H1", m1)


def reference(S: sim.Series, d: int, entry_bar: int, stop: float, atr: float, limit=None, cancel=None, wait=50):
    """Plain loops over minutes: the definition the vectorized simulator must reproduce exactly."""
    m1, p = S.m1, S.m1.point
    bid, ask = m1.bid.astype(float) * p, m1.ask.astype(float) * p
    ex_hi, ex_lo, ex_op = (bid[:, 1], bid[:, 2], bid[:, 0]) if d > 0 else (ask[:, 1], ask[:, 2], ask[:, 0])
    if limit is None:
        e, P, first = entry_bar, (ask[S.m1_lo[entry_bar], 0] if d > 0 else bid[S.m1_lo[entry_bar], 0]), S.m1_lo[entry_bar]
        skip = -1
    else:
        e = None
        for j in range(entry_bar, min(S.n, entry_bar + wait)):
            mins = range(S.m1_lo[j], S.m1_hi[j])
            hit = [m for m in mins if (ask[m, 2] < limit if d > 0 else bid[m, 1] > limit)]
            if hit:
                f = hit[0]
                op = ask[f, 0] if d > 0 else bid[f, 0]
                e, P, first, skip = j, (min(limit, op) if d > 0 else max(limit, op)), f, f
                break
            if (S.bc[j] < cancel) if d > 0 else (S.bc[j] > cancel):
                return None
        if e is None:
            return None
    raw = (P - stop) if d > 0 else (stop - P)
    if raw <= 0 or e + sim.HMAX > S.n:
        return None
    R = max(raw, sim.MIN_RISK_ATR * atr)
    stop_m, stop_r = None, np.nan
    fav_by_minute = {}
    for m in range(first, S.m1_hi[e + sim.HMAX - 1]):
        fav = ((ex_hi[m] - P) if d > 0 else (P - ex_lo[m])) / R
        adv = ((P - ex_lo[m]) if d > 0 else (ex_hi[m] - P)) / R
        if adv >= 1:
            stop_m = m
            gap = ((P - ex_op[m]) if d > 0 else (ex_op[m] - P)) / R
            stop_r = -1.0 if m == skip else -max(1.0, gap)
            break
        fav_by_minute[m] = -np.inf if m == skip else fav
    out = {"stop_r": stop_r}
    for h in sim.HOLDS:
        end = S.m1_hi[e + h - 1]
        favs = [v for m, v in fav_by_minute.items() if m < end]
        out[f"mfe_{h}"] = max(favs) if favs else -np.inf
        out[f"stopped_{h}"] = stop_m is not None and stop_m < end
        last = e + h - 1
        close = S.bc[last] if d > 0 else S.ac[last]
        out[f"end_r_{h}"] = ((close - P) if d > 0 else (P - close)) / R
    return out


def test_vectorized_simulator_matches_minute_reference_for_market_and_limit_orders(world):
    _, _, S = world
    rng = np.random.default_rng(3)
    n = 300
    atr = np.full(n, 3.0)
    d = rng.choice([-1, 1], n)
    eb = rng.integers(5, S.n - sim.HMAX - 60, n)
    px = np.where(d > 0, S.ao[eb], S.bo[eb])
    stop = px - d * rng.uniform(0.5, 6.0, n)
    mk = sim.simulate(S, sim.Orders(d=d, entry_bar=eb, stop=stop, atr=atr))
    near = S.bc[eb - 1] - d * rng.uniform(0.0, 4.0, n)
    far = near - d * rng.uniform(0.5, 4.0, n)
    lim = sim.simulate(S, sim.Orders(d=d, entry_bar=eb, stop=far - d * 0.3, atr=atr, limit=near, cancel=far, wait=20))
    checked = {"market": 0, "limit": 0}
    for kind, res in (("market", mk), ("limit", lim)):
        for i in range(n):
            ref = reference(S, int(d[i]), int(eb[i]), float(far[i] - d[i] * 0.3) if kind == "limit" else float(stop[i]), 3.0,
                            *((float(near[i]), float(far[i]), 20) if kind == "limit" else ()))
            if ref is None:
                assert not res["simulated"][i]
                continue
            assert res["simulated"][i]
            checked[kind] += 1
            for h in sim.HOLDS:
                assert res[f"stopped_{h}"][i] == ref[f"stopped_{h}"], (kind, i, h)
                assert res[f"mfe_{h}"][i] == pytest.approx(ref[f"mfe_{h}"], abs=1e-4), (kind, i, h)
                if not ref[f"stopped_{h}"]:
                    assert res[f"end_r_{h}"][i] == pytest.approx(ref[f"end_r_{h}"], abs=1e-4)
            if ref["stop_r"] == ref["stop_r"]:
                assert res["stop_r"][i] == pytest.approx(ref["stop_r"], abs=1e-6)
    assert checked["market"] > 250 and checked["limit"] > 100


def test_r_multiple_rules(world):
    o = {"simulated": np.array([True, True, True, False]), "stop_r": np.array([-1.0, -1.7, -1.0, -1.0]),
         "mfe_12": np.array([2.5, 0.4, 1.2, 9.0]), "stopped_12": np.array([False, True, False, False]),
         "end_r_12": np.array([0.3, 0.1, 0.7, 0.0])}
    r = sim.r_multiple(o, 2.0, 12)
    assert r[0] == 2.0 and r[1] == -1.7 and r[2] == pytest.approx(0.7) and np.isnan(r[3])


def test_brownian_world_has_no_edge_for_random_market_or_limit_trades(world):
    """Random 'patterns' on a path with no memory: after controls, the edge must be about zero for both entry types."""
    _, _, S = world
    from app.feature_engineering.indicators import atr as atr_fn
    a = atr_fn(S.bh, S.bl, S.bc, 14)
    vol = C.vol_bucket(a)
    rng = np.random.default_rng(5)
    bars = np.sort(rng.choice(np.arange(100, S.n - sim.HMAX - 2), 400, replace=False))
    pool = C.pool(S, a, vol, bars, "train")
    assert pool.height > 5000
    pat = rng.choice(np.arange(100, S.n - sim.HMAX - 2), 300, replace=False)
    for d in (1, -1):
        px = np.where(d > 0, S.ao[pat + 1], S.bo[pat + 1])
        res = sim.simulate(S, sim.Orders(d=np.full(len(pat), d), entry_bar=pat + 1, stop=px - d * 0.875 * a[pat], atr=a[pat]))
        ok = res["simulated"]
        ts = res["fill_ts"][ok]
        tr = pl.DataFrame({"entry": "market", "direction": np.int8(d), "risk_b": np.int8(2), "dist_b": np.int8(-1), "width_b": np.int8(-1),
                           "session": C.session_ny(ts), "vol": vol[pat][ok], "period": C.period_key(ts, "train"), "segment": "train",
                           "r": sim.r_multiple(res, 2.0, 24)[ok], "entry_ts": ts})
        ex = C.expectation(tr, pool.with_columns(r=pl.Series(sim.r_multiple({k: pool[k].to_numpy() for k in pool.columns} | {
            "simulated": np.ones(pool.height, bool)}, 2.0, 24))), "r")
        st = Stt.edge_stats(ex["r"].to_numpy(), ex["ctrl_mean"].to_numpy(), ex["ctrl_var"].to_numpy(), ex["ctrl_n"].to_numpy(),
                            ex["ctrl_cell"].to_numpy(), ex["entry_ts"].to_numpy(), 24 * 3600)
        assert abs(st["edge"]) < 3 * st["edge_se"] + 0.05, st


def test_statistics_helpers():
    rng = np.random.default_rng(0)
    ts = np.sort(rng.integers(0, 400 * Stt.WEEK, 4000))
    noise = Stt.clustered_mean(rng.normal(0, 1, 4000), Stt.cluster_ids(ts, 3600))
    planted = Stt.clustered_mean(rng.normal(0.15, 1, 4000), Stt.cluster_ids(ts, 3600))
    assert noise["p"] > 0.01 and planted["p"] < 1e-4
    q = Stt.bh(np.array([0.001, 0.01, 0.04, 0.5]))
    assert q[0] == pytest.approx(0.004) and q[3] == pytest.approx(0.5)
    h = Stt.holm(np.array([0.01, 0.02, 0.5]))
    assert h[0] == pytest.approx(0.03) and h[1] == pytest.approx(0.04)
    assert Stt.mde(0.05, 0.05) == pytest.approx((1.6449 + 0.8416) * 0.05, rel=1e-3)
    assert Stt.drawdown_r(np.array([1, -1, -1, 2, -3])) == 3


def test_whole_pipeline_finds_no_candidates_in_a_brownian_world(tmp_path, monkeypatch):
    """Detectors + simulator + controls + discovery statistics on a synthetic year with no memory: no edges may come out."""
    from app.gold_research import study
    from app.historical import split as Sp
    from app.historical import store as Sto
    from app.historical.build import build_timeframes

    for mod, names in ((Sto, ("CLEAN", "DATA_ROOT", "SPLIT_DIR")), (Sp, ("CLEAN", "SPLIT_DIR", "REPORTS")), (study, ("CLEAN", "DATA_ROOT", "SPLIT_DIR"))):
        for nm in names:
            monkeypatch.setattr(mod, nm, tmp_path / ("research_docs" if nm == "SPLIT_DIR" else "clean" if nm == "CLEAN" else
                                                     "reports" if nm == "REPORTS" else ""))
    m1df = nulls.brownian_m1(datetime(2021, 1, 4, tzinfo=timezone.utc), 300, seed=21)
    (tmp_path / "clean" / "XAUUSD" / "M1").mkdir(parents=True)
    m1df.write_parquet(tmp_path / "clean" / "XAUUSD" / "M1" / "2021.parquet")
    for tf, df in build_timeframes(resample(m1df, "5m")).items():
        (tmp_path / "clean" / "XAUUSD" / tf).mkdir(parents=True)
        df.write_parquet(tmp_path / "clean" / "XAUUSD" / tf / "all.parquet")
    Sp.freeze_split("XAUUSD", log=lambda m: None)
    Sto.build_m1_store("XAUUSD", log=lambda m: None)
    for tf in ("H1", "H4"):
        study.run_timeframe("XAUUSD", tf, "train")
    s = study.discover("XAUUSD", ["H1", "H4"], log=lambda m: None)
    tested = [r for r in s["rows"] if "q" in r]
    assert len(tested) >= 15
    assert len(s["candidates"]) <= 1, s["candidates"]
    edges = np.array([r["primary"]["edge"] for r in tested])
    assert np.median(np.abs(edges)) < 0.12, edges
    limit_tests = [r for r in tested if r["entry"] == "limit"]
    assert limit_tests and np.median([abs(r["primary"]["edge"]) for r in limit_tests]) < 0.15
