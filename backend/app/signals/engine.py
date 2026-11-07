"""Signal engine: top-down multi-timeframe evaluation. Pure and causal (docs/SIGNAL_ENGINE.md).

Input: `frames` = complete candles per timeframe (already "as of" the evaluation time). Output: per-timeframe trade plans with entry
state, final instruction, 100-point confluence checklist and reasons; plus the instrument summary and report. The live service and the
historical replay both call `evaluate_timeframe` / `evaluate_instrument`, so the track record measures exactly what the page shows.
"""
from dataclasses import dataclass, field

import numpy as np

from app.market_data.bars import Bars
from app.opportunities.setup import Concepts, compute_concepts
from app.price_action.engine import PriceActionResult, analyze_price_action
from app.signals.config import (
    CHAINS,
    CONFIG_VERSION,
    GROUP_TFS,
    GROUPS,
    OVERALL_WEIGHTS,
    PARAMS,
    PROBABILITY_NOTE,
    SCORE_LABEL,
    SIGNAL_TFS,
    STATE_ORDER,
    THRESHOLDS,
    Group,
    spread_for,
)
from app.signals.context import (
    as_of,
    atr_rank,
    fmt,
    in_active_session,
    iso,
    period_levels,
    period_sweeps,
    read_tf,
    session_name,
)
from app.signals.plan import Plan, build_plan, rejection_after, side_word, zone_pois
from app.signals.scoring import score_plan

ACTIONABLE = ("ENTRY_READY", "WAITING_FOR_CONFIRMATION", "SETUP_DEVELOPING")
TF_RANK = {tf: i for i, tf in enumerate(SIGNAL_TFS)}
DISCLAIMER = ("Analysis only: no orders are placed and no broker is connected. The confluence score measures setup quality; it is not a "
              "probability of winning. Past behaviour does not guarantee future results.")


@dataclass
class Frame:
    """Complete candles of one timeframe plus lazily computed (and cached) price action, concepts and market read."""
    tf: str
    bars: Bars | None
    status: str = "completed"  # completed | insufficient_data | unsupported | failed
    reason: str | None = None
    stale_bars: float | None = None
    derived_from: str | None = None
    quality: dict = field(default_factory=dict)
    _pa: PriceActionResult | None = None
    _cx: Concepts | None = None
    _read: dict | None = None

    @property
    def n(self) -> int:
        return 0 if self.bars is None else len(self.bars)

    @property
    def pa(self) -> PriceActionResult:
        if self._pa is None:
            self._pa = analyze_price_action(self.bars)
        return self._pa

    @property
    def cx(self) -> Concepts:
        if self._cx is None:
            self._cx = compute_concepts(self.bars, self.pa)
        return self._cx

    @property
    def read(self) -> dict:
        if self._read is None:
            self._read = read_tf(self.tf, self.bars, self.pa)
        return self._read


def view_at(f: Frame | None, end_ts: int, min_bars: int) -> Frame | None:
    """The frame as it was known at end_ts (complete candles only). Returns the same object (and its caches) when nothing is cut."""
    if f is None or f.bars is None or not len(f.bars):
        return None
    cut = as_of(f.bars, end_ts)
    if len(cut) < min_bars:
        return None
    if len(cut) == len(f.bars):
        return f
    return Frame(f.tf, cut, f.status, f.reason, None, f.derived_from, f.quality)


def _empty(base: dict, status: str, reason: str, market: dict | None = None) -> dict:
    return {**base, "status": status, "state": "NO_SETUP", "instruction": "NO TRADE", "decision": "NO TRADE", "direction": None, "score": None,
            "grade": None, "buy_score": None, "sell_score": None, "reason": reason, "reasons_against": [reason], "reasons_for": [],
            "market": market, "targets": [], "factors": [], "conditions": [], "warnings": [], "blocked": [],
            "probability_note": PROBABILITY_NOTE, "win_probability": None}


