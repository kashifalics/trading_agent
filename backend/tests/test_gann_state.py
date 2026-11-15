"""Gann parameters, confluence families, causal panel and state (spec sections 3.1, 4.2; methodology 4.12)."""
from datetime import datetime, timezone

import numpy as np
import pytest

from app.gann.anchors import Anchor, cut
from app.gann.confluence import FAMILIES, families_at
from app.gann.params import GannParams
from app.gann.state import TIME_COLS, gann_state, levels_at, panel
from app.gann.time_cycles import bar_cycle_mask, calendar_cycle_mask
from app.market_data.bars import Bars

DAY = 86400


def walk(n=1500, seed=5, step=3600, start=1_104_537_600):  # 2005-01-01
    rng = np.random.default_rng(seed)
    c = 1000 + np.cumsum(rng.normal(0, 3, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 2, n)
    l = np.minimum(o, c) - rng.uniform(0, 2, n)  # noqa: E741
    return Bars(t=start + step * np.arange(n, dtype=np.int64), o=o, h=h, l=l, c=c, v=np.ones(n), step=step)


@pytest.fixture(scope="module")
def series():
    return walk()


def test_params_sha_stable():
    p = GannParams()
    assert p.sha() == GannParams().sha() and len(p.sha()) == 64
    assert GannParams(major_k=4.0).sha() != p.sha()
    assert p.to_dict()["counts"][-1] == 365.25


def test_state_prefix_equality(series):
    p = GannParams()
    for i in np.linspace(300, len(series.c) - 1, 20).astype(int):
        assert gann_state(series, int(i), p, daily=False) == gann_state(cut(series, int(i) + 1), int(i), p, daily=False)


def test_panel_matches_state(series):
    p = GannParams()
    pn = panel(series, p, daily=False)
    assert pn.height == len(series.c)
    for i in np.linspace(300, len(series.c) - 1, 15).astype(int):
        st = gann_state(series, int(i), p, daily=False)
        row = pn.row(int(i), named=True)
        assert {c for c in TIME_COLS if row[c]} == {w["column"] for w in st.windows}
        assert row["families"] == st.confluence == len(st.families)


def test_panel_is_causal(series):
    p = GannParams()
    full = panel(series, p, daily=False)
    part = panel(cut(series, 900), p, daily=False)
    assert full.head(900).fill_nan(None).equals(part.fill_nan(None), null_equal=True)


def test_no_projection_from_later_anchor(series):
    st = gann_state(series, 1000, GannParams(), daily=False)
    assert st.anchors and all(a["tc"] <= 1000 for a in st.anchors)
    assert all(w["anchor_tc"] is None or w["anchor_tc"] <= 1000 for w in st.windows + st.upcoming)
    assert all(lv["anchor_tc"] is None or lv["anchor_tc"] <= 1000 for lv in st.levels)


def test_families_merge_identities():
    sq9 = [{"family": "square9", "method": "square9", "price": 2000.0 + k * 0.01} for k in range(20)]
    extra = [{"family": "square9", "method": "sq4", "price": 2000.05},
             {"family": "divisions", "method": "twelfth", "price": 1999.9},
             {"family": "divisions", "method": "division", "price": 2100.0}]
    assert families_at(sq9 + extra, [], 2000.0, 0.2) == {"square9", "divisions"}
    assert families_at([], [{"family": "angles", "method": "balance_swing"}], 2000.0, 0.2) == {"angles"}
    assert set(FAMILIES) == {"cycles", "seasonal", "divisions", "square9", "angles", "symmetry"}


def test_calendar_vs_bar_counts_differ_over_weekend():
    start = int(datetime(2019, 1, 7, tzinfo=timezone.utc).timestamp())  # a Monday
    ts = np.array([start + DAY * d for d in range(70) if (d % 7) < 5], dtype=np.int64)  # weekdays only
    a = Anchor(0, 1, 1.0, "low", "major")
    by_bars = np.flatnonzero(bar_cycle_mask(len(ts), [(a, 1, len(ts))], [7]))
    by_days = np.flatnonzero(calendar_cycle_mask(ts, [(a, 1, len(ts))], [7]))
    assert by_bars.tolist() != by_days.tolist()


def test_levels_at_carry_parameters(series):
    lv = levels_at(series, 1200, GannParams())
    assert lv and {"family", "method", "price", "anchor_tc"} <= set(lv[0])
    assert {x["family"] for x in lv} <= set(FAMILIES)
    assert all(round(x["price"], 2) == x["price"] for x in lv)  # tick 0.01
