"""Signal lifecycle (DESIGN section 9): every qualified v2 plan is stored once and stepped through later 1-minute candles.

Before entry: a close beyond the invalidation -> INVALIDATED; past the expiry -> EXPIRED; TP1 trading before the entry -> ENTRY
MISSED; touching the entry -> ENTRY TRIGGERED, then ACTIVE. After entry the stop is checked before the targets inside a candle
(conservative); TP1, TP2 and TP3 are recorded in order; TP3 or the stop closes the record. The stop is never moved. These are
hypothetical signals, not paper trades."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import SignalRecord
from app.market_data.bars import Bars
from app.strategy_engine.config import ENGINE_VERSION

OPEN = ("WAITING FOR ENTRY", "ENTRY READY", "ACTIVE", "TP1 HIT", "TP2 HIT")
CLOSED = ("TP3 HIT", "STOP LOSS HIT", "INVALIDATED", "EXPIRED", "ENTRY MISSED")


def _dt(iso_or_ts) -> datetime | None:
    if iso_or_ts is None:
        return None
    if isinstance(iso_or_ts, datetime):
        return iso_or_ts
    if isinstance(iso_or_ts, (int, float)):
        return datetime.fromtimestamp(int(iso_or_ts), tz=timezone.utc)
    return datetime.fromisoformat(str(iso_or_ts))


def _event(rec: SignalRecord, status: str, at: datetime, price: float | None, note: str = "") -> None:
    rec.history = [*(rec.history or []), {"status": status, "at": at.isoformat(), "price": price, "note": note}]
    rec.status = status


def setup_key(symbol: str, tf: str, strategy: str, direction: str, signal_time: str) -> str:
    return f"{symbol}|{tf}|{strategy}|{direction}|{signal_time}"[:160]


def record(session: Session, analysis: dict, instrument_id: int, provider_id: int | None, now: datetime | None = None) -> list[SignalRecord]:
    """Store each timeframe's qualified plan once (same setup on the next refresh = the same record)."""
    now = now or datetime.now(timezone.utc)
    out = []
    for r in analysis.get("timeframes", []):
        p = r.get("plan")
        if r.get("action") == "NO TRADE" or not p or p.get("entry_status") not in ("READY", "WAITING FOR ENTRY"):
            continue
        key = setup_key(analysis["symbol"], r["timeframe"], r["strategy"], r["direction"], p["signal_time"])
        if session.scalar(select(SignalRecord.id).where(SignalRecord.setup_key == key)) is not None:
            continue
        tg = p["targets"]
        rec = SignalRecord(setup_key=key, instrument_id=instrument_id, provider_id=provider_id, symbol=analysis["symbol"], timeframe=r["timeframe"],
                           strategy=r["strategy"], direction=r["direction"], regime=r["regime"]["label"], entry_mode=p["entry_mode"],
                           entry=p["entry"], stop_loss=p["stop_loss"], tp1=tg[0]["price"], tp2=tg[1]["price"] if len(tg) > 1 else None,
                           tp3=tg[2]["price"] if len(tg) > 2 else None, invalidation=p["invalidation"], risk=p["risk"], status="DETECTED",
                           research_status=r.get("research_status") or "INSUFFICIENT EVIDENCE", signal_time=_dt(p["signal_time"]),
                           detected_at=now, expires_at=_dt(p.get("expires_at")), cursor_at=now, last_price=p.get("price_now"),
                           best_target=0, history=[], plan={**p, "strategy_name": r.get("strategy_name"), "why": r.get("why")},
                           engine_version=ENGINE_VERSION)
        _event(rec, "DETECTED", now, p.get("price_now"), r.get("headline", ""))
        if p["entry_status"] == "READY" and p["entry_mode"] == "market":
            _event(rec, "ENTRY READY", now, p.get("price_now"))
            _event(rec, "ENTRY TRIGGERED", now, p["entry"], "market entry at the signal close")
            _event(rec, "ACTIVE", now, p["entry"])
            rec.triggered_at = now
        else:
            _event(rec, "WAITING FOR ENTRY", now, p.get("price_now"), p.get("trigger", ""))
        session.add(rec)
        out.append(rec)
    session.flush()
    return out


