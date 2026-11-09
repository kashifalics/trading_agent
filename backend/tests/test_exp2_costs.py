"""Experiment-2 cost and calendar rules (no market data)."""
from datetime import date, datetime, timezone

import numpy as np
import polars as pl

from app.gold_research.exp2 import data as D
from app.gold_research.exp2 import financing as F
from app.historical.holidays import holiday_windows, in_holiday_window, us_holidays


def ts(*a):
    return int(datetime(*a, tzinfo=timezone.utc).timestamp())


def test_us_holiday_rules_and_windows():
    h = us_holidays
    assert date(2019, 11, 28) in h(2019) and date(2019, 4, 19) in h(2019) and date(2020, 1, 20) in h(2020)
    assert date(2022, 6, 20) in h(2022) and date(2021, 6, 18) not in h(2021) and date(2020, 7, 3) in h(2020)
    w = holiday_windows(2019, 2019)
    # Thanksgiving 2019-11-28: Wed 17:00 NY (22:00 UTC) to Thu 18:00 NY (23:00 UTC)
    inside = in_holiday_window(np.array([ts(2019, 11, 27, 22, 30), ts(2019, 11, 28, 18, 0), ts(2019, 11, 28, 23, 30)]), w)
    assert list(inside) == [True, True, False]


def test_gap_rule_counts_only_gaps_while_the_trade_is_open():
    gs = np.array([100, 500, 900])
    hit = D.gap_between(gs, np.array([0, 101, 501, 950]), np.array([99, 499, 950, 2000]))
    assert list(hit) == [False, False, True, False]


def test_nights_and_fixed_financing():
    roll = F.rollovers(2021, 2021)
    # Monday 2021-03-08 15:00 UTC (10:00 NY) to Wednesday 15:00 UTC: Monday and Tuesday 17:00 NY rollovers -> 2 nights
    n = F.nights(np.array([ts(2021, 3, 8, 15)]), np.array([ts(2021, 3, 10, 15)]), roll)
    assert n[0] == 2
    # Friday 15:00 UTC to Monday 15:00 UTC: one Friday rollover = 3 nights
    n = F.nights(np.array([ts(2021, 3, 12, 15)]), np.array([ts(2021, 3, 15, 15)]), roll)
    assert n[0] == 3
    c = F.cost_usd_per_oz("fixed_0.10", np.array([1]), np.array([ts(2021, 3, 12, 15)]), np.array([ts(2021, 3, 15, 15)]),
                          np.array([1700.0]), roll)
    assert abs(c[0] - 0.30) < 1e-12
    assert F.cost_usd_per_oz("fred_proxy", np.array([1]), np.array([0]), np.array([1]), np.array([1.0]), roll, None) is None


def test_fred_proxy_signs(tmp_path):
    p = tmp_path / "dff.csv"
    p.write_text("observation_date,DFF\n2021-03-01,0.07\n2023-03-01,4.57\n")
    fred = F.load_fred(p)
    roll = F.rollovers(2021, 2023)
    e = np.array([ts(2021, 3, 8, 15), ts(2023, 3, 6, 15)] * 2)
    x = e + 2 * 86400
    d = np.array([1, 1, -1, -1])
    c = F.cost_usd_per_oz("fred_proxy", d, e, x, np.full(4, 1825.0), roll, fred)
    assert c[0] > 0 and c[1] > c[0] and c[2] > 0 and c[3] < 0  # shorts receive financing when DFF > 2.5%
    assert isinstance(fred, pl.DataFrame)
