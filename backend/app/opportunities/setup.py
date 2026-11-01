"""Deterministic trade-setup generation for one timeframe.

A setup is only produced when ALL of these hold (otherwise the outcome is WAIT with the reasons):
  1. a direction is permitted: higher-timeframe bias is not opposed, and either the setup-timeframe structure trend agrees
     (`trend_pullback`) or a liquidity sweep was followed by a same-direction BOS/CHoCH (`sweep_reversal`);
  2. a STRUCTURAL entry exists: an unmitigated same-side zone (order block / FVG / supply-demand / breaker) or a
     support/resistance band, at or within `max_approach_atr` of price. Entries are never "current price +/- something";
  3. a structural stop exists (beyond the entry zone / protecting swing) within the style's ATR bounds;
  4. a structural first target exists at >= the style's minimum R, with no strong opposing structure in between
     (or, when price is in discovery with no structure beyond it, a labelled volatility multiple);
  5. round-trip costs consume no more than the style's maximum share of the risk.
The result is `waiting_for_confirmation` until price has traded into the entry zone AND a confirming event
(rejection candle, BOS/CHoCH, sweep, retest) appeared at/after the touch; then `entry_triggered`.

The function is pure and causal (uses only bars[:n] and events confirmed by then), so the validation backtest calls
exactly this code.
"""
from dataclasses import dataclass, field

import numpy as np

from app.core.events import Event, iso
from app.market_data.bars import Bars
from app.market_structure.swings import confirmed
from app.opportunities.config import SETUP, StyleProfile
from app.price_action.engine import PriceActionResult
from app.price_action.levels import detect_breakouts, detect_levels, detect_trendlines

DEAD = ("filled", "invalidated", "broken")
BULL_REJ = {"bullish_engulfing", "hammer", "pin_bar", "morning_star"}
BEAR_REJ = {"bearish_engulfing", "shooting_star", "pin_bar", "evening_star"}


@dataclass
class Bias:
    direction: int = 0
    score: float = 0.0
    conflict: bool = False
    views: list[dict] = field(default_factory=list)


@dataclass
class Concepts:
    levels: list[Event]
    trendlines: list[Event]
    breakouts: list[Event]


def compute_concepts(b: Bars, pa: PriceActionResult) -> Concepts:
    lv = detect_levels(b, pa.swings, pa.atr)
    return Concepts(lv, detect_trendlines(b, pa.swings, pa.atr), detect_breakouts(b, lv, pa.atr))


@dataclass
class Setup:
    direction: str
    setup_type: str
    status: str
    entry_low: float
    entry_high: float
    entry_ref: float
    stop_loss: float
    invalidation: float
    targets: list[dict]
    risk_reward: float
    anchor_ts: int
    poi: dict
    confirmations: list[dict]
    conditions: list[str]
    warnings: list[str]
    reasoning: dict
    cost_r: float
    trigger_ts: int | None
    atr: float


@dataclass
class SetupOutcome:
    setup: Setup | None
    lean: int
    wait_reasons: list[str]
    considered: int = 0


def _band(low: float, high: float, atr: float) -> tuple[float, float]:
    if high - low < 0.1 * atr:
        mid = (low + high) / 2
        return mid - 0.05 * atr, mid + 0.05 * atr
    return low, high


def _zones(pa: PriceActionResult, n: int, sd: str) -> list[dict]:
    out = []
    for z in pa.order_blocks + pa.fvgs + pa.zones + pa.breakers:
        if z.direction != sd or z.status in DEAD or z.low is None or z.high is None or n - z.idx > SETUP["zone_max_age_bars"]:
            continue
        out.append({"kind": z.kind, "low": float(z.low), "high": float(z.high), "ts": z.ts, "idx": z.idx, "evidence": z.evidence})
    return out


def _levels_as_zones(cx: Concepts, atr: float, long_: bool, px: float) -> list[dict]:
    out = []
    for e in cx.levels:
        low, high = _band(e.low, e.high, atr)
        if (long_ and high <= px + 0.5 * atr) or (not long_ and low >= px - 0.5 * atr):
            out.append({"kind": "support_band" if long_ else "resistance_band", "low": low, "high": high, "ts": e.ts, "idx": e.idx,
                        "evidence": e.evidence, "touches": e.meta.get("touches")})
    return out


