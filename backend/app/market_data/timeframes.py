"""Timeframe registry and bucket (candle boundary) arithmetic.

Conventions (see docs/MARKET_DATA_PROVIDERS.md):
  * All timestamps are UTC and denote the candle OPEN time.
  * Intraday buckets (< 1D) are aligned to the UTC epoch (4H -> 00,04,08,... UTC).
  * 1D+ buckets are aligned to the instrument's SessionAnchor (time zone + daily open),
    so DST shifts are handled by zoneinfo, not by fixed UTC offsets.
  * 1W starts on the Monday trading day; 1M/3M/6M/12M are calendar month / quarter / half / year.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


@dataclass(frozen=True)
class Timeframe:
    code: str
    seconds: int | None  # fixed length, None for calendar-month based
    months: int | None
    label: str
    binance: str | None = None
    twelve_data: str | None = None

    @property
    def is_intraday(self) -> bool:
        return self.seconds is not None and self.seconds < 86400

    @property
    def kind(self) -> str:
        if self.months:
            return "month"
        if self.code == "1W":
            return "week"
        if self.code == "1D":
            return "day"
        return "intraday"


_TF_LIST = [
    Timeframe("1m", 60, None, "1 minute", "1m", "1min"),
    Timeframe("3m", 180, None, "3 minutes", "3m", None),
    Timeframe("5m", 300, None, "5 minutes", "5m", "5min"),
    Timeframe("15m", 900, None, "15 minutes", "15m", "15min"),
    Timeframe("30m", 1800, None, "30 minutes", "30m", "30min"),
    Timeframe("1H", 3600, None, "1 hour", "1h", "1h"),
    Timeframe("2H", 7200, None, "2 hours", "2h", "2h"),
    Timeframe("4H", 14400, None, "4 hours", "4h", "4h"),
    Timeframe("1D", 86400, None, "1 day", "1d", "1day"),
    Timeframe("1W", 604800, None, "1 week", "1w", "1week"),
    Timeframe("1M", None, 1, "1 month", "1M", "1month"),
    Timeframe("3M", None, 3, "3 months (quarter)"),
    Timeframe("6M", None, 6, "6 months (half-year)"),
    Timeframe("12M", None, 12, "12 months (year)"),
]
TIMEFRAMES: dict[str, Timeframe] = {t.code: t for t in _TF_LIST}
TIMEFRAME_ORDER = [t.code for t in _TF_LIST]


def get_timeframe(code: str) -> Timeframe:
    try:
        return TIMEFRAMES[code]
    except KeyError:
        raise ValueError(f"Unsupported timeframe '{code}'. Supported: {', '.join(TIMEFRAME_ORDER)}") from None


def approx_seconds(tf: Timeframe) -> int:
    return tf.seconds if tf.seconds else tf.months * 30 * 86400  # type: ignore[operator]


@dataclass(frozen=True)
class SessionAnchor:
    tz: str = "UTC"
    open: time = time(0, 0)

    @classmethod
    def from_strings(cls, tz: str, hhmm: str) -> "SessionAnchor":
        h, m = hhmm.split(":")
        return cls(tz, time(int(h), int(m)))


UTC_ANCHOR = SessionAnchor()
NY_17_ANCHOR = SessionAnchor("America/New_York", time(17, 0))


def _combine(d: date, t: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, t, tzinfo=tz).astimezone(UTC)


def _label_date(ts: datetime, anchor: SessionAnchor) -> date:
    """Trading-day label for an instant. A session opening at 17:00 the previous evening
    belongs to the NEXT calendar date (FX convention)."""
    tz = ZoneInfo(anchor.tz)
    local = ts.astimezone(tz)
    d, t = local.date(), local.time()
    if anchor.open == time(0, 0):
        return d
    if anchor.open >= time(12, 0):
        return d + timedelta(days=1) if t >= anchor.open else d
    return d if t >= anchor.open else d - timedelta(days=1)


def _start_for_label(label: date, anchor: SessionAnchor) -> datetime:
    tz = ZoneInfo(anchor.tz)
    if anchor.open == time(0, 0) or anchor.open < time(12, 0):
        return _combine(label, anchor.open, tz)
    return _combine(label - timedelta(days=1), anchor.open, tz)


def _add_months(d: date, n: int) -> date:
    idx = d.year * 12 + (d.month - 1) + n
    return date(idx // 12, idx % 12 + 1, 1)


def _period_first(label: date, months: int) -> date:
    idx = label.year * 12 + (label.month - 1)
    idx = idx // months * months
    return date(idx // 12, idx % 12 + 1, 1)


def bucket_start(ts: datetime, tf: Timeframe, anchor: SessionAnchor = UTC_ANCHOR) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("naive datetime")
    ts = ts.astimezone(UTC)
    kind = tf.kind
    if kind == "intraday":
        sec = tf.seconds
        return datetime.fromtimestamp(int(ts.timestamp()) // sec * sec, tz=UTC)  # type: ignore[operator]
    label = _label_date(ts, anchor)
    if kind == "day":
        return _start_for_label(label, anchor)
    if kind == "week":
        return _start_for_label(label - timedelta(days=label.weekday()), anchor)
    return _start_for_label(_period_first(label, tf.months), anchor)  # type: ignore[arg-type]


def bucket_end(start: datetime, tf: Timeframe, anchor: SessionAnchor = UTC_ANCHOR) -> datetime:
    """Exclusive end = open time of the next bucket."""
    kind = tf.kind
    if kind == "intraday":
        return start + timedelta(seconds=tf.seconds)  # type: ignore[arg-type]
    label = _label_date(start + timedelta(seconds=1), anchor)
    if kind == "day":
        return _start_for_label(label + timedelta(days=1), anchor)
    if kind == "week":
        monday = label - timedelta(days=label.weekday())
        return _start_for_label(monday + timedelta(days=7), anchor)
    first = _period_first(label, tf.months)  # type: ignore[arg-type]
    return _start_for_label(_add_months(first, tf.months), anchor)  # type: ignore[arg-type]


def plan_timeframe(target: str, native: set[str]) -> tuple[str, str] | None:
    """('native', tf) if the provider serves it, else ('aggregate', base_tf) using the
    largest native timeframe that divides the target exactly; None if impossible."""
    if target in native:
        return "native", target
    tf = get_timeframe(target)
    candidates = []
    for code in native:
        base = TIMEFRAMES[code]
        if tf.seconds and base.seconds and base.seconds < tf.seconds and tf.seconds % base.seconds == 0:
            if tf.kind in ("day", "week") and base.kind not in ("intraday", "day"):
                continue
            candidates.append(base)
        elif tf.months and base.months and base.months < tf.months and tf.months % base.months == 0:
            candidates.append(base)
    if not candidates:
        return None
    best = max(candidates, key=lambda b: approx_seconds(b))
    return "aggregate", best.code
