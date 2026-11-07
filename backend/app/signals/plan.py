"""Trade plan for ONE direction on ONE setup timeframe: logical entry location, structural stop, structural targets and the
must-pass rules. Pure and causal (uses only the bars and events it is given), so the historical replay runs exactly this code.

Entry locations (same side as the trade): unmitigated order block / FVG / supply-demand / breaker, support/resistance band, or the
level broken by a recent BOS (retest). Price never gets chased: a market entry needs a recent touch of the zone with price still
inside it or within `at_zone_tolerance_atr`; a zone further away (<= `max_approach_atr`) becomes a limit plan; anything else is no setup.
A liquidity sweep followed by a same-direction structure break is the only zone-less entry (stop beyond the sweep extreme).
"""
from dataclasses import dataclass, field

import numpy as np

from app.core.events import Event
from app.market_data.bars import Bars
from app.market_structure.swings import confirmed
from app.opportunities.setup import Concepts
from app.price_action.engine import PriceActionResult
from app.signals.config import PARAMS, Group
from app.signals.context import DEAD, fmt, last_atr

BULL_REJ = {"bullish_engulfing", "hammer", "pin_bar", "morning_star"}
BEAR_REJ = {"bearish_engulfing", "shooting_star", "pin_bar", "evening_star"}
STRONG_ZONES = {"order_block", "supply_zone", "demand_zone", "breaker_block"}


def side_word(d: int) -> str:
    return "bullish" if d == 1 else "bearish"


@dataclass
class Poi:
    kind: str
    low: float
    high: float
    ts: int
    idx: int
    evidence: str
    touches: int | None = None

    @property
    def label(self) -> str:
        return self.kind.replace("_", " ")


@dataclass
class Plan:
    direction: str  # BUY | SELL
    d: int
    setup_type: str
    entry_type: str  # market | limit
    entry: float
    stop_loss: float
    invalidation: float
    targets: list[dict]
    rr: float
    risk: float
    atr: float
    cost_r: float
    poi: Poi | None
    at_zone: bool
    touch_idx: int | None
    touch_ts: int | None
    sweep: dict | None
    anchor_ts: int
    anchor_note: str
    blocked: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reasoning: dict = field(default_factory=dict)
    obstacle: dict | None = None  # strong opposing level between entry and TP1 (costs the risk-to-reward points)

    @property
    def risk_atr(self) -> float:
        return self.risk / self.atr if self.atr else float("nan")

    @property
    def key(self) -> str:
        """Identity of the setup (same zone / same sweep = same setup), used for de-duplication and lifecycle tracking."""
        if self.poi is not None:
            return f"{self.direction}:{self.poi.kind}:{self.poi.ts}"
        return f"{self.direction}:sweep:{self.sweep['ts'] if self.sweep else self.anchor_ts}"


# ----------------------------------------------------------------------------------------------- entry locations
def zone_pois(pa: PriceActionResult, n: int, d: int) -> list[Poi]:
    sd = side_word(d)
    out = []
    for z in pa.order_blocks + pa.fvgs + pa.zones + pa.breakers:
        if z.direction != sd or z.status in DEAD or z.low is None or z.high is None or (n - 1) - z.idx > PARAMS["zone_max_age_bars"]:
            continue
        out.append(Poi(z.kind, float(z.low), float(z.high), int(z.ts), int(z.idx), z.evidence))
    return out


def _band(low: float, high: float, atr: float) -> tuple[float, float]:
    if high - low < 0.1 * atr:
        mid = (low + high) / 2
        return mid - 0.05 * atr, mid + 0.05 * atr
    return low, high


def level_pois(cx: Concepts, atr: float, d: int) -> list[Poi]:
    kind = "support" if d == 1 else "resistance"
    out = []
    for e in cx.levels:
        if e.kind != kind:
            continue
        lo, hi = _band(float(e.low), float(e.high), atr)
        out.append(Poi(f"{kind}_band", lo, hi, int(e.ts), int(e.idx), e.evidence, e.meta.get("touches")))
    return out