def _target_candidates(b: Bars, pa: PriceActionResult, cx: Concepts, long_: bool, ref: float, atr: float) -> list[dict]:
    n = len(b)
    out = []
    for s in confirmed(pa.swings, n - 1):
        if s.kind == ("high" if long_ else "low") and (s.price > ref if long_ else s.price < ref):
            out.append({"price": s.price, "basis": "swing_high" if long_ else "swing_low", "strong": False, "ts": int(b.t[s.idx])})
    for e in cx.levels:
        edge = e.low if long_ else e.high
        if (edge > ref if long_ else edge < ref):
            out.append({"price": edge, "basis": "resistance_band" if long_ else "support_band", "strong": True, "ts": e.ts})
    for e in pa.equal_levels:
        if e.kind == ("equal_highs" if long_ else "equal_lows") and e.price is not None and (e.price > ref if long_ else e.price < ref):
            out.append({"price": float(e.price), "basis": "equal_highs_liquidity" if long_ else "equal_lows_liquidity", "strong": True, "ts": e.ts})
    opp = "bearish" if long_ else "bullish"
    for z in pa.order_blocks + pa.fvgs + pa.zones + pa.breakers:
        if z.direction != opp or z.status in DEAD or z.low is None or z.high is None or n - z.idx > SETUP["zone_max_age_bars"]:
            continue
        edge = z.low if long_ else z.high
        if (edge > ref if long_ else edge < ref):
            out.append({"price": float(edge), "basis": f"opposing_{z.kind}", "strong": z.kind in ("order_block", "supply_zone", "demand_zone", "breaker_block"),
                        "ts": z.ts})
    out.sort(key=lambda c: c["price"], reverse=not long_)
    return out


def _confirmations(pa: PriceActionResult, cx: Concepts, sd: str, since: int) -> list[dict]:
    rej = BULL_REJ if sd == "bullish" else BEAR_REJ
    evs: list[tuple[str, Event]] = []
    evs += [("rejection_candle", e) for e in pa.candles if e.direction == sd and e.kind in rej and e.idx >= since]
    evs += [("structure_break", e) for e in pa.breaks if e.direction == sd and e.idx >= since]
    evs += [("liquidity_sweep", e) for e in pa.sweeps if e.direction == sd and e.idx >= since]
    evs += [("retest", e) for e in cx.breakouts if e.kind in ("retest", "failed_breakout") and e.direction == sd and e.idx >= since]
    return [{"type": t, "kind": e.kind, "idx": e.idx, "ts": e.ts, "time": iso(e.ts), "price": e.price, "evidence": e.evidence} for t, e in evs]


def _permitted(pa: PriceActionResult, cx: Concepts, bias: Bias, prof: StyleProfile, n: int, d: int) -> tuple[str | None, str | None]:
    """(setup_type, reason_if_blocked)."""
    last = n - 1
    if bias.direction == -d:
        return None, f"higher-timeframe bias is {'bearish' if d == 1 else 'bullish'}"
    if int(pa.trend[last]) == d:
        return "trend_pullback", None
    sd = "bullish" if d == 1 else "bearish"
    win = prof.confirm_bars * SETUP["sweep_window_mult"]
    sweeps = [e for e in pa.sweeps if e.direction == sd and last - e.idx <= win]
    for sw in sweeps:
        if any(e.direction == sd and e.idx > sw.idx and last - e.idx <= win for e in pa.breaks):
            return "sweep_reversal", None
    return None, "setup-timeframe structure does not support this direction and there is no sweep + structure-break reversal"


