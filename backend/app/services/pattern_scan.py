"""All-timeframe scan: what is the market doing on every timeframe right now, and what does history say about it?

Evidence comes from the stored pattern study (backend/app/data/pattern_evidence.json, produced by
scripts/export_pattern_evidence.py from a reproducible experiment). A pattern with no study data is reported as such,
never given a made-up track record."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.market_data.ingestion.service import resolve_mapping
from app.market_data.timeframes import TIMEFRAME_ORDER
from app.price_action.engine import analyze_price_action
from app.research.pattern_edge import MIN_N_IS, collect_signals
from app.services.data_service import load_bars

EVIDENCE_PATH = Path(__file__).resolve().parents[1] / "data" / "pattern_evidence.json"
MIN_BARS = 120


def load_evidence(path: Path | None = None) -> dict:
    p = path or EVIDENCE_PATH
    if not p.exists():
        return {"meta": {}, "symbols": {}}
    return json.loads(p.read_text(encoding="utf8"))


def study_caveat(symbol: str, path: Path | None = None) -> str | None:
    """One honest sentence for every BUY/SELL when the pattern study found no robust, profitable out-of-sample pattern."""
    ex = load_evidence(path).get("meta", {}).get("experiments", {}).get(symbol)
    if not ex:
        return None
    sm = ex["summary"]
    if sm.get("confirmed_net", 0) == 0:
        return (f"Pattern study #{ex['id']}: of {sm['tested']} patterns tested on {symbol} across timeframes, none showed a robust "
                f"out-of-sample edge after costs - treat this signal as unvalidated.")
    return None


def verdict(ev: dict | None) -> str:
    if not ev:
        return "no_study_data"
    if ev.get("cn"):
        return "confirmed_tradeable"
    if ev.get("cg"):
        return "confirmed_not_profitable_after_costs"
    if ev.get("cand"):
        return "failed_out_of_sample"
    if (ev.get("i_n") or 0) < MIN_N_IS:
        return "too_few_events"
    return "no_edge_found"


def resolve_source(session: Session, symbol: str, provider: str | None):
    """An explicit provider, else the one the Signals page uses for this instrument (so both pages read the same candles)."""
    if provider:
        return resolve_mapping(session, symbol, provider)
    from app.signals.service import resolve
    return resolve(session, symbol)


def series(session: Session, inst, prov, pi, tf: str, lookback: int):
    """Stored complete candles, or (when the native series is too short) candles built from a lower timeframe, as Signals does."""
    from app.opportunities.analysis import prepare_tf
    t = prepare_tf(session, inst, prov, pi, tf, lookback=lookback)
    return (t.bars if t.bars is not None else load_bars(session, inst, prov, tf, lookback)), t.derived_from


def scan_symbol(session: Session, symbol: str, provider: str | None = None, recent: int = 3, lookback: int = 800,
                evidence_file: Path | None = None) -> dict:
    inst, prov, pi = resolve_source(session, symbol, provider)
    store = load_evidence(evidence_file)
    ev_sym = store.get("symbols", {}).get(inst.canonical_symbol, {})
    frames = []
    for tf in TIMEFRAME_ORDER:
        bars, derived = series(session, inst, prov, pi, tf, lookback)
        n = len(bars)
        if n < MIN_BARS:
            frames.append({"timeframe": tf, "bars": n, "status": "insufficient_data"})
            continue
        pa = analyze_price_action(bars)
        sigs = collect_signals(bars, pa, intraday_hours=False)
        firing = []
        for name, idx in sigs.items():
            hit = idx[idx >= n - recent]
            if len(hit):
                pat, side = name.rsplit(":", 1)
                ev = ev_sym.get(tf, {}).get(name)
                firing.append({"pattern": pat, "side": side, "bars_ago": int(n - 1 - hit[-1]), "verdict": verdict(ev), "evidence": ev})
        order = {"confirmed_tradeable": 0, "confirmed_not_profitable_after_costs": 1, "failed_out_of_sample": 2}
        firing.sort(key=lambda f: (order.get(f["verdict"], 9), f["bars_ago"]))
        live_zones = [e for e in pa.fvgs + pa.order_blocks + pa.breakers + pa.zones
                      if e.status not in ("filled", "invalidated", "broken") and e.idx > n - 300]
        pd_ = pa.premium_discount
        frames.append({
            "timeframe": tf, "bars": n, "status": "ok", "last_bar": int(bars.t[-1]),
            "structure_trend": int(pa.trend[-1]), "last_break": (pa.breaks[-1].kind + ":" + pa.breaks[-1].direction) if pa.breaks else None,
            "zone": pd_.status if pd_ else None, "range_position": pd_.meta["position"] if pd_ else None,
            "atr": float(pa.atr[-1]) if n and pa.atr[-1] == pa.atr[-1] else None, "last_close": float(bars.c[-1]),
            "live_zones": len(live_zones), "patterns_firing": firing, "derived_from": derived,
        })
    ok = [f for f in frames if f["status"] == "ok"]
    ups = sum(f["structure_trend"] > 0 for f in ok)
    downs = sum(f["structure_trend"] < 0 for f in ok)
    return {"symbol": inst.canonical_symbol, "provider": prov.code, "recent_bars": recent, "timeframes": frames,
            "alignment": {"bullish_timeframes": ups, "bearish_timeframes": downs, "analysed": len(ok)},
            "evidence_meta": store.get("meta", {}),
            "note": "Pattern track records are out-of-sample measurements from a reproducible study (see docs/reports/PATTERN_EDGE_*.md). "
                    "'no_edge_found' means the pattern did not beat taking the same trade at random after correcting for the number of "
                    "patterns tested. Nothing here is a probability of profit."}