def broken_level_poi(b: Bars, pa: PriceActionResult, d: int, atr: float) -> Poi | None:
    """The level broken by the most recent same-direction BOS/CHoCH, while it still holds (retest entry)."""
    sd, last = side_word(d), len(b) - 1
    brk = next((e for e in reversed(pa.breaks) if e.direction == sd), None)
    if brk is None or brk.price is None or last - brk.idx > PARAMS["retest_max_age_bars"]:
        return None
    band = PARAMS["retest_band_atr"] * atr
    lvl = float(brk.price)
    after = b.c[brk.idx + 1: last + 1]
    if len(after) and ((d == 1 and (after < lvl - band).any()) or (d == -1 and (after > lvl + band).any())):
        return None  # closed back through the level: the break failed
    return Poi("broken_level", lvl - band, lvl + band, int(brk.ts), int(brk.idx),
               f"level {fmt(lvl)} broken by a {sd} {brk.kind} {last - brk.idx} bars ago (retest of the broken level)")


def rank_pois(b: Bars, pois: list[Poi], d: int, atr: float, group: Group) -> list[tuple[Poi, bool, int | None, float]]:
    """(poi, at_zone, touch_idx, distance_atr) for usable entry locations, best first: zones price is at, then the closest ahead."""
    n, px = len(b), float(b.c[-1])
    tw = group.confirm_bars * PARAMS["touch_window_mult"]
    tol = PARAMS["at_zone_tolerance_atr"] * atr
    ranked = []
    for z in pois:
        if (d == 1 and px < z.low) or (d == -1 and px > z.high):
            continue  # price is through the far side of the zone: not an entry location for this direction
        dist = (px - z.high) if d == 1 else (z.low - px)  # > 0: zone lies behind price (where a retracement meets it)
        start = max(z.idx + 1, n - tw)  # a touch must come AFTER the zone was known
        touch = next((j for j in range(start, n) if b.l[j] <= z.high and b.h[j] >= z.low), None)
        at = touch is not None and dist <= tol
        ahead = not at and 0 < dist <= PARAMS["max_approach_atr"] * atr
        if at or ahead:
            ranked.append((0 if at else 1, max(dist, 0.0), -z.idx, z, at, touch))
    ranked.sort(key=lambda r: r[:3])
    return [(r[3], r[4], r[5], r[1] / atr) for r in ranked]


def find_sweep(pa: PriceActionResult, extra: list[dict], b: Bars, d: int, window: int, atr: float) -> dict | None:
    """Most recent same-direction liquidity sweep within `window` bars (+ the same-direction break that followed it, if any)."""
    sd, last = side_word(d), len(b) - 1
    cands = []
    for e in pa.sweeps:
        if e.direction == sd and last - e.idx <= window:
            label = "swing low" if d == 1 else "swing high"
            eq = "equal_lows" if d == 1 else "equal_highs"
            if any(q.kind == eq and q.price is not None and abs(q.price - e.price) <= 0.1 * atr for q in pa.equal_levels):
                label = "equal lows" if d == 1 else "equal highs"
            cands.append({"label": label, "idx": e.idx, "ts": e.ts, "price": float(e.price), "low": float(e.low), "high": float(e.high),
                          "evidence": e.evidence})
    cands += [x for x in extra if x["direction"] == sd and last - x["idx"] <= window]
    if not cands:
        return None
    sw = max(cands, key=lambda x: x["idx"])
    brk = next((e for e in pa.breaks if e.direction == sd and e.idx >= sw["idx"] and last - e.idx <= window), None)
    return {**sw, "break": brk}


def classify_setup(z: Poi | None, sweep: dict | None, trend: int, d: int, cx: Concepts, last: int, window: int) -> str:
    if sweep and sweep["break"] is not None and sweep["break"].kind == "CHoCH":
        return "liquidity_sweep_reversal"
    if (z is not None and z.kind == "broken_level") or any(
            e.kind == "retest" and e.direction == side_word(d) and last - e.idx <= window for e in cx.breakouts):
        return "bos_retest"
    if trend == d:
        return "trend_pullback"
    return "countertrend_zone" if z is not None else "liquidity_sweep_reversal"


