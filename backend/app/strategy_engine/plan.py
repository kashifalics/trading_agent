"""Trade-plan builder (DESIGN section 5): entry, stop-loss, TP1-TP3, reward:risk, costs, entry status and expiry for one strategy
candidate, rounded to the instrument's tick and validated. Any rule failure returns no plan and the rule's name: a plan is never
repaired by moving a level."""
import math

from app.strategy_engine.config import (
    CHASE_R,
    MAX_ENTRY_DISTANCE_ATR,
    READY_EXPIRY_BARS,
    STOP_BUFFER_ATR,
    TARGETS,
    Group,
)
from app.strategy_engine.context import TFData, alive
from app.strategy_engine.strategies.base import Candidate, fmt


def tick_of(precision: int) -> float:
    return 10.0 ** (-precision)


def round_to(x: float, tick: float, mode: str) -> float:
    """mode: nearest | up | down, on the instrument's tick grid (tolerant of float noise)."""
    q = x / tick
    n = {"nearest": round(q), "up": math.ceil(q - 1e-9), "down": math.floor(q + 1e-9)}[mode]
    return round(n * tick, 10)


def structural_levels(t: TFData, d: int, beyond: float) -> list[tuple[float, str]]:
    """Identifiable levels beyond `beyond` in the trade's direction, nearest first: confirmed swing highs (lows), equal-high (low)
    clusters, the previous day / week high (low) and the near edge of opposite zones, all known by the last candle."""
    i = t.last
    out: list[tuple[float, str]] = []
    kind = "high" if d > 0 else "low"
    for s in t.swings_until(i, kind):
        out.append((float(s.price), f"swing {kind}"))
    for e in t.pa.equal_levels:
        if e.idx <= i and e.price is not None and e.kind == ("equal_highs" if d > 0 else "equal_lows"):
            out.append((float(e.price), e.kind.replace("_", " ")))
    for key, name in (("pdh", "previous day high"), ("pwh", "previous week high")) if d > 0 else (("pdl", "previous day low"), ("pwl", "previous week low")):
        if t.levels.get(key) is not None:
            out.append((float(t.levels[key]), name))
    opposite = "bearish" if d > 0 else "bullish"
    for z in t.pa.order_blocks + t.pa.zones:
        if z.idx <= i and z.direction == opposite and alive(z, i) and z.low is not None and z.high is not None:
            out.append((float(z.low if d > 0 else z.high), z.kind.replace("_", " ")))
    out = [(p, n) for p, n in out if (p - beyond) * d > 0]
    out.sort(key=lambda x: (x[0] - beyond) * d)
    return out


def pick_targets(levels: list[tuple[float, str]], entry: float, risk: float, d: int) -> list[dict]:
    """TP1 = nearest structural level at 1.5-4R (else 2R), TP2 = next <= 6R at least 0.75R beyond TP1 (else max(TP1+1R, 3R)), TP3 =
    next <= 10R at least 0.75R beyond TP2 (else max(TP2+1R, 5R)). A risk-objective target is labelled as such, never as a level."""
    p = TARGETS

    def r_of(px: float) -> float:
        return (px - entry) * d / risk

    out: list[dict] = []
    specs = ((p["tp1_min_r"], p["tp1_max_r"], p["tp1_default_r"]), (None, p["tp2_max_r"], p["tp2_default_r"]),
             (None, p["tp3_max_r"], p["tp3_default_r"]))
    for k, (lo, hi, default) in enumerate(specs, 1):
        floor_r = lo if k == 1 else out[-1]["rr"] + p["min_gap_r"]
        hit = next(((px, name) for px, name in levels if floor_r <= r_of(px) <= hi), None)
        if hit:
            out.append({"label": f"TP{k}", "price": hit[0], "rr": r_of(hit[0]), "basis": hit[1]})
        else:
            rr = default if k == 1 else max(out[-1]["rr"] + 1.0, default)
            out.append({"label": f"TP{k}", "price": entry + d * rr * risk, "rr": rr, "basis": f"risk objective {round(rr, 1):g}R"})
    return out


