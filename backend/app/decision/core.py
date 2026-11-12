"""The single decision function. Order of precedence (first match wins):

 1. a tracked open trade whose exit condition is met                    -> EXIT (stop-loss, target, invalidation)
 2. data for the timeframe unavailable, insufficient or stale            -> NO TRADE
 3. a tracked trade is already open (or pending) on this timeframe       -> WAIT (manage the open trade: HOLD; no second entry)
 4. the technical setup was invalidated or expired, or there is none     -> NO TRADE
 5. any mandatory condition failed (stop, targets / reward:risk, costs,
    required timeframes, higher-timeframe conflict, ...)                 -> NO TRADE   (a high score never overrides this)
 6. price already beyond the stop or the first target, or past the entry
    by more than the never-chase limit                                   -> NO TRADE
 8. score below the signal threshold                                     -> WAIT, setup developing
 9. price not yet at the entry zone                                      -> WAIT, price condition
10. confirmation missing (or market closed / spread abnormal)            -> WAIT, confirmation condition
11. technical entry confirmed: research-VALIDATED                        -> ENTER (immediate or conditional limit)
                                     NOT validated                       -> WAIT, UNVALIDATED SETUP

ENTER is therefore only possible for rules that passed out-of-sample validation; none has, so ENTER does not appear today. Entry,
stop and targets are shown with ENTER only; in experimental mode an unvalidated technical setup's levels are attached separately as
`hypothetical`, clearly marked, and the call stays WAIT. No probability or win rate is produced here.
"""
from dataclasses import dataclass, field

from app.paper.simulator import CHASE_R
from app.signals.execution import market_entry_ok

ENTER, WAIT, EXIT, NO_TRADE = "ENTER", "WAIT", "EXIT", "NO TRADE"
ORDER = {EXIT: 0, ENTER: 1, WAIT: 2, NO_TRADE: 3}
# an open or pending tracked trade is the first thing to manage, then the most concrete new setup
WAIT_ORDER = {"trade_open": 0, "order_pending": 1, "unvalidated": 2, "confirmation": 3, "market": 4, "price": 5, "developing": 6}
SCORE_NOTE = "setup quality checklist, not a probability of winning"
EXIT_LABEL = {"stop_loss": "EXIT — STOP-LOSS HIT", "target": "EXIT — TARGET REACHED", "invalidation": "EXIT — SETUP INVALIDATED"}
UNVALIDATED_NEXT = ("Research validation of these rules for this instrument and timeframe: at least 100 out-of-sample trades with a "
                    "positive expected result after costs. Until then this is a hypothetical setup; the Paper Trading forward test "
                    "records it automatically.")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    fix: str | None = None  # what would have to change for it to pass

    def out(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail, "fix": self.fix}


@dataclass
class DecisionInput:
    symbol: str
    timeframe: str | None
    data_status: str = "ok"  # ok | insufficient | stale | unavailable
    data_detail: str | None = None
    technical: str = "none"  # none | developing | awaiting_price | awaiting_confirmation | confirmed | invalidated | expired
    technical_detail: str | None = None
    direction: int = 0
    setup_name: str | None = None
    entry_mode: str | None = None  # market | limit
    entry: float | None = None
    entry_zone: list[float] | None = None
    stop: float | None = None
    targets: list[dict] = field(default_factory=list)  # {"label", "price", "rr"}
    risk_reward: float | None = None
    invalidation: float | None = None
    checks: list[Check] = field(default_factory=list)  # mandatory conditions: every one must pass for ENTER
    next_condition: str | None = None
    invalidation_text: str | None = None
    wait_kind: str | None = None  # confirmation | market | price | developing (why a WAIT waits)
    reasons_for: list[str] = field(default_factory=list)
    reasons_against: list[str] = field(default_factory=list)
    validation: dict = field(default_factory=lambda: {"status": "not_validated", "label": "Not validated", "note": ""})
    alignment: dict | None = None
    price_now: float | None = None
    price_source: str | None = None
    open_trade: dict | None = None  # tracked paper trade on this instrument x timeframe (status open or pending)
    score: int | None = None
    experimental: bool = False