# ----------------------------------------------------------------------------------------------- targets
def target_candidates(b: Bars, pa: PriceActionResult, cx: Concepts, d: int, ref: float, levels: dict, atr: float) -> list[dict]:
    last = len(b) - 1
    out: list[dict] = []

    def add(p, basis: str, strong: bool, ts=None):
        if p is None or not np.isfinite(p):
            return
        if (d == 1 and p > ref) or (d == -1 and p < ref):
            out.append({"price": float(p), "basis": basis, "strong": strong, "ts": None if ts is None else int(ts)})

    for s in confirmed(pa.swings, last):
        if s.kind == ("high" if d == 1 else "low"):
            add(s.price, "swing_high" if d == 1 else "swing_low", False, b.t[s.idx])
    for e in cx.levels:
        add(e.low if d == 1 else e.high, "resistance_band" if d == 1 else "support_band", True, e.ts)
    eq = "equal_highs" if d == 1 else "equal_lows"
    for e in pa.equal_levels:
        if e.kind != eq or e.price is None:
            continue
        later = b.h[e.idx + 1:] if d == 1 else b.l[e.idx + 1:]
        taken = len(later) and ((later.max() > e.price) if d == 1 else (later.min() < e.price))
        if not taken:  # resting (unswept) liquidity only
            add(e.price, "equal_highs_liquidity" if d == 1 else "equal_lows_liquidity", True, e.ts)
    opp = side_word(-d)
    for z in pa.order_blocks + pa.fvgs + pa.zones + pa.breakers:
        if z.direction != opp or z.status in DEAD or z.low is None or z.high is None or last - z.idx > PARAMS["zone_max_age_bars"]:
            continue
        add(z.low if d == 1 else z.high, f"opposing_{z.kind}", z.kind in STRONG_ZONES, z.ts)
    for key, basis in ((("pdh", "previous_day_high"), ("pwh", "previous_week_high")) if d == 1 else
                       (("pdl", "previous_day_low"), ("pwl", "previous_week_low"))):
        add(levels.get(key), basis, False)
    out.sort(key=lambda c: c["price"], reverse=(d == -1))
    merged: list[dict] = []  # levels within 0.1 ATR are one level (strong if any of them is)
    for c in out:
        if merged and abs(c["price"] - merged[-1]["price"]) <= 0.1 * atr:
            if c["strong"] and not merged[-1]["strong"]:
                merged[-1] = {**c}
            continue
        merged.append(c)
    return merged


