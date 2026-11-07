"""DB side of paper trading (docs/PAPER_TRADING.md): records every actionable signal the moment the backend sees it, simulates it on later
candles and keeps the paper account. Analysis only: nothing in this package can reach a broker or place a real order."""
import logging
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.core.jsonutil import to_jsonable
from app.database.models import Instrument, PaperAccount, PaperTrade
from app.database.session import session_scope
from app.paper.simulator import LIVE, SimTrade, advance, build_path
from app.signals import service as signals
from app.signals.config import CONFIG_VERSION
from app.signals.context import session_name

log = logging.getLogger(__name__)
_LOCK = threading.Lock()
WORKER: dict = {"enabled": False, "interval_s": 0, "running": False, "cycles": 0, "last_cycle_at": None, "last_duration_s": None,
                "last_results": None, "last_error": None}
SNAPSHOT_KEYS = ("timeframe", "group_label", "state", "instruction", "side", "score", "grade", "checks_met", "checks_total", "factors",
                 "setup_type", "entry_type", "entry", "entry_zone", "zone_kind", "stop_loss", "invalidation", "targets", "risk_reward",
                 "risk", "risk_atr", "atr", "cost_r", "spread", "reasons_for", "reasons_against", "conditions", "warnings", "summary",
                 "signal_time", "valid_until", "bias", "bias_tfs", "confirm_tf", "confirm_used", "track_record", "probability_note")


class Busy(AppError):
    status_code = 409
    code = "busy"


def _dt(ts: int | float) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


def _ts(dt: datetime | None) -> int | None:
    return None if dt is None else int(dt.timestamp())


def _f(x) -> float | None:
    return None if x is None else float(x)


# ---- account ---------------------------------------------------------------------------------------------------------------------------
def active_account(session: Session) -> PaperAccount:
    acc = session.scalar(select(PaperAccount).where(PaperAccount.is_active.is_(True)).order_by(PaperAccount.id.desc()).limit(1))
    if acc is None:
        s = get_settings()
        acc = PaperAccount(name="Paper account", start_balance=s.paper_start_balance, risk_pct=s.paper_risk_pct,
                           max_open_positions=s.paper_max_open_positions, max_daily_loss_pct=s.paper_max_daily_loss_pct, is_active=True)
        session.add(acc)
        session.flush()
    return acc


def realized_pnl(session: Session, account_id: int, before: datetime | None = None) -> float:
    q = select(func.coalesce(func.sum(PaperTrade.pnl), 0.0)).where(
        PaperTrade.account_id == account_id, PaperTrade.account_taken.is_(True), PaperTrade.status == "closed")
    if before is not None:
        q = q.where(PaperTrade.closed_at < before)
    return float(session.scalar(q) or 0.0)


def account_state(session: Session, acc: PaperAccount, now: datetime) -> dict:
    """Balance, today's realised P&L and whether the account may take a new trade now (and with how much risk)."""
    live = session.scalar(select(func.count(PaperTrade.id)).where(
        PaperTrade.account_id == acc.id, PaperTrade.account_taken.is_(True), PaperTrade.status.in_(LIVE))) or 0
    balance = acc.start_balance + realized_pnl(session, acc.id)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_day = acc.start_balance + realized_pnl(session, acc.id, before=day0)
    today = balance - start_of_day
    blocked = None
    if not acc.is_active:
        blocked = "account is closed"
    elif balance <= 0:
        blocked = "account balance exhausted"
    elif start_of_day > 0 and today <= -acc.max_daily_loss_pct / 100 * start_of_day:
        blocked = f"daily loss limit ({acc.max_daily_loss_pct:g}%) reached: no new trades until 00:00 UTC"
    elif live >= acc.max_open_positions:
        blocked = f"max open positions ({acc.max_open_positions}) reached"
    return {"balance": round(balance, 2), "start_of_day_balance": round(start_of_day, 2), "today_pnl": round(today, 2), "live_trades": live,
            "can_trade": blocked is None, "blocked_reason": blocked, "risk_per_trade": round(max(balance, 0) * acc.risk_pct / 100, 2)}


