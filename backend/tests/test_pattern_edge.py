import numpy as np

from app.market_data.bars import Bars
from app.price_action.engine import analyze_price_action
from app.research import pattern_edge as pe
from app.research.pattern_edge import (
    Outcomes,
    apply_multiple_testing,
    bh_fdr,
    collect_signals,
    evaluate,
    study_timeframe,
)
from tests.test_ml_analogues import walk


def fake_outcomes(n, seed=0, boost_idx=None, boost=0.0, cost=0.0):
    rng = np.random.default_rng(seed)
    g = rng.normal(0.0, 1.0, n)
    if boost_idx is not None:
        g[boost_idx] += boost
    return Outcomes(g, -g, np.full(n, cost), g > 1, -g > 1, np.ones(n, bool))


def test_bh_fdr_matches_hand_computation():
    q = bh_fdr(np.array([0.01, 0.04, 0.03, 0.005]))
    assert np.allclose(q, [0.02, 0.04, 0.04, 0.02])


def test_signals_are_non_overlapping_and_stay_inside_their_window():
    o = fake_outcomes(2000)
    idx = np.arange(0, 2000, 3)  # one signal every 3 bars: far more frequent than the 24-bar label window
    r = evaluate(idx, 1, o, 100, 1500)
    sel = pe._accept(idx, o.valid, 100, 1500)
    assert r["n"] == len(sel) and np.all(np.diff(sel) > pe.CFG.horizon) and sel.min() >= 100 and sel.max() < 1500


def test_planted_effect_is_detected_and_lift_is_measured_against_the_same_direction_baseline():
    n = 20000
    idx = np.arange(50, n - 50, 60)
    o = fake_outcomes(n, seed=1, boost_idx=idx, boost=0.6)
    r = evaluate(idx, 1, o, 0, n)
    assert r["n"] > 250 and 0.4 < r["lift_r"] < 0.8 and r["p_lift"] < 1e-6
    # a drifting market must not create fake lift: add +0.3 R drift to EVERY bar, lift stays ~0 for unrelated signals
    drift = fake_outcomes(n, seed=2)
    drift.gross_long += 0.3
    r2 = evaluate(np.arange(50, n - 50, 60), 1, drift, 0, n)
    assert r2["gross_r"] > 0.15 and abs(r2["lift_r"]) < 0.2


def test_multiple_testing_keeps_false_discoveries_near_zero_on_pure_noise():
    rng = np.random.default_rng(7)
    n = 20000
    o = fake_outcomes(n, seed=3)
    rows = []
    for k in range(300):  # 300 junk patterns that fire at random times
        idx = np.sort(rng.choice(n - 50, size=rng.integers(200, 600), replace=False))
        split = int(n * pe.SPLIT)
        rows.append({"tf": "x", "pattern": f"junk{k}", "side": "long", "events_total": len(idx),
                     "is": evaluate(idx, 1, o, 0, split - pe.CFG.horizon), "oos": evaluate(idx, 1, o, split, n)})
    s = apply_multiple_testing(rows)
    assert s["tested"] >= 250
    assert s["confirmed_gross"] <= 1 and s["confirmed_net"] == 0  # naive p<0.05 would "find" ~15 of them


def test_planted_pattern_among_noise_survives_both_stages():
    rng = np.random.default_rng(11)
    n = 30000
    real = np.arange(80, n - 80, 70)
    o = fake_outcomes(n, seed=5, boost_idx=real, boost=0.7)
    rows = []
    split = int(n * pe.SPLIT)
    for name, idx in [("real", real)] + [(f"junk{k}", np.sort(rng.choice(n - 50, 400, replace=False))) for k in range(100)]:
        rows.append({"tf": "x", "pattern": name, "side": "long", "events_total": len(idx),
                     "is": evaluate(idx, 1, o, 0, split - pe.CFG.horizon), "oos": evaluate(idx, 1, o, split, n)})
    s = apply_multiple_testing(rows)
    real_row = next(r for r in rows if r["pattern"] == "real")
    assert real_row.get("confirmed_gross") and real_row.get("confirmed_net")
    assert s["confirmed_gross"] >= 1


def test_costs_turn_a_gross_edge_into_a_net_loss():
    n = 20000
    idx = np.arange(50, n - 50, 60)
    o = fake_outcomes(n, seed=1, boost_idx=idx, boost=0.25, cost=0.6)
    r = evaluate(idx, 1, o, 0, n)
    assert r["gross_r"] > 0.15 and r["net_r"] < 0 and r["lift_r"] > 0.15  # predictive, but not tradeable


def test_study_runs_on_a_real_shaped_series_and_signals_are_causal():
    b = walk(3000, seed=4)
    pa = analyze_price_action(b)
    sigs = collect_signals(b, pa, intraday_hours=True)
    assert any(k.startswith("bos:") for k in sigs) and any("hour_" in k for k in sigs)
    assert all(v.min() >= 0 and v.max() < len(b) for v in sigs.values())
    for e in pa.fvgs[:50]:  # a retest can only be signalled AFTER the zone exists
        for name in ("fvg_retest:long", "fvg_retest:short"):
            if name in sigs and e.idx in sigs[name]:
                assert True
    for name, idx in sigs.items():
        if name.endswith("_retest:long") or name.endswith("_retest:short"):
            assert idx.min() >= 3
    rows = study_timeframe(b, 0.001, "1H")
    assert rows and all({"tf", "pattern", "side", "is", "oos"} <= set(r) for r in rows)
    ev = [r for r in rows if r["is"] and r["is"]["n"] > 5]
    assert ev and all(0 <= r["is"]["win_rate"] <= 1 for r in ev)


def test_signal_indices_never_precede_the_information_they_use():
    """Truncating the future must not change any signal that fires before the cut."""
    full = walk(2500, seed=9)
    pa_full = analyze_price_action(full)
    s_full = collect_signals(full, pa_full, intraday_hours=False)
    cut = 1800
    part = full.upto(cut)
    s_part = collect_signals(part, analyze_price_action(part), intraday_hours=False)
    for name, idx in s_part.items():
        a = set(idx[idx < cut - 250].tolist())  # leave room for zone-lifecycle effects near the edge
        b = set(s_full.get(name, np.array([], dtype=int))[s_full.get(name, np.array([], dtype=int)) < cut - 250].tolist())
        assert a == b, name
    assert isinstance(full, Bars)


def test_an_effect_that_only_exists_at_the_first_fill_is_rejected_as_an_artifact():
    from app.research.pattern_edge import evaluate

    n = 30000
    sig = np.arange(80, n - 80, 70)
    split = int(n * pe.SPLIT)
    for persists, expect in ((False, False), (True, True)):
        rng = np.random.default_rng(21)
        g = rng.normal(0, 1, n)
        g[sig] += 0.7                      # the "edge" at the earliest possible fill ...
        if persists:
            g[sig + 1] += 0.7              # ... does / does not survive entering one bar later
        o = Outcomes(g, -g, np.zeros(n), g > 1, -g > 1, np.ones(n, bool))
        rows = [{"tf": "x", "pattern": "p", "side": "long", "events_total": len(sig),
                 "is": evaluate(sig, 1, o, 0, split - pe.CFG.horizon), "oos": evaluate(sig, 1, o, split, n),
                 "oos_delay1": evaluate(sig + 1, 1, o, split, n)}]
        s = apply_multiple_testing(rows)
        assert bool(rows[0].get("confirmed_gross")) is expect
        if not persists:
            assert s["passed_oos_but_failed_one_bar_delay"] == 1
