"""Experiment 7 timing track: vectorised windows, coverage-matched controls, null and planted checks (spec 4.3, 5)."""
import numpy as np
import pytest

from app.gann.anchors import Anchor
from app.gann.params import GannParams
from app.gann.state import panel
from app.gold_research.exp7 import stats as S
from app.gold_research.exp7 import timing as T
from app.market_data.bars import Bars

DAY = 86400


def gbm(n=3000, seed=2, step=DAY, start=1_104_537_600):
    rng = np.random.default_rng(seed)
    c = 1000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, 0.004, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 0.004, n))  # noqa: E741
    return Bars(t=start + step * np.arange(n, dtype=np.int64), o=o, h=h, l=l, c=c, v=np.ones(n), step=step)


@pytest.fixture(scope="module")
def daily():
    return gbm()


def test_vector_masks_match_gann_panel(daily):
    p = GannParams()
    pn = panel(daily, p, daily=True)
    sets = T.window_sets(daily, p, daily=True)
    for col, ws in sets.items():
        assert np.array_equal(S.vmask(ws, ws.L, ws.W, len(daily.c), ws.bday), pn[col].to_numpy()), col
    assert np.array_equal(T.seasonal_real(daily, p), pn["t_seasonal"].to_numpy())


def test_control_coverage_matched(daily):
    p = GannParams()
    ws = T.window_sets(daily, p, daily=True)["t_cycle_bars"]
    real = S.vmask(ws, ws.L, ws.W, len(daily.c), ws.bday).mean()
    rng = np.random.default_rng(0)
    covs = [m.mean() for m in S.control_masks(ws, p, draws=30, rng=rng, target_cov=real)]
    assert len(covs) == 30 and np.mean(np.abs(np.array(covs) - real)) <= 0.01


def test_null_random_walk_lifts_near_one():
    b = gbm(n=6000, seed=9)
    rows = T.run_series(b, symbol="SYN", tf="D1", daily=True, draws=300, seed=1, eval_mask=np.ones(6000, bool))
    tested = [r for r in rows if r["status"] == "tested"]
    assert len(tested) >= 20
    lifts = np.array([r["lift"] for r in tested])
    assert 0.9 <= np.median(lifts) <= 1.1
    assert np.mean([r["p"] < 0.05 for r in tested]) <= 0.10


def test_planted_reversals_detected():
    n = 4000
    anchors = [Anchor(i, i + 3, 1.0, "low" if k % 2 else "high", "major") for k, i in enumerate(range(50, 3800, 120))]
    ws = S.WindowSet.from_bar_counts(anchors, n, counts=[90], fracs=None, tol_frac=0.025)
    inside = S.vmask(ws, ws.L, ws.W, n, ws.bday)
    rng = np.random.default_rng(4)
    y = np.where(inside, rng.random(n) < 0.6, rng.random(n) < 0.05).astype(float)
    res = S.time_test(y, inside, ws, GannParams(), np.ones(n, bool), draws=500, rng=rng, two_sided=False)
    assert res["lift"] > 1.5 and res["p"] < 0.01


def test_reaction_same_candle_counts_reaction():
    # support at 100 (approached from above), ATR 2: candle 2 reaches 102 AND closes below 98 -> the reaction wins
    h = np.array([104.0, 101.0, 102.5, 99.0])
    l = np.array([101.0, 99.9, 97.0, 96.0])  # noqa: E741
    c = np.array([103.0, 100.5, 97.5, 97.0])
    got = T.reactions(h, l, c, np.full(4, 2.0), touch_i=np.array([1]), level=np.array([100.0]), side=np.array([1]), horizon=5)
    assert got.tolist() == [1.0]
    # the touch candle itself closing beyond the level by 1 ATR is a failure
    c2 = c.copy()
    c2[1] = 97.9
    assert T.reactions(h, l, c2, np.full(4, 2.0), np.array([1]), np.array([100.0]), np.array([1]), 5).tolist() == [0.0]


def test_coverage_rule_marks_not_testable():
    inside = np.zeros(1000, bool)
    inside[:950] = True
    assert T.status_for(inside, np.ones(1000), np.ones(1000, bool), GannParams()) == "not testable: covers nearly every candle"


def test_planted_level_reaction_detected():
    rng = np.random.default_rng(3)
    n = 3000
    phase = np.arange(n) % 40
    c = np.where(phase < 20, 100 + phase * 0.5, 110 - (phase - 20) * 0.5) + rng.normal(0, 0.05, n)
    h, l = c + 0.3, c - 0.3  # noqa: E741
    atr = np.full(n, 1.0)
    lines = S.LineSet.static(x0=np.array([0]), x1=np.array([n]), levels=[np.array([100.0, 110.0])])
    res = S.level_test(h, l, c, atr, lines, np.ones(n, bool), GannParams(), draws=200, rng=rng, horizon=20)
    assert res["lift"] > 1.5 and res["p"] < 0.01
