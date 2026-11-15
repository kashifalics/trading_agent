"""Gann time cycles: windows, sessions, calendar arithmetic (docs/gann/GANN_METHODOLOGY.md sections 4.1, 4.9, 4.10)."""
from datetime import datetime, timezone

import numpy as np

from app.gann.anchors import Anchor
from app.gann.time_cycles import (
    COUNTS,
    add_months,
    anniversary_mask,
    bar_cycle_mask,
    calendar_cycle_mask,
    calendar_window,
    coverage,
    seasonal_mask,
    session_day,
    sq9_time_counts,
    tol,
)

DAY = 86400


def ts(*a) -> int:
    return int(datetime(*a, tzinfo=timezone.utc).timestamp())


def days(start: int, n: int) -> np.ndarray:
    return start + DAY * np.arange(n, dtype=np.int64)


def test_counts_and_tol_values():
    assert len(COUNTS) == 21 and COUNTS[-1] == 365.25
    assert (tol(7), tol(90), tol(360)) == (1, 2, 9)


def test_window_must_start_after_confirmation():
    a = Anchor(100, 103, 1.0, "low", "major")
    m = bar_cycle_mask(200, [(a, 103, 200)], [7])
    assert np.flatnonzero(m).tolist() == [106, 107, 108]
    late = Anchor(100, 108, 1.0, "low", "major")
    assert not bar_cycle_mask(200, [(late, 108, 200)], [7]).any()


def test_mask_respects_active_span():
    a = Anchor(100, 103, 1.0, "low", "major")
    assert np.flatnonzero(bar_cycle_mask(200, [(a, 103, 107)], [7])).tolist() == [106]


def test_fraction_windows():
    a = Anchor(0, 3, 1.0, "high", "major")
    m = bar_cycle_mask(200, [(a, 3, 200)], [90], fracs=[0.5])
    assert np.flatnonzero(m).tolist() == [44, 45, 46]  # 45 +- tol(45)=1


def test_session_day_dst():
    # before the March change New York is UTC-5: the session rolls at 22:00 UTC
    assert session_day(np.array([ts(2019, 3, 8, 21, 30)]))[0] != session_day(np.array([ts(2019, 3, 8, 22, 30)]))[0]
    # after it New York is UTC-4: the session rolls at 21:00 UTC
    assert session_day(np.array([ts(2019, 3, 11, 20, 30)]))[0] != session_day(np.array([ts(2019, 3, 11, 21, 30)]))[0]
    assert session_day(np.array([ts(2019, 3, 11, 21, 30)]))[0] == session_day(np.array([ts(2019, 3, 11, 23, 0)]))[0]
    # back to UTC-5 after 2019-11-03
    assert session_day(np.array([ts(2019, 11, 4, 21, 30)]))[0] == session_day(np.array([ts(2019, 11, 4, 20, 0)]))[0]


def test_add_months_clamps():
    assert add_months(ts(2019, 1, 31, 12), 1) == ts(2019, 2, 28, 12)
    assert add_months(ts(2020, 1, 31), 1) == ts(2020, 2, 29)
    assert add_months(ts(2019, 11, 15), 3) == ts(2020, 2, 15)


def test_calendar_window_units():
    t0 = ts(2019, 1, 31)
    assert calendar_window(t0, 7, "day") == (ts(2019, 2, 6), ts(2019, 2, 8))
    assert calendar_window(t0, 2, "week") == (ts(2019, 2, 7), ts(2019, 2, 21))
    assert calendar_window(t0, 1, "month") == (ts(2019, 1, 31), ts(2019, 3, 31))
    assert calendar_window(t0, 1, "year") == (ts(2019, 1, 31), ts(2021, 1, 31))


def test_calendar_cycle_mask_days():
    bt = days(ts(2019, 1, 1), 60)
    a = Anchor(0, 2, 1.0, "low", "major")
    m = calendar_cycle_mask(bt, [(a, 2, 60)], [30])
    assert np.flatnonzero(m).tolist() == [29, 30, 31]  # Jan 31 +- 1 day


def test_seasonal_mask_dates():
    bt = days(ts(2019, 3, 15), 12)
    inside = {datetime.fromtimestamp(int(t), timezone.utc).day for t in bt[seasonal_mask(bt)]}
    assert inside == {19, 20, 21, 22, 23}


def test_anniversary_window():
    bt = days(ts(2005, 6, 1), 3 * 366)
    a = Anchor(14, 20, 1.0, "high", "major")  # 2005-06-15
    m = anniversary_mask(bt, [a], tol_days=2, years=(1,))
    got = [datetime.fromtimestamp(int(t), timezone.utc).strftime("%Y-%m-%d") for t in bt[m]]
    assert got == ["2006-06-13", "2006-06-14", "2006-06-15", "2006-06-16", "2006-06-17"]


def test_sq9_time_counts_are_cardinal_cross():
    assert sq9_time_counts(50)[:8] == [2, 4, 6, 8, 11, 15, 19, 23]


def test_coverage():
    assert coverage(np.array([True, False, False, True])) == 0.5
