"""The confirmation matrix (docs/engine_v2/CONFIRMATION_DESIGN.md sections 6-8).

Ten components per chosen setup, each PASS | FAIL | NEUTRAL | UNAVAILABLE with the reason and the raw evidence:
  mandatory (decide exactly as before; this module only labels them): regime, higher timeframe, entry, structure, execution, R:R;
  evidence (shown; a category gates a strategy on an instrument only once Experiment 6 promoted it, config.GATES): VSA, momentum,
  trend, volatility.
One verdict per category: momentum is decided by one primary indicator per strategy (the others are evidence only), and trend uses
only signals the regime classifier does not already use (EMA 200, the +DI/-DI spread, session VWAP). UNAVAILABLE never passes.
"""
from dataclasses import dataclass, field

import numpy as np

from app.strategy_engine import vsa
from app.strategy_engine.config import (
    COMBOS,
    COMPATIBLE,
    CONFIRM,
    CONFIRM_STATUS,
    GATES,
    VSA_T,
)
from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies.base import Candidate, fmt

PASS, FAIL, NEUTRAL, UNAVAILABLE = "PASS", "FAIL", "NEUTRAL", "UNAVAILABLE"
LABELS = {"regime": "Market regime", "htf": "Higher timeframe", "entry": "Entry", "structure": "Market structure", "vsa": "VSA",
          "momentum": "Momentum", "trend": "Trend", "volatility": "Volatility", "execution": "Spread & execution", "rr": "Risk/reward"}
ORDER = ("regime", "htf", "entry", "structure", "vsa", "momentum", "trend", "volatility", "execution", "rr")
NOTES = {"gate": "gate: Experiment 6", "not passed": "did not pass Experiment 6"}
NOT_TESTED = "evidence only — not tested"


@dataclass
class Component:
    key: str
    label: str
    verdict: str
    reason: str
    evidence: dict = field(default_factory=dict)
    mandatory: bool = False
    gating: bool = False
    promoted_by: str | None = None
    note: str = ""


def _fin(*xs) -> bool:
    return all(x is not None and np.isfinite(x) for x in xs)


def _val(a: np.ndarray | None, i: int) -> float:
    return float(a[i]) if a is not None and 0 <= i < len(a) and np.isfinite(a[i]) else float("nan")


def _r(x: float, nd: int = 2) -> float | None:
    return round(float(x), nd) if np.isfinite(x) else None


# ---- trend --------------------------------------------------------------------------------------------------------------------------
def trend_verdict(t: TFData, d: int) -> tuple[str, str, dict]:
    i, c = t.last, float(t.bars.c[t.last])
    subs: list[tuple[int, str]] = []
    e200 = _val(t.ema200, i)
    if np.isfinite(e200):
        s = int(np.sign((c - e200) * d))
        subs.append((s, f"close {'above' if c > e200 else 'below'} EMA200 {fmt(e200)}"))
    pdi, mdi = _val(t.pdi, i), _val(t.mdi, i)
    if _fin(pdi, mdi):
        spread = (pdi - mdi) * d
        s = 1 if spread >= CONFIRM["di_for"] else -1 if spread <= -CONFIRM["di_for"] else 0
        lead = "+DI" if pdi >= mdi else "-DI"
        subs.append((s, f"{lead} leads by {abs(pdi - mdi):.0f}" + (" (flat)" if s == 0 else "")))
    vw = _val(t.vwap, i)
    if np.isfinite(vw) and t.bars.step <= 3600 and t.volume.reliable:
        s = int(np.sign((c - vw) * d))
        subs.append((s, f"close {'above' if c > vw else 'below'} session VWAP {fmt(vw)}"))
    ev = {"ema200": _r(e200, 5), "plus_di": _r(pdi), "minus_di": _r(mdi), "vwap": _r(vw, 5)}
    if len(subs) < 2:
        return UNAVAILABLE, f"needs 2 of EMA200, the DI spread and session VWAP; has {len(subs)}", ev
    fors, against = sum(1 for s, _ in subs if s > 0), sum(1 for s, _ in subs if s < 0)
    text = "; ".join(x for _, x in subs)
    if fors >= 2 and against == 0:
        return PASS, text, ev
    if against >= 2:
        return FAIL, text, ev
    return NEUTRAL, text, ev


# ---- momentum -----------------------------------------------------------------------------------------------------------------------
def _momentum_evidence(t: TFData, i: int) -> dict:
    return {"rsi": _r(_val(t.rsi, i), 1), "macd_hist": _r(_val(t.macd_hist, i), 6), "stoch_k": _r(_val(t.stoch_k, i), 1),
            "stoch_d": _r(_val(t.stoch_d, i), 1), "roc10": _r(_val(t.roc10, i), 5)}


