"""Trading sessions in their own time zones (DESIGN section 11), so daylight-saving changes come from the tz database:
Asia 00:00-07:00 London, London 08:00-16:30 London, New York 08:00-17:00 New York, overlap = both open; no new entries during the
rollover (16:55-17:10 New York) or in the first 60 minutes after the Sunday open. Crypto trades around the clock (no rollover).
News: no free, reliable economic calendar exists, so the news filter is reported unavailable and never claimed."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

LON, NY = ZoneInfo("Europe/London"), ZoneInfo("America/New_York")
NEWS = {"available": False, "status": "unavailable",
        "note": "No free, reliable economic-calendar source is connected: high-impact news is NOT filtered."}


def _between(t: time, a: time, b: time) -> bool:
    return a <= t < b


def session_info(now: datetime, calendar: str = "fx") -> dict:
    now = now.astimezone(timezone.utc)
    lt, nt = now.astimezone(LON), now.astimezone(NY)
    if calendar == "continuous":
        return {"sessions": ["24/7"], "label": "24/7 market", "entry_allowed": True, "block_reason": None, "london_time": lt.strftime("%H:%M"),
                "new_york_time": nt.strftime("%H:%M")}
    weekday_ny = nt.weekday()  # Monday 0 .. Sunday 6
    closed = weekday_ny == 5 or (weekday_ny == 4 and nt.time() >= time(17, 0)) or (weekday_ny == 6 and nt.time() < time(17, 0))
    names = []
    if not closed:
        if _between(lt.time(), time(0, 0), time(7, 0)):
            names.append("Asia")
        if lt.weekday() < 5 and _between(lt.time(), time(8, 0), time(16, 30)):
            names.append("London")
        if nt.weekday() < 5 and _between(nt.time(), time(8, 0), time(17, 0)):
            names.append("New York")
    overlap = "London" in names and "New York" in names
    block = None
    if closed:
        block = "market closed (weekend)"
    elif _between(nt.time(), time(16, 55), time(17, 10)):
        block = "daily rollover (16:55-17:10 New York): no new entries"
    elif weekday_ny == 6 and nt - nt.replace(hour=17, minute=0, second=0, microsecond=0) < timedelta(minutes=60):
        block = "first hour after the weekly open: no new entries"
    label = "closed" if closed else ("London/New York overlap" if overlap else (" / ".join(names) if names else "off-session"))
    return {"sessions": names, "overlap": overlap, "label": label, "entry_allowed": block is None, "block_reason": block,
            "london_time": lt.strftime("%H:%M"), "new_york_time": nt.strftime("%H:%M")}
