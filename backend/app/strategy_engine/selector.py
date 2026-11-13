"""Strategy selector for one signal timeframe (DESIGN sections 7-8): regime -> compatible strategies -> candidates -> plans ->
de-duplication -> conflict resolution -> one action: BUY, SELL, WAIT FOR BUY, WAIT FOR SELL or NO TRADE. BUY and SELL are never
averaged; a conflict without a known context direction is NO TRADE."""
from app.strategy_engine.config import (
    CHAINS,
    COMPATIBLE,
    GROUPS,
    PLAN_LABEL_UNVALIDATED,
    PLAN_LABEL_VALIDATED,
    RESEARCH_STATUS,
    SPECIFICITY,
    STRATEGY_NAMES,
)
from app.strategy_engine.context import TFData
from app.strategy_engine.plan import build_plan
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies import STRATEGIES
from app.strategy_engine.strategies.base import fmt

LIVE = ("READY", "WAITING FOR ENTRY")
DEDUP_ATR = 0.5


def _side(d: int) -> str:
    return "BUY" if d > 0 else "SELL"


def _rank(x: dict, context: Regime | None) -> tuple:
    aligned = context is not None and context.label == "TRENDING" and context.direction == x["direction"]
    return (0 if x["plan"]["entry_status"] == "READY" else 1, 0 if aligned else 1, -x["plan"]["risk_reward"],
            SPECIFICITY.index(x["strategy"]))


MAX_STALE_BARS = 3  # more complete candles missing than this (closed-market time excluded): the data is stale, no plan