# ----------------------------------------------------------------------------------------------- plan
def _finish(b: Bars, pa: PriceActionResult, cx: Concepts, d: int, group: Group, spread: float, levels: dict, *, setup_type: str,
            entry_type: str, entry: float, base: float, anchor_ts: int, anchor_note: str, poi: Poi | None, at: bool,
            touch: int | None, sweep: dict | None, atr: float) -> tuple["Plan | None", str | None]:
    n, last = len(b), len(b) - 1
    px = float(b.c[last])
    side = "BUY" if d == 1 else "SELL"
    if (d == 1 and px <= base) or (d == -1 and px >= base):
        return None, f"{side}: price is already beyond the invalidation level {fmt(base)}"
    if touch is not None:
        seg = b.c[touch:n]
        if (d == 1 and (seg < base).any()) or (d == -1 and (seg > base).any()):
            return None, f"{side}: a candle closed beyond {fmt(base)} after the touch (zone failed)"
    buf = PARAMS["stop_buffer_atr"] * atr
    stop = base - buf if d == 1 else base + buf
    risk = (entry - stop) if d == 1 else (stop - entry)
    if risk <= 0:
        return None, f"{side}: entry is beyond the stop"
    warnings: list[str] = []
    blocked: list[str] = []
    if risk < group.min_stop_atr * atr:
        risk = group.min_stop_atr * atr
        stop = entry - risk if d == 1 else entry + risk
        warnings.append(f"stop widened to the {group.label.lower()} minimum of {group.min_stop_atr} ATR")
    if risk > group.max_stop_atr * atr:
        blocked.append(f"structural stop is {risk / atr:.1f} ATR from entry (maximum {group.max_stop_atr} ATR for {group.label.lower()})")
    ref = max(entry, px) if d == 1 else min(entry, px)  # levels price has already passed are not targets
    cands = target_candidates(b, pa, cx, d, ref, levels, atr)

    def rr_of(p: float) -> float:
        return abs(p - entry) / risk

    obstacle = next((c for c in cands if c["strong"] and rr_of(c["price"]) < group.min_rr), None)
    if obstacle and rr_of(obstacle["price"]) < PARAMS["obstacle_block_rr"]:
        blocked.append(f"strong {obstacle['basis'].replace('_', ' ')} at {fmt(obstacle['price'])} is only {rr_of(obstacle['price']):.2f}R away: "
                       f"no room to move before the first target")
    elif obstacle:
        warnings.append(f"strong {obstacle['basis'].replace('_', ' ')} at {fmt(obstacle['price'])} ({rr_of(obstacle['price']):.2f}R) may stop price "
                        f"before TP1: consider partial profit there")
    weak = [c for c in cands if not c["strong"] and rr_of(c["price"]) < group.min_rr]
    if weak:
        warnings.append(f"minor {weak[0]['basis'].replace('_', ' ')} at {fmt(weak[0]['price'])} ({rr_of(weak[0]['price']):.2f}R) sits before TP1")
    gap = PARAMS["min_target_gap_atr"] * atr
    targets: list[dict] = []
    for c in cands:
        if rr_of(c["price"]) < group.min_rr:
            continue
        if not targets or abs(c["price"] - targets[-1]["price"]) >= gap:
            targets.append({**c, "rr": rr_of(c["price"])})
        if len(targets) == 3:
            break
    if not targets:
        if not cands:
            p = entry + d * group.min_rr * risk
            targets = [{"price": float(p), "basis": "volatility_multiple", "strong": False, "ts": None, "rr": group.min_rr}]
            warnings.append(f"price discovery: no structure beyond entry, TP1 is a {group.min_rr:g}R volatility multiple (not a level)")
        else:
            far = max(cands, key=lambda c: rr_of(c["price"]))
            targets = [{**far, "rr": rr_of(far["price"])}]
            blocked.append(f"no structural target at >= {group.min_rr}R (furthest: {far['basis'].replace('_', ' ')} at {rr_of(far['price']):.2f}R)")
    for i, t in enumerate(targets, 1):
        t["label"] = f"TP{i}"
    tp1 = targets[0]["price"]
    if touch is not None and ((d == 1 and (b.h[touch:n] >= tp1).any()) or (d == -1 and (b.l[touch:n] <= tp1).any())):
        return None, f"{side}: TP1 {fmt(tp1)} was already reached after the zone touch (move played out)"
    cost_r = spread / risk
    if cost_r > group.max_cost_r:
        blocked.append(f"spread {fmt(spread)} would cost {cost_r:.2f}R of the risk (limit {group.max_cost_r}R for {group.label.lower()})")
    if poi is not None and at:
        entry_txt = (f"{side} at market {fmt(entry)}: price is at the {side_word(d)} {poi.label} "
                     f"{fmt(poi.low)}–{fmt(poi.high)} ({poi.evidence})")
    elif poi is not None:
        entry_txt = (f"{side} limit at {fmt(entry)}: the near edge of the {poi.label} {fmt(poi.low)}–{fmt(poi.high)}, "
                     f"{abs(px - entry) / atr:.2f} ATR from price ({poi.evidence})")
    else:
        entry_txt = (f"{side} at market {fmt(entry)} after a {sweep['label']} sweep at {fmt(sweep['price'])} and a {side_word(d)} "
                     f"{sweep['break'].kind} at {fmt(sweep['break'].price)}")
    reasoning = {
        "entry": entry_txt,
        "stop": (f"Stop {fmt(stop)} {'below' if d == 1 else 'above'} {fmt(base)} ({anchor_note}) plus a {PARAMS['stop_buffer_atr']} ATR buffer; "
                 f"risk {fmt(risk)} = {risk / atr:.2f} ATR (allowed {group.min_stop_atr}–{group.max_stop_atr})"),
        "targets": [f"{t['label']} {fmt(t['price'])} ({t['rr']:.2f}R): {t['basis'].replace('_', ' ')}" for t in targets],
    }
    plan = Plan(side, d, setup_type, entry_type, float(entry), float(stop), float(base), targets, float(targets[0]["rr"]), float(risk),
                float(atr), float(cost_r), poi, at, touch, int(b.t[touch]) if touch is not None else None, sweep, int(anchor_ts), anchor_note,
                blocked, warnings, reasoning)
    if obstacle:
        plan.obstacle = {"price": obstacle["price"], "basis": obstacle["basis"], "rr": rr_of(obstacle["price"])}
    return plan, None


