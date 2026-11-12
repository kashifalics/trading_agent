"""Translate each module's native output into the one decision function (app.decision.core.decide). No thresholds are invented here:
every condition comes from the module's own rules (the signal engine's must-pass rules, score thresholds and confirmation logic, the
opportunity scanner's states, the decision engine's BUY / SELL / WAIT)."""
from app.decision.core import Check, DecisionInput, decide
from app.signals.config import THRESHOLDS

VALIDATION_TEXT = {
    "validated": ("Validated", "These rules passed out-of-sample validation."),
    "untested": ("Not validated", "No out-of-sample test of these rules exists yet."),
    "no_edge": ("Not validated", "Tested out of sample: no edge distinguishable from zero."),
    "negative": ("Not validated", "Tested out of sample: the rules lost money after costs."),
}


def _validation(status: str | None, note: str | None = None) -> dict:
    s = status or "untested"
    label, text = VALIDATION_TEXT.get(s, VALIDATION_TEXT["untested"])
    return {"status": "validated" if s == "validated" else "not_validated", "label": label, "note": note or text, "research_status": s}


def _blocked_check(text: str) -> Check:
    t = text.lower()
    if "structural stop" in t:
        return Check("Stop-loss", False, text, "A setup whose structural stop is within the allowed distance")
    if "no structural target" in t:
        return Check("Reward:risk", False, text, "A structural target at the minimum reward:risk or better")
    if "opposing" in t or "away: no room" in t:
        return Check("Room to target", False, text, "The opposing level is cleared, leaving room for the target")
    if "spread" in t:
        return Check("Transaction costs", False, text, "A wider stop or a lower spread, so costs stay within the limit")
    return Check("Mandatory rule", False, text, None)


def _alignment(plan: dict) -> tuple[dict, list[Check]]:
    d = 1 if plan.get("side") == "BUY" else -1 if plan.get("side") == "SELL" else 0
    higher, missing, against = [], [], []
    for b in plan.get("bias") or []:
        if b.get("direction") is None:
            agrees = None
            missing.append(b["timeframe"])
        else:
            agrees = (b["direction"] == d) if b["direction"] != 0 else None
            if b["direction"] == -d:
                against.append(f"{b['timeframe']} is {b['label'].lower()}")
        higher.append({"timeframe": b["timeframe"], "label": b.get("label"), "agrees": agrees})
    conf_tf, used = plan.get("confirm_tf"), plan.get("confirm_used")
    conf_ok = used is None or conf_tf is None or used == conf_tf
    if not conf_ok:
        missing.append(conf_tf)
    state = plan.get("state")
    conf_status = ("confirmed" if state == "ENTRY_READY" else "pending" if state in ("WAITING_FOR_CONFIRMATION", "SETUP_DEVELOPING")
                   else "not applicable")
    parts = [f"{h['timeframe']} {'agrees' if h['agrees'] else 'conflicts' if h['agrees'] is False else 'unavailable' if h['label'] in (None, 'unavailable') else 'neutral'}"
             for h in higher]
    parts.append(f"confirmation on {conf_tf}: {conf_status if conf_ok else 'timeframe unavailable'}")
    checks = []
    if d:
        checks.append(Check("Required timeframes", not missing,
                            "all required timeframes have data" if not missing else
                            f"no usable data for {', '.join(missing)} (not assumed aligned)",
                            None if not missing else f"Usable candles for {', '.join(missing)}"))
        checks.append(Check("Higher-timeframe agreement", not against,
                            "no higher timeframe points against the trade" if not against else
                            f"{'; '.join(against)}: against a {plan.get('side')}",
                            None if not against else "The higher timeframes turn in the trade's direction"))
    return ({"higher": higher, "confirmation": {"timeframe": conf_tf, "status": conf_status if conf_ok else "unavailable"},
             "summary": "; ".join(parts)}, checks)


