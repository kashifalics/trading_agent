from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.candlestick.patterns import PATTERN_DEFINITIONS
from app.core.exceptions import AppError
from app.core.jsonutil import to_jsonable
from app.database.session import get_session
from app.market_data.timeframes import TIMEFRAMES
from app.price_action.engine import analyze_price_action
from app.services.pattern_scan import resolve_source, scan_symbol, series
from app.services.pipeline import overlay_events, swing_points

router = APIRouter(prefix="/patterns", tags=["patterns"])

CONCEPT_DEFINITIONS = {
    "BOS": "Close beyond the last confirmed swing high/low in the direction of the prevailing trend.",
    "CHoCH": "Close beyond the last confirmed swing level AGAINST the prevailing trend.",
    "fvg": "Three-candle imbalance: low[i] > high[i-2] (bullish) or high[i] < low[i-2] (bearish), >= 0.1 ATR.",
    "order_block": "Last opposite candle before an impulse that breaks structure with >= 1.5 ATR displacement.",
    "breaker_block": "An order block that failed (closed through) and flips polarity.",
    "liquidity_sweep": "Wick beyond a resting swing level with a close back inside.",
    "equal_highs": "Two swing highs within 0.1 ATR; equal_lows mirrors.",
    "demand_zone": "1-3 bar base followed by a >=1.5 ATR impulse up; supply_zone mirrors.",
    "premium_discount": "Close position within the last confirmed swing range (equilibrium = 50%).",
}


@router.get("/definitions")
def definitions() -> dict:
    return {"candlestick": PATTERN_DEFINITIONS, "price_action": CONCEPT_DEFINITIONS,
            "note": "Detections are descriptive. They do not imply a profitable trade."}


@router.get("/scan")
def scan(symbol: str, provider: str | None = None, recent: int = Query(3, ge=1, le=20),
         session: Session = Depends(get_session)) -> dict:
    """Every timeframe with stored candles: structure, zone, and the patterns firing in the last `recent` bars, each with
    its measured out-of-sample track record (or an explicit 'no_study_data'). Database only, no provider calls."""
    return to_jsonable(scan_symbol(session, symbol, provider, recent))


@router.get("")
def patterns(symbol: str, timeframe: str, provider: str | None = None, lookback_bars: int = Query(600, ge=100, le=5000),
             session: Session = Depends(get_session)) -> dict:
    """Pattern/structure detections on stored complete candles (no network call)."""
    if timeframe not in TIMEFRAMES:
        raise AppError(f"Unsupported timeframe '{timeframe}'")
    inst, prov, pi = resolve_source(session, symbol, provider)
    bars, _derived = series(session, inst, prov, pi, timeframe, lookback_bars)
    if len(bars) < 30:
        return {"symbol": inst.canonical_symbol, "timeframe": timeframe, "provider": prov.code, "n_bars": len(bars),
                "events": [], "swings": [], "message": "Not enough stored candles; sync data first."}
    pa = analyze_price_action(bars)
    events = overlay_events(pa, len(bars), limit_bars=lookback_bars, cap=1000)
    counts: dict[str, int] = {}
    for e in events:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    return to_jsonable({"symbol": inst.canonical_symbol, "timeframe": timeframe, "provider": prov.code, "n_bars": len(bars),
                        "events": events, "swings": swing_points(pa, len(bars), bars, lookback_bars), "counts": counts,
                        "structure_trend": int(pa.trend[-1]), "atr": pa.atr[-1]})