def _zone_plan(b: Bars, pa: PriceActionResult, cx: Concepts, d: int, group: Group, spread: float, levels: dict, z: Poi, at: bool,
               touch: int | None, sweep: dict | None, setup_type: str, atr: float):
    last, px = len(b) - 1, float(b.c[-1])
    entry = px if at else (z.high if d == 1 else z.low)
    base, anchor_ts, note = (z.low if d == 1 else z.high), z.ts, f"{z.label} {'low' if d == 1 else 'high'}"
    prot = PARAMS["protect_swing_atr"] * atr
    for s in confirmed(pa.swings, last):
        if s.kind != ("low" if d == 1 else "high"):
            continue
        near = (z.low - prot <= s.price <= z.high) if d == 1 else (z.low <= s.price <= z.high + prot)
        if near and ((d == 1 and s.price < base) or (d == -1 and s.price > base)):
            base, anchor_ts, note = s.price, int(b.t[s.idx]), f"protecting swing {'low' if d == 1 else 'high'}"
    if setup_type == "liquidity_sweep_reversal" and sweep is not None:
        ext = sweep["low"] if d == 1 else sweep["high"]
        if (d == 1 and ext < base) or (d == -1 and ext > base):
            base, anchor_ts, note = ext, sweep["ts"], f"{sweep['label']} sweep extreme"
    return _finish(b, pa, cx, d, group, spread, levels, setup_type=setup_type, entry_type="market" if at else "limit", entry=entry,
                   base=base, anchor_ts=anchor_ts, anchor_note=note, poi=z, at=at, touch=touch, sweep=sweep, atr=atr)


def build_plan(b: Bars, pa: PriceActionResult, cx: Concepts, d: int, group: Group, spread: float, levels: dict,
               extra_sweeps: list[dict]) -> tuple[Plan | None, str | None]:
    """Best plan for direction d (a non-blocked one if any exists), or (None, reason)."""
    n, last = len(b), len(b) - 1
    side = "BUY" if d == 1 else "SELL"
    atr = last_atr(pa)
    if atr is None:
        return None, "ATR unavailable"
    window = group.confirm_bars * PARAMS["sweep_window_mult"]
    sweep = find_sweep(pa, extra_sweeps, b, d, window, atr)
    trend = int(pa.trend[last]) if len(pa.trend) else 0
    pois = zone_pois(pa, n, d) + level_pois(cx, atr, d)
    bl = broken_level_poi(b, pa, d, atr)
    if bl is not None:
        pois.append(bl)
    plans: list[Plan] = []
    reasons: list[str] = []
    for z, at, touch, _ in rank_pois(b, pois, d, atr, group)[:6]:
        stype = classify_setup(z, sweep, trend, d, cx, last, window)
        p, why = _zone_plan(b, pa, cx, d, group, spread, levels, z, at, touch, sweep, stype, atr)
        if p is None:
            reasons.append(why)
            continue
        plans.append(p)
        if not p.blocked:
            break
    if not any(not p.blocked for p in plans) and sweep is not None and sweep["break"] is not None:
        stype = classify_setup(None, sweep, trend, d, cx, last, window)
        base = sweep["low"] if d == 1 else sweep["high"]
        p, why = _finish(b, pa, cx, d, group, spread, levels, setup_type=stype, entry_type="market", entry=float(b.c[last]), base=base,
                         anchor_ts=sweep["ts"], anchor_note=f"{sweep['label']} sweep extreme", poi=None, at=True, touch=sweep["idx"],
                         sweep=sweep, atr=atr)
        if p is not None:
            plans.append(p)
        else:
            reasons.append(why)
    if not plans:
        return None, (reasons[0] if reasons else
                      f"{side}: no logical entry location (no zone, S/R band or retest within {PARAMS['max_approach_atr']} ATR, "
                      f"and no liquidity sweep followed by a structure break)")
    return next((p for p in plans if not p.blocked), plans[0]), None


def rejection_after(pa: PriceActionResult, d: int, since_idx: int) -> Event | None:
    rej = BULL_REJ if d == 1 else BEAR_REJ
    sd = side_word(d)
    return next((e for e in reversed(pa.candles) if e.direction == sd and e.kind in rej and e.idx >= since_idx), None)