def evaluate_timeframe(t: TFData | None, tf: str, regime: Regime, context: Regime | None, *, precision: int, spread: float,
                       price_now: float | None, market_open: bool = True, spread_normal: bool = True,
                       stale_bars: float | None = None) -> dict:
    chain = CHAINS[tf]
    group = GROUPS[chain.group]
    base = {"timeframe": tf, "group": chain.group, "context_tf": chain.context, "trigger_tf": chain.trigger, "regime": regime.out(),
            "context_regime": context.out() if context is not None else None, "candidates": [], "agreeing": [], "conflict": None}
    if t is None or regime.subtype == "insufficient_data":
        return {**base, **_no_trade(f"NO TRADE: {regime.reason}", "NO SETUP", ["Enough complete candles on this timeframe"])}
    if stale_bars is not None and stale_bars > MAX_STALE_BARS:
        return {**base, **_no_trade(f"NO TRADE: data stale, the latest {tf} candle is {stale_bars:.0f} candles late (sync the data)",
                                    "NO SETUP", ["Fresh, complete candles for this timeframe"])}
    if regime.label == "HIGH_VOLATILITY":
        return {**base, **_no_trade(f"NO TRADE: {regime.reason}", "NO SETUP", ["Volatility back to normal (ATR below its 95th percentile)"])}
    allowed = COMPATIBLE[regime.label]
    rows, live = [], []
    for key, strat in STRATEGIES.items():
        for d in (1, -1):
            if key not in allowed:
                rows.append({"strategy": key, "name": STRATEGY_NAMES[key], "direction": d, "side": _side(d), "status": "not run",
                             "missing": [f"not compatible with a {regime.label.lower().replace('_', ' ')} regime"], "reasons": [], "plan": None})
                continue
            c = strat.evaluate(t, regime, context, d)
            row = {**c.out(), "plan": None}
            if c.status in ("ready", "pending"):
                plan, why = build_plan(c, t, group=group, precision=precision, spread=spread, price_now=price_now)
                if plan is None:
                    row["status"], row["missing"] = "rejected", [f"plan rejected: {why}"]
                else:
                    row["plan"] = plan
                    if plan["entry_status"] in LIVE:
                        live.append(row)
                    else:
                        row["missing"] = [f"entry status {plan['entry_status'].lower()}"]
            rows.append(row)
    base["candidates"] = rows
    # duplicates: same side, entries within 0.5 ATR = one market event; keep the most specific strategy
    live.sort(key=lambda x: SPECIFICITY.index(x["strategy"]))
    kept: list[dict] = []
    for x in live:
        twin = next((k for k in kept if k["direction"] == x["direction"]
                     and abs(k["plan"]["entry"] - x["plan"]["entry"]) <= DEDUP_ATR * x["plan"]["atr"]), None)
        if twin is not None:
            twin.setdefault("agreeing", []).append(x["name"])
        else:
            kept.append(x)
    buys, sells = [x for x in kept if x["direction"] > 0], [x for x in kept if x["direction"] < 0]
    if buys and sells:
        ctx_dir = context.direction if context is not None and context.label == "TRENDING" else 0
        if ctx_dir == 0:
            b0, s0 = min(buys, key=lambda x: _rank(x, context)), min(sells, key=lambda x: _rank(x, context))
            base["conflict"] = {"buy": b0["name"], "sell": s0["name"],
                                "resolution": "no trend on the context timeframe to break the tie: NO TRADE"}
            return {**base, **_no_trade(f"NO TRADE: conflicting setups, {b0['name']} (BUY) against {s0['name']} (SELL), and the context "
                                        f"timeframe {chain.context or '-'} shows no direction", "QUALIFIED",
                                        ["One side's setup fails or the context timeframe turns directional"])}
        loser = sells if ctx_dir > 0 else buys
        base["conflict"] = {"buy": buys[0]["name"], "sell": sells[0]["name"],
                            "resolution": f"the context timeframe {chain.context} trends {'up' if ctx_dir > 0 else 'down'}: "
                                          f"{'BUY' if ctx_dir > 0 else 'SELL'} kept, {', '.join(x['name'] for x in loser)} set aside"}
        kept = buys if ctx_dir > 0 else sells
    if not kept:
        forming = [r for r in rows if r["status"] == "forming"]
        missing = [f"{r['name']} ({r['side']}): {r['missing'][0]}" for r in forming[:3]]
        reasons = [f"{r['name']} ({r['side']}): {r['missing'][0]}" for r in rows if r["status"] == "rejected"][:4]
        return {**base, **_no_trade("NO TRADE: no strategy qualifies on " + tf + (f" ({regime.reason})" if regime.reason else ""),
                                    "DEVELOPING" if forming else "NO SETUP", missing or ["A compatible strategy's conditions are all met"],
                                    reasons)}
    best = min(kept, key=lambda x: _rank(x, context))
    p, d = best["plan"], best["direction"]
    research = RESEARCH_STATUS[best["strategy"]]
    ready = p["entry_status"] == "READY"
    blocked = [] if (market_open and spread_normal) else (["the market is closed"] if not market_open else ["the live spread is abnormal"])
    action = _side(d) if ready and not blocked else f"WAIT FOR {_side(d)}"
    if ready and not blocked:
        nxt = (f"{_side(d)} now near {fmt(p['entry'])} (skip it if price runs more than 0.3R past the entry); stop {fmt(p['stop_loss'])}, "
               f"TP1 {fmt(p['targets'][0]['price'])}. Research: {research.lower()}: a hypothetical plan.")
    elif ready:
        nxt = f"Wait: {blocked[0]}. The setup stays valid until {fmt(p['invalidation'])} is broken or it expires."
    else:
        nxt = f"{best['trigger']}. Cancel if {p['invalidation_text']} or after {GROUPS[chain.group].pending_expiry_bars} {tf} candles."
    return {**base, "action": action, "direction": _side(d), "strategy": best["strategy"], "strategy_name": best["name"],
            "technical_status": "QUALIFIED", "research_status": research,
            "plan_label": PLAN_LABEL_VALIDATED if research == "VALIDATED" else PLAN_LABEL_UNVALIDATED, "plan": p,
            "why": best["reasons"], "agreeing": best.get("agreeing", []), "next_action": nxt, "missing": blocked,
            "headline": f"{action}: {best['name']} on {tf} ({regime.out()['name'].lower()})"}


def _no_trade(headline: str, technical: str, missing: list[str], reasons: list[str] | None = None) -> dict:
    return {"action": "NO TRADE", "direction": None, "strategy": None, "strategy_name": None, "technical_status": technical,
            "research_status": None, "plan_label": None, "plan": None, "why": reasons or [], "missing": missing,
            "next_action": "Wait for: " + "; ".join(missing[:2]), "headline": headline}