def _fmt(x: float | None) -> str:
    if x is None:
        return "-"
    a = abs(x)
    return f"{x:,.2f}" if a >= 100 else f"{x:.5f}" if a < 10 else f"{x:.3f}"


def _side(d: int) -> str:
    return "BUY" if d > 0 else "SELL" if d < 0 else "NONE"


def _levels(i: DecisionInput) -> dict | None:
    if i.entry is None or i.stop is None:
        return None
    return {"entry": i.entry, "entry_zone": i.entry_zone, "entry_mode": i.entry_mode, "stop_loss": i.stop, "targets": i.targets,
            "risk_reward": i.risk_reward, "invalidation": i.invalidation}


def manage_trade(trade: dict | None, price: float | None = None) -> dict | None:
    """HOLD / EXIT / WAIT for a tracked paper trade (never invented: no trade -> None). Uses the trade's own stop, first target and
    invalidation level and the latest price the forward test saw (or `price`)."""
    if not trade or trade.get("status") not in ("open", "pending"):
        return None
    d = 1 if trade.get("direction") == "BUY" else -1
    px = price if price is not None else trade.get("last_price")
    sl, tp, inv = trade.get("stop_loss"), trade.get("take_profit"), trade.get("invalidation")
    entry = trade.get("fill_price") or trade.get("entry_price")
    base = {"trade_id": trade.get("id"), "status": trade.get("status"), "direction": trade.get("direction"), "entry_price": entry,
            "current_price": px, "stop_loss": sl, "take_profit": tp,
            "stop_distance": abs(px - sl) if px is not None and sl is not None else None,
            "target_distance": abs(tp - px) if px is not None and tp is not None else None,
            "unrealized_r": trade.get("unrealized_r"), "unrealized_pnl": trade.get("unrealized_pnl")}
    if trade["status"] == "pending":
        if px is not None and tp is not None and d * (px - tp) >= 0:
            return {**base, "action": NO_TRADE, "reason": f"The first target {_fmt(tp)} traded before the limit {_fmt(entry)} filled: "
                                                          "cancel the order (the paper simulator marks it missed)."}
        return {**base, "action": WAIT, "reason": f"Limit order at {_fmt(entry)} waiting for a fill; cancel if a candle closes beyond "
                                                  f"{_fmt(inv or sl)} or the first target trades first."}
    if px is None:
        return {**base, "action": "HOLD", "reason": "No price since the fill yet; the stop and target stay in force."}
    if sl is not None and d * (px - sl) <= 0:
        return {**base, "action": EXIT, "exit_kind": "stop_loss", "reason": f"Price {_fmt(px)} is at or beyond the stop-loss {_fmt(sl)}."}
    if tp is not None and d * (px - tp) >= 0:
        return {**base, "action": EXIT, "exit_kind": "target", "reason": f"Price {_fmt(px)} reached the first target {_fmt(tp)}."}
    if inv is not None and trade.get("last_close") is not None and d * (trade["last_close"] - inv) < 0:
        return {**base, "action": EXIT, "exit_kind": "invalidation",
                "reason": f"A candle closed at {_fmt(trade['last_close'])}, beyond the invalidation level {_fmt(inv)}."}
    return {**base, "action": "HOLD", "reason": f"Between the stop {_fmt(sl)} and the first target {_fmt(tp)}; no exit condition is met."}