def momentum_verdict(strategy: str, t: TFData, d: int) -> tuple[str, str, dict]:
    i = t.last
    ev = _momentum_evidence(t, i)
    if strategy in ("trend_pullback", "sweep_reversal"):
        h0, h1, h2 = _val(t.macd_hist, i), _val(t.macd_hist, i - 1), _val(t.macd_hist, i - 2)
        if not _fin(h0, h1, h2):
            return UNAVAILABLE, "MACD histogram not available yet (warm-up)", ev
        rising = h0 > h1 > h2 if d > 0 else h0 < h1 < h2
        against = h0 < h1 < h2 if d > 0 else h0 > h1 > h2
        word = "rising" if d > 0 else "falling"
        if rising:
            return PASS, f"MACD histogram {word} 2 candles in a row", ev
        if against:
            return FAIL, f"MACD histogram {'falling' if d > 0 else 'rising'} 2 candles in a row, against the trade", ev
        return NEUTRAL, "MACD histogram mixed over the last 2 candles", ev
    if strategy == "momentum_continuation":
        h0, h3 = _val(t.macd_hist, i), _val(t.macd_hist, i - 3)
        if not _fin(h0, h3):
            return UNAVAILABLE, "MACD histogram not available yet (warm-up)", ev
        if h0 * d < 0:
            return FAIL, "MACD histogram against the trade", ev
        if h0 * d > 0 and abs(h0) >= abs(h3):
            return PASS, "MACD histogram for the trade and not shrinking (vs 3 candles ago)", ev
        return NEUTRAL, "MACD histogram for the trade but shrinking", ev
    if strategy in ("breakout_retest", "volatility_expansion"):
        a = _val(t.atr, i)
        if i < 10 or not _fin(a, float(t.bars.c[i - 10])) or not np.isfinite(_val(t.roc10, i)):
            return UNAVAILABLE, "ROC 10 not available yet (warm-up)", ev
        change = float(t.bars.c[i]) - float(t.bars.c[i - 10])
        if abs(change) < CONFIRM["roc_dead_atr"] * a:
            return NEUTRAL, f"10-candle change {change / a:+.2f} ATR (within the +-{CONFIRM['roc_dead_atr']} ATR dead zone)", ev
        if change * d > 0:
            return PASS, f"ROC 10 for the trade ({change / a:+.2f} ATR over 10 candles)", ev
        return FAIL, f"ROC 10 against the trade ({change / a:+.2f} ATR over 10 candles)", ev
    if strategy == "range_reversion":
        lo_x, hi_x = CONFIRM["stoch_lo"], CONFIRM["stoch_hi"]
        ks = [_val(t.stoch_k, j) for j in (i - 2, i - 1, i)]
        ds = [_val(t.stoch_d, j) for j in (i - 2, i - 1, i)]
        if not _fin(*ks, *ds):
            return UNAVAILABLE, "Stochastic RSI not available yet (warm-up)", ev
        crossed = False
        for j in (1, 2):  # a cross on the last two candles
            if d > 0 and ks[j - 1] <= ds[j - 1] and ks[j] > ds[j] and min(ks[j - 1], ks[j]) < lo_x:
                crossed = True
            if d < 0 and ks[j - 1] >= ds[j - 1] and ks[j] < ds[j] and max(ks[j - 1], ks[j]) > hi_x:
                crossed = True
        if crossed:
            return PASS, f"Stochastic RSI %K crossed %D {'up from below ' + str(lo_x) if d > 0 else 'down from above ' + str(hi_x)}", ev
        if (d > 0 and ks[2] > hi_x) or (d < 0 and ks[2] < lo_x):
            return FAIL, f"Stochastic RSI %K {ks[2]:.0f}: at the opposite extreme", ev
        return NEUTRAL, f"no Stochastic RSI cross from the {'oversold' if d > 0 else 'overbought'} zone", ev
    return UNAVAILABLE, f"no momentum rule for {strategy}", ev


