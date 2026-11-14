"""docs/reports/EXPERIMENT6_CONFIRMATIONS.md from the frozen Experiment 6 files: every arm with its sample, failures included."""
import json
from datetime import date

from app.gold_research.exp6 import run
from app.historical.config import REPO_ROOT
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
    lines += ["", "## What this means", "",
              "- A gate changes BUY/SELL into WAIT only for a promoted category, on the instrument it passed on. Every other category "
              "stays evidence on the signal card, marked \"did not pass Experiment 6\" when it was tested.",
              "- Passing here does not validate a strategy: that still needs Experiment 5's criteria and the owner's approval for the "
              "one-time sealed final test.",
              "- Gold VSA uses Dukascopy venue volume; live gold uses broker tick counts, and their only overlap is sealed, so gold VSA is "
              "research only.",
              "- EURUSD and GBPUSD are not tested yet (their history is still incomplete)."]
    return "\n".join(lines) + "\n"


def write() -> str:
    OUT.write_text(render(), encoding="utf8")
    return str(OUT)
