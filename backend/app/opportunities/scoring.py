"""Transparent evidence score (0-100). NOT a probability of winning.

score = clamp( 100 * sum(weight_i * component_i) - penalties, 0, 100 ), then capped by what the strategy's measured
validation supports (an untested or negative strategy can never score as if it were validated).
Every component, weight, penalty and cap is returned so the UI can show exactly why a setup got its number.
The score is never calibrated against outcomes, so it is always labelled "Evidence Score - Not Win Probability".
"""
from dataclasses import dataclass

import numpy as np

from app.opportunities.config import (
    PENALTIES,
    SCORE_LABEL,
    VALIDATION_CAPS,
    VALIDATION_COMPONENT,
    WEIGHTS,
    CONFIG_VERSION,
    StyleProfile,
)
from app.opportunities.setup import Bias, Setup


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(max(lo, min(hi, x)))


@dataclass
class ScoreInputs:
    setup: Setup
    bias: Bias
    profile: StyleProfile
    trend: int  # setup-timeframe structure trend at the last bar
    recent_break_same_dir: bool
    zone_position: float | None  # 0 (bottom) .. 1 (top) of the dealing range
    poi_touches: int | None
    feats: dict  # ret_10, slope_20, rsi_14 (0..1), vol_ratio, atr_pct_rank (0..1)
    analogue: dict
    quality: dict  # score, issues, stale_bars, gap_count
    validation: dict


def _comp(name: str, raw: float, detail: str) -> dict:
    return {"name": name, "weight": WEIGHTS[name], "raw": round(clamp(raw), 4), "points": round(100 * WEIGHTS[name] * clamp(raw), 2), "detail": detail}


