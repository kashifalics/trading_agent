"""Pattern edge study: does a price-action / indicator pattern predict the next trade better than chance?

For every (timeframe, pattern, direction) hypothesis:
  * the signal fires at the CLOSE of a bar (causal: every detector confirms on or before that bar);
  * the trade enters at the next open with a triple barrier (+2 ATR target, -1 ATR stop, 24 bars), same-bar ambiguity = stop;
  * net R = gross R - round-trip cost / stop distance;
  * overlapping signals of the same pattern are skipped (no inflated n);
  * LIFT = mean R of the pattern minus mean R of taking the same direction on EVERY bar (removes drift/beta);
  * discovery on the first 60% of history (labels never reach the held-out part), confirmation on the last 40%,
    Benjamini-Hochberg FDR across all discovery tests, Holm correction across the confirmation tests.
A pattern is only "confirmed" if it survives both AND still shows a positive lift (p < 0.05) when the entry is delayed by one
extra bar (kills microstructure artifacts: edges that exist only if you could fill at the very first print of the next bar);
"tradeable" additionally needs positive NET expectancy out of sample.
"""
from dataclasses import dataclass

import numpy as np
from scipy import stats

from app.feature_engineering.indicators import ema, rsi
from app.feature_engineering.labels import LabelConfig, triple_barrier
from app.market_data.bars import Bars
from app.price_action.engine import PriceActionResult, analyze_price_action

CFG = LabelConfig(horizon=24, tp_atr=2.0, sl_atr=1.0)
SPLIT = 0.6
MIN_N_IS, MIN_N_OOS = 30, 20
ZONE_KINDS = ("fvg", "order_block", "breaker_block", "demand_zone", "supply_zone")


@dataclass
class Outcomes:
    gross_long: np.ndarray
    gross_short: np.ndarray
    cost_r: np.ndarray
    win_long: np.ndarray
    win_short: np.ndarray
    valid: np.ndarray


def outcomes(bars: Bars, atr: np.ndarray, cost_frac: float) -> Outcomes:
    lab = triple_barrier(bars, atr, CFG)
    rr = CFG.tp_atr / CFG.sl_atr
    fwd = np.nan_to_num(lab.fwd_ret_atr)

    def r(res, sign):
        return np.where(res == 1, rr, np.where(res == -1, -1.0, np.clip(sign * fwd / CFG.sl_atr, -1, rr)))

    with np.errstate(divide="ignore", invalid="ignore"):
        cost = cost_frac * bars.c / (CFG.sl_atr * atr)
    valid = lab.valid & np.isfinite(cost)
    return Outcomes(r(lab.long_result, 1), r(lab.short_result, -1), np.where(valid, cost, 0.0),
                    lab.long_result == 1, lab.short_result == 1, valid)


# ------------------------------------------------------------------ signals (all causal, index = bar whose CLOSE confirms)
def _zone_retests(bars: Bars, events, max_age: int = 200) -> list[tuple[int, int]]:
    """First bar that trades back into a zone (before it is closed through) = 'mitigation / retest' entry signal."""
    out = []
    n = len(bars)
    for e in events:
        if e.low is None or e.high is None:
            continue
        bull = e.direction == "bullish"
        for k in range(e.idx + 2, min(n, e.idx + 1 + max_age)):
            if (bull and bars.c[k] < e.low) or (not bull and bars.c[k] > e.high):
                break  # invalidated before any retest
            if bars.l[k] <= e.high and bars.h[k] >= e.low:
                out.append((k, 1 if bull else -1))
                break
    return out