def account_out(session: Session, acc: PaperAccount, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    st = account_state(session, acc, now)
    open_taken = session.scalars(select(PaperTrade).where(PaperTrade.account_id == acc.id, PaperTrade.account_taken.is_(True),
                                                          PaperTrade.status == "open")).all()
    unrealized = sum((_unrealized_r(t) or 0.0) * (t.risk_amount or 0.0) for t in open_taken)
    open_risk = sum(t.risk_amount or 0.0 for t in open_taken)
    return {"id": acc.id, "name": acc.name, "start_balance": acc.start_balance, "risk_pct": acc.risk_pct,
            "max_open_positions": acc.max_open_positions, "max_daily_loss_pct": acc.max_daily_loss_pct, "is_active": acc.is_active,
            "created_at": acc.created_at, **st, "equity": round(st["balance"] + unrealized, 2), "unrealized_pnl": round(unrealized, 2),
            "open_risk": round(open_risk, 2), "return_pct": round((st["balance"] / acc.start_balance - 1) * 100, 2) if acc.start_balance else None}


def update_account(session: Session, changes: dict) -> dict:
    acc = active_account(session)
    for k in ("name", "risk_pct", "max_open_positions", "max_daily_loss_pct"):
        if changes.get(k) is not None:
            setattr(acc, k, changes[k])
    session.commit()
    return to_jsonable(account_out(session, acc))


def reset_account(session: Session, params: dict) -> dict:
    """Close the active account and open a new one. Recorded signals and their outcomes are kept (forward test continues)."""
    now = datetime.now(timezone.utc)
    old = active_account(session)
    s = get_settings()
    old.is_active, old.closed_at = False, now
    acc = PaperAccount(name=params.get("name") or "Paper account",
                       start_balance=params.get("start_balance") or s.paper_start_balance,
                       risk_pct=params.get("risk_pct") or old.risk_pct,
                       max_open_positions=params.get("max_open_positions") or old.max_open_positions,
                       max_daily_loss_pct=params.get("max_daily_loss_pct") or old.max_daily_loss_pct, is_active=True)
    session.add(acc)
    session.commit()
    return to_jsonable(account_out(session, acc, now))


# ---- signals -> orders -----------------------------------------------------------------------------------------------------------------
def order_kind(p: dict) -> str | None:
    """EXECUTE NOW -> market order, PLACE LIMIT ORDER -> limit order; anything else is not a signal."""
    if not p.get("setup_key") or not p.get("targets") or p.get("side") not in ("BUY", "SELL") or p.get("stop_loss") is None:
        return None
    if p.get("state") == "ENTRY_READY" and p.get("instruction") == "EXECUTE NOW":
        return "market"
    if p.get("instruction") == "PLACE LIMIT ORDER":
        return "limit"
    return None


def record_signals(session: Session, acc: PaperAccount, inst: Instrument, provider_id: int | None, analysis: dict,
                   now: datetime) -> list[PaperTrade]:
    """One paper trade per (instrument, timeframe, setup); none while that instrument x timeframe already has a pending/open trade."""
    new = []
    for p in analysis.get("plans") or []:
        kind = order_kind(p)
        if kind is None:
            continue
        tf = p["timeframe"]
        clash = session.scalar(select(PaperTrade.id).where(
            PaperTrade.instrument_id == inst.id, PaperTrade.timeframe == tf,
            (PaperTrade.setup_key == p["setup_key"][:200]) | PaperTrade.status.in_(LIVE)).limit(1))
        if clash is not None:
            continue
        st = account_state(session, acc, now)
        taken = st["can_trade"]
        tr = PaperTrade(
            account_id=acc.id, instrument_id=inst.id, provider_id=provider_id, symbol=inst.canonical_symbol, timeframe=tf,
            setup_key=p["setup_key"][:200], direction=p["side"], order_type=kind, status="pending", score=p.get("score"),
            grade=p.get("grade"), setup_type=p.get("setup_type"), entry_type=p.get("entry_type"), session=session_name(int(p["signal_ts"])),
            signal_ts=_dt(p["signal_ts"]), detected_at=now, valid_until=_dt(p["valid_until_ts"]), entry_price=float(p["entry"]),
            stop_loss=float(p["stop_loss"]), take_profit=float(p["targets"][0]["price"]), invalidation=_f(p.get("invalidation")),
            planned_rr=p.get("risk_reward"), spread=float(p.get("spread") or 0.0), cursor_at=now, account_taken=taken,
            account_note=None if taken else st["blocked_reason"], risk_amount=st["risk_per_trade"] if taken else None,
            plan=to_jsonable({k: p.get(k) for k in SNAPSHOT_KEYS}), config_version=analysis.get("config_version") or CONFIG_VERSION)
        session.add(tr)
        session.flush()
        new.append(tr)
    return new


# ---- simulation ------------------------------------------------------------------------------------------------------------------------
def to_sim(tr: PaperTrade) -> SimTrade:
    return SimTrade(d=1 if tr.direction == "BUY" else -1, order_type=tr.order_type, entry=float(tr.entry_price), sl=float(tr.stop_loss),
                    tp=float(tr.take_profit), inv=_f(tr.invalidation), spread=tr.spread or 0.0, detected_ts=_ts(tr.detected_at),
                    valid_until_ts=_ts(tr.valid_until), status=tr.status, cursor_ts=_ts(tr.cursor_at), fill_price=_f(tr.fill_price),
                    fill_ts=_ts(tr.filled_at), risk=tr.risk, mfe_r=tr.mfe_r, mae_r=tr.mae_r, last_price=tr.last_price,
                    last_ts=_ts(tr.last_price_at))


def _unrealized_r(tr: PaperTrade) -> float | None:
    if tr.status != "open" or tr.last_price is None or not tr.risk or tr.fill_price is None:
        return None
    d = 1 if tr.direction == "BUY" else -1
    return d * (tr.last_price - float(tr.fill_price)) / tr.risk - (tr.spread or 0.0) / tr.risk


def apply_sim(tr: PaperTrade, sim: SimTrade) -> None:
    tr.status, tr.exit_reason, tr.note = sim.status, sim.exit_reason, sim.note
    tr.fill_price, tr.filled_at = sim.fill_price, None if sim.fill_ts is None else _dt(sim.fill_ts)
    tr.risk, tr.r_gross, tr.r_net, tr.mfe_r, tr.mae_r = sim.risk, sim.r_gross, sim.r_net, sim.mfe_r, sim.mae_r
    tr.exit_price = sim.exit_price if sim.status == "closed" else None
    tr.cursor_at = _dt(sim.cursor_ts)
    tr.last_price, tr.last_price_at = sim.last_price, None if sim.last_ts is None else _dt(sim.last_ts)
    if sim.status not in LIVE:
        tr.closed_at = _dt(sim.exit_ts) if sim.exit_ts is not None else datetime.now(timezone.utc)
        tr.pnl = round(sim.r_net * tr.risk_amount, 2) if (sim.status == "closed" and tr.account_taken and tr.risk_amount) else (
            0.0 if tr.account_taken else None)


def step_trades(session: Session, inst: Instrument, frames: dict, now: datetime) -> list[PaperTrade]:
    """Advance every pending/open trade of an instrument through the complete candles stored since its cursor."""
    trades = session.scalars(select(PaperTrade).where(PaperTrade.instrument_id == inst.id, PaperTrade.status.in_(LIVE))
                             .order_by(PaperTrade.id)).all()
    if not trades:
        return []
    series = {tf: f.bars for tf, f in frames.items() if f is not None and f.bars is not None and len(f.bars)}
    changed = []
    for tr in trades:
        sim = to_sim(tr)
        before = sim.status
        b = series.get(tr.timeframe)
        closes = list(zip((b.t + b.step).tolist(), b.c.tolist())) if b is not None else []
        advance(sim, build_path(series, sim.cursor_ts), closes, now_ts=int(now.timestamp()))
        apply_sim(tr, sim)
        if sim.status != before:
            changed.append(tr)
    session.flush()
    return changed


# ---- cycle -----------------------------------------------------------------------------------------------------------------------------
def process_symbol(session: Session, symbol: str, now: datetime | None = None) -> dict:
    """Step existing trades through new candles, then record the signals the engine shows now (same output as the Signals page)."""
    now = now or datetime.now(timezone.utc)
    inst, prov, pi = signals.resolve(session, symbol)
    acc = active_account(session)
    analysis = signals.analyze(session, symbol, now)
    if analysis.get("status") != "ok":
        return {"symbol": inst.canonical_symbol, "status": analysis.get("status"), "reason": analysis.get("reason"), "new": [], "updated": []}
    frames = signals.load_frames(session, inst, prov, pi, now)
    changed = step_trades(session, inst, frames, now)
    new = record_signals(session, acc, inst, prov.id, analysis, now)
    session.commit()
    return {"symbol": inst.canonical_symbol, "status": "ok", "new": [{"id": t.id, "timeframe": t.timeframe, "side": t.direction,
                                                                     "order_type": t.order_type} for t in new],
            "updated": [{"id": t.id, "timeframe": t.timeframe, "status": t.status, "exit_reason": t.exit_reason} for t in changed]}


def run_cycle(sync: bool = True, symbols: list[str] | None = None, now: datetime | None = None) -> dict:
    """sync (keyless providers only) -> analyse -> simulate -> record, for every configured instrument. One cycle at a time."""
    if not _LOCK.acquire(blocking=False):
        raise Busy("a paper-trading cycle is already running")
    t0 = time.monotonic()
    WORKER["running"] = True
    results = []
    try:
        for sym in symbols or get_settings().signal_list:
            sync_note = None
            if sync:
                try:
                    with session_scope() as s:
                        res = signals.sync(s, sym)
                        sync_note = None if res.get("synced") else "; ".join(res.get("notes") or [])
                except Exception as exc:  # noqa: BLE001 - a provider failure must not stop the simulation on stored candles
                    log.warning("paper: sync %s failed: %s", sym, exc)
                    sync_note = f"sync failed: {exc.__class__.__name__}"
            try:
                with session_scope() as s:
                    out = process_symbol(s, sym, now)
            except Exception as exc:  # noqa: BLE001 - one instrument must not stop the others
                log.exception("paper: %s failed", sym)
                out = {"symbol": sym, "status": "failed", "reason": f"{exc.__class__.__name__}: {exc}"[:200], "new": [], "updated": []}
            if sync_note:
                out["sync_note"] = sync_note[:300]
            results.append(out)
    finally:
        WORKER.update(running=False, cycles=WORKER["cycles"] + 1, last_cycle_at=datetime.now(timezone.utc).isoformat(),
                      last_duration_s=round(time.monotonic() - t0, 2), last_results=results)
        _LOCK.release()
    return to_jsonable({"results": results, "duration_s": WORKER["last_duration_s"], "finished_at": WORKER["last_cycle_at"]})


# ---- read side -------------------------------------------------------------------------------------------------------------------------
def trade_out(tr: PaperTrade, detail: bool = False) -> dict:
    u = _unrealized_r(tr)
    out = {"id": tr.id, "account_id": tr.account_id, "symbol": tr.symbol, "timeframe": tr.timeframe, "direction": tr.direction,
           "order_type": tr.order_type, "status": tr.status, "exit_reason": tr.exit_reason, "note": tr.note, "score": tr.score,
           "grade": tr.grade, "setup_type": tr.setup_type, "entry_type": tr.entry_type, "session": tr.session, "signal_time": tr.signal_ts,
           "detected_at": tr.detected_at, "valid_until": tr.valid_until, "entry_price": _f(tr.entry_price), "stop_loss": _f(tr.stop_loss),
           "take_profit": _f(tr.take_profit), "invalidation": _f(tr.invalidation), "planned_rr": tr.planned_rr,
           "fill_price": _f(tr.fill_price), "filled_at": tr.filled_at, "exit_price": _f(tr.exit_price), "closed_at": tr.closed_at,
           "risk": tr.risk, "spread": tr.spread, "spread_r": (tr.spread / tr.risk) if tr.risk else None, "r_gross": tr.r_gross,
           "r_net": tr.r_net, "mfe_r": tr.mfe_r, "mae_r": tr.mae_r, "last_price": tr.last_price, "last_price_at": tr.last_price_at,
           "unrealized_r": u, "account_taken": tr.account_taken, "account_note": tr.account_note, "risk_amount": tr.risk_amount,
           "pnl": tr.pnl, "unrealized_pnl": round(u * tr.risk_amount, 2) if (u is not None and tr.account_taken and tr.risk_amount) else None,
           "summary": (tr.plan or {}).get("summary"), "config_version": tr.config_version}
    if detail:
        out["plan"] = tr.plan
    return out


FILTERS = {"live": LIVE, "finished": ("closed", "cancelled", "missed", "expired", "skipped"),
           "unfilled": ("cancelled", "missed", "expired", "skipped")}


def list_trades(session: Session, status: str | None = None, symbol: str | None = None, timeframe: str | None = None,
                limit: int = 100, offset: int = 0) -> dict:
    q = select(PaperTrade)
    if status and status != "all":
        q = q.where(PaperTrade.status.in_(FILTERS.get(status, (status,))))
    if symbol:
        q = q.where(PaperTrade.symbol == symbol.upper())
    if timeframe:
        q = q.where(PaperTrade.timeframe == timeframe)
    total = session.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = session.scalars(q.order_by(PaperTrade.detected_at.desc(), PaperTrade.id.desc()).limit(limit).offset(offset)).all()
    return to_jsonable({"items": [trade_out(t) for t in rows], "total": total, "limit": limit, "offset": offset})


def get_trade(session: Session, trade_id: int) -> dict:
    tr = session.get(PaperTrade, trade_id)
    if tr is None:
        raise NotFoundError(f"Paper trade {trade_id} not found")
    return to_jsonable(trade_out(tr, detail=True))


def worker_status() -> dict:
    return to_jsonable(dict(WORKER))
