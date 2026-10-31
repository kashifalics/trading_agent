"""Fill logic shared by the backtester. All prices are MID prices; spread is applied as +/- half spread.

Conservative assumptions (documented in docs/BACKTESTING_METHODOLOGY.md):
  * entry at the NEXT bar's open after the signal (never the signal bar's close);
  * if a bar's range contains both stop and target, the STOP is assumed to be hit first;
  * a bar that opens beyond the stop fills the stop at the open (gap risk), a favourable gap fills the target at the target price;
  * stops pay slippage; targets (limit orders) do not.
"""
from dataclasses import dataclass


@dataclass
class Position:
    direction: int  # +1 long, -1 short
    entry_idx: int
    signal_idx: int
    entry_price: float  # includes half spread + slippage
    stop: float
    target: float | None
    units: float
    entry_costs: float


def check_exit(pos: Position, o: float, h: float, l: float, half_spread: float,  # noqa: E741
               slippage: float) -> tuple[str, float] | None:
    """Returns (reason, exit_price) if the position exits during a bar with mid OHLC (o,h,l)."""
    if pos.direction == 1:  # long exits at bid = mid - half
        sl_hit = l <= pos.stop + half_spread
        tp_hit = pos.target is not None and h >= pos.target + half_spread
        if sl_hit:  # includes ambiguous bars
            fill = min(pos.stop, o - half_spread) if o - half_spread < pos.stop else pos.stop
            return "stop", fill - slippage
        if tp_hit:
            return "target", pos.target  # type: ignore[return-value]
    else:  # short exits at ask = mid + half
        sl_hit = h >= pos.stop - half_spread
        tp_hit = pos.target is not None and l <= pos.target - half_spread
        if sl_hit:
            fill = max(pos.stop, o + half_spread) if o + half_spread > pos.stop else pos.stop
            return "stop", fill + slippage
        if tp_hit:
            return "target", pos.target  # type: ignore[return-value]
    return None
