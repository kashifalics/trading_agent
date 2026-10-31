"""BUY / SELL / WAIT policy.

WAIT is the default. A BUY/SELL requires, simultaneously:
  1. data quality >= min_quality,
  2. |analytical confluence| >= threshold,
  3. no multi-timeframe conflict (higher vs entry) and, if configured, higher-TF direction not opposed,
  4. limited contradictory evidence,
  5. historical analogues (when sufficient) not clearly worse than the unconditional base rate,
  6. a valid trade plan (bounded stop, risk/reward >= min_rr).
Only a calibrated model that passed minimum validation contributes to the decision; research-only
model output is displayed but weighted at zero.
"""
from dataclasses import asdict, dataclass, field

import numpy as np

from app.core.events import Event, iso
from app.historical_engine.analogues import AnalogueResult
from app.market_data.bars import Bars
from app.prediction.confidence import PASSED, confidence_panel
from app.prediction.explanation import explain
from app.prediction.risk import TradePlan, build_trade_plan
from app.price_action.engine import PriceActionResult

WEIGHTS = {"structure": 0.25, "multi_timeframe": 0.20, "premium_discount": 0.10, "candlestick": 0.10,
           "liquidity": 0.10, "zones": 0.15, "historical_analogues": 0.10, "ml_model": 0.15}


@dataclass
class DecisionConfig:
    confluence_threshold: float = 0.35
    min_rr: float = 1.5
    min_quality: float = 0.6
    recent_bars: int = 10
    max_opposition: float = 0.40


@dataclass
class DecisionInputs:
    symbol: str
    timeframe: str
    bars: Bars
    pa: PriceActionResult
    quality: dict
    mtf: dict | None = None
    analogues: AnalogueResult | None = None
    ml: dict | None = None
    price_calibrated: bool = True


@dataclass
class Decision:
    decision: str
    confluence: float | None
    evidence: list[dict]
    wait_reasons: list[str]
    warnings: list[str]
    plan: TradePlan | None
    panel: dict
    explanation: str
    as_of_ts: int | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"decision": self.decision, "confluence": self.confluence, "evidence": self.evidence,
                "wait_reasons": self.wait_reasons, "warnings": self.warnings,
                "plan": asdict(self.plan) if self.plan else None, "confidence": self.panel,
                "explanation": self.explanation, "as_of": iso(self.as_of_ts), **self.extra}


def _ev(cat, name, score, detail, ts=None, price=None, weight=None) -> dict:
    score = float(np.clip(score, -1, 1))
    return {"category": cat, "name": name, "direction": "bullish" if score > 0.05 else "bearish" if score < -0.05 else "neutral",
            "weight": WEIGHTS[cat] if weight is None else weight, "score": score, "detail": detail,
            "ts": iso(ts), "price": price}


