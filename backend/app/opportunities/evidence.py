"""Builds the detailed, computed-evidence explanation for an opportunity. Every sentence is derived from numbers the engine
actually computed; nothing here is generated free text about the market."""
from dataclasses import asdict

import numpy as np

from app.core.events import iso
from app.opportunities.analysis import TF, tf_result
from app.opportunities.config import BIAS_TFS, SCORE_LABEL, StyleProfile
from app.opportunities.setup import Bias, Setup

DIRWORD = {1: "bullish", -1: "bearish", 0: "undetermined"}


def mtf_rows(tfs: dict[str, TF], setup_tf: str | None, bias: Bias, direction: int, prof: StyleProfile) -> list[dict]:
    roles = {}
    if setup_tf:
        roles[setup_tf] = "setup"
        for r, h in zip(("higher", "intermediate"), reversed(BIAS_TFS.get(setup_tf, ()))):
            roles[h] = r
    rows = []
    for code, t in tfs.items():
        row = {"timeframe": code, "status": t.status, "role": roles.get(code, "context"), "relevant_to_style": code in prof.setup_tfs,
               "reason": t.reason or t.error, "n_bars": t.n_bars, "derived_from": t.derived_from, "stale_bars": t.stale_bars}
        if t.ok:
            pa = t.pa
            tr = int(pa.trend[-1]) or int(pa.bias)
            brk = pa.breaks[-1] if pa.breaks else None
            row.update({"trend": int(pa.trend[-1]), "direction": tr, "summary": tf_result(t)["summary"],
                        "last_break": f"{brk.kind}:{brk.direction}" if brk else None,
                        "stance": "neutral" if not direction or not tr else "supports" if tr == direction else "opposes"})
        rows.append(row)
    return rows


def _fmt(p: float | None) -> str:
    return "-" if p is None else f"{p:.6g}"


def thesis(symbol: str, prof: StyleProfile, s: Setup | None, lean: int, bias: Bias, setup_tf: str | None, t: TF | None) -> str:
    if t is None or setup_tf is None:
        return f"No {prof.label.lower()} timeframe has enough usable data for {symbol}."
    pa = t.pa
    tr = int(pa.trend[-1])
    parts = [f"{setup_tf} structure is {DIRWORD[tr]}"]
    if pa.breaks:
        b = pa.breaks[-1]
        parts[0] += f" (last {b.kind} {b.direction}, {len(t.bars) - 1 - b.idx} bars ago)"
    if bias.views:
        parts.append("higher timeframes: " + ", ".join(f"{v['timeframe']} {DIRWORD[v['direction']]}" for v in bias.views)
                     + (" (disagree)" if bias.conflict else ""))
    else:
        parts.append("no higher-timeframe data available for bias")
    if s:
        parts.append(f"{s.direction} lean via {s.setup_type.replace('_', ' ')}: retracement into a {s.poi['kind'].replace('_', ' ')} "
                     f"{_fmt(s.entry_low)}-{_fmt(s.entry_high)} with structural stop {_fmt(s.stop_loss)}; first target {_fmt(s.targets[0]['price'])} "
                     f"({s.risk_reward:.2f}R)")
    else:
        parts.append(f"no tradeable setup; lean is {DIRWORD[lean]}")
    return ". ".join(parts) + "."


def risks(symbol: str, prof: StyleProfile, s: Setup | None, bias: Bias, t: TF, analogue: dict, validation: dict, direction: int) -> dict:
    opp, warn = [], []
    d = direction
    if d:
        for v in bias.views:
            if v["direction"] == -d:
                opp.append(f"{v['timeframe']} structure is {DIRWORD[v['direction']]}, opposite to the trade ({v['note']})")
        pa, last = t.pa, len(t.bars) - 1
        opp_dir = "bearish" if d == 1 else "bullish"
        for e in pa.breaks[-3:]:
            if e.direction == opp_dir and last - e.idx <= 20:
                opp.append(f"{e.kind} {e.direction} {last - e.idx} bars ago on {t.tf}")
        for e in pa.candles:
            if e.direction == opp_dir and last - e.idx <= 3 and e.kind not in ("doji", "inside_bar", "outside_bar"):
                opp.append(f"{e.kind.replace('_', ' ')} ({e.direction}) {last - e.idx} bars ago")
        for e in pa.sweeps[-3:]:
            if e.direction == opp_dir and last - e.idx <= 12:
                opp.append(f"liquidity sweep {e.direction} {last - e.idx} bars ago")
        pdz = pa.premium_discount
        if pdz and ((d == 1 and pdz.status == "premium") or (d == -1 and pdz.status == "discount")):
            opp.append(f"price is in the {pdz.status} half of its dealing range, unfavourable for a {'BUY' if d == 1 else 'SELL'}")
    if s:
        warn += s.warnings
        if s.cost_r > 0.5 * prof.max_cost_r:
            warn.append(f"round-trip costs consume {s.cost_r:.2f}R (limit {prof.max_cost_r}R)")
    if analogue.get("available"):
        if analogue.get("edge_within_noise"):
            warn.append("historical analogue frequency is within sampling noise of the base rate")
        if analogue["sample_quality"] != "moderate":
            warn.append(f"analogue sample is {analogue['sample_quality']} (n={analogue['n_obs']})")
    else:
        warn.append(f"no analogue evidence: {analogue.get('reason')}")
    st = validation["status"]
    if st != "validated":
        warn.append({"untested": "this setup rule set has NOT been validated out of sample",
                     "no_edge": "out-of-sample testing found no evidence of a positive edge",
                     "negative": "out-of-sample testing found NEGATIVE expectancy after costs"}[st] + f" ({validation['summary']})")
    for q in t.quality.get("issues", []):
        warn.append(q)
    return {"opposing_evidence": opp, "warnings": list(dict.fromkeys(warn))}