def collect_signals(bars: Bars, pa: PriceActionResult, intraday_hours: bool) -> dict[str, np.ndarray]:
    n = len(bars)
    sig: dict[str, list[int]] = {}

    def add(name: str, i: int, d: int):
        sig.setdefault(f"{name}:{'long' if d == 1 else 'short'}", []).append(i)

    dirv = {"bullish": 1, "bearish": -1}
    for e in pa.candles:
        if e.direction in dirv and e.kind not in ("outside_bar",):
            add(e.kind, e.idx, dirv[e.direction])
    for e in pa.breaks:
        add(e.kind.lower(), e.idx, dirv[e.direction])
    for e in pa.sweeps:
        add("liquidity_sweep", e.idx, dirv[e.direction])
    for e in pa.equal_levels:
        add(e.kind, e.idx, dirv[e.direction])
    groups = {"fvg": pa.fvgs, "order_block": pa.order_blocks, "breaker_block": pa.breakers,
              "demand_zone": [z for z in pa.zones if z.kind == "demand_zone"], "supply_zone": [z for z in pa.zones if z.kind == "supply_zone"]}
    for kind, evs in groups.items():
        for e in evs:
            add(f"{kind}_formed", e.idx, dirv[e.direction])
        for k, d in _zone_retests(bars, evs):
            add(f"{kind}_retest", k, d)
    # inside-bar breakout
    for e in pa.candles:
        if e.kind == "inside_bar" and e.idx + 1 < n and e.start_idx is not None:
            k, mh, ml = e.idx + 1, bars.h[e.start_idx], bars.l[e.start_idx]
            if bars.c[k] > mh:
                add("inside_bar_breakout", k, 1)
            elif bars.c[k] < ml:
                add("inside_bar_breakout", k, -1)
    # indicator patterns
    c = bars.c
    e20, e50 = ema(c, 20), ema(c, 50)
    for i in range(51, n):
        if e20[i - 1] <= e50[i - 1] and e20[i] > e50[i]:
            add("ema20_50_cross", i, 1)
        elif e20[i - 1] >= e50[i - 1] and e20[i] < e50[i]:
            add("ema20_50_cross", i, -1)
    sma200 = np.convolve(c, np.ones(200) / 200, mode="full")[:n]
    for i in range(201, n):
        if c[i - 1] <= sma200[i - 1] and c[i] > sma200[i]:
            add("sma200_cross", i, 1)
        elif c[i - 1] >= sma200[i - 1] and c[i] < sma200[i]:
            add("sma200_cross", i, -1)
    r = rsi(c, 14)
    for i in range(16, n):
        if r[i - 1] < 30 <= r[i]:
            add("rsi_oversold_exit", i, 1)
        elif r[i - 1] > 70 >= r[i]:
            add("rsi_overbought_exit", i, -1)
    for i in range(21, n):
        if c[i] > bars.h[i - 20:i].max():
            add("donchian20_breakout", i, 1)
        elif c[i] < bars.l[i - 20:i].min():
            add("donchian20_breakout", i, -1)
    if intraday_hours:
        for i in range(n):
            h = int((bars.t[i] % 86400) // 3600)
            add(f"hour_{h:02d}utc", i, 1)
            add(f"hour_{h:02d}utc", i, -1)
    return {k: np.array(sorted(set(v)), dtype=int) for k, v in sig.items()}


# ------------------------------------------------------------------ statistics
def _accept(idx: np.ndarray, valid: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Non-overlapping signals inside [lo, hi): a new one must start after the previous label window."""
    out, busy = [], -1
    for i in idx:
        if i < lo or i >= hi or not valid[i] or i <= busy:
            continue
        out.append(i)
        busy = i + CFG.horizon
    return np.array(out, dtype=int)


def _t_greater(x: np.ndarray, mu: float) -> tuple[float, float]:
    n = len(x)
    if n < 3 or x.std(ddof=1) == 0:
        return 0.0, 1.0
    t = (x.mean() - mu) / (x.std(ddof=1) / np.sqrt(n))
    return float(t), float(stats.t.sf(t, n - 1))


def evaluate(idx: np.ndarray, d: int, o: Outcomes, lo: int, hi: int) -> dict | None:
    sel = _accept(idx, o.valid, lo, hi)
    if len(sel) == 0:
        return None
    gross = (o.gross_long if d == 1 else o.gross_short)
    win = (o.win_long if d == 1 else o.win_short)
    g, net = gross[sel], gross[sel] - o.cost_r[sel]
    rng = np.arange(lo, hi)
    rng = rng[o.valid[lo:hi]]
    base_g, base_n = float(gross[rng].mean()), float((gross[rng] - o.cost_r[rng]).mean())
    t_lift, p_lift = _t_greater(g, base_g)  # lift is cost-independent (same costs apply to the baseline)
    t_net, p_net = _t_greater(net, 0.0)
    return {"n": int(len(sel)), "win_rate": float(win[sel].mean()), "gross_r": float(g.mean()), "net_r": float(net.mean()),
            "base_gross_r": base_g, "base_net_r": base_n, "lift_r": float(g.mean() - base_g), "p_lift": p_lift,
            "p_net_positive": p_net, "net_sd": float(net.std(ddof=1)) if len(sel) > 1 else None}


def bh_fdr(p: np.ndarray) -> np.ndarray:
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, i in zip(range(n, 0, -1), order[::-1]):
        prev = min(prev, p[i] * n / rank)
        q[i] = prev
    return q


def study_timeframe(bars: Bars, cost_frac: float, tf: str) -> list[dict]:
    """All hypotheses for one series: discovery (first 60%) and confirmation (last 40%) statistics."""
    pa = analyze_price_action(bars)
    o = outcomes(bars, pa.atr, cost_frac)
    n = len(bars)
    split = int(n * SPLIT)
    sigs = collect_signals(bars, pa, intraday_hours=bars.step <= 3600)
    rows = []
    for name, idx in sigs.items():
        pat, side = name.rsplit(":", 1)
        d = 1 if side == "long" else -1
        ins = evaluate(idx, d, o, 0, split - CFG.horizon)
        oos = evaluate(idx, d, o, split, n)
        late = evaluate(idx + 1, d, o, split, n)  # same signals, entry one bar later than the earliest possible fill
        rows.append({"tf": tf, "pattern": pat, "side": side, "is": ins, "oos": oos, "oos_delay1": late, "events_total": int(len(idx))})
    return rows


def apply_multiple_testing(rows: list[dict], fdr_q: float = 0.20, alpha: float = 0.05) -> dict:
    """Mark candidates (discovery FDR) and confirmations (Holm over candidates); mutates rows, returns counts."""
    testable = [r for r in rows if r["is"] and r["is"]["n"] >= MIN_N_IS]
    if not testable:
        return {"tested": 0, "candidates": 0, "confirmed_gross": 0, "confirmed_net": 0}
    q = bh_fdr(np.array([r["is"]["p_lift"] for r in testable]))
    for r, qi in zip(testable, q):
        r["is_q"] = float(qi)
    cands = [r for r in testable if r["is_q"] < fdr_q and r["is"]["lift_r"] > 0]
    ok = [r for r in cands if r["oos"] and r["oos"]["n"] >= MIN_N_OOS]
    ps = sorted((r["oos"]["p_lift"], i) for i, r in enumerate(ok))
    m = len(ps)
    holm = {}
    run = 0.0
    for rank, (p, i) in enumerate(ps):
        run = max(run, min(1.0, p * (m - rank)))
        holm[i] = run
    cg = cn = 0
    for i, r in enumerate(ok):
        r["oos_holm_p"] = holm[i]
        late = r.get("oos_delay1")  # rows built without it (unit tests) skip the gate; real studies always have it
        r["delay_robust"] = True if "oos_delay1" not in r else bool(late and late["lift_r"] > 0 and late["p_lift"] < alpha)
        r["confirmed_gross"] = bool(holm[i] < alpha and r["oos"]["lift_r"] > 0 and r["delay_robust"])
        r["confirmed_net"] = bool(r["confirmed_gross"] and r["oos"]["net_r"] > 0 and r["oos"]["p_net_positive"] < alpha)
        cg += r["confirmed_gross"]
        cn += r["confirmed_net"]
    for r in cands:
        r["candidate"] = True
    failed_delay = sum(1 for r in ok if holm_ok(r, alpha) and not r["delay_robust"])
    return {"tested": len(testable), "candidates": len(cands), "oos_testable": len(ok), "confirmed_gross": cg, "confirmed_net": cn,
            "passed_oos_but_failed_one_bar_delay": failed_delay, "fdr_q": fdr_q, "alpha": alpha}


def holm_ok(r: dict, alpha: float) -> bool:
    return r.get("oos_holm_p", 1.0) < alpha and r["oos"]["lift_r"] > 0