def _fresh_break(pa: PriceActionResult, d: int, last: int) -> dict | None:
    sw = side_word(d)
    e = next((x for x in reversed(pa.breaks) if x.direction == sw and last - x.idx <= PARAMS["fresh_break_bars"]), None)
    if e is None:
        return None
    ago = last - e.idx
    return {"text": f"{sw} {e.kind} at {fmt(e.price)} {ago} bar{'s' if ago != 1 else ''} ago", "ts": e.ts, "kind": e.kind}


def _ltf(plan: Plan, f: Frame, cf: Frame) -> tuple[dict | None, dict | None]:
    """(lower-timeframe structure shift, rejection candle) that happened at/after the zone touch."""
    if not plan.at_zone or plan.touch_ts is None:
        return None, None
    sw = side_word(plan.d)
    brk = next((e for e in reversed(cf.pa.breaks) if e.direction == sw and e.ts >= plan.touch_ts), None)
    ltf = ({"text": f"{sw} {brk.kind} on {cf.tf} at {fmt(brk.price)} ({iso(brk.ts)[:16].replace('T', ' ')} UTC)", "ts": brk.ts}
           if brk is not None else None)
    rej = rejection_after(f.pa, plan.d, plan.touch_idx)
    where = f.tf
    if rej is None and cf is not f:
        k = int(np.searchsorted(cf.bars.t, plan.touch_ts, side="left"))
        rej, where = rejection_after(cf.pa, plan.d, k), cf.tf
    rj = ({"text": f"{rej.kind.replace('_', ' ')} on {where} at {fmt(rej.price)} ({iso(rej.ts)[:16].replace('T', ' ')} UTC)", "ts": rej.ts}
          if rej is not None else None)
    return ltf, rj


def _confluence(plan: Plan, f: Frame) -> str | None:
    z = plan.poi
    if z is None:
        return None
    tol = PARAMS["confluence_atr"] * plan.atr
    kind = "support" if plan.d == 1 else "resistance"
    for e in f.cx.levels:
        same = z.kind == f"{kind}_band" and int(e.ts) == z.ts
        if e.kind == kind and not same and e.low - tol <= z.high and e.high + tol >= z.low:
            return f"{kind} band {fmt(e.low)}–{fmt(e.high)} ({e.meta.get('touches')} touches)"
    tl = "trendline_support" if plan.d == 1 else "trendline_resistance"
    for e in f.cx.trendlines:
        if e.kind == tl and z.low - tol <= e.meta["value_now"] <= z.high + tol:
            return f"{e.meta['touches']}-touch trendline at {fmt(e.meta['value_now'])}"
    for o in zone_pois(f.pa, f.n, plan.d):
        if o.kind != z.kind and o.low <= z.high and o.high >= z.low:
            return f"overlaps a {o.label} {fmt(o.low)}–{fmt(o.high)}"
    return None


def _decide(plan: Plan, score: int, ltf: dict | None, rej: dict | None, tf: str, confirm_tf: str) -> tuple[str, str, list[str]]:
    T = THRESHOLDS
    d, side, sw = plan.d, plan.direction, side_word(plan.d)
    beyond = "below" if d == 1 else "above"
    if plan.blocked:
        return ("WATCHLIST" if score >= T["watch"] else "NO_SETUP"), "NO TRADE", []
    if score < T["watch"]:
        return "NO_SETUP", "NO TRADE", []
    if score < T["signal"]:
        return "WATCHLIST", "NO TRADE", []
    tp1 = plan.targets[0]["price"]
    if not plan.at_zone:
        z = plan.poi
        if score >= T["preferred"]:
            return "SETUP_DEVELOPING", "PLACE LIMIT ORDER", [
                f"{side} limit at {fmt(plan.entry)} · stop {fmt(plan.stop_loss)} · TP1 {fmt(tp1)}",
                f"Cancel the order if a {tf} candle closes {beyond} {fmt(plan.invalidation)} or TP1 trades before the fill"]
        return "SETUP_DEVELOPING", "WAIT FOR CONFIRMATION", [
            f"Price retraces into the {z.label} {fmt(z.low)}–{fmt(z.high)}",
            f"Then a {sw} BOS/CHoCH on {confirm_tf} or a {sw} rejection candle at the zone"]
    confirmed = bool(ltf or rej or (plan.poi is None and plan.sweep and plan.sweep.get("break") is not None))
    if confirmed:
        chase = plan.entry + d * 0.3 * plan.risk
        return "ENTRY_READY", "EXECUTE NOW", [
            f"Enter {side} near {fmt(plan.entry)}; skip it if price is already {'above' if d == 1 else 'below'} {fmt(chase)} (never chase)",
            f"Invalid if a {tf} candle closes {beyond} {fmt(plan.invalidation)}"]
    return "WAITING_FOR_CONFIRMATION", "WAIT FOR CONFIRMATION", [
        f"A {sw} BOS/CHoCH on {confirm_tf}, or a {sw} rejection candle (engulfing, pin bar, hammer/star) at the zone",
        f"No {tf} close {beyond} {fmt(plan.invalidation)}"]