# ---- volatility ---------------------------------------------------------------------------------------------------------------------
def volatility_verdict(strategy: str, t: TFData, d: int, anchors: dict) -> tuple[str, str, dict]:
    i = t.last
    if strategy == "volatility_expansion":
        k = anchors.get("expansion")
        if k is None:
            return UNAVAILABLE, "the expansion candle is not known", {}
        c, up, mid, lo = float(t.bars.c[k]), _val(t.kc_up, k), _val(t.kc_mid, k), _val(t.kc_lo, k)
        ev = {"close": _r(c, 5), "keltner_upper": _r(up, 5), "keltner_middle": _r(mid, 5), "keltner_lower": _r(lo, 5)}
        if not _fin(up, mid, lo):
            return UNAVAILABLE, "Keltner Channel not available yet (warm-up)", ev
        if (c > up) if d > 0 else (c < lo):
            return PASS, f"expansion closed beyond the Keltner {'upper' if d > 0 else 'lower'} band {fmt(up if d > 0 else lo)}", ev
        if (c < mid) if d > 0 else (c > mid):
            return FAIL, f"expansion closed on the far side of the Keltner middle line {fmt(mid)}", ev
        return NEUTRAL, "expansion closed inside the Keltner Channel", ev
    p = _val(t.atr_pct, i)
    ev = {"atr": _r(_val(t.atr, i), 5), "atr_percentile": _r(100 * p, 0) if np.isfinite(p) else None}
    if not np.isfinite(p):
        return UNAVAILABLE, "ATR percentile not available yet (needs 50 candles)", ev
    pct = 100 * p
    lo_p, hi_p = CONFIRM["atr_pct_pass"]
    fail_lo, fail_hi = CONFIRM["atr_pct_fail"]
    if lo_p <= pct <= hi_p:
        return PASS, f"ATR in its {pct:.0f}th percentile (normal: {lo_p}-{hi_p})", ev
    if pct > fail_hi:
        return FAIL, f"ATR in its {pct:.0f}th percentile: abnormally high", ev
    if pct < fail_lo:
        return FAIL, f"ATR in its {pct:.0f}th percentile: too quiet, costs are large next to the move", ev
    return NEUTRAL, f"ATR in its {pct:.0f}th percentile (between normal and extreme)", ev


# ---- VSA ------------------------------------------------------------------------------------------------------------------------------
def _heavy_against(t: TFData, k: int, d: int) -> bool:
    """A wide-spread, high-RVOL candle closing against the trade's direction."""
    a, rv = _val(t.atr, k), _val(t.rv, k)
    sp = (float(t.bars.h[k]) - float(t.bars.l[k])) / a if np.isfinite(a) and a > 0 else float("nan")
    return _fin(sp, rv) and sp >= VSA_T["wide"] and rv >= VSA_T["high"] and (float(t.bars.c[k]) - float(t.bars.o[k])) * d < 0


def _mean_rv(t: TFData, idx: list[int]) -> float:
    xs = [_val(t.rv, k) for k in idx]
    xs = [x for x in xs if np.isfinite(x)]
    return float(np.mean(xs)) if xs else float("nan")


