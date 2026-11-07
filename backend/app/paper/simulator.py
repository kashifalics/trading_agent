"""Pure simulation of one paper trade over later candles (docs/PAPER_TRADING.md). No database access: the service feeds it candles.

Orders start when the backend first SAW the signal (`detected_ts`), never earlier, so a signal noticed late is traded late:
  * market order: filled at the open of the first candle that starts after detection; skipped when that open is already beyond the
    stop or TP1, or more than CHASE_R past the planned entry (the plan's own "never chase" rule);
  * limit order: rests at the planned entry until `valid_until`; cancelled when a setup-timeframe candle closes beyond the invalidation
    level, missed when TP1 trades before the entry is touched;
  * exits (stop or TP1) follow app.signals.execution with gap fills on, on the finest stored candles (1m where available).
"""
from dataclasses import dataclass

import numpy as np

from app.market_data.bars import Bars
from app.signals.execution import (
    exit_on_candle,
    limit_touch,
    market_entry_ok,
    r_multiple,
)

PATH_TFS = ("1m", "5m", "15m", "1H", "4H", "1D")
CHASE_R = 0.3
LIVE = ("pending", "open")
EXPIRED_NOTE = "the plan's lifetime ended before the order could fill"
PathCandle = tuple[int, float, float, float, float, int]  # (open time, open, high, low, close, step seconds)


def build_path(series: dict[str, Bars], start_ts: int) -> list[PathCandle]:
    """Complete candles from `start_ts` on, finest first: a 1m candle where one is stored, otherwise the finest timeframe with a candle
    starting at that moment (gaps in 1m data, e.g. while the backend was off, are bridged by 5m/15m/1H/... candles). A candle that started
    before `start_ts` is never used: its range may contain prices from before the order existed."""
    avail = [series[tf] for tf in PATH_TFS if series.get(tf) is not None and len(series[tf])]
    out: list[PathCandle] = []
    t_now = int(start_ts)
    while True:
        chosen, nxt = None, None
        for b in avail:
            i = int(np.searchsorted(b.t, t_now, side="left"))
            if i >= len(b):
                continue
            ti = int(b.t[i])
            if ti == t_now:
                chosen = (b, i)
                break
            if nxt is None or ti < nxt:
                nxt = ti
        if chosen is None:
            if nxt is None:
                return out
            t_now = nxt
            continue
        b, i = chosen
        out.append((int(b.t[i]), float(b.o[i]), float(b.h[i]), float(b.l[i]), float(b.c[i]), int(b.step)))
        t_now = int(b.t[i]) + int(b.step)


@dataclass
class SimTrade:
    d: int
    order_type: str  # market | limit
    entry: float
    sl: float
    tp: float
    inv: float | None
    spread: float
    detected_ts: int
    valid_until_ts: int
    status: str = "pending"
    cursor_ts: int = 0
    fill_price: float | None = None
    fill_ts: int | None = None
    risk: float | None = None
    exit_price: float | None = None
    exit_ts: int | None = None
    exit_reason: str | None = None
    note: str | None = None
    r_gross: float | None = None
    r_net: float | None = None
    mfe_r: float | None = None
    mae_r: float | None = None
    last_price: float | None = None
    last_ts: int | None = None

    @property
    def spread_r(self) -> float | None:
        return self.spread / self.risk if self.risk else None

    def unrealized_r(self, price: float | None = None) -> float | None:
        px = self.last_price if price is None else price
        if self.status != "open" or px is None or not self.risk:
            return None
        return r_multiple(self.d, self.fill_price, px, self.risk) - self.spread / self.risk


def _end(sim: SimTrade, status: str, reason: str, note: str, ts: int) -> SimTrade:
    sim.status, sim.exit_reason, sim.note, sim.exit_ts = status, reason, note, int(ts)
    return sim


def _open(sim: SimTrade, price: float, ts: int) -> None:
    sim.status, sim.fill_price, sim.fill_ts = "open", float(price), int(ts)
    sim.risk = abs(sim.fill_price - sim.sl)
    sim.mfe_r = sim.mae_r = 0.0


