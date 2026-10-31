import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.backtesting.engine import BacktestConfig, run_backtest
from app.backtesting.strategies import STRATEGIES
from app.core.exceptions import AppError
from app.core.jsonutil import to_jsonable
from app.database.base import utcnow
from app.database.models import BacktestRun, BacktestTrade, Instrument
from app.market_data.ingestion.service import resolve_mapping
from app.services.analysis_service import _dec
from app.services.data_service import ensure_data, load_bars

log = logging.getLogger(__name__)


def create_backtest(session: Session, user_id: int, params: dict) -> BacktestRun:
    inst, prov, _ = resolve_mapping(session, params["symbol"], params.get("provider"))
    run = BacktestRun(user_id=user_id, instrument_id=inst.id, provider_id=prov.id, timeframe=params["timeframe"],
                      strategy=params["strategy"], status="queued", config=to_jsonable(params))
    session.add(run)
    session.commit()
    return run


def run_backtest_job(run_id: int) -> None:
    from app.database.session import session_scope

    with session_scope() as session:
        run = session.get(BacktestRun, run_id)
        if run is None:
            return
        run.status = "running"
        session.commit()
        try:
            execute_backtest(session, run)
            run.status = "completed"
        except AppError as exc:
            session.rollback()
            run = session.get(BacktestRun, run_id)
            run.status, run.error = "failed", exc.message
        except Exception as exc:  # pragma: no cover
            log.exception("backtest %s crashed", run_id)
            session.rollback()
            run = session.get(BacktestRun, run_id)
            run.status, run.error = "failed", f"internal error ({exc.__class__.__name__})"
        run.completed_at = utcnow()
        session.commit()


def execute_backtest(session: Session, run: BacktestRun) -> None:
    p = run.config or {}
    inst = session.get(Instrument, run.instrument_id)
    inst, prov, pi = resolve_mapping(session, inst.canonical_symbol, p.get("provider"))
    start = datetime.fromisoformat(p["start"]) if p.get("start") else None
    end = datetime.fromisoformat(p["end"]) if p.get("end") else None
    if p.get("auto_sync", True) and not start:
        ensure_data(session, inst, prov, pi, run.timeframe, int(p.get("bars", 3000)), True)
    bars = load_bars(session, inst, prov, run.timeframe, int(p.get("bars", 3000)), end=end, start=start)
    strat = STRATEGIES[run.strategy]()
    if len(bars) <= strat.warmup + 50:
        raise AppError(f"Only {len(bars)} complete bars available; need more than {strat.warmup + 50} to backtest.")
    cfg = BacktestConfig(
        initial_equity=p.get("initial_equity", 10_000), risk_pct=p.get("risk_pct", 1.0), spread=p.get("spread", 0.0),
        slippage=p.get("slippage", 0.0), commission_pct=p.get("commission_pct", 0.0),
        contract_size=float(inst.contract_size) if inst.contract_size else 1.0,
        max_bars_in_trade=p.get("max_bars_in_trade", 200), eval_every=p.get("eval_every", 2),
        allowed_hours_utc=p.get("allowed_hours_utc"))
    res = run_backtest(bars, strat, cfg)
    step = max(1, len(res.equity_curve) // 1000)
    run.metrics = to_jsonable({**res.metrics, "skipped_signals": res.skipped_signals, "bars": res.meta["bars"],
                               "caveats": ["same-bar SL/TP resolved as SL", "entry at next bar open",
                                           "no holidays/maintenance breaks modelled", "past performance is not predictive"]})
    run.equity_curve = to_jsonable(res.equity_curve[::step])
    run.start_ts = datetime.fromisoformat(res.meta["start"]) if res.meta["start"] else None
    run.end_ts = datetime.fromisoformat(res.meta["end"]) if res.meta["end"] else None
    places = inst.price_precision
    for t in res.trades:
        session.add(BacktestTrade(
            run_id=run.id, direction=t["direction"], signal_ts=datetime.fromisoformat(t["signal_ts"]),
            entry_ts=datetime.fromisoformat(t["entry_ts"]), entry_price=_dec(t["entry_price"], places),
            exit_ts=datetime.fromisoformat(t["exit_ts"]), exit_price=_dec(t["exit_price"], places),
            exit_reason=t["exit_reason"], stop_loss=_dec(t["stop_loss"], places),
            take_profit=_dec(t["take_profit"], places) if t["take_profit"] is not None else None,
            units=t["units"], pnl=t["pnl"], r_multiple=t["r_multiple"], costs=t["costs"]))
    session.commit()


__all__ = ["create_backtest", "run_backtest_job", "execute_backtest", "Decimal", "timezone"]