def vsa_verdict(strategy: str, t: TFData, d: int, anchors: dict) -> tuple[str, str, dict]:
    i = t.last
    q = t.volume
    if not q.reliable:
        return UNAVAILABLE, f"VSA unavailable: {q.reason}", {"volume": q.label}
    events = [e for e in vsa.until(t.vsa_events, i) if e.idx >= i - 30]
    ev = {"volume": q.label, "rvol": _r(_val(t.rv, i)),
          "events": [{"kind": e.kind, "candle": int(e.idx), "state": vsa.state(e, t.bars, i), "text": e.text} for e in events[-6:]]}
    if strategy == "trend_pullback":
        pb = anchors.get("pullback")
        if not pb:
            return UNAVAILABLE, "the pullback candles are not known", ev
        m = _mean_rv(t, pb)
        if not np.isfinite(m):
            return UNAVAILABLE, "no relative volume on the pullback candles", ev
        ev["pullback_rvol"] = _r(m)
        if m >= CONFIRM["pullback_rvol_fail"] or any(_heavy_against(t, k, d) for k in pb):
            return FAIL, f"the pullback came on heavy volume (average {m:.2f}x) or a wide, heavy candle against the trend", ev
        if m <= CONFIRM["pullback_rvol_pass"]:
            return PASS, f"the pullback came on light volume (average {m:.2f}x): no {'supply' if d > 0 else 'demand'}", ev
        return NEUTRAL, f"pullback volume average {m:.2f}x", ev
    if strategy == "breakout_retest":
        k = anchors.get("breakout")
        if k is None:
            return UNAVAILABLE, "the breakout candle is not known", ev
        rk = _val(t.rv, k)
        if not np.isfinite(rk):
            return UNAVAILABLE, "no relative volume on the breakout candle", ev
        after = anchors.get("retest") or list(range(k + 1, i + 1))
        m = _mean_rv(t, after) if after else float("nan")
        ev |= {"breakout_rvol": _r(rk), "retest_rvol": _r(m)}
        if rk < CONFIRM["weak_rvol"]:
            return FAIL, f"the breakout came on below-average volume ({rk:.2f}x)", ev
        if rk >= CONFIRM["breakout_rvol"] and (not after or m <= CONFIRM["retest_rvol"]):
            return PASS, f"breakout on {rk:.2f}x volume" + (f", retest on {m:.2f}x" if after else ", no retest candle yet"), ev
        return NEUTRAL, f"breakout on {rk:.2f}x volume" + (f", retest on {m:.2f}x" if after else ""), ev
    if strategy == "momentum_continuation":
        k, pb = anchors.get("displacement"), anchors.get("pullback") or []
        if k is None:
            return UNAVAILABLE, "the displacement candle is not known", ev
        rk, m = _val(t.rv, k), _mean_rv(t, pb)
        if not np.isfinite(rk):
            return UNAVAILABLE, "no relative volume on the displacement candle", ev
        climax = [e for e in events if e.kind == "climactic" and e.direction == d and e.idx >= i - 2]
        ev |= {"displacement_rvol": _r(rk), "pullback_rvol": _r(m)}
        if rk < CONFIRM["weak_rvol"] or climax:
            return FAIL, ("climactic volume in the trade's direction in the last 3 candles (possible exhaustion)" if climax
                          else f"the displacement came on below-average volume ({rk:.2f}x): no effort behind it"), ev
        if rk >= CONFIRM["disp_rvol"] and np.isfinite(m) and m < CONFIRM["disp_pullback_ratio"] * rk:
            return PASS, f"displacement on {rk:.2f}x volume, pullback on {m:.2f}x", ev
        return NEUTRAL, f"displacement on {rk:.2f}x volume" + (f", pullback on {m:.2f}x" if np.isfinite(m) else ""), ev
    if strategy == "range_reversion":
        touch = anchors.get("touch")
        if not touch:
            return UNAVAILABLE, "the boundary candles are not known", ev
        if any(_heavy_against(t, k, d) for k in touch):
            return FAIL, "a wide, heavy candle closed against the trade at the boundary", ev
        good = {"spring", "no_supply"} if d > 0 else {"upthrust", "no_demand"}
        hits = [e for e in events if e.idx in touch and ((e.kind in good and e.direction == d) or e.kind == "effort_no_result")
                and vsa.state(e, t.bars, i) in ("confirmed", "n/a")]  # an unconfirmed event cannot make a PASS
        if hits:
            return PASS, hits[-1].text, ev
        return NEUTRAL, "no failed-effort evidence at the boundary yet", ev
    if strategy == "sweep_reversal":
        j = anchors.get("sweep")
        if j is None:
            return UNAVAILABLE, "the sweep candle is not known", ev
        rj = _val(t.rv, j)
        ev["sweep_rvol"] = _r(rj)
        if any(_heavy_against(t, k, d) for k in range(j + 1, i + 1)):
            return FAIL, "after the sweep, a wide, heavy candle closed in the sweep's direction", ev
        tests = [e for e in events if e.kind == "test" and e.direction == d and j < e.idx <= i]
        if np.isfinite(rj) and rj >= CONFIRM["sweep_rvol"]:
            return PASS, f"the sweep candle took {rj:.2f}x volume and closed back inside (stopping volume)", ev
        if tests:
            return PASS, tests[-1].text, ev
        if not np.isfinite(rj):
            return UNAVAILABLE, "no relative volume on the sweep candle", ev
        return NEUTRAL, f"sweep on {rj:.2f}x volume, no test yet", ev
    if strategy == "volatility_expansion":
        k = anchors.get("expansion")
        if k is None:
            return UNAVAILABLE, "the expansion candle is not known", ev
        rk = _val(t.rv, k)
        if not np.isfinite(rk):
            return UNAVAILABLE, "no relative volume on the expansion candle", ev
        ev["expansion_rvol"] = _r(rk)
        if rk >= CONFIRM["expansion_rvol"]:
            return PASS, f"the expansion came on {rk:.2f}x volume", ev
        if rk < CONFIRM["weak_rvol"]:
            return FAIL, f"the expansion came on below-average volume ({rk:.2f}x)", ev
        return NEUTRAL, f"expansion on {rk:.2f}x volume", ev
    return UNAVAILABLE, f"no VSA rule for {strategy}", ev