def _close(sim: SimTrade, price: float, why: str, ts: int) -> SimTrade:
    sim.r_gross = r_multiple(sim.d, sim.fill_price, price, sim.risk)
    sim.r_net = sim.r_gross - sim.spread / sim.risk
    if why == "target":
        sim.mfe_r = max(sim.mfe_r or 0.0, sim.r_gross)
    else:
        sim.mae_r = min(sim.mae_r or 0.0, sim.r_gross)
    sim.exit_price, sim.last_price, sim.last_ts = float(price), float(price), int(ts)
    note = "TP1 reached" if why == "target" else "stop loss hit"
    return _end(sim, "closed", why, note, ts)


def _invalidated(sim: SimTrade, closes: list[tuple[int, float]], upto_ts: int) -> int | None:
    """Close time of the first setup-timeframe candle after detection (and by `upto_ts`) that closed beyond the invalidation level."""
    if sim.inv is None:
        return None
    for close_ts, c in closes:
        if close_ts <= sim.detected_ts:
            continue
        if close_ts > upto_ts:
            return None
        if (c < sim.inv) if sim.d == 1 else (c > sim.inv):
            return close_ts
    return None


def advance(sim: SimTrade, path: list[PathCandle], setup_closes: list[tuple[int, float]] = (), now_ts: int | None = None) -> SimTrade:
    """Step a pending/open trade through candles starting at or after its cursor. Idempotent: candles before the cursor are ignored."""
    if sim.status not in LIVE:
        return sim
    for t, o, h, lo, c, step in path:
        if t < sim.cursor_ts:
            continue
        tp_allowed = True
        if sim.status == "pending":
            if t >= sim.valid_until_ts:
                return _end(sim, "expired", "expired", EXPIRED_NOTE, sim.valid_until_ts)
            if sim.order_type == "market":
                if not market_entry_ok(sim.d, o, sim.sl, sim.tp):
                    return _end(sim, "skipped", "gapped", "price opened beyond the stop or TP1 before the order could fill", t)
                if sim.d * (o - sim.entry) > CHASE_R * abs(sim.entry - sim.sl):
                    return _end(sim, "skipped", "chased", f"price was already more than {CHASE_R:g}R past the planned entry (never chase)", t)
                _open(sim, o, t)
            else:
                inv_ts = _invalidated(sim, setup_closes, t)
                if inv_ts is not None:
                    return _end(sim, "cancelled", "invalidated", "a setup candle closed beyond the invalidation level before the fill", inv_ts)
                touch = limit_touch(sim.d, sim.entry, sim.tp, h, lo)
                if touch == "missed":
                    return _end(sim, "missed", "tp_before_fill", "TP1 traded before the limit price was touched (never chased)", t)
                if touch is None:
                    sim.cursor_ts = t + step
                    continue
                _open(sim, sim.entry, t)
                tp_allowed = False  # on the fill candle only the stop counts
        ex = exit_on_candle(sim.d, sim.sl, sim.tp, o, h, lo, tp_allowed=tp_allowed, gap_fills=True)
        if ex is not None:
            return _close(sim, ex[0], ex[1], t)
        best, worst = (h, lo) if sim.d == 1 else (lo, h)
        sim.mfe_r = max(sim.mfe_r or 0.0, r_multiple(sim.d, sim.fill_price, best, sim.risk))
        sim.mae_r = min(sim.mae_r or 0.0, r_multiple(sim.d, sim.fill_price, worst, sim.risk))
        sim.last_price, sim.last_ts, sim.cursor_ts = c, t + step, t + step
    if sim.status == "pending" and now_ts is not None:  # no new candles (e.g. market closed): time still runs
        if now_ts >= sim.valid_until_ts:
            return _end(sim, "expired", "expired", EXPIRED_NOTE, sim.valid_until_ts)
        inv_ts = _invalidated(sim, setup_closes, now_ts) if sim.order_type == "limit" else None
        if inv_ts is not None:
            return _end(sim, "cancelled", "invalidated", "a setup candle closed beyond the invalidation level before the fill", inv_ts)
    return sim
