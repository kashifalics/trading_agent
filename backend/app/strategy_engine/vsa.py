"""Volume Spread Analysis (docs/engine_v2/CONFIRMATION_DESIGN.md section 5): objective bar measures and events.

* An event is decided from candles up to its own candle (causal). Its confirmation, where the definition needs one, uses only the
  completed candles after it, judged at a view candle i: unconfirmed until the window has passed, then confirmed or failed.
* High volume alone never makes an event: every event needs its price context (a prior move, a level, a narrow spread...).
* A candle with no range (high = low) or no ATR has no measures and produces no event.
* Callers decide whether the volume is reliable (volume.quality); VSA on unreliable volume is UNAVAILABLE, never computed here.
"""
from dataclasses import dataclass

import numpy as np

from app.market_data.bars import Bars
from app.strategy_engine.config import VSA_T as T


@dataclass
class Measures:
    spread: np.ndarray  # (high - low) / ATR
    close_pos: np.ndarray  # 0 = close at the low, 1 = at the high
    rvol: np.ndarray
    prior_move: np.ndarray  # net close change over the previous prior_n candles, in ATR (candles before i)


@dataclass
class VsaEvent:
    kind: str  # climactic | stopping | no_demand | no_supply | upthrust | spring | test | effort_no_result | result_no_effort | absorption
    idx: int
    direction: int  # +1 bullish implication, -1 bearish, 0 neutral
    confirm_n: int  # candles after idx that decide it; 0 = needs no confirmation
    text: str
    ref: float = float("nan")  # the price the confirmation is judged against (the candle's low or high, or the level)
    atr: float = float("nan")  # ATR at the event


