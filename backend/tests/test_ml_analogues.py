import numpy as np
import pytest

from app.feature_engineering.features import compute_features
from app.feature_engineering.labels import LabelConfig, triple_barrier
from app.historical_engine.analogues import AnalogueConfig, find_analogues
from app.historical_engine.similarity import knn
from app.historical_engine.stats import wilson_interval
from app.market_data.bars import Bars
from app.ml_engine.calibration import ProbabilityCalibrator
from app.ml_engine.datasets import build_dataset
from app.ml_engine.evaluation import calibration_curve, trade_metrics
from app.ml_engine.training import (
    ALGORITHMS,
    purged_walk_forward_splits,
    train_and_evaluate,
)


def walk(n, seed=3, vol=1.0, drift=0.0):
    rng = np.random.default_rng(seed)
    c = 1000 + np.cumsum(rng.normal(drift, vol, n))
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + rng.uniform(0.05, 0.6, n) * vol
    low = np.minimum(o, c) - rng.uniform(0.05, 0.6, n) * vol
    return Bars.from_arrays(o, h, low, c)


def test_features_are_point_in_time():
    b = walk(600)
    _, full = compute_features(b)
    for k in (120, 300, 450):
        _, part = compute_features(b.upto(k + 1))
        assert np.allclose(full[k], part[k], equal_nan=True), k
        assert np.allclose(full[: k + 1], part, equal_nan=True)


def test_labels_depend_only_on_bars_up_to_t1():
    b = walk(400)
    from app.feature_engineering.indicators import atr
    a = atr(b.h, b.l, b.c)
    lab = triple_barrier(b, a, LabelConfig(horizon=12))
    b2 = Bars(b.t.copy(), b.o.copy(), b.h.copy(), b.l.copy(), b.c.copy(), b.v.copy(), b.step)
    cut = 200
    b2.h[cut:] += 50  # corrupt the future
    b2.l[cut:] += 50
    b2.o[cut:] += 50
    b2.c[cut:] += 50
    lab2 = triple_barrier(b2, atr(b2.h, b2.l, b2.c), LabelConfig(horizon=12))
    safe = np.flatnonzero(lab.valid & (lab.t1 < cut - 1) & (np.arange(len(lab.t1)) < cut - 14))
    assert len(safe) > 50
    assert (lab.y[safe] == lab2.y[safe]).all()


def test_triple_barrier_conservative_same_bar():
    # ATR will be ~2 (range 2 bars). entry = open of next bar.
    n = 40
    o = np.full(n, 100.0)
    h = np.full(n, 101.0)
    low = np.full(n, 99.0)
    c = np.full(n, 100.0)
    h[30], low[30] = 110.0, 90.0  # both TP and SL reachable in one bar for both directions
    b = Bars.from_arrays(o, h, low, c)
    from app.feature_engineering.indicators import atr
    lab = triple_barrier(b, atr(b.h, b.l, b.c), LabelConfig(horizon=5, tp_atr=2, sl_atr=1))
    assert lab.long_result[27] == -1 and lab.short_result[27] == -1 and lab.y[27] == 0
    # clean up-move: TP hit first
    h2 = h.copy()
    h2[30] = 120.0
    low2 = low.copy()
    low2[30] = 99.5
    lab2 = triple_barrier(Bars.from_arrays(o, h2, low2, c), atr(h2, low2, c), LabelConfig(horizon=5, tp_atr=2, sl_atr=1))
    assert lab2.long_result[27] == 1 and lab2.y[27] == 1 and lab2.t1[27] == 30


def test_purged_walk_forward_has_no_overlap():
    b = walk(1500)
    ds = build_dataset(b, LabelConfig(horizon=24))
    splits = list(purged_walk_forward_splits(ds.row_idx, ds.t1, n_splits=5, embargo=6))
    assert len(splits) == 5
    for train, test in splits:
        assert train.max() < test.min()
        assert ds.t1[train].max() < ds.row_idx[test[0]]  # no label window reaches into the test period
    assert all(splits[i][1].max() < splits[i + 1][1].min() for i in range(4))  # chronological test blocks


