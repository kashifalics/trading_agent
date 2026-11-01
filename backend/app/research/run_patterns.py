"""Gold + Bitcoin, all timeframes: load data, test every pattern, write reports.

  python -m app.research.run_patterns data  [--symbols BTCUSDT XAUUSD]
  python -m app.research.run_patterns study [--symbols ...]
  python -m app.research.run_patterns report
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.exceptions import AppError
from app.database.init_db import init_db
from app.database.models import Experiment
from app.database.session import session_scope
from app.market_data.aggregation.aggregate import aggregate_candles
from app.market_data.ingestion.backfill import backfill_candles
from app.market_data.ingestion.service import (
    anchor_for,
    load_candles,
    refresh_coverage,
    resolve_mapping,
    store_candles,
)
from app.market_data.registry import get_provider
from app.market_data.timeframes import get_timeframe
from app.research.experiments import Timer, dataset_snapshot, record_experiment
from app.research.pattern_edge import apply_multiple_testing, study_timeframe
from app.services.data_service import load_bars, trading_hours_only

REPORT_DIR = Path(__file__).resolve().parents[3] / "docs" / "reports"
# bars wanted per timeframe (history is capped so the study stays tractable); (native on provider?) decided per symbol
WANT = {"1m": 30000, "3m": 30000, "5m": 30000, "15m": 30000, "30m": 30000, "1H": 28800, "2H": 14400, "4H": 7200, "1D": 3400, "1W": 480}
# round-trip cost as a fraction of price: BTC spot taker fees dominate; gold/FX CFD cost is spread + slippage
COST = {"BTCUSDT": 2 * (0.0010 + 0.0001) + 0.00002, "XAUUSD": 2 * 0.00005 + 0.0001}
AGGREGATED = {"XAUUSD": {"3m": "1m", "2H": "1H", "4H": "1H"}}
PROVIDER = {"BTCUSDT": "binance", "XAUUSD": "twelve_data"}


def log(m: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def cmd_data(symbols: list[str]) -> None:
    now = datetime.now(timezone.utc)
    for sym in symbols:
        with session_scope() as s:
            inst, prov, pi = resolve_mapping(s, sym, PROVIDER[sym])
            provider = get_provider(prov.code)
            native = set(provider.native_timeframes)
            for tf, bars in WANT.items():
                if sym in AGGREGATED and tf in AGGREGATED[sym]:
                    continue
                if tf not in native:
                    log(f"{sym} {tf}: not native on {prov.code}, skipped")
                    continue
                step = get_timeframe(tf).seconds
                factor = 1.0 if inst.calendar == "continuous" else 1.5
                start = now - timedelta(seconds=step * bars * factor)
                try:
                    run = backfill_candles(s, provider, inst, prov, pi, tf, start, now=now, window_candles=3500 if prov.code == "twelve_data" else 1000)
                    log(f"{sym} {tf}: {run.status} requests={run.requests} stored={run.stored} misaligned={run.misaligned} missing {run.missing_before}->{run.missing_after}")
                except AppError as e:
                    log(f"{sym} {tf}: FAILED {e.message}")
            for tf, base_tf in AGGREGATED.get(sym, {}).items():  # built on OUR UTC grid from trading-hour candles only
                base = trading_hours_only(load_candles(s, inst.id, prov.id, base_tf, complete_only=False), inst.calendar)
                agg = aggregate_candles(base, base_tf, tf, anchor_for(inst), inst.calendar)
                n = store_candles(s, inst.id, prov.id, tf, agg)
                refresh_coverage(s, inst, prov, tf, status="ok")
                log(f"{sym} {tf}: aggregated {n} candles from {base_tf}")


def cmd_study(symbols: list[str]) -> None:
    for sym in symbols:
        rows, tfs, snaps = [], {}, {}
        with Timer() as t:
            with session_scope() as s:
                inst, prov, _ = resolve_mapping(s, sym, PROVIDER[sym])
                for tf in WANT:
                    bars = load_bars(s, inst, prov, tf, 40000)
                    if len(bars) < 400:
                        log(f"{sym} {tf}: only {len(bars)} bars, skipped")
                        continue
                    snaps[tf] = dataset_snapshot(s, inst.id, prov.id, tf, sym, prov.code)
                    r = study_timeframe(bars, COST[sym], tf)
                    tfs[tf] = {"bars": len(bars), "first": datetime.fromtimestamp(int(bars.t[0]), tz=timezone.utc).isoformat(),
                               "last": datetime.fromtimestamp(int(bars.t[-1]), tz=timezone.utc).isoformat(), "hypotheses": len(r)}
                    rows += r
                    log(f"{sym} {tf}: {len(bars)} bars, {len(r)} hypotheses")
        summary = apply_multiple_testing(rows)
        log(f"{sym}: {summary}")
        with session_scope() as s:
            e = record_experiment(s, "pattern", f"patterns:{sym}", {"snapshots": snaps}, {"symbol": sym, "cost_round_trip_frac": COST[sym],
                                  "label": {"horizon": 24, "tp_atr": 2.0, "sl_atr": 1.0}, "split": 0.6, "fdr_q": 0.2, "alpha": 0.05},
                                  {"timeframes": tfs, "summary": summary, "rows": rows}, t.elapsed)
        log(f"{sym}: experiment #{e.id} stored ({t.elapsed:.0f}s)")


def _f(v, d=2, sign=False):
    return "—" if v is None else (f"{v:+.{d}f}" if sign else f"{v:.{d}f}")


def _line(r):
    i, o = r["is"] or {}, r["oos"] or {}
    return (f"| {r['tf']} | {r['pattern']} | {r['side']} | {i.get('n', 0)} | {_f(i.get('lift_r'), 3, True)} | {_f(r.get('is_q'), 3)} | "
            f"{o.get('n', 0)} | {_f(o.get('win_rate') and 100 * o['win_rate'], 0)}% | {_f(o.get('gross_r'), 3, True)} | {_f(o.get('net_r'), 3, True)} | "
            f"{_f(o.get('lift_r'), 3, True)} | {_f(o.get('p_lift'), 3)} | {_f(r.get('oos_holm_p'), 3)} | "
            f"{_f((r.get('oos_delay1') or {}).get('lift_r'), 3, True)} (p {_f((r.get('oos_delay1') or {}).get('p_lift'), 2)}) |")


HEAD = ("| TF | Pattern | Side | IS n | IS lift (R) | IS FDR q | OOS n | OOS win | OOS gross R | OOS net R | OOS lift (R) | OOS p | Holm p | Lift if entry 1 bar later |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def _power_table(res: dict) -> str:
    import statistics

    by_tf: dict[str, list[int]] = {}
    sds = []
    for r in res["rows"]:
        if r["is"] and r["is"]["n"] >= 30:
            by_tf.setdefault(r["tf"], []).append(r["is"]["n"])
            if r["is"].get("net_sd"):
                sds.append(r["is"]["net_sd"])
    sd = statistics.median(sds) if sds else 1.2
    lines = ["| TF | Median discovery events per pattern | Smallest lift reliably detectable (80% power, p~0.005) |", "|---|---|---|"]
    for tf, ns in by_tf.items():
        n = statistics.median(ns)
        lines.append(f"| {tf} | {n:.0f} | {(2.58 + 0.84) * sd / n ** 0.5:.2f} R per trade |")
    return ("\n".join(lines) + f"\n\nTypical R standard deviation: {sd:.2f}. **A pattern whose true advantage is smaller than this would NOT be found - "
            "'nothing confirmed' means 'no large edge', not 'no edge at all'.**")


def render(sym: str, e: Experiment) -> str:
    res, cfg = e.results, e.config
    rows, summ = res["rows"], res["summary"]
    cg = [r for r in rows if r.get("confirmed_gross")]
    cn = [r for r in rows if r.get("confirmed_net")]
    cand = sorted([r for r in rows if r.get("candidate")], key=lambda r: r["is_q"])
    o = [f"# {sym} - pattern edge study (all timeframes)", "",
         f"_Generated from experiment #{e.id} by `python -m app.research.run_patterns report`. Nothing here is hand-entered._", "",
         "## Method (so the numbers can be trusted - or doubted)", "",
         "* Every pattern fires at the **close** of a bar; the trade enters at the **next open** with +2 ATR target / -1 ATR stop / 24-bar limit (same-bar ambiguity = stop). R = P&L / stop distance.",
         f"* Costs: round trip **{100 * cfg['cost_round_trip_frac']:.3f}%** of price, converted to R per trade (BTC: 0.10% fee/side + slippage; gold: spread + slippage). *Gross* = no costs.",
         "* **Lift** = pattern mean R minus the mean R of taking the same direction on *every* bar of the same period (removes drift: a rising market makes every long look good).",
         "* **Execution realism:** entries assume a fill at the next bar's open. That is optimistic on very short timeframes, so a pattern must ALSO keep a significant positive lift when the entry is delayed by one more bar. (An earlier run produced eight 1-minute 'confirmations' on gold that vanished after a one-bar delay; they were fill-price artifacts and are now filtered out.)",
         "* Overlapping signals of one pattern are skipped. Discovery on the first 60% of history (label windows never reach the held-out part); confirmation on the last 40%.",
         f"* {summ['tested']} hypotheses with enough discovery events were tested. Discovery keeps only those with Benjamini-Hochberg FDR q < {summ.get('fdr_q', 0.2)} and positive lift; "
         f"confirmation applies a Holm correction (alpha {summ.get('alpha', 0.05)}) over the candidates. **Confirmed** = survives both. **Tradeable** = confirmed AND positive net expectancy out of sample.",
         "* The engine is unit-tested to find a planted effect and to produce ~0 confirmations from pure noise.", "",
         "## Result", "",
         "| Hypotheses tested | Discovery candidates | Out-of-sample testable | **Confirmed (gross lift)** | **Tradeable (net of costs)** |", "|---|---|---|---|---|",
         f"| {summ['tested']} | {summ['candidates']} | {summ.get('oos_testable', 0)} | **{summ['confirmed_gross']}** | **{summ['confirmed_net']}** |", "",
         f"Patterns that passed discovery and Holm-corrected confirmation but **failed the one-bar-delay check** (artifacts that need an unattainable fill): **{summ.get('passed_oos_but_failed_one_bar_delay', 0)}**.", "",
         "## What this study can and cannot detect (statistical power)", "", _power_table(res), "",
         "## Timeframes studied", "", "| TF | Bars | From | To | Hypotheses |", "|---|---|---|---|---|"]
    o += [f"| {tf} | {v['bars']:,} | {v['first'][:10]} | {v['last'][:10]} | {v['hypotheses']} |" for tf, v in res["timeframes"].items()]
    o += ["", "Timeframes not listed (1M and above) have too little history for any statistical statement; 1W has very low power."]
    o += ["", "## Patterns that passed out-of-sample confirmation", ""]
    if not cg:
        o.append("**None.** No pattern kept a statistically significant advantage out of sample after correcting for the number of patterns tested.")
    else:
        o += [HEAD] + [_line(r) for r in sorted(cg, key=lambda r: r["oos_holm_p"])]
        o += ["", f"Of these, **{len(cn)}** also had positive net expectancy out of sample." if cn else "None of them is profitable after costs (predictive information, not a tradeable edge)."]
    o += ["", "## Strongest discovery candidates and what happened out of sample", "",
          "Shown even when they failed, so you can see how much looks like an edge in-sample and then disappears.", "", HEAD]
    o += [_line(r) for r in cand[:30]] or ["| — | no candidate passed discovery | | | | | | | | | | | |"]
    o += ["", f"Full catalogue (every pattern x timeframe with its statistics): `docs/reports/data/PATTERN_EDGE_{sym}.csv`.", "",
          "## Reading guide", "",
          "* A pattern with high win rate but negative lift is just the market's drift or the 2:1 bracket - not information.",
          "* Many tests means some will look good by chance: a lone p < 0.05 means nothing here; only Holm-corrected out-of-sample results count.",
          "* Short timeframes pay the same fee on much smaller moves, so net results degrade sharply as the timeframe shrinks.", ""]
    return "\n".join(o)


def cmd_report() -> None:
    (REPORT_DIR / "data").mkdir(parents=True, exist_ok=True)
    summaries = {}
    with session_scope() as s:
        for sym in PROVIDER:
            e = s.scalars(select(Experiment).where(Experiment.name == f"patterns:{sym}").order_by(Experiment.id.desc()).limit(1)).first()
            if e is None:
                log(f"no study stored for {sym}")
                continue
            (REPORT_DIR / f"PATTERN_EDGE_{sym}.md").write_text(render(sym, e), encoding="utf8")
            with open(REPORT_DIR / "data" / f"PATTERN_EDGE_{sym}.csv", "w", newline="", encoding="utf8") as fh:
                w = csv.writer(fh)
                w.writerow(["tf", "pattern", "side", "events_total", "is_n", "is_win", "is_gross_r", "is_net_r", "is_lift_r", "is_p", "is_q",
                            "oos_n", "oos_win", "oos_gross_r", "oos_net_r", "oos_lift_r", "oos_p", "oos_holm_p", "confirmed_gross", "confirmed_net"])
                for r in e.results["rows"]:
                    i, o = r["is"] or {}, r["oos"] or {}
                    w.writerow([r["tf"], r["pattern"], r["side"], r["events_total"], i.get("n"), i.get("win_rate"), i.get("gross_r"), i.get("net_r"),
                                i.get("lift_r"), i.get("p_lift"), r.get("is_q"), o.get("n"), o.get("win_rate"), o.get("gross_r"), o.get("net_r"),
                                o.get("lift_r"), o.get("p_lift"), r.get("oos_holm_p"), r.get("confirmed_gross"), r.get("confirmed_net")])
            summaries[sym] = (e.id, e.results["summary"])
    log(f"reports written: {summaries}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["data", "study", "report"])
    ap.add_argument("--symbols", nargs="+", default=["BTCUSDT", "XAUUSD"])
    a = ap.parse_args(argv)
    init_db()
    {"data": lambda: cmd_data(a.symbols), "study": lambda: cmd_study(a.symbols), "report": cmd_report}[a.cmd]()


if __name__ == "__main__":
    main(sys.argv[1:])