def decide(i: DecisionInput) -> dict:
    d = i.direction
    failed = [c for c in i.checks if not c.passed]
    out = {"symbol": i.symbol, "timeframe": i.timeframe, "direction": _side(d) if i.technical != "none" else "NONE",
           "setup": i.setup_name, "entry_mode": None, "levels": None, "hypothetical": None, "watch": None,
           "technical_status": i.technical, "technical_detail": i.technical_detail,
           "data_quality": {"status": i.data_status, "detail": i.data_detail or ("fresh, complete candles" if i.data_status == "ok" else None)},
           "validation": i.validation, "alignment": i.alignment, "checks": [c.out() for c in i.checks],
           "failed_checks": [c.out() for c in failed], "reasons_for": i.reasons_for[:5], "reasons_against": i.reasons_against[:5],
           "invalidation": i.invalidation_text, "score": i.score, "score_note": SCORE_NOTE, "experimental": i.experimental,
           "price_now": i.price_now, "price_source": i.price_source, "trade": manage_trade(i.open_trade)}

    def done(decision: str, label: str, headline: str, nxt: str | None, wait_kind: str | None = None, **extra) -> dict:
        res = {**out, "decision": decision, "label": label, "headline": headline, "next_condition": nxt, "wait_kind": wait_kind, **extra}
        if decision == NO_TRADE:
            res["direction"] = "NONE" if i.technical in ("none", "invalidated", "expired") else res["direction"]
        return res

    # 1. tracked open trade with an exit condition
    t = out["trade"]
    if t and t.get("action") == EXIT:
        return done(EXIT, EXIT_LABEL.get(t.get("exit_kind"), "EXIT"), t["reason"], "Close the tracked trade; look for a new setup afterwards.",
                    exit_price=t.get("current_price"), exit_reason=t.get("exit_kind"))
    # 2. data
    if i.data_status != "ok":
        what = {"stale": "Market data is stale", "insufficient": "Not enough market data", "unavailable": "Market data is unavailable"}
        return done(NO_TRADE, "NO TRADE — DATA", f"{what.get(i.data_status, 'Market data is unreliable')}: {i.data_detail or ''}".rstrip(": "),
                    "Fresh, complete candles for this timeframe (sync the data first).")
    # 3. a tracked trade is already running here: manage it (HOLD / WAIT), never a second entry
    if t is not None and t["action"] == NO_TRADE:  # a pending order whose cancel condition is met
        return done(NO_TRADE, "NO TRADE — CANCEL PENDING ORDER", t["reason"], "A new setup forms.")
    if t is not None:
        kind = "trade_open" if t["status"] == "open" else "order_pending"
        return done(WAIT, "WAIT — TRADE OPEN" if kind == "trade_open" else "WAIT — ORDER PENDING",
                    f"A tracked paper trade is already {t['status']} on {i.symbol} {i.timeframe}: manage it ({t['action']}), no new entry.",
                    t["reason"], kind, watch={"zone": i.entry_zone, "invalidation": i.invalidation})
    # 4. no live setup
    if i.technical in ("invalidated", "expired"):
        return done(NO_TRADE, f"NO TRADE — SETUP {i.technical.upper()}", i.technical_detail or f"The setup was {i.technical}.",
                    "A new setup forms.")
    if i.technical == "none":
        return done(NO_TRADE, "NO TRADE", i.technical_detail or "No valid setup on this timeframe.", i.next_condition or "A new setup forms.")
    # 5. mandatory conditions: never overridden by the score
    if failed:
        first = failed[0]
        return done(NO_TRADE, "NO TRADE — CONDITION FAILED", f"{first.name}: {first.detail}",
                    first.fix or "All mandatory conditions pass.", **_hypo(i))
    # 6. price already past the plan
    if i.price_now is not None and i.entry is not None and i.stop is not None and i.targets:
        px, tp1 = i.price_now, i.targets[0]["price"]
        if d * (px - i.stop) <= 0:
            return done(NO_TRADE, "NO TRADE — PRICE BEYOND STOP", f"Price {_fmt(px)} is already beyond the stop {_fmt(i.stop)}: the setup is void.",
                        "A new setup forms.")
        if d * (tp1 - px) <= 0:
            return done(NO_TRADE, "NO TRADE — TARGET ALREADY REACHED", f"Price {_fmt(px)} already reached the first target {_fmt(tp1)} "
                        "before any entry.", "A new setup forms.")
        if i.entry_mode == "market" and i.technical == "confirmed" and d * (px - i.entry) > CHASE_R * abs(i.entry - i.stop):
            return done(NO_TRADE, "NO TRADE — ENTRY MISSED", f"Price {_fmt(px)} is more than {CHASE_R:g}R past the entry {_fmt(i.entry)}: "
                        "never chase.", f"Price returns to {_fmt(i.entry)} or a new setup forms.")
        if not market_entry_ok(d, px, i.stop, tp1):
            return done(NO_TRADE, "NO TRADE — PRICE OUTSIDE PLAN", f"Price {_fmt(px)} is not between the stop and the first target.",
                        "A new setup forms.")
    watch = {"zone": i.entry_zone, "invalidation": i.invalidation}
    # 8-10. technically incomplete
    if i.technical in ("developing", "awaiting_price", "awaiting_confirmation"):
        kind = i.wait_kind or {"developing": "developing", "awaiting_price": "price", "awaiting_confirmation": "confirmation"}[i.technical]
        label = {"developing": "WAIT — SETUP DEVELOPING", "price": "WAIT — PRICE NOT AT ENTRY ZONE", "confirmation": "WAIT — CONFIRMATION PENDING",
                 "market": "WAIT — MARKET CONDITIONS"}[kind]
        head = {"developing": f"A possible {_side(d)} setup is forming but does not yet meet enough conditions.",
                "price": f"A {_side(d)} setup is waiting for price to reach its entry zone.",
                "confirmation": f"A {_side(d)} setup is at its zone; the confirmation signal has not appeared yet.",
                "market": f"A {_side(d)} setup exists, but current market conditions do not allow an entry."}[kind]
        zone = f" {_fmt(i.entry_zone[0])} - {_fmt(i.entry_zone[1])}" if i.entry_zone else (f" {_fmt(i.entry)}" if i.entry is not None else "")
        default = {"developing": "The setup meets enough of its conditions to qualify as a signal.",
                   "price": f"Price trades into the entry zone{zone}.",
                   "confirmation": f"A confirmation signal in the {_side(d)} direction (a candle or structure break) on the confirmation timeframe.",
                   "market": "The market is open and the live spread is back to normal."}[kind]
        return done(WAIT, label, head, i.next_condition or default, kind, watch=watch, **_hypo(i))
    # 11. technical entry confirmed
    if i.validation.get("status") == "validated":
        mode = "immediate" if i.entry_mode == "market" else "conditional"
        how = (f"Enter {_side(d)} now near {_fmt(i.entry)}" if mode == "immediate"
               else f"Enter {_side(d)} with a limit order at {_fmt(i.entry)} (conditional on a fill)")
        default = (f"Enter near {_fmt(i.entry)}; skip it if price runs more than {CHASE_R:g}R past the entry (never chase)." if mode == "immediate"
                   else f"The limit order at {_fmt(i.entry)} fills before the setup expires.")
        return done(ENTER, "ENTER", f"{how}. All mandatory conditions pass and these rules passed out-of-sample validation.",
                    i.next_condition or default, entry_mode=mode, levels=_levels(i))
    return done(WAIT, "WAIT — UNVALIDATED SETUP",
                f"The technical {_side(d)} conditions are present, but these rules have not shown a profitable edge in out-of-sample "
                "testing, so the system does not recommend entering.", UNVALIDATED_NEXT, "unvalidated", watch=watch, **_hypo(i))


def _hypo(i: DecisionInput) -> dict:
    """Experimental mode only: the technical levels, marked hypothetical and unvalidated (never with ENTER)."""
    lv = _levels(i)
    if not i.experimental or lv is None:
        return {}
    return {"hypothetical": {**lv, "direction": _side(i.direction), "label": "HYPOTHETICAL — UNVALIDATED",
                             "note": "Technical levels for analysis only. These rules have not passed out-of-sample validation; this is "
                                     "not a recommendation."}}


def rank(calls: list[dict]) -> dict | None:
    """The instrument-level call: EXIT > ENTER > WAIT (trade open, order pending, unvalidated, confirmation, market, price, developing)
    > NO TRADE; ties by score."""
    if not calls:
        return None
    return min(calls, key=lambda c: (ORDER[c["decision"]], WAIT_ORDER.get(c.get("wait_kind") or "", 9), -(c.get("score") or 0)))
