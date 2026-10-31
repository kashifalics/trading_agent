"""Minimal market-session calendars used for gap detection and completeness checks.

Holidays and daily maintenance breaks are NOT modelled: a candle missing on such a day is
reported as a gap rather than silently accepted (conservative).
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


class MarketCalendar:
    name = "continuous"

    def is_open(self, ts: datetime) -> bool:
        return True


class FxWeeklyCalendar(MarketCalendar):
    """Open Sun 17:00 -> Fri 17:00 New York time (DST-aware)."""

    name = "fx_weekly"

    def is_open(self, ts: datetime) -> bool:
        local = ts.astimezone(NY)
        wd, t = local.weekday(), local.time()
        if wd == 4 and t >= time(17, 0):
            return False
        if wd == 5:
            return False
        if wd == 6 and t < time(17, 0):
            return False
        return True


_CALENDARS = {"continuous": MarketCalendar(), "fx_weekly": FxWeeklyCalendar()}


def get_calendar(name: str) -> MarketCalendar:
    return _CALENDARS.get(name, _CALENDARS["continuous"])
