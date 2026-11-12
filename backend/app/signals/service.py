"""DB-facing side of the signal engine (docs/SIGNAL_ENGINE.md).

One provider per instrument (never mixed), complete candles per timeframe, the live quote (spread check), market hours, a content-signature
cache (price action is computed once per set of candles) and the in-memory plan lifecycle. Provider quotas are only spent by `sync`.
"""
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError, UnsupportedError
from app.core.jsonutil import to_jsonable
from app.database.models import Candle as CandleRow
from app.database.models import (
    DataCoverage,
    DataProvider,
    Instrument,
    ProviderInstrument,
)
from app.market_data.bars import Bars
from app.market_data.calendars import get_calendar
from app.market_data.coverage.gaps import staleness
from app.market_data.ingestion.service import (
    anchor_for,
    ingest_candles,
    resolve_mapping,
)
from app.market_data.registry import get_provider
from app.market_data.timeframes import bucket_end, get_timeframe
from app.opportunities.analysis import prepare_tf, provider_configured
from app.signals import classify, track_record
from app.signals.config import (
    CONFIG_VERSION,
    PARAMS,
    SIGNAL_TFS,
    provider_override,
    spread_for,
)
from app.signals.engine import DISCLAIMER, Frame, evaluate_instrument
from app.signals.lifecycle import apply_lifecycle