def collect_evidence(inp: DecisionInputs, cfg: DecisionConfig) -> list[dict]:
    b, pa, n = inp.bars, inp.pa, len(inp.bars)
    last = n - 1
    out: list[dict] = []
    a = pa.atr[last] if n else np.nan

    # structure
    trend = int(pa.trend[last])
    recent_break = next((e for e in reversed(pa.breaks) if last - e.idx <= 15), None)
    s = 0.7 * trend + (0.3 * (1 if recent_break.direction == "bullish" else -1) if recent_break else 0.0)
    detail = f"structure trend {'up' if trend > 0 else 'down' if trend < 0 else 'undetermined'}"
    if recent_break:
        detail += f"; {recent_break.kind} {recent_break.direction} {last - recent_break.idx} bars ago"
    out.append(_ev("structure", "market_structure", s, detail, int(b.t[last]), float(b.c[last])))

    # premium / discount
    pd_ = pa.premium_discount
    if pd_:
        pos = pd_.meta["position"]
        out.append(_ev("premium_discount", "premium_discount", (0.5 - pos) * 2, pd_.evidence, pd_.ts, pd_.price))
    else:
        out.append(_ev("premium_discount", "premium_discount", 0, "no dealing range yet", weight=0.0))

    # candlestick (last 3 bars)
    pats = [e for e in pa.candles if last - e.idx < 3 and e.direction != "neutral"]
    sc = sum(1 if e.direction == "bullish" else -1 for e in pats)
    out.append(_ev("candlestick", "candlestick_patterns", 0.7 * sc,
                   ", ".join(f"{e.kind} ({e.direction})" for e in pats) or "no directional pattern in last 3 bars",
                   int(b.t[last]), float(b.c[last])))

    # liquidity (recent sweeps are reversal evidence in their stated direction)
    sw = [e for e in pa.sweeps if last - e.idx < cfg.recent_bars]
    out.append(_ev("liquidity", "liquidity_sweep", sum(1 if e.direction == "bullish" else -1 for e in sw),
                   "; ".join(e.evidence for e in sw[-2:]) or "no sweep in last %d bars" % cfg.recent_bars,
                   sw[-1].ts if sw else None, sw[-1].price if sw else None))

    # zones interacting with price
    zs = [z for z in pa.order_blocks + pa.fvgs + pa.zones + pa.breakers
          if z.status not in ("filled", "invalidated", "broken") and z.low is not None and z.high is not None
          and last - z.idx <= 300]
    z_score, z_notes = 0.0, []
    for z in zs:
        touching = b.l[last] <= z.high and b.h[last] >= z.low
        near = np.isfinite(a) and min(abs(b.c[last] - z.low), abs(b.c[last] - z.high)) <= 0.5 * a
        if touching or near:
            w = 1.0 if touching else 0.5
            z_score += w * (1 if z.direction == "bullish" else -1)
            z_notes.append(f"{z.kind} {z.direction} {z.low:.6g}-{z.high:.6g}")
    out.append(_ev("zones", "zones_of_interest", z_score / 2, "; ".join(z_notes[:3]) or "price not at an unmitigated zone"))

    # multi-timeframe
    if inp.mtf and inp.mtf.get("available"):
        out.append(_ev("multi_timeframe", "mtf_alignment", inp.mtf["score"],
                       "; ".join(f"{v['timeframe']}({v['role']}): {v['note']}" for v in inp.mtf["views"])))

    # historical analogues (frequency edge vs unconditional base rate)
    an = inp.analogues
    if an and an.sufficient:
        s_ = an.stats
        edge_l = s_["long_tp_before_sl"]["frequency"] - s_["base_rate_long"]["frequency"]
        edge_s = s_["short_tp_before_sl"]["frequency"] - s_["base_rate_short"]["frequency"]
        out.append(_ev("historical_analogues", "historical_analogues", (edge_l - edge_s) / 0.2,
                       f"{an.n_obs} analogues: long TP-first {s_['long_tp_before_sl']['frequency']:.0%} "
                       f"(base {s_['base_rate_long']['frequency']:.0%}), short {s_['short_tp_before_sl']['frequency']:.0%} "
                       f"(base {s_['base_rate_short']['frequency']:.0%})"))

    # ML
    if inp.ml:
        validated = inp.ml.get("is_calibrated") and inp.ml.get("validation_status") == PASSED
        out.append(_ev("ml_model", f"ml_{inp.ml.get('algorithm', 'model')}", inp.ml["p_long_tp_first"] - inp.ml["p_short_tp_first"],
                       f"P(long TP first)={inp.ml['p_long_tp_first']:.2f}, P(short)={inp.ml['p_short_tp_first']:.2f}"
                       + ("" if validated else " [research-only: weight 0]"), weight=WEIGHTS["ml_model"] if validated else 0.0))
    return out