# ---- the matrix -----------------------------------------------------------------------------------------------------------------------
def _from_checks(c: Candidate, comp: str) -> tuple[str, str] | None:
    rows = [(ok, text) for k, ok, text in c.checks if k == comp]
    if not rows:
        return None
    bad = [text for ok, text in rows if not ok]
    if bad:
        return FAIL, bad[0]
    return PASS, "; ".join(text for _, text in rows)


def score(c: Candidate, t: TFData, regime: Regime, context: Regime | None, plan: dict | None, *, blocked: list[str], stale: bool,
          symbol: str) -> list[Component]:
    out: dict[str, Component] = {}
    # 1 regime
    if regime.label == "HIGH_VOLATILITY":
        out["regime"] = Component("regime", LABELS["regime"], FAIL, regime.reason or "abnormal volatility: no strategy runs", mandatory=True)
    elif regime.subtype == "insufficient_data":
        out["regime"] = Component("regime", LABELS["regime"], UNAVAILABLE, regime.reason or "not enough candles", mandatory=True)
    elif c.strategy in COMPATIBLE.get(regime.label, ()):
        out["regime"] = Component("regime", LABELS["regime"], PASS, regime.reason or regime.name, mandatory=True)
    else:
        out["regime"] = Component("regime", LABELS["regime"], FAIL, f"{c.name} does not run in a {regime.name.lower()} regime", mandatory=True)
    # 2 higher timeframe
    h = _from_checks(c, "htf")
    if h is not None:
        out["htf"] = Component("htf", LABELS["htf"], h[0], h[1], mandatory=True)
    elif context is None:
        out["htf"] = Component("htf", LABELS["htf"], NEUTRAL, "no context timeframe for this timeframe", mandatory=True)
    else:
        out["htf"] = Component("htf", LABELS["htf"], NEUTRAL, f"{c.name} has no higher-timeframe rule; context: {context.name.lower()}",
                               {"context": context.name}, mandatory=True)
    # 3 entry
    if c.status == "ready":
        out["entry"] = Component("entry", LABELS["entry"], PASS, c.trigger or "entry condition met", mandatory=True)
    elif c.status == "pending":
        out["entry"] = Component("entry", LABELS["entry"], NEUTRAL, f"waiting for the trigger: {c.trigger}", mandatory=True)
    else:
        out["entry"] = Component("entry", LABELS["entry"], FAIL, (c.missing or ["entry condition not met"])[0], mandatory=True)
    # 4 structure
    s = _from_checks(c, "structure")
    out["structure"] = Component("structure", LABELS["structure"], *(s or (NEUTRAL, "no structural condition reported")), mandatory=True)
    # 5-8 evidence categories
    gates = GATES.get(symbol, {}).get(c.strategy, ())
    status = CONFIRM_STATUS.get(symbol, {}).get(c.strategy, {})
    for key, (v, reason, ev) in (("vsa", vsa_verdict(c.strategy, t, c.direction, c.anchors)),
                                 ("momentum", momentum_verdict(c.strategy, t, c.direction)),
                                 ("trend", trend_verdict(t, c.direction)),
                                 ("volatility", volatility_verdict(c.strategy, t, c.direction, c.anchors))):
        gating = key in gates
        out[key] = Component(key, LABELS[key], v, reason, ev, mandatory=False, gating=gating,
                             promoted_by="Experiment 6" if gating else None,
                             note=NOTES.get("gate" if gating else status.get(key, ""), NOT_TESTED))
    # 9 execution
    if blocked or stale:
        why = blocked[0] if blocked else "the data is stale"
        out["execution"] = Component("execution", LABELS["execution"], FAIL, why, mandatory=True)
    else:
        out["execution"] = Component("execution", LABELS["execution"], PASS, "spread within its limit, session open, data fresh", mandatory=True)
    # 10 risk/reward
    if plan is None:
        out["rr"] = Component("rr", LABELS["rr"], FAIL, "no valid plan (rejected by the plan rules)", mandatory=True)
    else:
        out["rr"] = Component("rr", LABELS["rr"], PASS, f"TP1 at {plan.get('risk_reward', 0):.2f}R (minimum 1.5R)",
                              {"risk_reward": plan.get("risk_reward")}, mandatory=True)
    return [out[k] for k in ORDER]


def combo_pass(components: list[Component], strategy: str) -> bool:
    need = set(COMBOS[strategy])
    got = {x.key: x.verdict for x in components}
    return all(got.get(k) == PASS for k in need)


def gate_failures(components: list[Component], symbol: str, strategy: str) -> list[Component]:
    promoted = GATES.get(symbol, {}).get(strategy, ())
    return [x for x in components if x.key in promoted and x.verdict != PASS]