def candle_evidence(t: TF, s: Setup | None) -> list[dict]:
    b, pa = t.bars, t.pa
    last = len(b) - 1
    evs = [e for e in pa.candles if last - e.idx <= 6 and e.kind not in ("doji",) and e.direction != "neutral"]
    out = []
    for e in evs[-6:]:
        i = int(np.searchsorted(b.t, e.ts))
        out.append({"kind": e.kind, "direction": e.direction, "ts": e.ts, "time": iso(e.ts), "evidence": e.evidence,
                    "candle": {"o": float(b.o[i]), "h": float(b.h[i]), "l": float(b.l[i]), "c": float(b.c[i])},
                    "role": "confirmation" if s and any(c["ts"] == e.ts for c in s.confirmations) else "context"})
    return out


def structure_block(t: TF) -> dict:
    r = tf_result(t)
    return {k: r[k] for k in ("timeframe", "trend", "last_break", "last_break_bars_ago", "zone", "range_position", "swings",
                              "notable_events", "live_zones", "levels", "trendlines", "breakouts", "summary")}


def chart_overlays(t: TF, s: Setup | None, analogue: dict) -> dict:
    pa, b = t.pa, t.bars
    last = len(b) - 1
    px = float(b.c[last])
    live = [z for z in pa.fvgs + pa.order_blocks + pa.breakers + pa.zones
            if z.status not in ("filled", "invalidated", "broken") and z.low is not None and last - z.idx <= 300]
    live.sort(key=lambda z: min(abs(px - z.low), abs(px - z.high)))
    zones = [{"kind": z.kind, "direction": z.direction, "from": z.ts, "low": z.low, "high": z.high} for z in live[:5]]
    if s and not any(abs(z["low"] - s.poi["low"]) < 1e-9 and abs(z["high"] - s.poi["high"]) < 1e-9 for z in zones):
        zones.append({"kind": s.poi["kind"], "direction": "bullish" if s.direction == "BUY" else "bearish", "from": s.poi["ts"],
                      "low": s.poi["low"], "high": s.poi["high"]})
    levels = [{"kind": e.kind, "low": e.low, "high": e.high, "from": e.start_ts, "touches": e.meta.get("touches")} for e in t.cx.levels[:4]]
    lines = [{"kind": e.kind, "from_ts": int(b.t[e.meta["anchor_idx"][0]]), "from_price": e.meta["anchor_price"][0],
              "to_ts": int(b.t[last]), "to_price": e.meta["value_now"]} for e in t.cx.trendlines if e.kind.startswith("trendline")]
    marks = [{"kind": e.kind, "direction": e.direction, "ts": e.ts, "price": e.price} for e in (pa.breaks[-4:] + pa.sweeps[-2:])]
    ana = [{"ts": n["ts"], "outcome": n["outcome"], "similarity": n["similarity"]} for n in analogue.get("neighbors", [])]
    return {"timeframe": t.tf, "zones": zones, "levels": levels, "trendlines": lines, "markers": marks, "analogue_markers": ana}


def build_evidence(*, symbol: str, provider: str, prof: StyleProfile, tfs: dict[str, TF], setup_tf: str | None, setup: Setup | None,
                   lean: int, wait_reasons: list[str], bias: Bias, analogue: dict, score: dict | None, validation: dict,
                   actionable: bool, note: str | None = None) -> dict:
    t = tfs.get(setup_tf) if setup_tf else None
    d = (1 if setup.direction == "BUY" else -1) if setup else lean
    ev = {
        "actionable": actionable, "note": note, "scope": prof.scope, "style": prof.key, "symbol": symbol, "provider": provider,
        "lean": DIRWORD[lean], "wait_reasons": wait_reasons, "score": score, "score_label": SCORE_LABEL, "validation": validation,
        "bias": asdict(bias), "analogues": analogue, "setup": asdict(setup) if setup else None,
        "multi_timeframe": mtf_rows(tfs, setup_tf, bias, d, prof),
    }
    if t is not None and t.ok:
        ev.update({
            "thesis": thesis(symbol, prof, setup, lean, bias, setup_tf, t), "structure": structure_block(t),
            "candlesticks": candle_evidence(t, setup), "risks": risks(symbol, prof, setup, bias, t, analogue, validation, d),
            "chart": chart_overlays(t, setup, analogue),
            "data": {"setup_timeframe": setup_tf, "n_bars": t.n_bars, "stale_bars": t.stale_bars, "derived_from": t.derived_from,
                     "quality": t.quality, "last_bar": iso(int(t.bars.t[-1])), "volume_available": bool(np.isfinite(t.bars.v).any())},
        })
    return ev
