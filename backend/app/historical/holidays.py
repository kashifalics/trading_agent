"""US market holidays that close or shorten gold trading (rule-based, no external data).

Spot gold liquidity follows the US metals schedule: on these days trading stops early or the whole session is closed. Experiment 1
treated the resulting quiet hours as missing data. Here a gap counts as a scheduled holiday closure when it starts inside the
holiday's trading window: from 17:00 New York the evening before the holiday until 18:00 New York on the holiday itself (the usual
reopen). Rules (observed dates: Saturday -> Friday, Sunday -> Monday):
  New Year's Day (Jan 1), Martin Luther King Jr. Day (3rd Monday of January, from 1998), Presidents' Day (3rd Monday of February),
  Good Friday (Easter Sunday - 2 days), Memorial Day (last Monday of May), Juneteenth (Jun 19, from 2022), Independence Day (Jul 4),
  Labor Day (1st Monday of September), Thanksgiving (4th Thursday of November), Christmas (Dec 25).
Christmas Eve to Boxing Day and Dec 31 to Jan 2 were already treated as holidays in the build.
"""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def _observed(d: date) -> date:
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def easter(year: int) -> date:
    """Anonymous Gregorian algorithm."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month = (h + m - 7 * n + 114) // 31
    return date(year, month, (h + m - 7 * n + 114) % 31 + 1)


@lru_cache(maxsize=None)
def us_holidays(year: int) -> dict[date, str]:
    out = {_observed(date(year, 1, 1)): "New Year's Day", _nth_weekday(year, 2, 0, 3): "Presidents' Day",
           easter(year) - timedelta(days=2): "Good Friday", _last_weekday(year, 5, 0): "Memorial Day",
           _observed(date(year, 7, 4)): "Independence Day", _nth_weekday(year, 9, 0, 1): "Labor Day",
           _nth_weekday(year, 11, 3, 4): "Thanksgiving", _observed(date(year, 12, 25)): "Christmas"}
    if year >= 1998:
        out[_nth_weekday(year, 1, 0, 3)] = "Martin Luther King Jr. Day"
    if year >= 2022:
        out[_observed(date(year, 6, 19))] = "Juneteenth"
    return out


def holiday_windows(start_year: int, end_year: int) -> list[tuple[int, int, str]]:
    """(start epoch, end epoch, name): 17:00 New York the evening before each holiday to 18:00 New York on the holiday."""
    w = []
    for y in range(start_year, end_year + 1):
        for d, name in us_holidays(y).items():
            s = datetime(d.year, d.month, d.day, 17, tzinfo=NY) - timedelta(days=1)
            e = datetime(d.year, d.month, d.day, 18, tzinfo=NY)
            w.append((int(s.astimezone(timezone.utc).timestamp()), int(e.astimezone(timezone.utc).timestamp()), name))
    return sorted(w)


def in_holiday_window(epoch_s, windows: list[tuple[int, int, str]]):
    """Boolean array: each timestamp falls inside one of the windows."""
    import numpy as np
    t = np.asarray(epoch_s, dtype=np.int64)
    starts = np.array([w[0] for w in windows], dtype=np.int64)
    ends = np.array([w[1] for w in windows], dtype=np.int64)
    j = np.searchsorted(starts, t, side="right") - 1
    ok = j >= 0
    return ok & (t < np.where(ok, ends[np.maximum(j, 0)], 0))
