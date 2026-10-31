from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jsonutil import to_jsonable
from app.database.models import Instrument, Prediction
from app.market_data.bars import Bars
from app.market_data.ingestion.service import load_candles, resolve_mapping
from app.prediction.outcome import evaluate_outcome
from app.services.data_service import tf_step


def refresh_outcomes(session: Session, user_id: int | None = None, max_bars: int = 100) -> int:
    """Re-evaluates every open BUY/SELL prediction against candles that arrived after it was made."""
    q = select(Prediction).where(Prediction.outcome == "open")
    if user_id is not None:
        q = q.where(Prediction.user_id == user_id)
    updated = 0
    for pred in session.scalars(q):
        inst = session.get(Instrument, pred.instrument_id)
        try:
            _, prov, _ = resolve_mapping(session, inst.canonical_symbol, pred.provider_code)
        except Exception:
            continue
        candles = load_candles(session, inst.id, prov.id, pred.timeframe, start=pred.as_of_ts, complete_only=True)
        after = Bars.from_candles(candles, tf_step(pred.timeframe))
        if not pred.take_profit or pred.entry_low is None:
            continue
        res = evaluate_outcome(pred.decision, float(pred.entry_low), float(pred.entry_high), float(pred.stop_loss),
                               float(pred.take_profit[0]), after, max_bars)
        if res["outcome"] != pred.outcome:
            pred.outcome = res["outcome"]
            pred.outcome_meta = to_jsonable(res)
            if "ts" in res:
                pred.outcome_ts = datetime.fromtimestamp(res["ts"], tz=timezone.utc)
            updated += 1
    session.commit()
    return updated


__all__ = ["refresh_outcomes", "Decimal"]