def decide(inp: DecisionInputs, cfg: DecisionConfig | None = None) -> Decision:
    cfg = cfg or DecisionConfig()
    b, n = inp.bars, len(inp.bars)
    wait: list[str] = []
    warnings: list[str] = list(inp.quality.get("issues", []))
    if n < 60:
        wait.append(f"only {n} bars available; need at least 60 for structure analysis")
        panel = confidence_panel(ml=inp.ml, analogues=inp.analogues.to_dict() if inp.analogues else None,
                                 confluence=None, confluence_components=[], quality=inp.quality, warnings=warnings)
        return Decision("WAIT", None, [], wait, warnings, None, panel,
                        explain("WAIT", inp.symbol, inp.timeframe, None, [], wait, None, warnings),
                        int(b.t[-1]) if n else None)

    evidence = collect_evidence(inp, cfg)
    tw = sum(e["weight"] for e in evidence)
    contrib = [e["weight"] * e["score"] for e in evidence]
    confluence = float(sum(contrib) / tw) if tw > 0 else 0.0
    cand = "BUY" if confluence > 0 else "SELL" if confluence < 0 else None
    comps = [{"name": e["name"], "weight": e["weight"], "score": e["score"], "contribution": c / tw if tw else 0}
             for e, c in zip(evidence, contrib)]

    if inp.quality["score"] < cfg.min_quality:
        wait.append(f"data quality {inp.quality['score']:.2f} below {cfg.min_quality}: " + "; ".join(inp.quality["issues"]))
    if not inp.price_calibrated:
        wait.append("price scale could not be calibrated; price levels (entry/stop/target) are not reliable")
    if abs(confluence) < cfg.confluence_threshold:
        wait.append(f"confluence {confluence:+.2f} is below the +/-{cfg.confluence_threshold} threshold (weak evidence)")
    if cand and inp.mtf and inp.mtf.get("available"):
        sign = 1 if cand == "BUY" else -1
        if inp.mtf["conflict"]:
            wait.append("higher timeframe and entry timeframe structure disagree")
        else:
            higher = next((v for v in inp.mtf["views"] if v["role"] == "higher"), None)
            if higher and higher["direction"] == -sign:
                wait.append(f"{cand} would trade against the {higher['timeframe']} structure")
    if cand:
        sign = 1 if cand == "BUY" else -1
        pro = sum(abs(c) for c in contrib if c * sign > 0)
        con = sum(abs(c) for c in contrib if c * sign < 0)
        if pro + con > 0 and con / (pro + con) > cfg.max_opposition:
            wait.append(f"contradictory evidence: {con / (pro + con):.0%} of the weighted signal opposes {cand}")
    an = inp.analogues
    if cand and an and an.sufficient:
        key = "long_tp_before_sl" if cand == "BUY" else "short_tp_before_sl"
        base = an.stats["base_rate_long" if cand == "BUY" else "base_rate_short"]["frequency"]
        hi = an.stats[key]["ci_high"]
        if hi is not None and hi < base:
            wait.append(f"similar historical setups hit TP first less often than the base rate ({an.stats[key]['frequency']:.0%} vs {base:.0%})")
    elif an and not an.sufficient:
        warnings.append(f"historical analogues unavailable: {an.reason}")
    elif an is None:
        warnings.append("no historical analogue evidence")
    if inp.ml and not (inp.ml.get("is_calibrated") and inp.ml.get("validation_status") == PASSED):
        warnings.append("ML model is research-only (not validated); excluded from the decision")
    if not inp.ml:
        warnings.append("no trained ML model for this instrument/timeframe")

    plan: TradePlan | None = None
    if cand and not wait:
        zones = inp.pa.order_blocks + inp.pa.fvgs + inp.pa.zones + inp.pa.breakers
        plan, why = build_trade_plan(b, cand, float(inp.pa.atr[-1]), inp.pa.swings, zones, cfg.min_rr)
        if plan is None:
            wait.append(f"no valid trade plan: {why}")
        else:
            warnings += plan.warnings

    decision = "WAIT" if (wait or not cand) else cand
    if decision == "WAIT":
        plan = None
    panel = confidence_panel(ml=inp.ml, analogues=an.to_dict() if an else None, confluence=confluence,
                             confluence_components=comps, quality=inp.quality, warnings=warnings)
    text = explain(decision, inp.symbol, inp.timeframe, confluence, evidence, wait,
                   asdict(plan) if plan else None, warnings)
    return Decision(decision, confluence, evidence, wait, warnings, plan, panel, text, int(b.t[-1]))


__all__ = ["decide", "DecisionConfig", "DecisionInputs", "Decision", "Event"]