def signal_call(plan: dict, symbol: str, *, price_now: float | None = None, price_source: str | None = None,
                open_trade: dict | None = None, experimental: bool = False) -> dict:
    """The call for one timeframe plan of the signal engine (app.signals.engine.evaluate_timeframe output, after lifecycle)."""
    tf = plan.get("timeframe")
    status = plan.get("status")
    data = {"ok": "ok", "insufficient_data": "insufficient", "stale": "stale"}.get(status, "unavailable")
    state, instr = plan.get("state"), plan.get("instruction")
    side = plan.get("side")
    d = 1 if side == "BUY" else -1 if side == "SELL" else 0
    conds = list(plan.get("conditions") or [])
    targets = [{"label": t["label"], "price": t["price"], "rr": t["rr"]} for t in plan.get("targets") or []]
    base = dict(symbol=symbol, timeframe=tf, data_status=data, data_detail=plan.get("reason") if data != "ok" else None,
                validation=plan.get("validation") or _validation("untested"), score=plan.get("score"), experimental=experimental,
                reasons_for=list(plan.get("reasons_for") or []), reasons_against=list(plan.get("reasons_against") or []),
                price_now=price_now, price_source=price_source, open_trade=open_trade)
    if state in ("TRADE_INVALIDATED", "TRADE_EXPIRED"):
        prev = plan.get("previous") or {}
        return decide(DecisionInput(**base, technical="invalidated" if state == "TRADE_INVALIDATED" else "expired",
                                    technical_detail=f"The previous {prev.get('side', '')} setup ended: {prev.get('reason', 'no longer valid')}.".replace("  ", " ")))
    if d == 0 or state == "NO_SETUP" or not plan.get("entry"):
        why = plan.get("reason") or next((r for r in plan.get("reasons_against") or [] if r.startswith("Blocked")), None)
        detail = f"No valid setup: {why}" if why else f"No setup scores {THRESHOLDS['watch']}/100 or more on {tf}."
        return decide(DecisionInput(**base, technical="none", technical_detail=detail))
    alignment, align_checks = _alignment(plan)
    blocked = [_blocked_check(x) for x in plan.get("blocked") or []]
    passed = [] if blocked else [
        Check("Stop-loss", True, f"structural stop at {plan['stop_loss']} ({plan.get('risk_atr')} ATR)"),
        Check("Reward:risk", True, f"first target at {targets[0]['rr']}R" if targets else "targets available"),
        Check("Transaction costs", True, f"spread costs {plan.get('cost_r')}R of the risk")]
    beyond = "below" if d > 0 else "above"
    if state == "ENTRY_READY":
        technical, mode, wait_kind = "confirmed", "market", None
    elif state == "SETUP_DEVELOPING" and instr == "PLACE LIMIT ORDER":
        technical, mode, wait_kind = "confirmed", "limit", None
    elif state == "SETUP_DEVELOPING":
        technical, mode, wait_kind = "awaiting_price", "limit", "price"
    elif state == "WAITING_FOR_CONFIRMATION":
        technical, mode = "awaiting_confirmation", plan.get("entry_type") or "market"
        wait_kind = "market" if conds and (conds[0].startswith("Market is closed") or conds[0].startswith("Live spread")) else "confirmation"
    else:  # WATCHLIST: a possible setup below the signal threshold (blocked ones fail a mandatory check above)
        technical, mode, wait_kind = "developing", plan.get("entry_type"), "developing"
    nxt = conds[0] if conds and technical != "developing" else None
    if technical == "developing":
        # "Reward:risk >= 2 ... missing: detail" -> the check's name; split on " missing", never on the first colon
        missing = [r.split(" missing")[0] for r in plan.get("reasons_against") or [] if " missing" in r][:3]
        nxt = f"The setup quality reaches {THRESHOLDS['signal']}/100 (now {plan.get('score')}/100)" + (f": {', '.join(missing)}" if missing else "")
    return decide(DecisionInput(
        **base, technical=technical, technical_detail=plan.get("summary"), direction=d,
        setup_name=(plan.get("setup_type") or "").replace("_", " ") or None, entry_mode=mode, entry=plan.get("entry"),
        entry_zone=plan.get("entry_zone"), stop=plan.get("stop_loss"), targets=targets, risk_reward=plan.get("risk_reward"),
        invalidation=plan.get("invalidation"), checks=blocked + passed + align_checks, next_condition=nxt, wait_kind=wait_kind,
        invalidation_text=f"A {tf} candle closing {beyond} {plan.get('invalidation')}" if plan.get("invalidation") is not None else None,
        alignment=alignment))


