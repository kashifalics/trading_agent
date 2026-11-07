"""100-point confluence checklist (docs/SIGNAL_ENGINE.md). A setup-quality score, NOT a win probability.

Every check reports its points, its maximum, whether it is met and a one-line reason built from the detected data. Anything that
cannot be measured scores 0 (never assumed).
"""
from app.signals.config import FACTOR_LABELS, FACTORS, PARAMS, POINTS, Group
from app.signals.context import fmt
from app.signals.plan import Plan, side_word


def _check(key: str, label: str, max_pts: float, pts: float, detail: str) -> dict:
    return {"key": key, "label": label, "max": max_pts, "points": round(float(pts), 1), "met": pts > 0, "detail": detail}


def score_plan(*, plan: Plan, setup_tf: str, group: Group, bias: list[tuple[str, dict | None]], setup_read: dict, fresh_break,
               sweep: dict | None, zone_pos: float | None, confluence: str | None, ltf_break: dict | None, rejection: dict | None,
               confirm_tf: str, atr_pct: float | None, session_ok: bool | None) -> dict:
    d = plan.d
    sw = side_word(d)
    factors: dict[str, list[dict]] = {k: [] for k in FACTORS}

    # A. higher-timeframe alignment (10 per bias timeframe)
    for tf, read in bias:
        if read is None:
            factors["htf_alignment"].append(_check(f"htf_{tf}", f"{tf} trend {sw}", POINTS["htf_each"], 0,
                                                   f"no usable {tf} data (not assumed aligned)"))
        else:
            ok = read["direction"] == d
            note = f"{tf} is {read['label'].lower()}" + (f" ({read['structure']})" if read.get("structure") else "") + f"; {read['observation']}"
            factors["htf_alignment"].append(_check(f"htf_{tf}", f"{tf} trend {sw}", POINTS["htf_each"], POINTS["htf_each"] if ok else 0, note))
    if not bias:
        factors["htf_alignment"].append(_check("htf_none", "Higher-timeframe context", 0, 0, f"{setup_tf} has no higher timeframe"))

    # B. market structure on the setup timeframe
    ok = setup_read["direction"] == d
    factors["market_structure"].append(_check(
        "structure_class", f"{setup_tf} structure {sw}", POINTS["structure_class"], POINTS["structure_class"] if ok else 0,
        f"{setup_tf} is {setup_read['label'].lower()}" + (f" ({setup_read['structure']})" if setup_read.get("structure") else "")))
    factors["market_structure"].append(_check(
        "fresh_break", f"Fresh {sw} BOS/CHoCH (≤ {PARAMS['fresh_break_bars']} bars)", POINTS["fresh_break"],
        POINTS["fresh_break"] if fresh_break is not None else 0,
        fresh_break["text"] if fresh_break is not None else f"no {sw} break of structure in the last {PARAMS['fresh_break_bars']} bars"))

    # C. liquidity event
    if sweep is not None and sweep.get("break") is not None:
        pts, detail = POINTS["sweep_and_break"], (f"{sweep['label']} liquidity at {fmt(sweep['price'])} swept, then a {sw} "
                                                  f"{sweep['break'].kind} at {fmt(sweep['break'].price)}")
    elif sweep is not None:
        pts, detail = POINTS["sweep_only"], f"{sweep['label']} liquidity at {fmt(sweep['price'])} swept (no structure break after it yet)"
    else:
        pts, detail = 0, f"no {'sell' if d == 1 else 'buy'}-side liquidity sweep in the recent window"
    factors["liquidity"].append(_check("liquidity_sweep", "Liquidity sweep", POINTS["sweep_and_break"], pts, detail))

    # D. entry-zone quality
    z = plan.poi
    factors["entry_zone"].append(_check(
        "at_zone", "Entry at a point of interest", POINTS["at_zone"], POINTS["at_zone"] if z is not None else 0,
        f"{z.label} {fmt(z.low)}–{fmt(z.high)}" + (f" ({z.touches} touches)" if z.touches else "") if z is not None
        else "entry comes from the sweep, not from a zone"))
    if zone_pos is None:
        pts, detail = 0, "dealing range unavailable"
    else:
        good = zone_pos < 0.5 if d == 1 else zone_pos > 0.5
        pts = POINTS["discount_premium"] if good else 0
        detail = f"entry at {zone_pos:.0%} of the dealing range ({'discount' if zone_pos < 0.5 else 'premium'})"
    factors["entry_zone"].append(_check("discount_premium", "Discount entry" if d == 1 else "Premium entry", POINTS["discount_premium"], pts, detail))
    factors["entry_zone"].append(_check("zone_confluence", "Zone confluence", POINTS["zone_confluence"],
                                        POINTS["zone_confluence"] if confluence else 0, confluence or "no overlapping level, trendline or second zone"))

    # E. lower-timeframe confirmation
    if not plan.at_zone:
        msg = "price has not reached the entry zone yet"
        factors["ltf_confirmation"].append(_check("ltf_structure", f"{confirm_tf} {sw} structure shift", POINTS["ltf_structure"], 0, msg))
        factors["ltf_confirmation"].append(_check("rejection_candle", "Rejection candle at the zone", POINTS["rejection_candle"], 0, msg))
    else:
        factors["ltf_confirmation"].append(_check(
            "ltf_structure", f"{confirm_tf} {sw} structure shift", POINTS["ltf_structure"], POINTS["ltf_structure"] if ltf_break else 0,
            ltf_break["text"] if ltf_break else f"no {sw} BOS/CHoCH on {confirm_tf} since price reached the zone"))
        factors["ltf_confirmation"].append(_check(
            "rejection_candle", "Rejection candle at the zone", POINTS["rejection_candle"], POINTS["rejection_candle"] if rejection else 0,
            rejection["text"] if rejection else "no engulfing / hammer / pin bar / star since price reached the zone"))

    # F. risk-to-reward quality
    rr = plan.rr
    pts = 0.0 if rr < group.min_rr else POINTS["rr_at_min"] + (POINTS["rr_full"] - POINTS["rr_at_min"]) * min(1.0, (rr - group.min_rr) / group.min_rr)
    detail = f"TP1 {fmt(plan.targets[0]['price'])} = {rr:.2f}R (full points at {2 * group.min_rr:g}R)"
    if plan.obstacle:
        pts = 0.0
        detail += (f", but a strong {plan.obstacle['basis'].replace('_', ' ')} at {fmt(plan.obstacle['price'])} "
                   f"({plan.obstacle['rr']:.2f}R) sits in the way")
    factors["risk_reward"].append(_check("risk_reward", f"Reward:risk ≥ {group.min_rr:g} with a clear path", POINTS["rr_full"], pts, detail))

    # G. session and volatility
    if atr_pct is None:
        pts, detail = 0, "volatility history unavailable"
    else:
        ok = PARAMS["vol_pct_low"] <= atr_pct <= PARAMS["vol_pct_high"]
        pts = POINTS["volatility"] if ok else 0
        detail = f"ATR at the {atr_pct:.0%} percentile of recent history" + ("" if ok else " (outside the 15–90% normal band)")
    factors["session_volatility"].append(_check("volatility", "Normal volatility", POINTS["volatility"], pts, detail))
    if session_ok is None:
        factors["session_volatility"].append(_check("session", "Active session", POINTS["session"], POINTS["session"],
                                                    f"session filter not applied on {setup_tf}"))
    else:
        factors["session_volatility"].append(_check(
            "session", "Active session (07–20 UTC)", POINTS["session"], POINTS["session"] if session_ok else 0,
            "candle closed during London / New York hours" if session_ok else "candle closed outside London / New York hours (thin liquidity)"))

    out, total, checks = [], 0.0, []
    for key, items in factors.items():
        pts = min(float(FACTORS[key]), sum(c["points"] for c in items))
        total += pts
        checks += items
        out.append({"key": key, "label": FACTOR_LABELS[key], "max": FACTORS[key], "points": round(pts, 1), "checks": items})
    real = [c for c in checks if c["max"] > 0]
    return {"score": int(round(total)), "factors": out, "met": sum(1 for c in real if c["met"]), "total": len(real)}