def step(rec: SignalRecord, m1: Bars) -> None:
    """Advance one record through 1-minute candles that closed after its cursor (in time order)."""
    d = 1 if rec.direction == "BUY" else -1
    cur = int(rec.cursor_at.timestamp()) if rec.cursor_at else 0
    tps = [x for x in (rec.tp1, rec.tp2, rec.tp3) if x is not None]
    for k in range(len(m1)):
        t_close = int(m1.t[k]) + int(m1.step)
        if t_close <= cur or rec.status in CLOSED:
            continue
        at = datetime.fromtimestamp(t_close, tz=timezone.utc)
        o, h, lo, c = float(m1.o[k]), float(m1.h[k]), float(m1.l[k]), float(m1.c[k])
        rec.last_price, rec.cursor_at = c, at
        if rec.status in ("WAITING FOR ENTRY", "ENTRY READY"):
            if rec.expires_at is not None and at > rec.expires_at:
                _event(rec, "EXPIRED", at, c, "the entry window passed")
                rec.closed_at = at
                continue
            if rec.entry_mode == "limit":  # a BUY limit sits below price: touched when the low reaches it
                touched = (lo <= rec.entry) if d > 0 else (h >= rec.entry)
            elif rec.entry_mode == "stop":  # a BUY stop sits above price: touched when the high reaches it
                touched = (h >= rec.entry) if d > 0 else (lo <= rec.entry)
            else:
                touched = True
            tp1_first = ((h >= rec.tp1) if d > 0 else (lo <= rec.tp1)) and not touched
            if (c - rec.invalidation) * d < 0 and not touched:
                _event(rec, "INVALIDATED", at, c, "a close beyond the invalidation before the entry")
                rec.closed_at = at
                continue
            if tp1_first:
                _event(rec, "ENTRY MISSED", at, c, "TP1 traded before the entry price")
                rec.closed_at = at
                continue
            if not touched:
                continue
            # a stop entry fills at the worse of its price and the candle's open (a gap through it)
            fill = (max(rec.entry, o) if d > 0 else min(rec.entry, o)) if rec.entry_mode == "stop" else rec.entry
            _event(rec, "ENTRY TRIGGERED", at, fill)
            _event(rec, "ACTIVE", at, fill)
            rec.triggered_at = at
        # active: the stop first (conservative), then the targets in order
        if (lo <= rec.stop_loss) if d > 0 else (h >= rec.stop_loss):
            _event(rec, "STOP LOSS HIT", at, rec.stop_loss, f"after TP{rec.best_target}" if rec.best_target else "")
            rec.closed_at = at
            continue
        for n, tp in enumerate(tps, 1):
            if n > rec.best_target and ((h >= tp) if d > 0 else (lo <= tp)):
                rec.best_target = n
                _event(rec, f"TP{n} HIT", at, tp)
        if rec.best_target == len(tps) and tps:
            rec.status = "TP3 HIT" if len(tps) == 3 else f"TP{len(tps)} HIT"
            rec.closed_at = at


def step_symbol(session: Session, symbol: str, m1: Bars | None) -> int:
    if m1 is None or not len(m1):
        return 0
    recs = session.scalars(select(SignalRecord).where(SignalRecord.symbol == symbol, SignalRecord.status.in_(OPEN))).all()
    for rec in recs:
        step(rec, m1)
    session.flush()
    return len(recs)


def record_out(rec: SignalRecord) -> dict:
    return {"id": rec.id, "symbol": rec.symbol, "timeframe": rec.timeframe, "strategy": rec.strategy, "strategy_name": (rec.plan or {}).get("strategy_name"),
            "direction": rec.direction, "regime": rec.regime, "entry_mode": rec.entry_mode, "entry": rec.entry, "stop_loss": rec.stop_loss,
            "tp1": rec.tp1, "tp2": rec.tp2, "tp3": rec.tp3, "invalidation": rec.invalidation, "risk": rec.risk, "status": rec.status,
            "research_status": rec.research_status, "signal_time": rec.signal_time, "detected_at": rec.detected_at, "expires_at": rec.expires_at,
            "triggered_at": rec.triggered_at, "closed_at": rec.closed_at, "last_price": rec.last_price, "best_target": rec.best_target,
            "history": rec.history or [], "engine_version": rec.engine_version, "hypothetical": True}
