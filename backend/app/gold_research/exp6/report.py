"""docs/reports/EXPERIMENT6_CONFIRMATIONS.md from the frozen Experiment 6 files: every arm with its sample, failures included."""
import json
from datetime import date

from app.gold_research.exp6 import run
from app.historical.config import REPO_ROOT
from app.historical.split import load_split
from app.strategy_engine.config import STRATEGY_NAMES

OUT = REPO_ROOT / "docs" / "reports" / "EXPERIMENT6_CONFIRMATIONS.md"


def _load(p):
    return json.loads(p.read_text()) if p.exists() else None


def _f(x, nd: int = 3, signed: bool = True) -> str:
    if x is None:
        return "—"
    try:
        return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def _segments(symbol: str) -> str:
    try:
        sp = load_split(symbol)
    except Exception:  # noqa: BLE001 - a missing split only drops this line
        return f"{symbol}: split not on this machine"
    return (f"{symbol} development {sp['train']['start'][:10]} to {sp['train']['end_exclusive'][:10]}, confirmation to "
            f"{sp['validation']['end_exclusive'][:10]}")


def _row(a: dict, stage: str) -> str:
    k, b = a.get("kept") or {}, a.get("baseline") or {}
    if stage == "development":
        verdict = "passed development" if a.get("passed") else "did not pass"
    else:
        verdict = "confirmed" if a.get("passed") else "did not pass"
    if a.get("passed") and not a.get("promotable"):
        verdict += " (gold VSA: research only, never a gate)"
    return (f"| {a['symbol']} | {STRATEGY_NAMES.get(a['strategy'], a['strategy'])} | {a['arm']} | {a.get('trades', 0):,} | "
            f"{k.get('trades', 0):,} | {_f(b.get('expectancy_r'))} | {_f(k.get('expectancy_r'))} | {_f(a.get('improvement_r'))} | "
            f"{_f(a.get('improvement_r_2x_costs'))} | {_f(a.get('p_random'), 4, False)} | {_f(a.get('p_holm'), 4, False)} | "
            f"{_f(a.get('positive_year_share'), 2, False)} | {verdict} |")


HEAD = ("| Symbol | Strategy | Arm | Trades | Kept | Baseline R | Kept R | Improvement | At 2x costs | Random-filter p | Holm p | "
        "Years improved | Result |\n|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")