log = logging.getLogger(__name__)
_FRAMES: dict[tuple, Frame] = {}
_MEMORY: dict = {}
_QUOTES: dict[str, tuple[float, dict | None]] = {}
MAX_FRAMES = 400
# The summary reuses each instrument's latest analysis for this long. The paper-trading cycle re-analyses every instrument every minute
# and stores the result here (so does every Signals request), so the summary normally answers at once instead of analysing all of them.
SUMMARY_TTL_S = 90
_ITEMS: dict[tuple[str, bool], tuple[float, dict]] = {}
REFRESH_TFS = ("1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "1D", "1W", "1M")
NOT_SERVED = {"biquote": {"1M"}}  # BiQuote has no monthly series (docs/BIQUOTE_PROVIDER_EVALUATION.md)
PUBLISH_GRACE_S = 90  # providers publish a closed candle within a minute or two: one more try after that
RETRY_MISSING_S = 1800
DEEPEN_SHORT_S = 6 * 3600


def resolve(session: Session, symbol: str) -> tuple[Instrument, DataProvider, ProviderInstrument]:
    code = provider_override(symbol)
    if code:
        try:
            return resolve_mapping(session, symbol, code)
        except (NotFoundError, UnsupportedError):
            pass
    return resolve_mapping(session, symbol)


def _has_candles(session: Session, inst: Instrument, prov: DataProvider) -> bool:
    return session.scalar(select(CandleRow.id).where(CandleRow.instrument_id == inst.id, CandleRow.provider_id == prov.id).limit(1)) is not None


def _sig(b: Bars) -> str:
    raw = f"{len(b)}|{int(b.t[0])}|{int(b.t[-1])}|{b.o[-1]:.10g}|{b.h[-1]:.10g}|{b.l[-1]:.10g}|{b.c[-1]:.10g}|{b.c[0]:.10g}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def load_frames(session: Session, inst: Instrument, prov: DataProvider, pi: ProviderInstrument, now: datetime) -> dict[str, Frame]:
    frames: dict[str, Frame] = {}
    for tf in SIGNAL_TFS:
        t = prepare_tf(session, inst, prov, pi, tf, now, lookback=PARAMS["lookback_bars"])
        if t.bars is None or not len(t.bars):
            frames[tf] = Frame(tf, None, t.status, t.reason or t.error)
            continue
        key = (CONFIG_VERSION, inst.id, prov.id, tf, t.derived_from, _sig(t.bars))
        f = _FRAMES.get(key)
        if f is None:
            f = Frame(tf, t.bars, t.status, t.reason, t.stale_bars, t.derived_from, t.quality)
            _FRAMES[key] = f
            while len(_FRAMES) > MAX_FRAMES:
                _FRAMES.pop(next(iter(_FRAMES)))
        else:  # time-dependent facts change even when the candles do not
            f.status, f.reason, f.stale_bars, f.quality = t.status, t.reason, t.stale_bars, t.quality
        frames[tf] = f
    return frames


def _quote(prov: DataProvider, pi: ProviderInstrument) -> dict | None:
    k = f"{prov.code}:{pi.provider_symbol}"
    hit = _QUOTES.get(k)
    if hit and time.monotonic() - hit[0] < 10:
        return hit[1]
    try:
        q = get_provider(prov.code).get_latest_quote(pi.provider_symbol)
        bid = None if q.bid is None else float(q.bid)
        ask = None if q.ask is None else float(q.ask)
        res = {"price": float(q.price), "bid": bid, "ask": ask, "spread": (ask - bid) if bid is not None and ask is not None else None,
               "time": q.ts.isoformat(), "delayed": bool(q.is_delayed), "provider": prov.code}
    except Exception as exc:  # noqa: BLE001 - a quote is optional context, never a reason to fail the analysis
        log.info("quote unavailable for %s: %s", k, exc)
        res = None
    _QUOTES[k] = (time.monotonic(), res)
    return res


def unavailable_call(symbol: str, reason: str) -> dict:
    from app.decision.core import DecisionInput, decide
    return decide(DecisionInput(symbol=symbol, timeframe=None, data_status="unavailable", data_detail=reason))


def _unavailable(base: dict, reason: str) -> dict:
    return {**base, "status": "unavailable", "reason": reason, "plans": [], "timeframes": [], "best": None, "active": [], "watchlist": [],
            "overall": None, "counts": None, "report": None, "disclaimer": DISCLAIMER, "call": unavailable_call(base["symbol"], reason)}


def analyze(session: Session, symbol: str, now: datetime | None = None, experimental: bool = False) -> dict:
    now = now or datetime.now(timezone.utc)
    inst, prov, pi = resolve(session, symbol)
    sym = inst.canonical_symbol
    base = {"symbol": sym, "name": inst.name, "provider": prov.code, "provider_symbol": pi.provider_symbol, "provider_status": pi.status,
            "price_precision": inst.price_precision, "generated_at": now.isoformat(), "config_version": CONFIG_VERSION}
    if not _has_candles(session, inst, prov):
        configured, why = provider_configured(prov.code)
        return to_jsonable(_unavailable(base, why or "no stored candles yet."))
    frames = load_frames(session, inst, prov, pi, now)
    quote = _quote(prov, pi)
    open_now = get_calendar(inst.calendar).is_open(now)
    live = {"market_open": open_now, "quote": quote,
            "live_spread": quote["spread"] if quote and not quote["delayed"] and quote.get("spread") is not None else None}
    res = evaluate_instrument(sym, frames, live=live)
    apply_lifecycle(sym, res["plans"], frames, _MEMORY, int(now.timestamp()))
    for p in res["plans"]:
        tr = track_record.lookup(sym, p["timeframe"], p.get("score"))
        p["track_record"] = tr
        p["validation"] = track_record.validation_of(tr)
        if tr.get("win_probability") is not None:
            p["win_probability"] = tr["win_probability"]
            p["probability_note"] = f"Historical win rate {tr['win_probability']:.0%}: {tr['win_probability_basis']}"
    attach_validation(sym, res)
    last_close = next((r["last_close"] for r in res["timeframes"] if r.get("last_close") is not None), None)
    ref_price = (quote or {}).get("price") or last_close
    attach_calls(session, sym, res, quote, experimental)
    out = {**base, "status": "ok", "market_open": open_now, "calendar": inst.calendar, "quote": quote,
           "spread_model": spread_for(sym, ref_price) if ref_price else None, **res}
    return to_jsonable(classify.enrich(sym, out))


def open_trades(session: Session, symbol: str) -> dict[str, dict]:
    """Tracked paper trades (open or pending) by timeframe: the only trades EXIT / HOLD may refer to."""
    from app.database.models import PaperTrade
    from app.paper.service import trade_out
    rows = session.scalars(select(PaperTrade).where(PaperTrade.symbol == symbol, PaperTrade.status.in_(("open", "pending")))
                           .order_by(PaperTrade.id)).all()
    return {t.timeframe: trade_out(t) for t in rows}


def attach_calls(session: Session, sym: str, res: dict, quote: dict | None, experimental: bool) -> None:
    """The customer call (ENTER / HOLD / WAIT / EXIT / NO TRADE) for every timeframe and for the instrument, from app.decision."""
    from app.decision.adapters import signal_call
    from app.decision.core import rank
    closes = {r["timeframe"]: r.get("last_close") for r in res.get("timeframes", [])}
    live = quote is not None and not quote.get("delayed") and quote.get("price") is not None
    trades = open_trades(session, sym)
    for p in res["plans"]:
        tf = p["timeframe"]
        px, src = (quote["price"], "live quote") if live else (closes.get(tf), f"last {tf} close")
        tr = trades.get(tf)
        if tr is not None:
            tr = {**tr, "last_close": closes.get(tf)}
        p["call"] = signal_call(p, sym, price_now=px, price_source=src if px is not None else None, open_trade=tr, experimental=experimental)
    best = rank([p["call"] for p in res["plans"]])
    res["call"] = best
    res["experimental"] = experimental


def attach_validation(sym: str, res: dict) -> dict:
    """The best plan and the written report state the validation status explicitly ("Not validated" unless validated)."""
    best = res.get("best")
    if best is None:
        return res
    if "validation" not in best:
        best["validation"] = track_record.validation_of(track_record.lookup(sym, best["timeframe"], best.get("score")))
    rep = res.get("report")
    if rep is not None:
        rep["validation"] = best["validation"]
        line = f"Validation: {best['validation']['note']}"
        rep["text"] = f"{rep['text']}\n{line}" if rep.get("text") else line
    return res


def _compact_plan(p: dict | None) -> dict | None:
    if not p:
        return None
    keys = ("timeframe", "state", "instruction", "decision", "direction", "score", "grade", "setup_type", "entry_type", "entry", "stop_loss",
            "risk_reward", "summary", "signal_time", "valid_until", "probability_note", "win_probability")
    out = {k: p.get(k) for k in keys}
    out["call"] = compact_call(p.get("call"))
    out["validation_status"] = (p.get("validation") or {}).get("status", "not_validated")
    out["tp1"] = p["targets"][0]["price"] if p.get("targets") else None
    return out


def compact_call(c: dict | None) -> dict | None:
    if not c:
        return None
    return {k: c.get(k) for k in ("decision", "label", "headline", "timeframe", "direction", "setup", "next_condition", "wait_kind",
                                  "validation", "data_quality", "levels", "hypothetical", "experimental", "trade")}


def summary_item(r: dict) -> dict:
    """One instrument's row of the summary, from its full analysis. `as_of` is when that analysis ran."""
    if r["status"] != "ok":
        return ({k: r.get(k) for k in ("symbol", "name", "status", "reason", "provider", "price_precision")}
                | {"call": compact_call(r.get("call")), "as_of": r.get("generated_at")})
    return ({k: r.get(k) for k in ("symbol", "name", "status", "provider", "price_precision", "market_open", "quote", "overall", "counts",
                                   "session")}
            | {"best": _compact_plan(r.get("best")), "call": compact_call(r.get("call")),
               "active": [_compact_plan(p) for p in r.get("plans") or [] if p["timeframe"] in (r.get("active") or [])],
               # timeframes where the paper-trading test holds a trade or a pending order (shown with their levels and open R)
               "trades": [_compact_plan(p) for p in r.get("plans") or [] if (p.get("call") or {}).get("trade")],
               "last_candle": max((t.get("close_time") or "" for t in r.get("timeframes") or []), default=None) or None,
               "as_of": r.get("generated_at")})


def remember(r: dict, experimental: bool = False) -> None:
    """Keep an instrument's latest analysis for the summary (from the paper cycle, a Signals request or a sync)."""
    if r.get("status") == "ok" and r.get("symbol"):
        _ITEMS[(r["symbol"], experimental)] = (time.monotonic(), summary_item(r))


def summary(session: Session, experimental: bool = False) -> dict:
    items = []
    for sym in get_settings().signal_list:
        hit = _ITEMS.get((sym, experimental))
        if hit is not None and time.monotonic() - hit[0] < SUMMARY_TTL_S:
            items.append(hit[1])
            continue
        try:
            r = analyze(session, sym, experimental=experimental)
        except AppError as exc:
            items.append({"symbol": sym, "status": "unavailable", "reason": exc.message, "call": compact_call(unavailable_call(sym, exc.message))})
            continue
        except Exception as exc:  # noqa: BLE001 - one instrument must not break the page
            log.exception("signals summary: %s failed", sym)
            items.append({"symbol": sym, "status": "failed", "reason": f"{exc.__class__.__name__}: {exc}"[:200],
                          "call": compact_call(unavailable_call(sym, "the analysis failed"))})
            continue
        remember(r, experimental)
        items.append(summary_item(r))
    return to_jsonable({"items": items, "generated_at": datetime.now(timezone.utc).isoformat(), "config_version": CONFIG_VERSION,
                        "refresh_s": SUMMARY_TTL_S, "disclaimer": DISCLAIMER})


def latest_expected_close(last_ts: datetime, tf: str, now: datetime, calendar: str, anchor) -> datetime | None:
    """Close time of the most recent candle after `last_ts` that should be complete by `now` (same walk as `staleness`)."""
    tfo, cal = get_timeframe(tf), get_calendar(calendar)
    cur, latest, n = bucket_end(last_ts, tfo, anchor), None, 0
    while bucket_end(cur, tfo, anchor) <= now and n < 100_000:
        if cal.is_open(cur):
            latest = bucket_end(cur, tfo, anchor)
        cur, n = bucket_end(cur, tfo, anchor), n + 1
    return latest


def is_due(cov: DataCoverage | None, tf: str, now: datetime, inst: Instrument) -> bool:
    """Fetch a timeframe only when a candle closed since the last attempt. A candle the provider still lacks after its close (thin feeds
    around a market close, provider gaps) is retried every RETRY_MISSING_S instead of every cycle; a series shorter than the engine needs
    is topped up every DEEPEN_SHORT_S (most providers simply have no more history)."""
    if cov is None or cov.last_ts is None:
        return True
    since = (now - cov.last_sync_at).total_seconds() if cov.last_sync_at else None
    stale = staleness(cov.last_ts, tf, now, inst.calendar, anchor_for(inst))
    if not stale or stale < 1:
        return cov.candle_count < PARAMS["min_setup_bars"] and (since is None or since >= DEEPEN_SHORT_S)
    latest = latest_expected_close(cov.last_ts, tf, now, inst.calendar, anchor_for(inst))
    if latest is None or cov.last_sync_at is None or cov.last_sync_at < latest + timedelta(seconds=PUBLISH_GRACE_S):
        return True
    return since >= RETRY_MISSING_S


def sync(session: Session, symbol: str, now: datetime | None = None) -> dict:
    """Fetch new complete candles for every timeframe that is due (see `is_due`)."""
    now = now or datetime.now(timezone.utc)
    inst, prov, pi = resolve(session, symbol)
    configured, why = provider_configured(prov.code)
    if not configured:
        return {"synced": False, "provider": prov.code, "notes": [why]}
    if prov.code not in get_settings().signal_refresh_list:
        return {"synced": False, "provider": prov.code,
                "notes": [f"{prov.code} is quota-limited and is not synced automatically: use Data Sources to sync it"]}
    notes, fetched = [], []
    for tf in REFRESH_TFS:
        if tf in NOT_SERVED.get(prov.code, set()):
            continue
        cov = session.scalar(select(DataCoverage).where(DataCoverage.instrument_id == inst.id, DataCoverage.provider_id == prov.id,
                                                        DataCoverage.timeframe == tf))
        if not is_due(cov, tf, now, inst):
            continue
        fetched.append(tf)
        notes += [f"{tf}: {n}" for n in fetch_candles(session, inst, prov, pi, tf)]
    return {"synced": True, "provider": prov.code, "fetched": fetched, "notes": notes}


def fetch_candles(session: Session, inst: Instrument, prov: DataProvider, pi: ProviderInstrument, tf: str) -> list[str]:
    """Ingest the latest candles of one due timeframe. Unlike `ensure_data` (which tolerates one missing candle on long series), a live
    signal needs every closed candle as soon as it exists. Provider problems become notes; analysis continues on stored candles."""
    try:
        ingest_candles(session, get_provider(prov.code), inst, prov, pi, tf, bars=PARAMS["lookback_bars"] + 100)
        return []
    except AppError as exc:
        log.warning("signals sync failed for %s %s: %s", inst.canonical_symbol, tf, exc.message)
        return [f"data sync failed ({exc.message}); using previously stored candles"]
    except Exception as exc:  # noqa: BLE001 - network errors etc. must not break the analysis
        log.warning("signals sync error for %s %s: %s", inst.canonical_symbol, tf, exc)
        return [f"data sync failed ({exc.__class__.__name__}); using previously stored candles"]