def live_adjust(state: str, instr: str, conds: list[str], at_zone: bool, live: dict | None, spread: float) -> tuple[str, str, list[str]]:
    """Live-only downgrades: never EXECUTE / PLACE LIMIT while the market is closed or the live spread is abnormal."""
    conds = list(conds)
    if not live:
        return state, instr, conds
    if live.get("market_open") is False and (state == "ENTRY_READY" or instr == "PLACE LIMIT ORDER"):
        state = "WAITING_FOR_CONFIRMATION" if at_zone else "SETUP_DEVELOPING"
        instr = "WAIT FOR CONFIRMATION"
        conds.insert(0, "Market is closed: re-check after the open (spreads widen at the open)")
    ls = live.get("live_spread")
    if ls is not None and ls > PARAMS["abnormal_spread_mult"] * spread and (state == "ENTRY_READY" or instr == "PLACE LIMIT ORDER"):
        state = "WAITING_FOR_CONFIRMATION" if at_zone else "SETUP_DEVELOPING"
        instr = "WAIT FOR CONFIRMATION"
        conds.insert(0, f"Live spread {fmt(ls)} is more than {PARAMS['abnormal_spread_mult']:g}x the normal {fmt(spread)}: wait for it to normalise")
    return state, instr, conds


def _reasons(sc: dict, plan: Plan, bias: list[tuple[str, dict | None]]) -> tuple[list[str], list[str]]:
    checks = [c for f in sc["factors"] for c in f["checks"] if c["max"] > 0]
    met = sorted((c for c in checks if c["met"]), key=lambda c: -c["points"])
    unmet = sorted((c for c in checks if not c["met"] and c["max"] >= 4), key=lambda c: -c["max"])
    pro = [f"{c['label']}: {c['detail']}" for c in met]
    con = [f"Counter-trend: {tf} is {r['label'].lower()}" for tf, r in bias if r is not None and r["direction"] == -plan.d]
    con += [f"{c['label']} missing: {c['detail']}" for c in unmet]
    con += [f"Blocked: {x}" for x in plan.blocked] + [w[0].upper() + w[1:] for w in plan.warnings]
    con.append("News filter unavailable: check the economic calendar before trading")
    return pro, con


def _plan_out(plan: Plan, sc: dict, state: str, instr: str, conds: list[str], bias, group: Group, tf: str, end_ts: int, step: int,
              spread: float) -> dict:
    pro, con = _reasons(sc, plan, bias)
    actionable = state in ACTIONABLE
    z = plan.poi
    where = f"{z.label} {fmt(z.low)}–{fmt(z.high)}" if z is not None else f"{plan.sweep['label']} sweep"
    return {
        "state": state, "instruction": instr, "direction": plan.direction if actionable else None,
        "decision": plan.direction if actionable else ("WAIT" if state == "WATCHLIST" else "NO TRADE"),
        "side": plan.direction, "score": sc["score"], "grade": "A" if sc["score"] >= THRESHOLDS["preferred"] else "B" if sc["score"] >= THRESHOLDS["signal"] else None,
        "score_label": SCORE_LABEL, "checks_met": sc["met"], "checks_total": sc["total"], "factors": sc["factors"],
        "setup_type": plan.setup_type, "entry_type": plan.entry_type, "entry": plan.entry,
        "entry_zone": [z.low, z.high] if z is not None else None, "zone_kind": z.kind if z is not None else None,
        "stop_loss": plan.stop_loss, "invalidation": plan.invalidation,
        "targets": [{"label": t["label"], "price": t["price"], "rr": round(t["rr"], 2), "basis": t["basis"]} for t in plan.targets],
        "risk_reward": round(plan.rr, 2), "risk": plan.risk, "risk_atr": round(plan.risk_atr, 2), "atr": plan.atr, "cost_r": round(plan.cost_r, 3),
        "spread": spread, "reasons_for": pro, "reasons_against": con, "conditions": conds, "warnings": plan.warnings, "blocked": plan.blocked,
        "reasoning": plan.reasoning, "setup_key": plan.key,
        "summary": f"{plan.direction} {tf} {plan.setup_type.replace('_', ' ')} at {where}: {sc['score']}/100",
        "signal_ts": end_ts, "signal_time": iso(end_ts), "valid_until_ts": end_ts + group.expiry_bars * step,
        "valid_until": iso(end_ts + group.expiry_bars * step),
    }


