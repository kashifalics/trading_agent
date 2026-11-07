"""Per-timeframe market read for the signal engine. Causal: uses only the bars it is given (all complete)."""
from datetime import datetime, timezone

import numpy as np

from app.core.events import Event
from app.feature_engineering.indicators import ema
from app.market_data.bars import Bars
from app.market_structure.swings import confirmed, structure_bias
from app.price_action.engine import PriceActionResult
from app.signals.config import PARAMS

DEAD = ("filled", "invalidated", "broken")
CLASS_DIR = {"strong_bullish": 1, "bullish": 1, "strong_bearish": -1, "bearish": -1, "ranging": 0, "transitioning": 0}
CLASS_LABEL = {"strong_bullish": "Strong bullish", "bullish": "Bullish", "strong_bearish": "Strong bearish", "bearish": "Bearish",
               "ranging": "Ranging", "transitioning": "Transitioning"}


def fmt(x: float | None) -> str:
    return "—" if x is None or not np.isfinite(x) else f"{x:,.6g}"


def iso(ts: int | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


def last_atr(pa: PriceActionResult) -> float | None:
    if not len(pa.atr):
        return None
    a = float(pa.atr[-1])
    return a if np.isfinite(a) and a > 0 else None


def ema_side(b: Bars) -> int:
    """+1 when EMA50 is rising AND the close is above it, -1 when falling AND the close is below it, else 0."""
    n, k = PARAMS["ema_period"], PARAMS["ema_slope_bars"]
    last = len(b) - 1
    if last < n + k:
        return 0
    e = ema(b.c, n)
    if not (np.isfinite(e[last]) and np.isfinite(e[last - k])):
        return 0
    slope = int(np.sign(e[last] - e[last - k]))
    side = int(np.sign(b.c[last] - e[last]))
    return slope if slope == side else 0


def classify_direction(s: int, h: int, e: int) -> str:
    """s = last break-of-structure direction, h = swing sequence (HH+HL / LH+LL), e = EMA50 side+slope. See docs/SIGNAL_ENGINE.md."""
    if s != 0 and h == s and e == s:
        return "strong_bullish" if s > 0 else "strong_bearish"
    if s != 0 and (h == s or (h == 0 and e != -s)):
        return "bullish" if s > 0 else "bearish"
    if s != 0:
        return "transitioning"
    if h != 0:
        return "bullish" if h > 0 else "bearish"
    return "ranging"


def structure_label(pa: PriceActionResult, last: int) -> str | None:
    c = confirmed(pa.swings, last)
    hi = next((s.label for s in reversed(c) if s.kind == "high" and s.label), None)
    lo = next((s.label for s in reversed(c) if s.kind == "low" and s.label), None)
    if not hi and not lo:
        return None
    return f"{hi or '?'}/{lo or '?'}"


def live_zones(pa: PriceActionResult, last: int) -> list[Event]:
    return [z for z in pa.order_blocks + pa.fvgs + pa.zones + pa.breakers
            if z.status not in DEAD and z.low is not None and z.high is not None and last - z.idx <= PARAMS["zone_max_age_bars"]]


def _event_text(e: Event, last: int) -> str:
    ago = last - e.idx
    when = "on the last candle" if ago == 0 else f"{ago} bar{'s' if ago != 1 else ''} ago"
    if e.kind == "liquidity_sweep":
        side = "sell-side" if e.direction == "bullish" else "buy-side"
        return f"{side} liquidity swept at {fmt(e.price)} {when} ({e.direction} reaction)"
    return f"{e.direction.capitalize()} {e.kind} at {fmt(e.price)} {when}"


def read_tf(tf: str, b: Bars, pa: PriceActionResult) -> dict:
    """Trade-agnostic description of what this timeframe is doing (direction class, structure, events, zones)."""
    n = len(b)
    last = n - 1
    px = float(b.c[last])
    a = last_atr(pa)
    s = int(pa.trend[last]) if len(pa.trend) else 0
    h = structure_bias(pa.swings, last)
    e = ema_side(b)
    cls = classify_direction(s, h, e)
    brk = pa.breaks[-1] if pa.breaks else None
    sweep = pa.sweeps[-1] if pa.sweeps else None
    pdz = pa.premium_discount
    zones = live_zones(pa, last)
    zones.sort(key=lambda z: min(abs(px - z.low), abs(px - z.high)) if not (z.low <= px <= z.high) else 0.0)
    inside = next((z for z in zones if z.low <= px <= z.high), None)
    near = next((z for z in zones if a and min(abs(px - z.low), abs(px - z.high)) <= a), None)
    if sweep is not None and last - sweep.idx <= 5:
        obs = _event_text(sweep, last)
    elif brk is not None and last - brk.idx <= 10:
        obs = _event_text(brk, last)
    elif inside is not None:
        obs = f"price is inside a {inside.direction} {inside.kind.replace('_', ' ')} {fmt(inside.low)}–{fmt(inside.high)}"
    elif near is not None:
        obs = f"approaching a {near.direction} {near.kind.replace('_', ' ')} {fmt(near.low)}–{fmt(near.high)}"
    elif pdz is not None:
        obs = f"price in {pdz.status} ({pdz.meta['position']:.0%} of the dealing range)"
    else:
        obs = "no notable structure event"
    return {
        "timeframe": tf, "class": cls, "label": CLASS_LABEL[cls], "direction": CLASS_DIR[cls], "trend": s, "swing_bias": h, "ema_side": e,
        "structure": structure_label(pa, last), "last_event": _event_text(brk, last) if brk is not None else None,
        "last_event_kind": brk.kind if brk is not None else None, "last_event_dir": brk.direction if brk is not None else None,
        "zone": pdz.status if pdz is not None else None, "range_position": float(pdz.meta["position"]) if pdz is not None else None,
        "observation": obs, "last_close": px, "atr": a, "last_ts": int(b.t[last]), "close_ts": int(b.t[last]) + int(b.step), "n_bars": n,
    }


def as_of(b: Bars, end_ts: int) -> Bars:
    """Bars that were COMPLETE at time end_ts (open + step <= end_ts)."""
    k = int(np.searchsorted(b.t + b.step, end_ts, side="right"))
    return b.upto(k)


def period_levels(daily: Bars | None, weekly: Bars | None) -> dict:
    """Previous (last complete) day and week high/low from already as-of-cut bars."""
    out: dict = {}
    if daily is not None and len(daily):
        out.update(pdh=float(daily.h[-1]), pdl=float(daily.l[-1]), pd_ts=int(daily.t[-1]))
    if weekly is not None and len(weekly):
        out.update(pwh=float(weekly.h[-1]), pwl=float(weekly.l[-1]), pw_ts=int(weekly.t[-1]))
    return out


def period_sweeps(b: Bars, levels: dict, since: int) -> list[dict]:
    """Wick through a previous day/week high or low that closed back inside, on bars [since, n). Same shape as liquidity sweeps."""
    out = []
    names = (("pdl", "previous day low", "bullish"), ("pwl", "previous week low", "bullish"),
             ("pdh", "previous day high", "bearish"), ("pwh", "previous week high", "bearish"))
    for key, label, direction in names:
        lvl = levels.get(key)
        if lvl is None:
            continue
        for j in range(max(0, since), len(b)):
            hit = (b.l[j] < lvl < b.c[j]) if direction == "bullish" else (b.h[j] > lvl > b.c[j])
            if hit:
                out.append({"kind": "liquidity_sweep", "label": label, "direction": direction, "idx": j, "ts": int(b.t[j]), "price": float(lvl),
                            "low": float(b.l[j]), "high": float(b.h[j]),
                            "evidence": f"wick through the {label} {fmt(lvl)} closed back at {fmt(b.c[j])}"})
                break
    return out


def atr_rank(pa: PriceActionResult, b: Bars) -> float | None:
    """Percentile of the current ATR (as % of price) within the given window."""
    a = pa.atr / np.where(b.c > 0, b.c, np.nan)
    ok = a[np.isfinite(a)]
    if len(ok) < 30 or not np.isfinite(a[-1]):
        return None
    return float((ok < a[-1]).mean())


def session_name(ts: int) -> str:
    hr = datetime.fromtimestamp(int(ts), tz=timezone.utc).hour
    if hr < 7:
        return "Asia"
    if hr < 12:
        return "London"
    if hr < 16:
        return "London / New York overlap"
    if hr < 21:
        return "New York"
    return "Off-hours (rollover)"


def in_active_session(close_ts: int) -> bool:
    hr = datetime.fromtimestamp(int(close_ts), tz=timezone.utc).hour
    return PARAMS["session_start_utc"] <= hr < PARAMS["session_end_utc"]
