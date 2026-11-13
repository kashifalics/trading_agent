"""DB-facing side of strategy engine v2: the same candles and provider per instrument as the Signals engine v1 (never mixed), H8
built from complete 4H candles, live quote and spread, session, paper-trade management (kept separate), risk check, and one
primary action per instrument. Results are kept for a short time like v1's (the paper cycle refreshes them every minute)."""
import time
from datetime import datetime, timezone

import numpy as np
from sqlalchemy.orm import Session

from app.core.jsonutil import to_jsonable
from app.market_data.bars import Bars
from app.market_data.calendars import get_calendar
from app.strategy_engine.config import (
    CHAINS,
    ENGINE_VERSION,
    GROUPS,
    RESEARCH_NOTE,
    RESEARCH_STATUS,
    SIGNAL_TFS,
    STRATEGY_NAMES,
)
from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime, classify
from app.strategy_engine.risk import check as risk_check
from app.strategy_engine.selector import evaluate_timeframe
from app.strategy_engine.sessions import NEWS, session_info

CACHE_TTL_S = 45
_TFD: dict[tuple, TFData] = {}
_RESULTS: dict[str, tuple[float, dict]] = {}
MAX_TFD = 300


def derive_8h(b4: Bars | None, b1d: Bars | None) -> Bars | None:
    """8-hour candles from complete 4H candles: three buckets per trading day (anchored on the daily candles' open, tolerant of a
    one-hour daylight-saving shift); a bucket is complete with both 4H candles, or when a later bucket exists (early close)."""
    if b4 is None or len(b4) < 2:
        return None
    offset = int(b1d.t[-1]) % 86400 if b1d is not None and len(b1d) else 0
    t = b4.t.astype(np.int64)
    day = (t - offset + 7200) // 86400
    rel = t - day * 86400 - offset
    key = day * 3 + np.clip((rel + 3600) // 28800, 0, 2)
    rows = []
    uniq = np.unique(key)
    for n_, k in enumerate(uniq):
        idx = np.nonzero(key == k)[0]
        if len(idx) < 2 and n_ == len(uniq) - 1:
            continue  # the latest bucket is still forming
        rows.append((int(t[idx[0]]), float(b4.o[idx[0]]), float(b4.h[idx].max()), float(b4.l[idx].min()), float(b4.c[idx[-1]]),
                     float(b4.v[idx].sum())))
    if not rows:
        return None
    a = np.array(rows)
    return Bars(t=a[:, 0].astype(np.int64), o=a[:, 1], h=a[:, 2], l=a[:, 3], c=a[:, 4], v=a[:, 5], step=28800)


def _tfdata(key: tuple, tf: str, bars: Bars, pa, levels: dict) -> TFData:
    k = (*key, tf, len(bars), int(bars.t[-1]), float(bars.c[-1]), tuple(sorted((levels or {}).items())))
    hit = _TFD.get(k)
    if hit is None:
        hit = TFData.build(tf, bars, pa, levels)
        _TFD[k] = hit
        while len(_TFD) > MAX_TFD:
            _TFD.pop(next(iter(_TFD)))
    return hit


def _iso(ts: int | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


ACTION_RANK = {"BUY": 0, "SELL": 0, "WAIT FOR BUY": 1, "WAIT FOR SELL": 1, "NO TRADE": 2}


def best_of(results: list[dict]) -> dict | None:
    live = [r for r in results if r["action"] != "NO TRADE"]
    if not live:
        return None
    return min(live, key=lambda r: (ACTION_RANK[r["action"]], GROUPS[r["group"]].rank, -(r["plan"] or {}).get("risk_reward", 0)))


def analyze(session: Session, symbol: str, now: datetime | None = None) -> dict:
    from app.paper.service import account_state, active_account
    from app.signals import service as v1
    from app.signals.config import spread_for

    now = now or datetime.now(timezone.utc)
    inst, prov, pi = v1.resolve(session, symbol)
    sym = inst.canonical_symbol
    base = {"symbol": sym, "name": inst.name, "provider": prov.code, "price_precision": inst.price_precision, "engine_version": ENGINE_VERSION,
            "generated_at": now.isoformat(), "news": NEWS, "research": {"status": RESEARCH_STATUS, "note": RESEARCH_NOTE,
                                                                       "names": STRATEGY_NAMES}}
    frames = v1.load_frames(session, inst, prov, pi, now) if v1._has_candles(session, inst, prov) else {}
    bars = {tf: f.bars for tf, f in frames.items() if f.bars is not None and len(f.bars)}
    if not bars:
        return to_jsonable({**base, "status": "unavailable", "reason": "no stored candles yet", "primary": {"action": "NO TRADE",
                            "headline": "NO TRADE: no market data yet", "kind": "no_data"}, "opportunity": None, "timeframes": [],
                            "trades": [], "exits": []})
    lv: dict = {}
    if "1D" in bars and len(bars["1D"]):
        lv.update(pdh=float(bars["1D"].h[-1]), pdl=float(bars["1D"].l[-1]), pd_end=int(bars["1D"].t[-1]) + int(bars["1D"].step))
    if "1W" in bars and len(bars["1W"]):
        lv.update(pwh=float(bars["1W"].h[-1]), pwl=float(bars["1W"].l[-1]))
    b8 = derive_8h(bars.get("4H"), bars.get("1D"))
    key = (inst.id, prov.id)
    tfd: dict[str, TFData | None] = {}
    for tf in SIGNAL_TFS:
        b = b8 if tf == "8H" else bars.get(tf)
        if b is None or not len(b):
            tfd[tf] = None
            continue
        pa = frames[tf].pa if tf in frames and frames[tf].bars is not None else None
        tfd[tf] = _tfdata(key, tf, b, pa, lv)
    regimes: dict[str, Regime] = {tf: classify(tfd[tf]) for tf in SIGNAL_TFS}
    quote = v1._quote(prov, pi)
    live_q = quote is not None and not quote.get("delayed") and quote.get("price") is not None
    lowest = next((tfd[tf] for tf in SIGNAL_TFS if tfd[tf] is not None), None)
    price_now = float(quote["price"]) if live_q else (float(lowest.bars.c[-1]) if lowest is not None else None)
    model_spread = spread_for(sym, price_now) if price_now else 0.0
    live_spread = quote.get("spread") if live_q else None
    spread = float(live_spread) if live_spread is not None and live_spread > 0 else float(model_spread or 0.0)
    spread_normal = live_spread is None or not model_spread or live_spread <= 3 * model_spread
    market_open = get_calendar(inst.calendar).is_open(now)
    sess = session_info(now, "continuous" if inst.calendar == "continuous" else "fx")
    results = []
    for tf in SIGNAL_TFS:
        ctx_tf = CHAINS[tf].context
        r = evaluate_timeframe(tfd[tf], tf, regimes[tf], regimes.get(ctx_tf) if ctx_tf else None, precision=inst.price_precision,
                               spread=spread, price_now=price_now, market_open=market_open and sess["entry_allowed"],
                               spread_normal=spread_normal)
        t = tfd[tf]
        r["n_bars"] = 0 if t is None else t.n
        r["data_time"] = _iso(int(t.bars.t[-1]) + int(t.bars.step)) if t is not None else None
        if r.get("plan"):
            r["plan"]["signal_time"] = _iso(r["plan"]["signal_time"])
            r["plan"]["expires_at"] = _iso(r["plan"]["expires_at"])
        for c in r["candidates"]:
            if c.get("plan"):
                c["plan"]["signal_time"] = _iso(c["plan"]["signal_time"]) if isinstance(c["plan"]["signal_time"], int) else c["plan"]["signal_time"]
                c["plan"]["expires_at"] = _iso(c["plan"]["expires_at"]) if isinstance(c["plan"]["expires_at"], int) else c["plan"]["expires_at"]
        results.append(r)
    # paper-trade management: separate from new opportunities
    trades = list(v1.open_trades(session, sym).values())
    exits = [{"trade_id": tr["id"], "timeframe": tr["timeframe"], "direction": tr["direction"], **(tr.get("management") or {})}
             for tr in trades if (tr.get("management") or {}).get("action") == "EXIT"]
    best = best_of(results)
    acc = active_account(session)
    st = account_state(session, acc, now)
    open_risk = [{"symbol": tr["symbol"], "direction": tr["direction"], "risk_pct": (tr.get("risk_amount") or 0) / max(st["balance"], 1) * 100}
                 for tr in trades if tr.get("account_taken") and tr.get("status") == "open"]
    risk = None
    if best is not None:
        risk = risk_check(best, symbol=sym, equity=st["balance"], peak_equity=max(st["balance"], acc.start_balance),
                          today_pnl_pct=(st["today_pnl"] / st["start_of_day_balance"] * 100) if st["start_of_day_balance"] else 0.0,
                          open_trades=open_risk, regime_label=best["regime"]["label"], session=sess)
    if exits:
        e = exits[0]
        primary = {"action": "EXIT", "kind": "exit", "headline": f"EXIT the tracked paper {e['direction']} trade on {e['timeframe']}: {e.get('reason', '')}",
                   "exit": e}
    elif best is not None:
        primary = {"kind": "opportunity", **{k: best[k] for k in ("action", "headline", "timeframe")}}
    else:
        why = sorted({r["headline"].split(": ", 1)[-1] for r in results})[:3]
        primary = {"action": "NO TRADE", "kind": "no_trade",
                   "headline": "NO TRADE: no strategy qualifies on any timeframe", "why": why}
    data_ts = max((int(t.bars.t[-1]) + int(t.bars.step) for t in tfd.values() if t is not None), default=None)
    return to_jsonable({**base, "status": "ok", "calendar": inst.calendar, "market_open": market_open, "session": sess, "quote": quote,
                        "price_now": price_now, "price_source": "live quote" if live_q else "last close", "spread": spread,
                        "spread_source": "live bid/ask" if live_spread else "spread model", "data_time": _iso(data_ts),
                        "primary": primary, "opportunity": best, "risk": risk, "timeframes": results, "trades": trades, "exits": exits})


def analyze_cached(session: Session, symbol: str, max_age: float = CACHE_TTL_S) -> dict:
    hit = _RESULTS.get(symbol.upper())
    if hit is not None and time.monotonic() - hit[0] < max_age:
        return hit[1]
    r = analyze(session, symbol)
    remember(r)
    return r


def remember(r: dict) -> None:
    if r.get("symbol"):
        _RESULTS[r["symbol"]] = (time.monotonic(), r)


def compact(r: dict) -> dict:
    """One row per instrument for lists (Signals overview, Scanner, Overview)."""
    keep = ("symbol", "name", "status", "reason", "provider", "price_precision", "price_now", "price_source", "data_time", "generated_at",
            "market_open", "session", "primary", "opportunity", "exits", "engine_version", "risk")
    out = {k: r.get(k) for k in keep}
    if out.get("opportunity"):
        out["opportunity"] = {k: v for k, v in out["opportunity"].items() if k != "candidates"}
    out["tfs"] = [{"timeframe": t["timeframe"], "action": t["action"], "strategy_name": t.get("strategy_name"), "regime": t["regime"]["label"],
                   "regime_name": t["regime"]["name"], "entry_status": (t.get("plan") or {}).get("entry_status"),
                   "risk_reward": (t.get("plan") or {}).get("risk_reward"), "headline": t["headline"]} for t in r.get("timeframes", [])]
    out["trades"] = [{k: tr.get(k) for k in ("id", "timeframe", "direction", "status", "fill_price", "entry_price", "stop_loss",
                                             "take_profit", "last_price", "unrealized_r", "management")} for tr in r.get("trades", [])]
    return out


def summary(session: Session) -> dict:
    from app.core.config import get_settings
    items = []
    for sym in get_settings().signal_list:
        try:
            items.append(compact(analyze_cached(session, sym)))
        except Exception as exc:  # noqa: BLE001 - one instrument must not break the page
            items.append({"symbol": sym, "status": "failed", "reason": f"{exc.__class__.__name__}: {exc}"[:200],
                          "primary": {"action": "NO TRADE", "headline": "NO TRADE: the analysis failed", "kind": "no_data"}, "tfs": [], "trades": []})
    order = {"EXIT": 0, "BUY": 1, "SELL": 1, "WAIT FOR BUY": 2, "WAIT FOR SELL": 2, "NO TRADE": 3}
    items.sort(key=lambda x: (order.get((x.get("primary") or {}).get("action"), 4),
                              -(((x.get("opportunity") or {}).get("plan") or {}).get("risk_reward") or 0)))
    return to_jsonable({"items": items, "generated_at": datetime.now(timezone.utc).isoformat(), "engine_version": ENGINE_VERSION,
                        "research_note": RESEARCH_NOTE, "news": NEWS})

