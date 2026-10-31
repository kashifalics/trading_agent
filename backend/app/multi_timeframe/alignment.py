"""Multi-timeframe views and alignment (user-configured roles, no hard-coded strategy)."""
from dataclasses import asdict, dataclass

from app.market_data.bars import Bars
from app.price_action.engine import PriceActionResult, analyze_price_action

ROLE_WEIGHTS = {"higher": 0.5, "intermediate": 0.3, "entry": 0.2}


def htf_as_of(htf: Bars, t_epoch: int) -> Bars:
    """Higher-timeframe bars that were COMPLETE at time t (open + step <= t). Prevents unfinished
    higher-timeframe candles from leaking into analysis of an earlier moment."""
    n = int(((htf.t + htf.step) <= t_epoch).sum())
    return htf.upto(n)


@dataclass
class TFView:
    timeframe: str
    role: str
    direction: int  # +1 bullish structure, -1 bearish, 0 undetermined
    trend: int
    bias: int
    zone: str | None  # premium | discount | equilibrium
    last_break: str | None
    n_bars: int
    last_bar_ts: int | None
    note: str

    def to_dict(self) -> dict:
        return asdict(self)


def build_view(b: Bars, timeframe: str, role: str, pa: PriceActionResult | None = None) -> tuple[TFView, PriceActionResult]:
    pa = pa or analyze_price_action(b)
    if len(b) == 0:
        return TFView(timeframe, role, 0, 0, 0, None, None, 0, None, "no data"), pa
    trend = int(pa.trend[-1])
    direction = trend or pa.bias
    lb = pa.breaks[-1] if pa.breaks else None
    pdz = pa.premium_discount.status if pa.premium_discount else None
    note = f"{'bullish' if direction > 0 else 'bearish' if direction < 0 else 'undetermined'} structure"
    if lb:
        note += f"; last {lb.kind} {lb.direction}"
    return TFView(timeframe, role, direction, trend, pa.bias, pdz, f"{lb.kind}:{lb.direction}" if lb else None,
                  len(b), int(b.t[-1]), note), pa


def alignment(views: list[TFView]) -> dict:
    """Weighted directional agreement in [-1, 1]. Conflict if higher and entry views disagree."""
    use = [v for v in views if v.n_bars > 0]
    if not use:
        return {"score": 0.0, "aligned": False, "conflict": False, "direction": 0, "views": [], "available": False}
    tw = sum(ROLE_WEIGHTS.get(v.role, 0.2) for v in use)
    score = sum(ROLE_WEIGHTS.get(v.role, 0.2) * v.direction for v in use) / tw
    dirs = {v.direction for v in use if v.direction != 0}
    higher = next((v for v in use if v.role == "higher"), None)
    entry = next((v for v in use if v.role == "entry"), None)
    conflict = bool(higher and entry and higher.direction and entry.direction and higher.direction != entry.direction)
    return {
        "score": float(score), "aligned": len(dirs) == 1 and len(use) > 1 and all(v.direction for v in use),
        "conflict": conflict, "direction": (1 if score > 0 else -1 if score < 0 else 0), "available": True,
        "views": [v.to_dict() for v in use],
    }
