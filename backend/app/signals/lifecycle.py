"""In-memory lifecycle of actionable plans: reports TRADE_INVALIDATED / TRADE_EXPIRED when a plan that was actionable on a timeframe
stops qualifying. Kept in process memory (resets when the API restarts); the persistent signal history is paper trading (app/paper)."""
import numpy as np

from app.signals.context import fmt
from app.signals.engine import ACTIONABLE, Frame

KEEP = ("setup_key", "side", "entry", "stop_loss", "invalidation", "signal_ts", "valid_until_ts", "state", "instruction")


def _first(mask: np.ndarray) -> int | None:
    idx = np.flatnonzero(mask)
    return int(idx[0]) if len(idx) else None


def what_happened(prev: dict, f: Frame | None, tf: str, now_ts: int) -> dict:
    """Why a previously actionable plan no longer qualifies (target, invalidation, time, or the rules simply stopped holding)."""
    if f is not None and f.bars is not None and len(f.bars):
        b = f.bars
        m = b.t >= int(prev["signal_ts"])
        buy = prev["side"] == "BUY"
        if m.any():
            c, h, lo = b.c[m], b.h[m], b.l[m]
            i_inv = _first(c < prev["invalidation"]) if buy else _first(c > prev["invalidation"])
            tp1 = prev.get("tp1")
            i_tp = None if tp1 is None else (_first(h >= tp1) if buy else _first(lo <= tp1))
            if i_tp is not None and (i_inv is None or i_tp <= i_inv):
                return {"state": "TRADE_EXPIRED", "reason": f"TP1 {fmt(tp1)} was reached", "ts": int(b.t[m][i_tp])}
            if i_inv is not None:
                return {"state": "TRADE_INVALIDATED", "ts": int(b.t[m][i_inv]),
                        "reason": f"a {tf} candle closed {'below' if buy else 'above'} the invalidation level {fmt(prev['invalidation'])}"}
    if now_ts > int(prev.get("valid_until_ts") or 0):
        return {"state": "TRADE_EXPIRED", "reason": "the plan's lifetime elapsed", "ts": now_ts}
    return {"state": "TRADE_EXPIRED", "reason": "the setup no longer meets the entry rules", "ts": now_ts}


def apply_lifecycle(symbol: str, plans: list[dict], frames: dict[str, Frame], memory: dict, now_ts: int) -> None:
    for p in plans:
        key = (symbol, p["timeframe"])
        prev = memory.get(key)
        if p["state"] in ACTIONABLE and p.get("setup_key"):
            if prev is None or prev.get("setup_key") != p["setup_key"] or prev.get("closed"):
                memory[key] = {**{k: p.get(k) for k in KEEP}, "tp1": p["targets"][0]["price"] if p.get("targets") else None, "closed": None}
            continue
        if prev is None:
            continue
        if prev.get("closed") is None:
            prev["closed"] = what_happened(prev, frames.get(p["timeframe"]), p["timeframe"], now_ts)
        if now_ts > int(prev.get("valid_until_ts") or 0):
            memory.pop(key, None)  # the outcome is shown while the original plan would still have been valid
            continue
        ev = prev["closed"]
        p["previous"] = {"side": prev["side"], "entry": prev["entry"], "stop_loss": prev["stop_loss"], "signal_ts": prev["signal_ts"], **ev}
        if p["state"] == "NO_SETUP":
            p["state"], p["instruction"], p["decision"] = ev["state"], "NO TRADE", "NO TRADE"
            p["reasons_against"] = [f"Previous {prev['side']} plan: {ev['reason']}"] + list(p.get("reasons_against") or [])