def render() -> str:
    pre, dev, conf = _load(run.PREREG), _load(run.DEV), _load(run.CONF)
    if pre is None:
        return "# Experiment 6\n\nNot pre-registered yet."
    fam = set(pre.get("family", []))
    dev_rows = (dev or {}).get("arms", [])
    conf_rows = (conf or {}).get("arms", [])
    promoted = [f"{r['symbol']} {STRATEGY_NAMES.get(r['strategy'], r['strategy'])}: {r['arm']}" for r in conf_rows
                if r.get("passed") and r.get("promotable")]
    lead = (f"Promoted to a gate: {'; '.join(promoted)}." if promoted else
            "No confirmation was promoted to a gate: none improved net results reproducibly on out-of-sample data.")
    lines = [f"# Experiment 6: do VSA and indicator confirmations improve the six strategies? ({date.today().isoformat()})", "",
             lead, "",
             f"{len(fam)} arms entered the test family (counts only, decided before outcomes); "
             f"{len((dev or {}).get('passed', []))} passed development; "
             f"{len((conf or {}).get('passed', []))} passed the confirmation segment. "
             f"Trials counted from here on: {pre.get('total_trials', 0):,}.", "",
             "Method: [EXPERIMENT_6_PLAN.md](../engine_v2/EXPERIMENT_6_PLAN.md). An arm keeps a trade only when its confirmation is PASS; "
             "it is compared with the strategy without the filter and with 20,000 random filters keeping the same number of trades per "
             "timeframe, direction and year. R is net of the real spread (gold: Dukascopy bid/ask; BTCUSDT: the $2 round-trip model). "
             "Results are hypothetical research figures, not trading performance.", "",
             "Segments: " + "; ".join(_segments(s) for s in run.SYMBOLS) + ". The sealed final-test periods were never read.", "",
             "## Development (training segment)", "", HEAD]
    lines += [_row(a, "development") for a in dev_rows] or ["| — | — | — | — | — | — | — | — | — | — | — | — | not run yet |"]
    out = [a for a in pre.get("arms", []) if not a.get("in_family")]
    if out:
        lines += ["", "Arms below the count rule (fewer than 300 kept development signals, or fewer than 10% dropped), not tested:", ""]
        lines += [f"- {a['symbol']} {STRATEGY_NAMES.get(a['strategy'], a['strategy'])}, {a['arm']}: {a['kept']:,} kept of {a['signals']:,} "
                  f"signals (below the count rule)" for a in out]
    lines += ["", "## Confirmation segment (run once)", ""]
    if conf is None:
        lines.append("Not run yet.")
    elif not conf_rows:
        lines.append(f"{conf.get('status', 'not run')}.")
    else:
        lines += [HEAD] + [_row(a, "confirmation") for a in conf_rows]
    if dev_rows:
        def pair(a: dict, key: str, src: tuple[str, str] = ("kept", "baseline"), nd: int = 2) -> str:
            x, y = (a.get(src[0]) or {}).get(key), (a.get(src[1]) or {}).get(key)
            return f"{_f(x, nd, False)} / {_f(y, nd, False)}"

        lines += ["", "## Details per arm (development)", "",
                  "Kept trades against all trades of the strategy; stop-outs = trades that hit the stop before TP1 (false entries). "
                  "Taker fee: the improvement after Binance's 0.1% per side, BTCUSDT only. Max drawdown is the largest fall of "
                  "cumulative R and grows with the number of trades, so a smaller kept set shows a smaller drawdown by construction: "
                  "compare per-trade figures.", "",
                  "| Arm | Win rate kept / all | Profit factor kept / all | Sharpe per trade kept / all | Max drawdown R kept / all | "
                  "Stop-outs kept / dropped | Taker fee |", "|---|---|---|---|---|---|---:|"]
        for a in dev_rows:
            fe = a.get("false_entry") or {}
            lines.append(f"| {a['symbol']} {STRATEGY_NAMES.get(a['strategy'], a['strategy'])}, {a['arm']} | {pair(a, 'win_rate')} | "
                         f"{pair(a, 'profit_factor')} | {pair(a, 'sharpe_per_trade', nd=3)} | {pair(a, 'max_drawdown_r', nd=1)} | "
                         f"{_f(fe.get('stop_share_kept'), 2, False)} / {_f(fe.get('stop_share_dropped'), 2, False)} | "
                         f"{_f(a.get('improvement_r_fee')) if a['symbol'] == 'BTCUSDT' else '—'} |")
    names = {"vsa": "VSA", "momentum": "Momentum", "trend": "Trend", "volatility": "Volatility", "combo": "Combination"}
    conf_keys = {f"{r['symbol']}|{r['strategy']}|{r['arm']}" for r in conf_rows if r.get("passed")}
    lines += ["", "## By confirmation", "",
              "Arms tested in development, how many kept trades that did better than the unfiltered strategy, how many passed every "
              "development check, and how many were confirmed on fresh data.", "",
              "| Confirmation | Arms tested | Improved in development | Passed development | Confirmed | Mean improvement (R per trade) |",
              "|---|---:|---:|---:|---:|---:|"]
    for arm, label in names.items():
        rs = [r for r in dev_rows if r["arm"] == arm and r.get("trades")]
        if not rs:
            continue
        imps = [r["improvement_r"] for r in rs if r.get("improvement_r") is not None]
        confirmed = sum(1 for r in rs if "|".join((r["symbol"], r["strategy"], r["arm"])) in conf_keys)
        lines.append(f"| {label} | {len(rs)} | {sum(1 for x in imps if x > 0)} | {sum(1 for r in rs if r.get('passed'))} | "
                     f"{confirmed} | {_f(sum(imps) / len(imps) if imps else None)} |")
    carried = [r for r in dev_rows if r.get("passed") and r.get("by_regime")]
    if carried:
        lines += ["", "Market regime of the arms that passed development (mean R per trade, development segment):", "",
                  "| Arm | Regime | Unfiltered | Kept |", "|---|---|---:|---:|"]
        for r in carried:
            for reg, v in sorted(r["by_regime"].items()):
                lines.append(f"| {r['symbol']} {STRATEGY_NAMES.get(r['strategy'], r['strategy'])}, {r['arm']} | {reg.lower()} | "
                             f"{_f(v.get('baseline'))} | {_f(v.get('kept'))} |")
    lines += ["", "## What this means", "",
              "- A gate changes BUY/SELL into WAIT only for a promoted category, on the instrument it passed on. Every other category "
              "stays evidence on the signal card, marked \"did not pass Experiment 6\" when it was tested.",
              "- Passing here does not validate a strategy: that still needs Experiment 5's criteria and the owner's approval for the "
              "one-time sealed final test.",
              "- Gold VSA uses Dukascopy venue volume; live gold uses broker tick counts, and their only overlap is sealed, so gold VSA is "
              "research only.",
              "- EURUSD and GBPUSD are not tested yet (their history is still incomplete).",
              "- The live engine keeps about 500 candles per timeframe. Below 1H that is too short for the same-session volume baseline "
              "used here (the same time of the week over 20 weeks), so live VSA is unavailable on 1m-5m and often on 15m, and live trend "
              "decides from EMA 200 and the DI spread without VWAP there. This experiment measured the categories on full history: before "
              "any category could become a gate, the live computation must be made to match it."]
    return "\n".join(lines) + "\n"


def write() -> str:
    OUT.write_text(render(), encoding="utf8")
    return str(OUT)
