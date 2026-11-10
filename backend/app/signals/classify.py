"""Brief Parts 13-15 on top of the live signal engine: signal classes, confluence bands, historical evidence from the gold research,
hypothetical position size and the structured analyst report. ANALYSIS ONLY: nothing here places or sends orders.

The confluence score stays a heuristic quality measure, never a win probability. A probability is shown only when a model has
passed out-of-sample validation and calibration (none has, so it is reported as unavailable).
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "gold_research_summary.json"
BANDS = ((90, "exceptional"), (80, "strong"), (70, "preferred"), (60, "qualified"), (50, "watchlist"), (0, "research_only"))
LIVE_TO_RESEARCH_TF = {"5m": "M5", "15m": "M15", "30m": "M30", "1H": "H1", "4H": "H4", "1D": "D1"}
ZONE_TO_PATTERN = {"order_block": "order_block", "fvg": "fvg", "breaker_block": "breaker_block", "demand_zone": "demand_zone",
                   "supply_zone": "supply_zone", "support_band": "support_rejection", "resistance_band": "resistance_rejection",
                   "broken_level": "retest"}
SETUP_TO_PATTERNS = {"liquidity_sweep_reversal": ["sweep_to_bos", "sweep+choch"], "bos_retest": ["retest"], "trend_pullback": [],
                     "countertrend_zone": []}
FINAL = {"EXECUTE NOW": "ENTRY READY — ANALYSIS ONLY", "PLACE LIMIT ORDER": "SETUP DEVELOPING — LIMIT PLAN, ANALYSIS ONLY",
         "WAIT FOR CONFIRMATION": "WAIT FOR CONFIRMATION", "NO TRADE": "NO TRADE"}
XAU_CONTRACT_OZ = 100.0
XAU_TICK = 0.01


def confluence_band(score: float | None) -> str:
    if score is None:
        return "research_only"
    return next(label for lo, label in BANDS if score >= lo)


def signal_class(plan: dict) -> str:
    """The brief's nine classes. ENTRY_READY only when the engine's own must-pass rules and confirmation are all met."""
    state, instr, score = plan.get("state"), plan.get("instruction"), plan.get("score")
    if state == "TRADE_INVALIDATED":
        return "INVALIDATED"
    if state == "TRADE_EXPIRED":
        return "EXPIRED"
    if state == "ENTRY_READY":
        return "ENTRY_READY"
    if state == "WAITING_FOR_CONFIRMATION":
        return "WAITING_FOR_CONFIRMATION"
    if state == "SETUP_DEVELOPING":
        return "QUALIFIED_SETUP" if instr == "PLACE LIMIT ORDER" else "DEVELOPING_SETUP"
    if score is None:
        return "NO_TRADE"
    if score >= 50:
        return "WATCHLIST"
    return "RESEARCH_CANDIDATE" if score >= 40 else "NO_TRADE"


def position_size(balance: float, risk_pct: float, entry: float | None, stop: float | None, contract_oz: float = XAU_CONTRACT_OZ,
                  lot_step: float = 0.01) -> dict | None:
    """Hypothetical size for a risk budget: lots such that a stop-out loses about risk_pct of the balance (rounded down)."""
    if not entry or not stop or entry == stop or balance <= 0 or risk_pct <= 0:
        return None
    risk_usd = balance * risk_pct / 100
    per_lot = abs(entry - stop) * contract_oz  # loss per 1.00 lot at the stop
    lots = int(risk_usd / per_lot / lot_step) * lot_step
    return {"balance": balance, "risk_pct": risk_pct, "risk_usd": round(risk_usd, 2), "lots": round(lots, 2),
            "loss_at_stop_usd": round(lots * per_lot, 2), "usd_per_point_per_lot": contract_oz, "tick": XAU_TICK,
            "note": "hypothetical sizing for analysis; spread and slippage not included"}


def _summary() -> dict | None:
    if not DATA.exists():
        return None
    try:
        return json.loads(DATA.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return None


def evidence(symbol: str, plan: dict) -> dict:
    """Measured history of the patterns behind a live plan, from the gold research (training and, when run, validation)."""
    s = _summary()
    if symbol != "XAUUSD" or s is None:
        return {"available": False, "note": "historical research is only available for XAUUSD once the study has run"}
    tf = LIVE_TO_RESEARCH_TF.get(plan.get("timeframe", ""))
    side = {"BUY": "long", "SELL": "short"}.get(plan.get("side") or "", None)
    pats = [ZONE_TO_PATTERN[k] for k in [plan.get("zone_kind")] if k in ZONE_TO_PATTERN] + SETUP_TO_PATTERNS.get(plan.get("setup_type"), [])
    rows = [r for r in s.get("rows", []) if r["tf"] == tf and r["direction"] == side and r["pattern"] in pats]
    return {"available": bool(rows), "timeframe": tf, "patterns": pats, "rows": rows, "split": s.get("split"),
            "costs": s.get("costs"), "note": "training-period figures find candidates; only validation figures confirm them. "
                                             "The final test is sealed and not shown."}


def enrich(symbol: str, res: dict, balance: float = 10_000.0, risk_pct: float = 1.0) -> dict:
    for p in res.get("plans", []):
        p["signal_class"] = signal_class(p)
        p["confluence_band"] = confluence_band(p.get("score"))
        p["historical_evidence"] = evidence(symbol, p)
        p["position_size"] = position_size(balance, risk_pct, p.get("entry"), p.get("stop_loss")) if symbol == "XAUUSD" else None
        p["model_output"] = {"confluence_score": p.get("score"), "estimated_probability": None,
                             "calibration_status": "no model has passed out-of-sample validation and calibration",
                             "model_version": None}
    best = res.get("best")
    if best is not None:
        match = next((p for p in res.get("plans", []) if p.get("setup_key") == best.get("setup_key")), best)
        for k in ("signal_class", "confluence_band", "historical_evidence", "position_size", "model_output"):
            best[k] = match.get(k)
    res["analysis_report"] = analysis_report(symbol, res)
    return res


def analysis_report(symbol: str, res: dict) -> dict:
    """Brief Part 15 layout, filled only from the engine's structured output (no invented levels or statistics)."""
    best = res.get("best")
    quote = res.get("quote") or {}
    rows = [{"tf": r.get("timeframe"), "direction": r.get("label"), "structure": r.get("structure"), "evidence": r.get("observation")}
            for r in res.get("timeframes", []) if r.get("label")]
    out = {"instrument": symbol, "current_price": quote.get("price"), "analysis_timestamp": res.get("generated_at"),
           "trading_profile": best.get("group") if best else None, "market_regime": (res.get("overall") or {}).get("label"),
           "higher_timeframe_bias": (res.get("overall") or {}).get("detail"), "multi_timeframe_structure": rows,
           "pattern_identified": None, "historical_evidence": None, "model_output": None, "trade_plan": None,
           "reasons_for": [], "risks_and_counter_evidence": [], "final_decision": "NO TRADE"}
    if not best:
        return out
    tps = best.get("targets") or []
    out.update(
        pattern_identified=f"{best.get('setup_type', '').replace('_', ' ')} at {best.get('zone_kind') or 'liquidity sweep'}",
        historical_evidence=best.get("historical_evidence"), model_output=best.get("model_output"),
        trade_plan={"action": best.get("decision"), "execution_timeframe": best.get("confirm_tf") or best.get("timeframe"),
                    "setup_timeframe": best.get("timeframe"), "entry_zone": best.get("entry_zone"), "entry_type": best.get("entry_type"),
                    "entry": best.get("entry"), "entry_trigger": (best.get("conditions") or [None])[0], "stop_loss": best.get("stop_loss"),
                    "tp1": tps[0]["price"] if len(tps) > 0 else None, "tp2": tps[1]["price"] if len(tps) > 1 else None,
                    "tp3": tps[2]["price"] if len(tps) > 2 else None, "risk_reward": [t.get("rr") for t in tps],
                    "setup_expiry": best.get("valid_until"), "position_size": best.get("position_size")},
        reasons_for=best.get("reasons_for", []), risks_and_counter_evidence=best.get("reasons_against", []),
        final_decision=FINAL.get(best.get("instruction"), "NO TRADE"), signal_class=best.get("signal_class"),
        confluence_band=best.get("confluence_band"), validation=best.get("validation"))
    return out