def measures(b: Bars, atr: np.ndarray, rv: np.ndarray) -> Measures:
    h, lo, c = b.h.astype(float), b.l.astype(float), b.c.astype(float)
    a = np.asarray(atr, dtype=float)
    rng = h - lo
    ok = np.isfinite(a) & (a > 0) & (rng > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        spread = np.where(ok, rng / a, np.nan)
        cpos = np.where(ok, (c - lo) / rng, np.nan)
        n = T["prior_n"]
        prior = np.full(len(c), np.nan)
        if len(c) > n + 1:
            prior[n + 1:] = (c[n:-1] - c[:-n - 1]) / a[n:-1]
    return Measures(spread=spread, close_pos=cpos, rvol=np.asarray(rv, dtype=float), prior_move=prior)


def levels(b: Bars, n: int = T["level_n"]) -> tuple[np.ndarray, np.ndarray]:
    """The highest high and lowest low of the n candles before each candle (NaN until n candles exist): the meaningful level."""
    h, lo = b.h.astype(float), b.l.astype(float)
    hi_l, lo_l = np.full(len(h), np.nan), np.full(len(h), np.nan)
    if len(h) > n:
        wh = np.lib.stride_tricks.sliding_window_view(h, n)[:-1]
        wl = np.lib.stride_tricks.sliding_window_view(lo, n)[:-1]
        hi_l[n:], lo_l[n:] = wh.max(axis=1), wl.min(axis=1)
    return hi_l, lo_l


def _fmt(x: float) -> str:
    return f"{x:,.2f}" if abs(x) >= 100 else f"{x:.5f}" if abs(x) < 10 else f"{x:.3f}"


def detect(b: Bars, m: Measures, level_hi: np.ndarray, level_lo: np.ndarray) -> list[VsaEvent]:
    o, h, lo, c = b.o.astype(float), b.h.astype(float), b.l.astype(float), b.c.astype(float)
    sp, cp, rv, pm = m.spread, m.close_pos, m.rvol, m.prior_move
    atr = np.where(np.isfinite(sp) & (sp > 0), (h - lo) / np.where(sp > 0, sp, 1), np.nan)
    out: list[VsaEvent] = []
    origins: list[VsaEvent] = []  # springs, upthrusts and stopping volume a later test candle can refer to
    for i in range(len(c)):
        if not (np.isfinite(sp[i]) and np.isfinite(cp[i]) and np.isfinite(rv[i])):
            continue
        a = float(atr[i])
        up, down = c[i] > o[i], c[i] < o[i]
        wide, narrow = sp[i] >= T["wide"], sp[i] <= T["narrow"]
        top, bottom = cp[i] >= T["top"], cp[i] <= T["bottom"]
        prior = pm[i] if np.isfinite(pm[i]) else 0.0
        ev: list[VsaEvent] = []
        if rv[i] >= T["ultra"] and wide and ((up and prior >= T["prior_atr"]) or (down and prior <= -T["prior_atr"])):
            ev.append(VsaEvent("climactic", i, 1 if up else -1, 0,
                               f"climactic volume: {rv[i]:.1f}x volume on a wide candle after a {abs(prior):.1f} ATR move (possible exhaustion)"))
        if rv[i] >= T["high"] and down and prior <= -T["prior_atr"] and not bottom:
            ev.append(VsaEvent("stopping", i, 1, T["confirm_n"],
                               f"stopping volume: {rv[i]:.1f}x volume on a down candle after a {abs(prior):.1f} ATR decline, close off the low",
                               ref=float(lo[i]), atr=a))
        if rv[i] >= T["high"] and up and prior >= T["prior_atr"] and not top:
            ev.append(VsaEvent("stopping", i, -1, T["confirm_n"],
                               f"stopping volume: {rv[i]:.1f}x volume on an up candle after a {prior:.1f} ATR rally, close off the high",
                               ref=float(h[i]), atr=a))
        if i >= 5 and up and narrow and rv[i] <= 1.0 and rv[i] < rv[i - 1] and rv[i] < rv[i - 2] and c[i] > c[i - 5]:
            ev.append(VsaEvent("no_demand", i, -1, 0, f"no demand: narrow up candle on falling volume ({rv[i]:.1f}x) in a rally"))
        if i >= 5 and down and narrow and rv[i] <= 1.0 and rv[i] < rv[i - 1] and rv[i] < rv[i - 2] and c[i] < c[i - 5]:
            ev.append(VsaEvent("no_supply", i, 1, 0, f"no supply: narrow down candle on falling volume ({rv[i]:.1f}x) in a decline"))
        lh, ll = level_hi[i], level_lo[i]
        if np.isfinite(lh) and h[i] > lh and c[i] < lh and bottom and rv[i] >= 1.0:
            ev.append(VsaEvent("upthrust", i, -1, T["confirm_n"],
                               f"upthrust: traded above {_fmt(lh)} and closed back below, near the low, on {rv[i]:.1f}x volume",
                               ref=float(h[i]), atr=a))
        if np.isfinite(ll) and lo[i] < ll and c[i] > ll and top and rv[i] >= 1.0:
            ev.append(VsaEvent("spring", i, 1, T["confirm_n"],
                               f"spring: traded below {_fmt(ll)} and closed back above, near the high, on {rv[i]:.1f}x volume",
                               ref=float(lo[i]), atr=a))
        if rv[i] <= T["low"]:
            for e in reversed(origins):
                if i - e.idx > T["test_n"]:
                    break
                if e.direction > 0 and abs(lo[i] - e.ref) <= T["test_atr"] * e.atr and cp[i] >= 0.5:
                    ev.append(VsaEvent("test", i, 1, 0, f"test: back to {_fmt(e.ref)} on low volume ({rv[i]:.1f}x), close in the upper half",
                                       ref=e.ref, atr=e.atr))
                    break
                if e.direction < 0 and abs(h[i] - e.ref) <= T["test_atr"] * e.atr and cp[i] <= 0.5:
                    ev.append(VsaEvent("test", i, -1, 0, f"test: back to {_fmt(e.ref)} on low volume ({rv[i]:.1f}x), close in the lower half",
                                       ref=e.ref, atr=e.atr))
                    break
        if rv[i] >= T["high"] and narrow:
            ev.append(VsaEvent("effort_no_result", i, 0, 0, f"effort without result: {rv[i]:.1f}x volume on a narrow candle"))
            if np.isfinite(ll) and prior < 0 and abs(lo[i] - ll) <= T["test_atr"] * a:
                ev.append(VsaEvent("absorption", i, 1, T["absorb_n"],
                                   f"potential absorption at support {_fmt(ll)}: heavy volume, little downward progress",
                                   ref=float(ll), atr=a))
            elif np.isfinite(lh) and prior > 0 and abs(h[i] - lh) <= T["test_atr"] * a:
                ev.append(VsaEvent("absorption", i, -1, T["absorb_n"],
                                   f"potential absorption at resistance {_fmt(lh)}: heavy volume, little upward progress",
                                   ref=float(lh), atr=a))
        if rv[i] <= T["low"] and wide:
            ev.append(VsaEvent("result_no_effort", i, 0, 0, f"result without effort: a wide candle on low volume ({rv[i]:.1f}x)"))
        out.extend(ev)
        origins.extend(e for e in ev if e.kind in ("spring", "upthrust", "stopping"))
    return out


def state(e: VsaEvent, b: Bars, i: int) -> str:
    """n/a | unconfirmed | confirmed | failed, using only candles e.idx+1 .. min(i, e.idx + confirm_n)."""
    if e.confirm_n == 0:
        return "n/a"
    end = min(i, e.idx + e.confirm_n, len(b.c) - 1)
    after = b.c[e.idx + 1:end + 1].astype(float)
    if e.kind == "absorption":
        target = e.ref + e.direction * T["absorb_atr"] * e.atr
        if len(after) and ((after >= target).any() if e.direction > 0 else (after <= target).any()):
            return "confirmed"
        return "failed" if i >= e.idx + e.confirm_n else "unconfirmed"
    broken = (after < e.ref).any() if e.direction > 0 else (after > e.ref).any()
    if broken:
        return "failed"
    return "confirmed" if i >= e.idx + e.confirm_n else "unconfirmed"


def until(events: list[VsaEvent], i: int) -> list[VsaEvent]:
    return [e for e in events if e.idx <= i]


def context_label(events: list[VsaEvent], rng: tuple[float, float, int] | None, b: Bars, i: int) -> str | None:
    """'potential accumulation' (or distribution) when an established range holds a spring or stopping volume that has not failed,
    followed by a test candle. Display only: no verdict uses it."""
    if rng is None:
        return None
    _, _, start = rng
    inside = [e for e in events if start <= e.idx <= i]
    for d, label in ((1, "potential accumulation"), (-1, "potential distribution")):
        origin = [e for e in inside if e.direction == d and e.kind in ("spring", "stopping", "upthrust") and state(e, b, i) != "failed"]
        if origin and any(e.kind == "test" and e.direction == d and e.idx > origin[0].idx for e in inside):
            return label
    return None


def pressure(b: Bars, i: int) -> dict:
    """Buying or selling pressure on candle i: Binance's taker-buy share when reported, otherwise inferred from the close position."""
    v = float(b.v[i]) if np.isfinite(b.v[i]) else 0.0
    if b.tb is not None and v > 0 and np.isfinite(b.tb[i]):
        share = round(float(b.tb[i]) / v, 4)
        return {"source": "taker-buy share (Binance)", "value": share,
                "side": "buying" if share >= 0.55 else "selling" if share <= 0.45 else "balanced"}
    r = float(b.h[i] - b.l[i])
    pos = 0.5 if r <= 0 else float(b.c[i] - b.l[i]) / r
    return {"source": "inferred from price", "value": round(pos, 4),
            "side": "buying" if pos >= T["top"] else "selling" if pos <= T["bottom"] else "balanced"}
