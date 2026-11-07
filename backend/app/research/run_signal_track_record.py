"""Historical replay of the signal engine: the honest "confidence" behind every plan (docs/SIGNAL_ENGINE.md, Track record).

Usage (from backend/, with DATABASE_URL pointing at the database that holds the history, e.g. sqlite:///./research.db):
  python -m app.research.run_signal_track_record run --symbols XAUUSD --tfs 1H [--max-steps 8000]   # -> app/data/track_record_parts/
  python -m app.research.run_signal_track_record export                                             # parts -> app/data/signal_track_record.json
  python -m app.research.run_signal_track_record report                                             # -> docs/reports/SIGNAL_TRACK_RECORD.md

Protocol (fixed before any run; nothing is tuned on these results):
  * the engine (`app.signals.engine.evaluate_timeframe`, the exact live code) is evaluated at every closed setup-timeframe candle using only
    candles that were complete at that moment, on every timeframe of the chain (bias + confirmation), `lookback_bars` each;
  * a NEW ENTRY_READY plan opens a market trade at the next candle's open; a NEW "PLACE LIMIT ORDER" plan rests a limit order at the plan's
    entry for the plan's lifetime (cancelled on a close beyond the invalidation level or if TP1 trades first);
  * exits at the plan's stop or TP1; a candle that touches both counts as a LOSS; on the fill candle of a limit order only the stop counts;
  * the configured round-trip spread is charged on every trade (R net = R gross - spread / risk); one position per instrument x timeframe;
  * the steps cover only the period where every timeframe of the chain has history; first 60% = development, last 40% = out-of-sample;
  * status comes from `app.opportunities.validation.classify` on out-of-sample trades (>= 100 trades, CI > 0, p < 0.05, >= 2/3 positive
    sub-periods, better than random entries with the same execution model).
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.database.session import session_scope
from app.market_data.bars import Bars
from app.market_data.ingestion.service import load_candles, resolve_mapping
from app.ml_engine.evaluation import trade_metrics
from app.opportunities.validation import classify
from app.research.experiments import code_version
from app.research.strategy_eval import significance
from app.services.data_service import tf_step, trading_hours_only
from app.signals.config import CHAINS, CONFIG_VERSION, GROUPS, PARAMS, spread_for
from app.signals.context import session_name
from app.signals.engine import Frame, evaluate_timeframe
from app.signals.execution import exit_on_candle, limit_touch, market_entry_ok, r_multiple
from app.signals.track_record import TRACK_PATH, bucket_of

SOURCES = {"BTCUSDT": "binance", "XAUUSD": "twelve_data"}
DEFAULT_TFS = ("5m", "15m", "1H", "4H", "1D")
PARTS = TRACK_PATH.parent / "track_record_parts"
REPORT = Path(__file__).resolve().parents[3] / "docs" / "reports" / "SIGNAL_TRACK_RECORD.md"
OOS_SHARE = 0.4


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_series(session, symbol: str, tf: str) -> Bars | None:
    inst, prov, _ = resolve_mapping(session, symbol, SOURCES[symbol])
    candles = trading_hours_only(load_candles(session, inst.id, prov.id, tf, complete_only=True), inst.calendar)
    return Bars.from_candles(candles, tf_step(tf)) if candles else None


class Cutter:
    """Frames 'as of' a time: the last `lookback` candles complete at end_ts. Unchanged cuts reuse the same Frame (and its price action)."""

    def __init__(self, tf: str, bars: Bars, lookback: int):
        self.tf, self.bars, self.lookback = tf, bars, lookback
        self.close = bars.t + bars.step
        self._key, self._frame = None, None

    def at(self, end_ts: int) -> Frame | None:
        k = int(np.searchsorted(self.close, end_ts, side="right"))
        if k == 0:
            return None
        if k != self._key:
            self._key = k
            self._frame = Frame(self.tf, self.bars.slice(max(0, k - self.lookback), k))
        return self._frame


def _first_ts_ok(bars: Bars, need: int) -> int | None:
    return int(bars.t[need - 1] + bars.step) if len(bars) >= need else None


def replay(symbol: str, tf: str, max_steps: int | None = None) -> dict:
    chain, group = CHAINS[tf], GROUPS[CHAINS[tf].group]
    lookback = PARAMS["lookback_bars"]
    needed = {tf, chain.confirm, *chain.bias, "1D", "1W"}
    with session_scope() as s:
        series = {t: load_series(s, symbol, t) for t in needed}
    setup = series.get(tf)
    if setup is None or len(setup) < PARAMS["min_setup_bars"] + 10:
        return {"status": "untested", "summary": f"not enough stored {tf} history for {symbol}", "n_steps": 0}
    missing = [t for t in (chain.confirm, *chain.bias) if series.get(t) is None]
    starts = [_first_ts_ok(setup, PARAMS["min_setup_bars"])]
    for t in (chain.confirm, *chain.bias):
        if series.get(t) is not None:
            starts.append(_first_ts_ok(series[t], PARAMS["min_bias_bars"]))
    start_ts = max(x for x in starts if x is not None)
    cut = {t: Cutter(t, b, lookback) for t, b in series.items() if b is not None and t != tf}
    close = setup.t + setup.step
    i0 = int(np.searchsorted(close, start_ts, side="left"))
    i_end = len(setup) - 1  # the last candle can only be evaluated, not traded
    if max_steps and i_end - i0 > max_steps:
        i0 = i_end - max_steps
    spread = spread_for(symbol, float(np.median(setup.c[i0:])))
    o, h, lo, c = setup.o, setup.h, setup.l, setup.c
    trades, used_keys = [], set()
    pos = pend = None
    n_eval = 0
    t_start = time.time()
    for i in range(i0, i_end):
        # 1) manage an open position on candle i
        if pos is not None:
            d = pos["d"]
            ex = exit_on_candle(d, pos["sl"], pos["tp"], o[i], h[i], lo[i], tp_allowed=not (pos["fill_i"] == i and pos["limit"]))
            if ex is not None:  # both levels on one candle: the stop (conservative)
                gross = r_multiple(d, pos["entry"], ex[0], pos["risk"])
                trades.append({**pos["meta"], "exit_ts": int(setup.t[i]), "r": float(gross - pos["spread_r"]), "r_gross": float(gross),
                               "tp_hit": ex[1] == "target", "bars": i - pos["fill_i"] + 1})
                pos = None
            continue
        # 2) a resting limit order on candle i
        if pend is not None:
            d = pend["d"]
            touch = limit_touch(d, pend["entry"], pend["tp"], h[i], lo[i])
            if i > pend["expires_i"] or (d == 1 and c[i - 1] < pend["inv"]) or (d == -1 and c[i - 1] > pend["inv"]):
                pend = None
            elif touch == "missed":
                pend = None  # target traded before the fill: missed, never chased
            elif touch == "filled":
                risk = abs(pend["entry"] - pend["sl"])
                pos = {"d": d, "entry": pend["entry"], "sl": pend["sl"], "tp": pend["tp"], "risk": risk, "fill_i": i, "limit": True,
                       "spread_r": spread / risk, "meta": {**pend["meta"], "entry_ts": int(setup.t[i])}}
                pend = None
                if exit_on_candle(d, pos["sl"], pos["tp"], o[i], h[i], lo[i], tp_allowed=False) is not None:  # only the stop counts
                    trades.append({**pos["meta"], "exit_ts": int(setup.t[i]), "r": float(-1 - pos["spread_r"]), "r_gross": -1.0,
                                   "tp_hit": False, "bars": 1})
                    pos = None
            continue
        # 3) flat: evaluate the engine at the close of candle i
        end_ts = int(close[i])
        frames = {tf: Frame(tf, setup.slice(max(0, i + 1 - lookback), i + 1))}
        for t, ct in cut.items():
            f = ct.at(end_ts)
            if f is not None:
                frames[t] = f
        n_eval += 1
        p = evaluate_timeframe(symbol, tf, frames, spread=spread)
        key = p.get("setup_key")
        if not key or key in used_keys:
            continue
        meta = {"dir": p["side"], "setup_type": p["setup_type"], "score": p["score"], "signal_ts": end_ts,
                "session": session_name(end_ts), "entry_type": p["entry_type"]}
        if p["state"] == "ENTRY_READY":
            used_keys.add(key)
            d = 1 if p["side"] == "BUY" else -1
            entry = float(o[i + 1])
            sl, tp = p["stop_loss"], p["targets"][0]["price"]
            risk = d * (entry - sl)
            if not market_entry_ok(d, entry, sl, tp):
                continue  # gapped beyond the stop or the target: no trade
            pos = {"d": d, "entry": entry, "sl": sl, "tp": tp, "risk": risk, "fill_i": i + 1, "limit": False, "spread_r": spread / risk,
                   "meta": {**meta, "entry_ts": int(setup.t[i + 1]), "planned_rr": p["risk_reward"]}}
        elif p["state"] == "SETUP_DEVELOPING" and p["instruction"] == "PLACE LIMIT ORDER":
            used_keys.add(key)
            pend = {"d": 1 if p["side"] == "BUY" else -1, "entry": p["entry"], "sl": p["stop_loss"], "tp": p["targets"][0]["price"],
                    "inv": p["invalidation"], "expires_i": i + group.expiry_bars, "meta": {**meta, "planned_rr": p["risk_reward"]}}
        if n_eval % 500 == 0:
            log(f"{symbol} {tf}: {i - i0}/{i_end - i0} candles, {len(trades)} trades, {time.time() - t_start:.0f}s")
    t_split = int(setup.t[i0] + (setup.t[i_end] - setup.t[i0]) * (1 - OOS_SHARE))
    return summarize(symbol, tf, trades, setup, i0, i_end, t_split, spread, missing, n_eval, time.time() - t_start)


def _block(trades: list[dict]) -> dict:
    if not trades:
        return {"n_trades": 0}
    r = np.array([t["r"] for t in trades])
    m = trade_metrics(r)
    m["tp1_hit_rate"] = float(np.mean([t["tp_hit"] for t in trades]))
    m["avg_planned_rr"] = float(np.mean([t.get("planned_rr") or np.nan for t in trades]))
    return m


def _groups(trades: list[dict], key: str) -> dict:
    out = {}
    for k in sorted({str(t[key]) for t in trades}):
        sub = [t for t in trades if str(t[key]) == k]
        out[k] = {"n": len(sub), "tp1_hit_rate": float(np.mean([t["tp_hit"] for t in sub])), "expectancy_r": float(np.mean([t["r"] for t in sub]))}
    return out


def _buckets(trades: list[dict]) -> dict:
    out = {}
    for b in ("60-69", "70-79", "80-100"):
        sub = [t for t in trades if bucket_of(t["score"]) == b]
        out[b] = {"n": len(sub), "tp1_hit_rate": float(np.mean([t["tp_hit"] for t in sub])) if sub else None,
                  "expectancy_r": float(np.mean([t["r"] for t in sub])) if sub else None,
                  "mean_score": float(np.mean([t["score"] for t in sub])) if sub else None}
    return out


def random_baseline(bars: Bars, i0: int, i1: int, n: int, rr: float, spread: float, seed: int = 0) -> float | None:
    """Expectancy (R) of random-direction market entries with a 1.5 ATR stop and the median planned R:R target, same costs and rules."""
    if n < 10:
        return None
    from app.feature_engineering.indicators import atr as atr_fn

    a = atr_fn(bars.h, bars.l, bars.c, 14)
    rng = np.random.default_rng(seed)
    rs = []
    for _ in range(max(n, 200)):
        i = int(rng.integers(i0, max(i0 + 1, i1 - 2)))
        if not np.isfinite(a[i]) or a[i] <= 0:
            continue
        d = 1 if rng.random() < 0.5 else -1
        entry, risk = bars.o[i + 1], 1.5 * a[i]
        sl, tp = entry - d * risk, entry + d * rr * risk
        r = None
        for j in range(i + 1, min(len(bars), i + 500)):
            if (d == 1 and bars.l[j] <= sl) or (d == -1 and bars.h[j] >= sl):
                r = -1.0
                break
            if (d == 1 and bars.h[j] >= tp) or (d == -1 and bars.l[j] <= tp):
                r = rr
                break
        if r is not None:
            rs.append(r - spread / risk)
    return float(np.mean(rs)) if rs else None


def summarize(symbol, tf, trades, bars, i0, i_end, t_split, spread, missing, n_eval, secs) -> dict:
    dev = [t for t in trades if t["entry_ts"] < t_split]
    oos = [t for t in trades if t["entry_ts"] >= t_split]
    oos_m = _block(oos)
    sig = significance(np.array([t["r"] for t in oos])) if oos else {"n": 0}
    i_split = int(np.searchsorted(bars.t, t_split))
    edges = np.linspace(t_split, int(bars.t[i_end]), 5)
    subs = [[t for t in oos if edges[k] <= t["entry_ts"] < edges[k + 1] or (k == 3 and t["entry_ts"] == edges[4])] for k in range(4)]
    pos = [np.mean([t["r"] for t in sub]) > 0 for sub in subs if sub]
    fold_share = (sum(pos) / len(pos)) if pos else None
    rr = float(np.median([t.get("planned_rr") or 2.0 for t in trades])) if trades else 2.0
    rand = random_baseline(bars, i_split, i_end, len(oos), rr, spread)
    status, summary = classify(oos_m, sig, fold_share, rand) if oos else ("no_edge", "no out-of-sample trades: no conclusion possible")
    hits = np.array([t["tp_hit"] for t in oos], float)
    probs = np.array([t["score"] / 100 for t in oos], float)
    calib = {"brier_score_of_score_as_probability": float(np.mean((probs - hits) ** 2)) if len(oos) else None,
             "brier_of_base_rate": float(np.mean((hits.mean() - hits) ** 2)) if len(oos) else None,
             "note": "score/100 read as a probability, compared with always predicting the observed hit rate; a higher Brier = worse calibration"}
    iso = lambda ts: datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()  # noqa: E731
    return {
        "status": status, "summary": summary, "n_steps": int(i_end - i0), "n_evaluations": n_eval, "seconds": round(secs, 1),
        "period": {"start": iso(bars.t[i0]), "oos_start": iso(t_split), "end": iso(bars.t[i_end]), "oos_share": OOS_SHARE},
        "spread": spread, "missing_timeframes": missing, "trades_total": len(trades),
        "dev": _block(dev), "oos": {**oos_m, "significance": sig, "positive_subperiod_share": fold_share},
        "random_entry_expectancy_r": rand, "all": _block(trades), "oos_buckets": _buckets(oos), "all_buckets": _buckets(trades),
        "by_setup_type": _groups(trades, "setup_type"), "by_entry_type": _groups(trades, "entry_type"), "by_session": _groups(trades, "session"),
        "by_direction": _groups(trades, "dir"), "calibration": calib,
        "trades": [{k: t[k] for k in ("entry_ts", "dir", "setup_type", "entry_type", "score", "r", "tp_hit")} for t in trades][-400:],
    }


def cmd_run(symbols: list[str], tfs: list[str], max_steps: int | None) -> None:
    PARTS.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        for tf in tfs:
            log(f"replay {sym} {tf} ...")
            res = replay(sym, tf, max_steps)
            res["meta"] = {"symbol": sym, "timeframe": tf, "provider": SOURCES[sym], "config_version": CONFIG_VERSION,
                           "code_version": code_version(), "generated_at": datetime.now(timezone.utc).isoformat(), "max_steps": max_steps}
            (PARTS / f"{sym}_{tf}.json").write_text(json.dumps(res, default=float), encoding="utf8")
            log(f"{sym} {tf}: {res['status']} - {res['summary']} ({res.get('trades_total', 0)} trades, {res.get('seconds')}s)")


def cmd_export() -> None:
    results: dict = {}
    for p in sorted(PARTS.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf8"))
        m = r["meta"]
        if m.get("config_version") != CONFIG_VERSION:
            log(f"skip {p.name}: produced by config {m.get('config_version')}, current is {CONFIG_VERSION}")
            continue
        results.setdefault(m["symbol"], {})[m["timeframe"]] = r
    out = {"meta": {"generated_at": datetime.now(timezone.utc).isoformat(), "config_version": CONFIG_VERSION, "oos_share": OOS_SHARE,
                    "method": "docs/SIGNAL_ENGINE.md (Track record), app/research/run_signal_track_record.py"}, "results": results}
    TRACK_PATH.write_text(json.dumps(out, default=float), encoding="utf8")
    log(f"wrote {TRACK_PATH}")


def _pct(x) -> str:
    return "—" if x is None else f"{x:.0%}"


def _r(x) -> str:
    return "—" if x is None else f"{x:+.3f}"


def _interpretation(results: dict) -> list[str]:
    """Plain-language summary: pooled result, windows whose OOS CI excludes zero despite < 100 trades, and whether the score sorts outcomes."""
    trades = [t for tfs in results.values() for r in tfs.values() for t in r.get("trades", [])]
    n_all = sum(r.get("all", {}).get("n_trades", 0) for tfs in results.values() for r in tfs.values())
    pooled = sum((r.get("all", {}).get("expectancy_r") or 0) * r.get("all", {}).get("n_trades", 0) for tfs in results.values() for r in tfs.values())
    out = [f"* Pooled over every instrument and timeframe: **{n_all} trades, {pooled / n_all:+.3f} R per trade** after spread." if n_all else
           "* No trades were replayed."]
    neg, pos = [], []
    for sym, tfs in results.items():
        for tf, r in tfs.items():
            ci = r.get("oos", {}).get("significance", {}).get("boot_ci95")
            if ci and ci[1] < 0:
                neg.append(f"{sym} {tf} ({ci[0]:+.2f} to {ci[1]:+.2f} R)")
            elif ci and ci[0] > 0:
                pos.append(f"{sym} {tf} ({ci[0]:+.2f} to {ci[1]:+.2f} R)")
    out.append("* Out-of-sample 95% CI entirely **below** zero (the rules lost money there, even if the sample is under the 100-trade bar for a "
               f"formal verdict): {', '.join(neg) if neg else 'none'}.")
    out.append(f"* Out-of-sample 95% CI entirely **above** zero but too few trades to validate: {', '.join(pos) if pos else 'none'}.")
    bands = {}
    for b in ("60-69", "70-79", "80-100"):
        rs = [t["r"] for t in trades if bucket_of(t["score"]) == b]
        bands[b] = (len(rs), float(np.mean(rs)) if rs else None)
    out.append("* Does a higher score mean better trades? Expectancy by score band (last 400 trades kept per series): "
               + ", ".join(f"{b}: {v[1]:+.3f} R (n={v[0]})" if v[1] is not None else f"{b}: —" for b, v in bands.items())
               + ". A score that does not rise with outcomes is a checklist of setup quality, not a forecast.")
    out.append("* Verdict rules require >= 100 out-of-sample trades; no series reached that, so nothing is `validated` and no win probability is shown.")
    return out


def cmd_report() -> None:
    data = json.loads(TRACK_PATH.read_text(encoding="utf8"))
    lines = ["# Signal engine — historical track record", "",
             f"_Generated {data['meta']['generated_at'][:16]} UTC · config {data['meta']['config_version']} · method: docs/SIGNAL_ENGINE.md (Track record)._", "",
             "Every number below comes from replaying the exact live engine on stored candles, net of the configured spread. Development = first 60% "
             "of each period, out-of-sample (OOS) = last 40%. The confluence score is **not** a win probability; the calibration column shows how far "
             "score/100 is from the observed hit rate.", "",
             "| Instrument | TF | Period (OOS from) | Trades (OOS) | OOS TP1 hit | OOS expectancy R [95% CI] | OOS PF | Random entries R | Status |",
             "|---|---|---|---|---|---|---|---|---|"]
    for sym, tfs in data["results"].items():
        for tf, r in tfs.items():
            o = r.get("oos", {})
            ci = o.get("significance", {}).get("boot_ci95")
            lines.append(f"| {sym} | {tf} | {r['period']['start'][:10]} → {r['period']['end'][:10]} ({r['period']['oos_start'][:10]}) | "
                         f"{r.get('trades_total', 0)} ({o.get('n_trades', 0)}) | {_pct(o.get('tp1_hit_rate'))} | {_r(o.get('expectancy_r'))}"
                         f"{f' [{ci[0]:+.2f}, {ci[1]:+.2f}]' if ci else ''} | {o.get('profit_factor') and round(o['profit_factor'], 2) or '—'} | "
                         f"{_r(r.get('random_entry_expectancy_r'))} | **{r['status']}** |")
    lines += ["", "## Reading this table", ""] + _interpretation(data["results"])
    lines += ["", "## Details per instrument and timeframe", ""]
    for sym, tfs in data["results"].items():
        for tf, r in tfs.items():
            lines += [f"### {sym} {tf}", "", f"Verdict: **{r['status']}** — {r['summary']}.", ""]
            if r.get("missing_timeframes"):
                lines.append(f"Timeframes missing from the replay (scored 0, as live): {', '.join(r['missing_timeframes'])}.")
            lines += ["| Score band (OOS) | Trades | TP1 hit | Expectancy R |", "|---|---|---|---|"]
            for b, v in (r.get("oos_buckets") or {}).items():
                lines.append(f"| {b} | {v['n']} | {_pct(v['tp1_hit_rate'])} | {_r(v['expectancy_r'])} |")
            lines += ["", "| Setup type (all) | Trades | TP1 hit | Expectancy R |", "|---|---|---|---|"]
            for k, v in (r.get("by_setup_type") or {}).items():
                lines.append(f"| {k} | {v['n']} | {_pct(v['tp1_hit_rate'])} | {_r(v['expectancy_r'])} |")
            cal = r.get("calibration") or {}
            if cal.get("brier_score_of_score_as_probability") is not None:
                lines += ["", f"Calibration (OOS): Brier of score/100 = {cal['brier_score_of_score_as_probability']:.3f} vs "
                              f"{cal['brier_of_base_rate']:.3f} for the base rate."]
            lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf8")
    log(f"wrote {REPORT}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "export", "report"))
    ap.add_argument("--symbols", default="BTCUSDT,XAUUSD")
    ap.add_argument("--tfs", default=",".join(DEFAULT_TFS))
    ap.add_argument("--max-steps", type=int, default=None)
    a = ap.parse_args()
    if a.cmd == "run":
        cmd_run([s.strip().upper() for s in a.symbols.split(",") if s.strip()], [t.strip() for t in a.tfs.split(",") if t.strip()], a.max_steps)
    elif a.cmd == "export":
        cmd_export()
    else:
        cmd_report()


if __name__ == "__main__":
    main()