def score_setup(si: ScoreInputs) -> dict:
    s, p = si.setup, si.profile
    d = 1 if s.direction == "BUY" else -1
    comps: list[dict] = []

    # 1. higher-timeframe alignment
    if si.bias.views:
        raw = (d * si.bias.score + 1) / 2
        comps.append(_comp("htf_alignment", raw, "; ".join(f"{v['timeframe']}: {v['note']}" for v in si.bias.views)
                           + (" | higher timeframes DISAGREE" if si.bias.conflict else "")))
    else:
        comps.append(_comp("htf_alignment", 0.35, "no higher-timeframe data available (neutral-low, not assumed aligned)"))

    # 2. structure quality
    pts, why = 0.0, []
    if si.trend == d:
        pts += 0.40
        why.append("setup-timeframe structure trend agrees")
    if si.recent_break_same_dir:
        pts += 0.20
        why.append("recent same-direction BOS/CHoCH")
    zp = si.zone_position
    if zp is not None and ((d == 1 and zp <= 0.5) or (d == -1 and zp >= 0.5)):
        pts += 0.20
        why.append(f"zone in the {'discount' if d == 1 else 'premium'} half of the dealing range ({zp:.0%})")
    elif zp is not None and ((d == 1 and zp <= 0.65) or (d == -1 and zp >= 0.35)):
        pts += 0.08
        why.append(f"zone near equilibrium ({zp:.0%})")
    kind = s.poi["kind"]
    if kind in ("order_block", "breaker_block", "demand_zone", "supply_zone"):
        pts += 0.20
        why.append(kind.replace("_", " "))
    elif kind == "fvg":
        pts += 0.15
        why.append("fair value gap")
    elif si.poi_touches:
        pts += 0.20 if si.poi_touches >= 3 else 0.12
        why.append(f"S/R band with {si.poi_touches} touches")
    comps.append(_comp("structure_quality", pts, "; ".join(why) or "no structural support"))

    # 3. price-action confirmation
    got = {c["type"] for c in s.confirmations}
    w = {"rejection_candle": 0.40, "structure_break": 0.30, "liquidity_sweep": 0.20, "retest": 0.15}
    comps.append(_comp("price_action_confirmation", sum(w[t] for t in got),
                       ", ".join(sorted(got)) if got else "no confirming event yet (waiting for confirmation)"))

    # 4. historical analogues
    an = si.analogue
    if an.get("available") and an.get("edge_vs_base") is not None:
        n = an["n_obs"]
        raw = clamp(0.5 + an["edge_vs_base"] / 0.30) * min(1.0, n / 100)
        comps.append(_comp("historical_analogues", raw,
                           f"{n} analogues: TP-first {an['tp_first']['frequency']:.0%} vs base {an['base_rate']['frequency']:.0%} "
                           f"({an['sample_quality']} sample{', within noise' if an.get('edge_within_noise') else ''})"))
    else:
        comps.append(_comp("historical_analogues", 0.0, an.get("reason") or "no analogue evidence"))

    # 5. momentum
    f = si.feats
    if all(f.get(k) is not None and np.isfinite(f[k]) for k in ("ret_10", "slope_20", "rsi_14")):
        a1, a2 = d * np.tanh(f["ret_10"] / 2), d * np.tanh(f["slope_20"] / 2)
        rsi_s = 1 - min(1.0, abs(f["rsi_14"] - (0.58 if d == 1 else 0.42)) / 0.35)
        comps.append(_comp("momentum", 0.7 * clamp(0.5 + 0.25 * a1 + 0.25 * a2) + 0.3 * rsi_s,
                           f"10-bar move {f['ret_10']:+.2f} ATR, 20-bar slope {f['slope_20']:+.2f}, RSI {f['rsi_14'] * 100:.0f}"))
    else:
        comps.append(_comp("momentum", 0.0, "momentum features unavailable"))

    # 6. volatility suitability
    rk, vr = f.get("atr_pct_rank"), f.get("vol_ratio")
    if rk is not None and np.isfinite(rk):
        raw = 1.0 if 0.15 <= rk <= 0.85 else 0.3 + 0.7 * (min(rk, 1 - rk) / 0.15)
        if vr is not None and np.isfinite(vr) and vr > 2:
            raw *= 0.5
        comps.append(_comp("volatility_suitability", raw, f"ATR at the {rk:.0%} percentile of its own history"
                           + (f"; short/long ATR ratio {vr:.2f}" if vr is not None and np.isfinite(vr) else "")))
    else:
        comps.append(_comp("volatility_suitability", 0.0, "volatility history unavailable"))

    # 7. risk / reward
    rr = s.risk_reward
    comps.append(_comp("risk_reward", 0.0 if rr < p.min_rr else 0.5 + 0.5 * clamp((rr - p.min_rr) / p.min_rr),
                       f"TP1 {rr:.2f}R (style minimum {p.min_rr}R)"))

    # 8. data quality
    comps.append(_comp("data_quality", si.quality["score"], "; ".join(si.quality.get("issues") or []) or "no data issues found"))

    # 9. strategy validation
    st = si.validation["status"]
    comps.append(_comp("strategy_validation", VALIDATION_COMPONENT[st], si.validation.get("summary", st)))

    raw_total = sum(c["points"] for c in comps)
    pen: list[dict] = []

    def add(name: str, pts: float, why: str):
        pen.append({"name": name, "points": -round(pts, 2), "detail": why})

    if si.bias.conflict:
        add("conflicting_timeframes", PENALTIES["conflicting_timeframes"], "higher timeframes disagree with each other")
    stale = si.quality.get("stale_bars")
    if stale is not None and stale > p.max_stale_bars:
        add("stale_data", PENALTIES["stale_data_scalping" if p.key == "scalping" else "stale_data"],
            f"latest complete candle is {stale:.0f} bars old (limit {p.max_stale_bars})")
    gaps = si.quality.get("gap_count") or 0
    if gaps:
        add("missing_candles", min(PENALTIES["gaps_max"], PENALTIES["gaps_per_gap"] * gaps), f"{gaps} gap(s) in stored history")
    n_an = an.get("n_obs") or 0
    if n_an < 30:
        add("weak_sample", PENALTIES["sample_lt_30"], f"only {n_an} historical analogues (< 30)")
    elif n_an < 100:
        add("weak_sample", PENALTIES["sample_lt_100"], f"{n_an} historical analogues (< 100)")
    if (rk is not None and np.isfinite(rk) and rk > 0.95) or (vr is not None and np.isfinite(vr) and vr > 2):
        add("excessive_volatility", PENALTIES["excessive_volatility"], "ATR in its top 5% or short-term volatility more than doubled")
    if rr < 1.25 * p.min_rr:
        add("poor_risk_reward", PENALTIES["poor_rr"], f"TP1 {rr:.2f}R is close to the {p.min_rr}R minimum")
    score = clamp((raw_total + sum(x["points"] for x in pen)) / 100) * 100
    cap = VALIDATION_CAPS[st]
    capped = score > cap
    final = min(score, cap)
    return {"score": round(final, 1), "uncapped_score": round(score, 1), "label": SCORE_LABEL, "calibrated": False,
            "components": comps, "penalties": pen,
            "cap": {"status": st, "max_score": cap, "applied": capped,
                    "reason": f"strategy validation status '{st}' limits the score to {cap:.0f}" if capped else None},
            "method_version": CONFIG_VERSION,
            "note": "Weighted evidence quality. It is not a probability, was not calibrated on outcomes, and must not be read as one."}