def evaluate_timeframe(symbol: str, tf: str, frames: dict[str, Frame], *, live: dict | None = None, spread: float | None = None) -> dict:
    chain = CHAINS[tf]
    group = GROUPS[chain.group]
    base = {"timeframe": tf, "group": group.key, "group_label": group.label, "bias_tfs": list(chain.bias), "confirm_tf": chain.confirm,
            "probability_note": PROBABILITY_NOTE, "win_probability": None}
    f = frames.get(tf)
    if f is None or f.bars is None or f.n < PARAMS["min_setup_bars"]:
        why = (f.reason if f is not None and f.reason else None) or f"fewer than {PARAMS['min_setup_bars']} complete {tf} candles"
        return _empty(base, "insufficient_data", why)
    if f.stale_bars is not None and f.stale_bars > group.max_stale_bars:
        return _empty(base, "stale", f"latest {tf} candle is {f.stale_bars:.0f} bars old (limit {group.max_stale_bars}): sync data first", f.read)
    b, pa = f.bars, f.pa
    last = len(b) - 1
    end_ts = int(b.t[-1]) + int(b.step)
    setup_read = f.read
    bias = []
    for btf in chain.bias:
        v = view_at(frames.get(btf), end_ts, PARAMS["min_bias_bars"])
        bias.append((btf, v.read if v is not None else None))
    cf = f if chain.confirm == tf else (view_at(frames.get(chain.confirm), end_ts, PARAMS["min_bias_bars"]) or f)
    daily = view_at(frames.get("1D"), end_ts, 1) if b.step < 86400 else None
    weekly = view_at(frames.get("1W"), end_ts, 1) if b.step < 604800 else None
    levels = period_levels(daily.bars if daily else None, weekly.bars if weekly else None)
    window = group.confirm_bars * PARAMS["sweep_window_mult"]
    extra = period_sweeps(b, levels, last - window)
    sp = spread if spread is not None else spread_for(symbol, float(b.c[-1]))
    atr_pct = atr_rank(pa, b)
    session_ok = in_active_session(end_ts) if group.session_filter else None
    sides: dict[int, dict] = {}
    for d in (1, -1):
        plan, why = build_plan(b, pa, f.cx, d, group, sp, levels, extra)
        if plan is None:
            sides[d] = {"plan": None, "reason": why}
            continue
        pdz = pa.premium_discount
        zone_pos = (plan.entry - pdz.low) / (pdz.high - pdz.low) if pdz is not None and pdz.high > pdz.low else None
        ltf, rej = _ltf(plan, f, cf)
        sc = score_plan(plan=plan, setup_tf=tf, group=group, bias=bias, setup_read=setup_read, fresh_break=_fresh_break(pa, d, last),
                        sweep=plan.sweep, zone_pos=zone_pos, confluence=_confluence(plan, f), ltf_break=ltf, rejection=rej,
                        confirm_tf=cf.tf, atr_pct=atr_pct, session_ok=session_ok)
        state, instr, conds = _decide(plan, sc["score"], ltf, rej, tf, cf.tf)
        sides[d] = {"plan": plan, "score": sc, "state": state, "instr": instr, "conds": conds}
    buy_s = sides[1]["score"]["score"] if sides[1].get("plan") else None
    sell_s = sides[-1]["score"]["score"] if sides[-1].get("plan") else None
    base.update(status="ok", market=setup_read, buy_score=buy_s, sell_score=sell_s, as_of=iso(end_ts), as_of_ts=end_ts,
                bias=[{"timeframe": t, "label": r["label"] if r else "unavailable", "direction": r["direction"] if r else None,
                       "structure": r["structure"] if r else None, "observation": r["observation"] if r else None} for t, r in bias],
                confirm_used=cf.tf)
    ranked = sorted((s for s in sides.values() if s.get("plan")), key=lambda s: (STATE_ORDER[s["state"]], s["score"]["score"]), reverse=True)
    if not ranked:
        why = "; ".join(s["reason"] for s in (sides[1], sides[-1]) if s.get("reason"))
        return {**_empty(base, "ok", why or "no setup", setup_read), **{k: base[k] for k in ("buy_score", "sell_score", "bias", "as_of", "as_of_ts", "confirm_used")}}
    top = ranked[0]
    if (len(ranked) > 1 and top["state"] in ACTIONABLE and ranked[1]["state"] == top["state"]
            and ranked[1]["score"]["score"] == top["score"]["score"]):
        return {**_empty(base, "ok", "BUY and SELL setups qualify with the same score: conflicting evidence, no trade", setup_read),
                **{k: base[k] for k in ("buy_score", "sell_score", "bias", "as_of", "as_of_ts", "confirm_used")}}
    plan: Plan = top["plan"]
    state, instr, conds = live_adjust(top["state"], top["instr"], top["conds"], plan.at_zone, live, sp)
    out = {**base, **_plan_out(plan, top["score"], state, instr, conds, bias, group, tf, end_ts, int(b.step), sp)}
    other = sides[-plan.d]
    out["other_side"] = ({"direction": other["plan"].direction, "score": other["score"]["score"], "state": other["state"]}
                         if other.get("plan") else {"direction": "SELL" if plan.d == 1 else "BUY", "score": None, "reason": other.get("reason")})
    return out


