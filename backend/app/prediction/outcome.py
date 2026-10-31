"""Evaluates a prediction's trade plan against subsequent bars, independently of any backtest."""
from app.market_data.bars import Bars


def evaluate_outcome(decision: str, entry_low: float, entry_high: float, stop: float, target: float,
                     after: Bars, max_bars: int = 100) -> dict:
    """`after` = complete bars strictly after the prediction's as-of bar.
    Fill: first bar whose range touches the entry zone (filled at the open if the open is inside, else at the
    touched edge). Conservative: in the fill bar only the stop can trigger unless filled at the open;
    when stop and target are both in range the stop is assumed first."""
    if decision not in ("BUY", "SELL"):
        return {"outcome": "not_applicable"}
    long_ = decision == "BUY"
    filled, entry, fill_i = False, None, None
    for i in range(min(len(after), max_bars)):
        o, h, lo = after.o[i], after.h[i], after.l[i]
        if not filled:
            if lo <= entry_high and h >= entry_low:
                filled, fill_i = True, i
                inside = entry_low <= o <= entry_high
                entry = o if inside else (entry_high if long_ else entry_low)
                tp_ok = inside
            else:
                continue
        else:
            tp_ok = True
        sl_hit = (lo <= stop) if long_ else (h >= stop)
        tp_hit = tp_ok and ((h >= target) if long_ else (lo <= target))
        risk = abs(entry - stop)
        if sl_hit:
            return {"outcome": "sl_hit", "ts": int(after.t[i]), "entry_price": float(entry), "exit_price": float(stop),
                    "r_multiple": -1.0, "bars_to_fill": fill_i, "bars_in_trade": i - fill_i}
        if tp_hit:
            return {"outcome": "tp_hit", "ts": int(after.t[i]), "entry_price": float(entry), "exit_price": float(target),
                    "r_multiple": float(abs(target - entry) / risk) if risk else None, "bars_to_fill": fill_i,
                    "bars_in_trade": i - fill_i}
    if len(after) >= max_bars:
        if not filled:
            return {"outcome": "expired", "detail": "entry zone never reached"}
        last = after.c[max_bars - 1]
        risk = abs(entry - stop)
        return {"outcome": "expired", "entry_price": float(entry), "exit_price": float(last),
                "r_multiple": float((last - entry) * (1 if long_ else -1) / risk) if risk else None,
                "bars_to_fill": fill_i}
    return {"outcome": "open", "filled": filled}