def test_wilson_and_calibration_utilities():
    lo, hi = wilson_interval(5, 10)
    assert abs(lo - 0.2366) < 1e-3 and abs(hi - 0.7634) < 1e-3
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 5000)
    event = (rng.uniform(0, 1, 5000) < p).astype(int)
    assert calibration_curve(p, event)["ece"] < 0.05  # perfectly calibrated by construction
    assert trade_metrics(np.array([1.0, -1.0, 2.0, -1.0]))["profit_factor"] == pytest.approx(1.5)


def test_calibrator_fixes_overconfidence_and_normalises():
    rng = np.random.default_rng(1)
    n = 3000
    true_p = rng.dirichlet([2, 2, 2], n)
    y = np.array([rng.choice(3, p=p) for p in true_p])
    overconf = true_p ** 2
    overconf /= overconf.sum(axis=1, keepdims=True)
    cal = ProbabilityCalibrator().fit(overconf[:2000], y[:2000])
    out = cal.transform(overconf[2000:])
    assert np.allclose(out.sum(axis=1), 1)
    from app.ml_engine.evaluation import multiclass_brier
    assert multiclass_brier(out, y[2000:]) <= multiclass_brier(overconf[2000:], y[2000:]) + 1e-6


def test_analogues_ignore_the_future_and_report_base_rates():
    b = walk(1800, seed=11)
    names, X = compute_features(b)
    lab = triple_barrier(b, __import__("app.feature_engineering.indicators", fromlist=["atr"]).atr(b.h, b.l, b.c),
                         LabelConfig(horizon=12))
    q = 1500
    r_full = find_analogues(b, X, lab, q, AnalogueConfig(k=40, min_separation=6))
    b_cut = b.upto(q + 1)
    _, Xc = compute_features(b_cut)
    from app.feature_engineering.indicators import atr
    lab_c = triple_barrier(b_cut, atr(b_cut.h, b_cut.l, b_cut.c), LabelConfig(horizon=12))
    r_cut = find_analogues(b_cut, Xc, lab_c, q, AnalogueConfig(k=40, min_separation=6))
    assert [n["idx"] for n in r_full.neighbors] == [n["idx"] for n in r_cut.neighbors]
    assert all(n["idx"] + 12 <= q for n in r_full.neighbors)  # outcomes were fully known at query time
    assert r_full.n_obs == 40 and r_full.sufficient
    s = r_full.stats
    assert s["long_tp_before_sl"]["n"] == 40 and s["base_rate_long"]["n"] > 1000
    assert 0 < r_full.neighbors[0]["similarity"] <= 1 and "not a probability" in r_full.to_dict()["note"]


def test_analogues_flag_insufficient_history():
    b = walk(150)
    _, X = compute_features(b)
    from app.feature_engineering.indicators import atr
    lab = triple_barrier(b, atr(b.h, b.l, b.c), LabelConfig(horizon=12))
    r = find_analogues(b, X, lab)
    assert not r.sufficient and r.reason


def test_knn_min_separation_and_exact_match():
    lib = np.array([[0.0, 0], [0.01, 0], [5, 5], [0.02, 0.0], [9, 9]])
    picks = knn(np.array([0.0, 0.0]), lib, np.arange(5), k=3, min_separation=2)
    idx = [p[0] for p in picks]
    assert idx[0] == 0 and 1 not in idx  # neighbour at distance-1 bar suppressed
    assert picks[0][2] == pytest.approx(1.0)


@pytest.mark.parametrize("algo", ALGORITHMS)
def test_training_on_noise_is_never_labelled_validated(algo):
    b = walk(2600, seed=5)
    res = train_and_evaluate(b, algo, LabelConfig(horizon=12), n_splits=3, spread=0.2)
    assert res.report["n_oos_rows"] > 500
    assert res.status == "research_only" and res.reasons
    assert 0 <= res.report["prediction_coverage"] <= 1 and "calibration" in res.report
    P = res.calibrator.transform(res.model.predict_proba(res.dataset.X[:5]))
    assert np.allclose(P.sum(axis=1), 1)


def test_insufficient_training_data_is_research_only():
    res = train_and_evaluate(walk(200), "logistic", LabelConfig(horizon=12))
    assert res.status == "research_only" and "insufficient" in res.reasons[0]