def overall_bias(rows: dict[str, dict]) -> dict:
    used = [(tf, w, rows[tf]["direction"]) for tf, w in OVERALL_WEIGHTS.items() if tf in rows]
    den = sum(w for _, w, _ in used)
    score = sum(w * d for _, w, d in used) / den if den else 0.0
    label = "Bullish" if score > 0.33 else "Bearish" if score < -0.33 else "Mixed"
    groups = {}
    for name, tfs in GROUP_TFS.items():
        ds = [rows[t]["direction"] for t in tfs if t in rows]
        if not ds:
            groups[name] = "no data"
            continue
        s = sum(ds)
        groups[name] = "Bullish" if s > 0 else "Bearish" if s < 0 else "Mixed"
    detail = ", ".join(f"{tf} {rows[tf]['label'].lower()}" for tf, _, _ in used) or "no timeframe data"
    return {"label": label, "score": round(score, 2), "direction": 1 if label == "Bullish" else -1 if label == "Bearish" else 0,
            "detail": detail, "groups": groups}


def _row(f: Frame | None, tf: str) -> dict:
    if f is None or f.bars is None or f.n < PARAMS["min_bias_bars"]:
        return {"timeframe": tf, "status": f.status if f is not None else "insufficient_data", "n_bars": f.n if f else 0,
                "reason": (f.reason if f is not None else None) or "not enough stored candles"}
    r = f.read
    return {"timeframe": tf, "status": f.status, "n_bars": f.n, "stale_bars": f.stale_bars, "derived_from": f.derived_from,
            "class": r["class"], "label": r["label"], "direction": r["direction"], "structure": r["structure"], "observation": r["observation"],
            "last_event": r["last_event"], "zone": r["zone"], "range_position": r["range_position"], "last_close": r["last_close"],
            "last_ts": r["last_ts"], "close_time": iso(r["close_ts"])}