def build_plan(c: Candidate, t: TFData, *, group: Group, precision: int, spread: float, price_now: float | None) -> tuple[dict | None, str | None]:
    if c.entry is None or c.invalidation is None or c.entry_mode is None:
        return None, "no entry or invalidation defined"
    i, d, b = t.last, c.direction, t.bars
    a = float(t.atr[i])
    if not (a > 0 and math.isfinite(a)):
        return None, "ATR undefined on this history"
    tick = tick_of(precision)
    if c.entry_mode == "stop":
        entry = round_to(c.entry + d * tick, tick, "up" if d > 0 else "down")
    else:
        entry = round_to(c.entry, tick, "nearest")
    stop = round_to(c.invalidation - d * (STOP_BUFFER_ATR * a + spread), tick, "down" if d > 0 else "up")
    risk = (entry - stop) * d
    if not risk > 0:
        return None, f"entry {fmt(entry)} is not beyond the stop {fmt(stop)}"
    if risk < group.min_stop_atr * a:
        return None, f"stop too tight: {risk / a:.2f} ATR (minimum {group.min_stop_atr} for {group.label.lower()}): noise would hit it"
    if risk > group.max_stop_atr * a:
        return None, f"stop too wide: {risk / a:.2f} ATR (maximum {group.max_stop_atr} for {group.label.lower()})"
    ref = price_now if price_now is not None and math.isfinite(price_now) else float(b.c[i])
    if abs(entry - ref) > MAX_ENTRY_DISTANCE_ATR * a:
        return None, f"entry {fmt(entry)} is {abs(entry - ref) / a:.1f} ATR from price (limit {MAX_ENTRY_DISTANCE_ATR:g})"
    if c.targets:
        tg = [{"label": f"TP{k}", "price": px, "rr": (px - entry) * d / risk, "basis": name} for k, (px, name) in enumerate(c.targets, 1)]
    else:
        tg = pick_targets(structural_levels(t, d, entry), entry, risk, d)
    for x in tg:
        x["price"] = round_to(x["price"], tick, "down" if d > 0 else "up")  # toward the entry: conservative
        x["rr"] = (x["price"] - entry) * d / risk
        x["rr_net"] = ((x["price"] - entry) * d - spread) / risk
    seq = [stop, entry] + [x["price"] for x in tg]
    if not all(math.isfinite(v) for v in seq):
        return None, "a price level is not a finite number"
    ordered = all((seq[k + 1] - seq[k]) * d > 0 for k in range(len(seq) - 1))
    if not ordered:
        return None, (f"levels out of order for a {'BUY' if d > 0 else 'SELL'} (stop {fmt(stop)}, entry {fmt(entry)}, "
                      + ", ".join(f"{x['label']} {fmt(x['price'])}" for x in tg) + ")")
    if any(x["rr"] <= 0 for x in tg):
        return None, "a target has no positive reward:risk"
    if tg[0]["rr"] < TARGETS["tp1_min_r"] - 1e-9:
        return None, f"TP1 {fmt(tg[0]['price'])} offers only {tg[0]['rr']:.2f}R (minimum {TARGETS['tp1_min_r']:g}R)"
    cost_r = spread / risk
    if cost_r > group.max_cost_r:
        return None, f"the spread {fmt(spread)} would cost {cost_r:.2f}R (limit {group.max_cost_r}R for {group.label.lower()})"
    # entry status
    signal_idx = c.signal_idx if c.signal_idx is not None else i
    age = i - signal_idx
    expiry_bars = READY_EXPIRY_BARS if c.status == "ready" else group.pending_expiry_bars
    moved = (ref - entry) * d  # > 0: price is beyond the entry in the trade's direction
    if (ref - stop) * d <= 0:
        status = "INVALIDATED"
    elif (ref - tg[0]["price"]) * d >= 0:
        status = "ENTRY MISSED"
    elif age > expiry_bars:
        status = "EXPIRED"
    elif c.entry_mode == "market":
        status = "READY" if moved <= CHASE_R * risk else "ENTRY MISSED"
    elif c.entry_mode == "limit":
        status = "READY" if moved <= 0 else "WAITING FOR ENTRY"
    else:  # stop entry: triggered once price trades through it
        status = "WAITING FOR ENTRY" if moved < 0 else ("READY" if moved <= CHASE_R * risk else "ENTRY MISSED")
    step = int(b.step)
    signal_time = int(b.t[signal_idx]) + step
    return {
        "entry_mode": c.entry_mode, "entry": entry, "stop_loss": stop,
        "entry_zone": sorted(round_to(z, tick, "nearest") for z in c.entry_zone) if c.entry_zone else None,
        "risk": risk, "risk_atr": risk / a, "targets": tg, "risk_reward": tg[0]["rr"], "spread": spread, "cost_r": cost_r,
        "invalidation": c.invalidation,
        "invalidation_text": f"a {t.tf} close {'below' if d > 0 else 'above'} {fmt(c.invalidation)}",
        "entry_status": status, "trigger": c.trigger, "signal_time": signal_time, "signal_idx": signal_idx,
        "expires_at": signal_time + expiry_bars * step, "price_now": ref, "tick": tick, "atr": a,
    }, None