def generate_setup(b: Bars, pa: PriceActionResult, cx: Concepts, bias: Bias, prof: StyleProfile, cost_frac: float) -> SetupOutcome:
    n = len(b)
    if n < 60:
        return SetupOutcome(None, 0, [f"only {n} bars; at least 60 needed for structure analysis"])
    last = n - 1
    atr = float(pa.atr[last]) if np.isfinite(pa.atr[last]) else float("nan")
    if not np.isfinite(atr) or atr <= 0:
        return SetupOutcome(None, 0, ["ATR unavailable"])
    px = float(b.c[last])
    trend = int(pa.trend[last])
    lean = bias.direction or trend
    reasons: list[str] = []
    found: list[Setup] = []
    considered = 0
    for d in (1, -1):
        long_ = d == 1
        sd = "bullish" if long_ else "bearish"
        side = "BUY" if long_ else "SELL"
        stype, blocked = _permitted(pa, cx, bias, prof, n, d)
        if stype is None:
            if d == lean or lean == 0:
                reasons.append(f"{side}: {blocked}")
            continue
        considered += 1
        pois = _zones(pa, n, sd) + _levels_as_zones(cx, atr, long_, px)
        sel = []
        for z in pois:
            dist = (px - z["high"]) if long_ else (z["low"] - px)
            inside = z["low"] <= px <= z["high"]
            touched_recent = any(b.l[j] <= z["high"] and b.h[j] >= z["low"] for j in range(max(0, n - prof.confirm_bars - 1), n))
            if inside or touched_recent or 0 < dist <= SETUP["max_approach_atr"] * atr:
                sel.append((0 if (inside or touched_recent) else 1, abs(dist), -z["idx"], z))
        if not sel:
            reasons.append(f"{side}: no unmitigated {sd} zone or support/resistance band within {SETUP['max_approach_atr']} ATR of price")
            continue
        poi = sorted(sel, key=lambda t: t[:3])[0][3]
        ref = poi["high"] if long_ else poi["low"]
        # --- stop: beyond the zone, or beyond a protecting swing sitting in/just beyond it
        sw = [s for s in confirmed(pa.swings, last) if s.kind == ("low" if long_ else "high")]
        if long_:
            near = [s for s in sw if poi["low"] - atr <= s.price <= poi["high"]]
        else:
            near = [s for s in sw if poi["low"] <= s.price <= poi["high"] + atr]
        base, anchor_ts = (poi["low"] if long_ else poi["high"]), poi["ts"]
        for s in near:
            if (long_ and s.price < base) or (not long_ and s.price > base):
                base, anchor_ts = s.price, int(b.t[s.idx])
        stop = base - SETUP["stop_buffer_atr"] * atr if long_ else base + SETUP["stop_buffer_atr"] * atr
        risk = (ref - stop) if long_ else (stop - ref)
        warns: list[str] = []
        if risk < prof.min_stop_atr * atr:
            stop = ref - prof.min_stop_atr * atr if long_ else ref + prof.min_stop_atr * atr
            risk = prof.min_stop_atr * atr
            warns.append(f"stop widened to the minimum {prof.min_stop_atr} ATR")
        if risk > prof.max_stop_atr * atr:
            reasons.append(f"{side}: structural stop is {risk / atr:.1f} ATR away (limit {prof.max_stop_atr})")
            continue
        invalid_level = base
        if (long_ and px < invalid_level) or (not long_ and px > invalid_level):
            reasons.append(f"{side}: price is already beyond the invalidation level {invalid_level:.6g}")
            continue
        # --- targets
        cands = _target_candidates(b, pa, cx, long_, ref, atr)
        gap = SETUP["min_target_gap_atr"] * atr
        rr_of = lambda p: abs(p - ref) / risk  # noqa: E731
        obstacle = next((c for c in cands if c["strong"] and rr_of(c["price"]) < prof.min_rr), None)
        if obstacle:
            reasons.append(f"{side}: strong opposing structure ({obstacle['basis']}) at {obstacle['price']:.6g} is only "
                           f"{rr_of(obstacle['price']):.2f}R away (minimum {prof.min_rr}R)")
            continue
        weak_close = [c for c in cands if not c["strong"] and rr_of(c["price"]) < prof.min_rr]
        if weak_close:
            warns.append(f"minor {weak_close[0]['basis']} at {weak_close[0]['price']:.6g} sits before {prof.min_rr}R")
        good = [c for c in cands if rr_of(c["price"]) >= prof.min_rr]
        targets: list[dict] = []
        if good:
            for c in good:
                if not targets or abs(c["price"] - targets[-1]["price"]) >= gap:
                    targets.append({**c, "rr": rr_of(c["price"])})
                if len(targets) == 3:
                    break
        elif not cands:
            sign = 1 if long_ else -1
            targets = [{"price": ref + sign * prof.min_rr * risk, "basis": "volatility_multiple", "strong": False, "ts": None, "rr": prof.min_rr}]
            warns.append("no price structure beyond entry (price discovery): first target is a volatility multiple of risk, not a level")
        else:
            reasons.append(f"{side}: no structural target at >= {prof.min_rr}R")
            continue
        if len(targets) == 1:
            sign = 1 if long_ else -1
            ext = ref + sign * 1.5 * abs(targets[0]["price"] - ref)
            targets.append({"price": ext, "basis": "extension_1.5x_tp1", "strong": False, "ts": None, "rr": rr_of(ext)})
            warns.append("TP2 is a 1.5x extension of TP1 (no further structure found)")
        for i, t in enumerate(targets, 1):
            t["label"] = f"TP{i}"
        rr = targets[0]["rr"]
        cost_r = cost_frac * ref / risk
        if cost_r > prof.max_cost_r:
            reasons.append(f"{side}: round-trip costs would consume {cost_r:.2f}R of the {1.0:.0f}R risked (limit {prof.max_cost_r}R) - not viable for {prof.label.lower()}")
            continue
        # --- confirmation / status
        win_start = max(0, n - prof.confirm_bars - 1)
        touch_idx = next((j for j in range(win_start, n) if b.l[j] <= poi["high"] and b.h[j] >= poi["low"]), None)
        confs = _confirmations(pa, cx, sd, touch_idx if touch_idx is not None else n + 1)
        beyond_tp = any((b.h[j] >= targets[0]["price"]) if long_ else (b.l[j] <= targets[0]["price"])
                        for j in range(touch_idx, n)) if touch_idx is not None else False
        if beyond_tp:
            reasons.append(f"{side}: first target {targets[0]['price']:.6g} was already reached after the zone touch (move played out)")
            continue
        status = "entry_triggered" if (touch_idx is not None and confs) else "waiting_for_confirmation"
        trig = max((c["ts"] for c in confs), default=None) if status == "entry_triggered" else None
        conds = []
        if touch_idx is None:
            conds.append(f"Price trades into the entry zone {poi['low']:.6g} - {poi['high']:.6g}")
        if not confs:
            conds.append(f"A {sd} confirmation after the touch: rejection candle, {sd} BOS/CHoCH, or liquidity sweep reversal")
        conds.append(f"Price must not close {'below' if long_ else 'above'} {invalid_level:.6g} (invalidation)")
        reasoning = {
            "entry": (f"{side} zone {poi['low']:.6g}-{poi['high']:.6g} is a {poi['kind'].replace('_', ' ')} ({poi['evidence']}); entry reference "
                      f"{ref:.6g} is its {'upper' if long_ else 'lower'} edge, where a retracement first meets it. "
                      f"Setup type: {stype.replace('_', ' ')}."),
            "stop": (f"Stop {stop:.6g} = {'below' if long_ else 'above'} {base:.6g} (zone edge or protecting swing) plus a "
                     f"{SETUP['stop_buffer_atr']} ATR buffer; risk {risk:.6g} = {risk / atr:.2f} ATR (allowed {prof.min_stop_atr}-{prof.max_stop_atr})."),
            "targets": [f"{t['label']} {t['price']:.6g} ({t['rr']:.2f}R): {t['basis'].replace('_', ' ')}" for t in targets],
        }
        found.append(Setup(side, stype, status, poi["low"], poi["high"], ref, float(stop), float(invalid_level), targets, float(rr),
                           int(anchor_ts), {k: poi.get(k) for k in ("kind", "low", "high", "ts", "touches")}, confs, conds, warns, reasoning,
                           float(cost_r), trig, atr))
    if len(found) > 1:
        return SetupOutcome(None, lean, reasons + ["BUY and SELL setups are both valid: conflicting evidence"], considered)
    if found:
        return SetupOutcome(found[0], lean, reasons, considered)
    return SetupOutcome(None, lean, reasons or ["no setup conditions met"], considered)
