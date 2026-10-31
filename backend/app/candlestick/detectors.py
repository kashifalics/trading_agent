from dataclasses import asdict

import numpy as np

from app.candlestick.patterns import CandleParams
from app.core.events import Event
from app.market_data.bars import Bars


def _geom(b: Bars):
    body = np.abs(b.c - b.o)
    rng = b.h - b.l
    upper = b.h - np.maximum(b.o, b.c)
    lower = np.minimum(b.o, b.c) - b.l
    return body, rng, upper, lower


def _ev(b: Bars, i: int, kind: str, direction: str, evidence: str, p: CandleParams, **meta) -> Event:
    return Event(kind=kind, direction=direction, idx=i, ts=int(b.t[i]), price=float(b.c[i]), low=float(b.l[i]),
                 high=float(b.h[i]), start_idx=i, start_ts=int(b.t[i]), evidence=evidence,
                 params=asdict(p), meta=meta)


def detect_candlestick_patterns(b: Bars, p: CandleParams | None = None) -> list[Event]:
    p = p or CandleParams()
    n = len(b)
    body, rng, upper, lower = _geom(b)
    out: list[Event] = []
    lb = p.trend_lookback
    for i in range(n):
        if rng[i] <= p.min_range:
            continue
        r, bd, up, lo = rng[i], body[i], upper[i], lower[i]
        bull, bear = b.c[i] > b.o[i], b.c[i] < b.o[i]

        if bd <= p.doji_body_ratio * r:
            out.append(_ev(b, i, "doji", "neutral", f"body {bd / r:.0%} of range", p))
        else:
            down = i > lb and b.c[i - 1] < b.c[i - 1 - lb]
            up_tr = i > lb and b.c[i - 1] > b.c[i - 1 - lb]
            if bd >= p.min_body_ratio * r:
                if lo >= p.hammer_wick_mult * bd and up <= p.hammer_opp_wick_ratio * r and (down or not p.require_trend):
                    out.append(_ev(b, i, "hammer", "bullish", f"lower wick {lo / bd:.1f}x body after decline", p))
                if up >= p.hammer_wick_mult * bd and lo <= p.hammer_opp_wick_ratio * r and (up_tr or not p.require_trend):
                    out.append(_ev(b, i, "shooting_star", "bearish", f"upper wick {up / bd:.1f}x body after advance", p))
        if bd <= p.pin_body_ratio * r:
            if lo >= p.pin_wick_ratio * r and up <= p.pin_opp_wick_ratio * r:
                out.append(_ev(b, i, "pin_bar", "bullish", f"lower wick {lo / r:.0%} of range", p))
            elif up >= p.pin_wick_ratio * r and lo <= p.pin_opp_wick_ratio * r:
                out.append(_ev(b, i, "pin_bar", "bearish", f"upper wick {up / r:.0%} of range", p))

        if i >= 1:
            pb = body[i - 1]
            p_bull, p_bear = b.c[i - 1] > b.o[i - 1], b.c[i - 1] < b.o[i - 1]
            if bull and p_bear and b.o[i] <= b.c[i - 1] and b.c[i] >= b.o[i - 1] and bd > pb:
                out.append(_ev(b, i, "bullish_engulfing", "bullish",
                               f"body {bd:.4g} engulfs prior bearish body {pb:.4g}", p))
            if bear and p_bull and b.o[i] >= b.c[i - 1] and b.c[i] <= b.o[i - 1] and bd > pb:
                out.append(_ev(b, i, "bearish_engulfing", "bearish",
                               f"body {bd:.4g} engulfs prior bullish body {pb:.4g}", p))
            if b.h[i] < b.h[i - 1] and b.l[i] > b.l[i - 1]:
                out.append(_ev(b, i, "inside_bar", "neutral", "range contained in prior bar", p))
            elif b.h[i] > b.h[i - 1] and b.l[i] < b.l[i - 1]:
                out.append(_ev(b, i, "outside_bar", "bullish" if bull else "bearish" if bear else "neutral",
                               "range engulfs prior bar", p))

        if i >= 2 and rng[i - 2] > p.min_range:
            first_body, first_rng = body[i - 2], rng[i - 2]
            long_first = first_body >= p.first_body_ratio * first_rng
            small_mid = body[i - 1] <= p.star_body_ratio * first_body
            mid = (b.o[i - 2] + b.c[i - 2]) / 2
            if long_first and small_mid:
                if b.c[i - 2] < b.o[i - 2] and bull and b.c[i] > mid:
                    out.append(_ev(b, i, "morning_star", "bullish", "bearish bar, small star, bullish close above midpoint", p))
                if b.c[i - 2] > b.o[i - 2] and bear and b.c[i] < mid:
                    out.append(_ev(b, i, "evening_star", "bearish", "bullish bar, small star, bearish close below midpoint", p))
    for e in out:
        if e.kind in ("morning_star", "evening_star"):
            e.start_idx, e.start_ts = e.idx - 2, int(b.t[e.idx - 2])
            e.low, e.high = float(b.l[e.idx - 2:e.idx + 1].min()), float(b.h[e.idx - 2:e.idx + 1].max())
        elif e.kind in ("bullish_engulfing", "bearish_engulfing", "inside_bar", "outside_bar"):
            e.start_idx, e.start_ts = e.idx - 1, int(b.t[e.idx - 1])
    return out


__all__ = ["detect_candlestick_patterns", "CandleParams"]
