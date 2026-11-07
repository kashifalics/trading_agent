"""Order-execution rules shared by the historical replay and live paper trading (docs/PAPER_TRADING.md).

Pure functions on one candle at a time, so the backtest and the forward test cannot drift apart:
  * a resting limit order is MISSED when TP1 trades before the entry is touched, otherwise FILLED when the entry is touched;
  * an open position exits at its stop or TP1; a candle that touches both is a LOSS (the order of prices inside a candle is unknown);
  * on the candle that fills a limit order only the stop counts (the fill may have come after the candle's high/low);
  * a market order is only valid while the fill price is still between the stop and TP1.
With `gap_fills` (live paper trading) the candle's OPEN is honoured: a candle that opens beyond the stop exits at that open (a stop order
cannot fill at a price that never traded), one that opens beyond TP1 exits at that open. The historical replay keeps the simpler
exit-at-the-level rule its published numbers were produced with.
"""


def limit_touch(d: int, entry: float, tp: float, high: float, low: float) -> str | None:
    """'missed' (TP1 traded, entry never touched), 'filled' (entry touched) or None, for a limit order on one candle."""
    if (d == 1 and high >= tp and low > entry) or (d == -1 and low <= tp and high < entry):
        return "missed"
    if (d == 1 and low <= entry) or (d == -1 and high >= entry):
        return "filled"
    return None


def exit_on_candle(d: int, sl: float, tp: float, o: float, h: float, lo: float, *, tp_allowed: bool = True,
                   gap_fills: bool = False) -> tuple[float, str] | None:
    """(exit price, 'stop' | 'target') if the position closes on this candle, else None. Both levels touched = stop."""
    if gap_fills:
        if (o <= sl) if d == 1 else (o >= sl):
            return o, "stop"
        if tp_allowed and ((o >= tp) if d == 1 else (o <= tp)):
            return o, "target"
    hit_sl = lo <= sl if d == 1 else h >= sl
    if hit_sl:
        return sl, "stop"
    if tp_allowed and (h >= tp if d == 1 else lo <= tp):
        return tp, "target"
    return None


def market_entry_ok(d: int, price: float, sl: float, tp: float) -> bool:
    """A market fill is only a trade while the price is still between the stop and the target."""
    return d * (price - sl) > 0 and d * (tp - price) > 0


def r_multiple(d: int, entry: float, exit_px: float, risk: float) -> float:
    return d * (exit_px - entry) / risk