def evaluate_instrument(symbol: str, frames: dict[str, Frame], *, live: dict | None = None, setup_tfs: tuple[str, ...] | None = None) -> dict:
    plans = [evaluate_timeframe(symbol, tf, frames, live=live) for tf in (setup_tfs or SIGNAL_TFS)]
    rows = [_row(frames.get(tf), tf) for tf in SIGNAL_TFS]
    readable = {r["timeframe"]: r for r in rows if "direction" in r}
    active = sorted((p for p in plans if p["state"] in ACTIONABLE),
                    key=lambda p: (STATE_ORDER[p["state"]], p["score"] or 0, TF_RANK[p["timeframe"]]), reverse=True)
    watch = sorted((p for p in plans if p["state"] == "WATCHLIST"), key=lambda p: (p["score"] or 0, TF_RANK[p["timeframe"]]), reverse=True)
    best = active[0] if active else None
    last_ts = max((r["last_ts"] for r in rows if r.get("last_ts")), default=None)
    out = {"symbol": symbol, "config_version": CONFIG_VERSION, "overall": overall_bias(readable), "timeframes": rows, "plans": plans,
           "active": [p["timeframe"] for p in active], "watchlist": [p["timeframe"] for p in watch], "best": best,
           "counts": {"entry_ready": sum(p["state"] == "ENTRY_READY" for p in plans),
                      "waiting": sum(p["state"] == "WAITING_FOR_CONFIRMATION" for p in plans),
                      "developing": sum(p["state"] == "SETUP_DEVELOPING" for p in plans), "watchlist": len(watch),
                      "no_setup": sum(p["state"] in ("NO_SETUP", "TRADE_INVALIDATED", "TRADE_EXPIRED") for p in plans)},
           "session": session_name(last_ts) if last_ts else None, "disclaimer": DISCLAIMER,
           "news_filter": {"available": False, "note": "No economic-calendar integration: high-impact news is NOT filtered. Check the calendar manually."}}
    out["report"] = build_report(out, live)
    return out


def build_report(res: dict, live: dict | None) -> dict:
    """Structured analyst report (overview, multi-timeframe table, decision, execution plan, reasons, final instruction)."""
    best = res["best"]
    quote = (live or {}).get("quote") or {}
    ov = res["overall"]
    decision = best["decision"] if best else "NO TRADE"
    final = best["instruction"] if best else "NO TRADE"
    lines = [f"{res['symbol']} — overall {ov['label'].lower()} ({ov['detail']})."]
    if best:
        tps = ", ".join(f"{t['label']} {fmt(t['price'])} ({t['rr']:.2f}R)" for t in best["targets"])
        lines += [f"Decision: {decision} on {best['timeframe']} ({best['setup_type'].replace('_', ' ')}), confluence {best['score']}/100. "
                  f"{PROBABILITY_NOTE}.",
                  f"Plan: {best['entry_type']} entry {fmt(best['entry'])}, stop {fmt(best['stop_loss'])}, {tps}. "
                  f"Bias from {', '.join(best['bias_tfs']) or 'none'}, confirmation on {best['confirm_tf']}.",
                  f"Final instruction: {final}."]
    else:
        lines.append("Decision: NO TRADE — no timeframe has a setup that meets the 60/100 threshold and every must-pass rule.")
    return {"overview": {"symbol": res["symbol"], "price": quote.get("price"), "bid": quote.get("bid"), "ask": quote.get("ask"),
                         "spread": quote.get("spread"), "session": res["session"], "market_open": (live or {}).get("market_open"),
                         "overall": ov["label"]},
            "mtf_table": [{k: r.get(k) for k in ("timeframe", "label", "structure", "observation")} for r in res["timeframes"] if r.get("label")],
            "decision": {"action": decision, "timeframe": best["timeframe"] if best else None,
                         "setup_type": best["setup_type"] if best else None, "confluence_score": best["score"] if best else None,
                         "win_probability": None, "probability_note": PROBABILITY_NOTE},
            "reasons_for": best["reasons_for"][:6] if best else [], "reasons_against": best["reasons_against"][:6] if best else [],
            "final_instruction": final, "text": "\n".join(lines)}