def opportunity_call(o: dict, *, experimental: bool = False) -> dict:
    """The call for one Trade Opportunities row (app.opportunities.service.opp_out)."""
    status = o.get("status") or "none"
    side = o.get("side") or (o.get("direction") if o.get("direction") in ("BUY", "SELL") else None)
    d = 1 if side == "BUY" else -1 if side == "SELL" else 0
    tech = {"entry_triggered": "confirmed", "waiting_for_confirmation": "awaiting_confirmation", "watchlist": "developing",
            "invalidated": "invalidated", "expired": "expired"}.get(status, "none")
    if d == 0 and tech not in ("invalidated", "expired"):
        tech = "none"
    lo, hi = o.get("entry_low"), o.get("entry_high")
    entry = (lo + hi) / 2 if lo is not None and hi is not None else lo if lo is not None else hi
    targets = [{"label": f"TP{k}", "price": o[f"take_profit_{k}"], "rr": None} for k in (1, 2, 3) if o.get(f"take_profit_{k}") is not None]
    if targets and entry is not None and o.get("stop_loss") is not None:
        risk = abs(entry - o["stop_loss"]) or None
        for t in targets:
            t["rr"] = round(abs(t["price"] - entry) / risk, 2) if risk else None
    waits = list(o.get("wait_reasons") or [])
    conds = list(o.get("conditions") or [])
    return decide(DecisionInput(
        symbol=o.get("symbol") or "", timeframe=o.get("setup_timeframe"), technical=tech, direction=d,
        technical_detail=o.get("thesis") or (f"No setup qualifies: {waits[0]}" if waits and tech == "none" else None),
        setup_name=(o.get("setup_type") or "").replace("_", " ") or None, entry_mode="market" if tech == "confirmed" else "limit",
        entry=entry, entry_zone=[lo, hi] if lo is not None and hi is not None else None, stop=o.get("stop_loss"), targets=targets,
        risk_reward=o.get("risk_reward"), invalidation=o.get("invalidation"),
        next_condition=(conds[0] if conds else waits[0] if waits else None), reasons_against=waits,
        validation=_validation(o.get("validation_status")), score=round(o["evidence_score"]) if o.get("evidence_score") is not None else None,
        invalidation_text=f"Price closes beyond {o['invalidation']}" if o.get("invalidation") is not None else None, experimental=experimental))


def prediction_call(p: dict, *, wait_reasons: list[str] | None = None, experimental: bool = False) -> dict:
    """The call for one stored decision-engine prediction / analysis result (BUY / SELL / WAIT with its plan)."""
    dec = p.get("decision")
    d = 1 if dec == "BUY" else -1 if dec == "SELL" else 0
    lo, hi = p.get("entry_low"), p.get("entry_high")
    entry = (lo + hi) / 2 if lo is not None and hi is not None else lo
    tps = p.get("take_profit") or []
    risk = abs(entry - p["stop_loss"]) if entry is not None and p.get("stop_loss") is not None else None
    targets = [{"label": f"TP{k + 1}", "price": float(x), "rr": round(abs(float(x) - entry) / risk, 2) if risk else None}
               for k, x in enumerate(tps)]
    waits = list(wait_reasons or [])
    q = p.get("data_quality_score")
    data_bad = q is not None and q < 0.6 and d == 0
    return decide(DecisionInput(
        symbol=p.get("symbol") or "", timeframe=p.get("timeframe"),
        data_status="insufficient" if data_bad else "ok", data_detail=(f"data quality {q:.2f} below 0.6" if data_bad else None),
        technical="confirmed" if d else "none", direction=d,
        technical_detail=None if d else ("No trade is justified by the current evidence" + (f": {waits[0]}" if waits else ".")),
        setup_name="decision-engine plan" if d else None, entry_mode="limit" if d else None, entry=entry,
        entry_zone=[lo, hi] if lo is not None and hi is not None else None, stop=p.get("stop_loss"), targets=targets,
        risk_reward=p.get("risk_reward"), invalidation=p.get("invalidation_level"), reasons_against=list(p.get("warnings") or []) + waits,
        validation=_validation("untested", "The decision engine's rules have no out-of-sample validated edge (backtests: negative "
                                           "expectancy); no model passed validation."),
        experimental=experimental))


def redact_explanation(text: str | None, call: dict) -> str | None:
    """Stored explanations embed the technical plan ("Plan: entry …, stop …"). Without an ENTER call (or experimental
    hypothetical levels) those numbers must not reach the customer, so the line is replaced by a pointer to the decision."""
    if not text or call.get("levels") or call.get("hypothetical"):
        return text
    return "\n".join("Plan: entry, stop and targets withheld - see the decision (" + call["label"] + ")."
                     if ln.startswith("Plan:") else ln for ln in text.split("\n"))
