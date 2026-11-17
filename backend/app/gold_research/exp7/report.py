"""Experiment 7 documents: the parameter register (before any outcome) and the backtest report (after confirmation)."""
import json


def _v(x) -> str:
    if isinstance(x, (list, tuple)):
        return ", ".join(_v(y) for y in x)
    if isinstance(x, float):
        return f"{x:g}"
    return str(x)


def register_markdown(reg: dict) -> str:
    g = reg["gann"]
    L = ["# Gann parameter register (Experiment 7)", "",
         f"Generated from `app/gold_research/exp7/params.py` before any Experiment 7 outcome was computed. Register sha256 "
         f"`{reg['sha']}`; Gann settings sha256 `{reg['gann_sha']}`. It is frozen in `docs/research/EXP7_parameters.json` and "
         "hashed into the pre-registration: any change after an outcome is seen is a new, recorded trial.", "",
         "## Gann settings (`app/gann/params.py`)", "", "| Setting | Value |", "|---|---|"]
    L += [f"| `{k}` | {_v(v)} |" for k, v in g.items()]
    L += ["", "## Timing track", "", f"Tested timeframes: {_v(reg['timing']['tfs'])}. Information only: "
          f"{_v(reg['timing']['info_tfs'])}.", "", "| Method | Panel column | Timeframes |", "|---|---|---|"]
    L += [f"| {m} | `{x['column']}` | {_v(x['tfs'])} |" for m, x in reg["timing"]["methods"].items()]
    L += ["", f"Level methods (tested): {_v(reg['timing']['levels'])}. Descriptive only (cannot pass): "
          f"{_v(reg['timing']['descriptive_levels'])}.", "", "| Outcome | Definition | Tested |", "|---|---|---|"]
    L += [f"| {o} | {x['rule']} | {x['tested']} |" for o, x in reg["outcomes"].items()]
    L += ["", "Level reaction: " + "; ".join(f"{k}: {_v(v)}" for k, v in reg["reaction"].items()) + ".", "",
          "## Filter track", "", f"Arms: {_v(reg['filters']['arms'])} (definitions in `GANN_ENGINE_DESIGN.md` section 4.4).",
          "", "## Gann-only rules", ""]
    L += [f"- {k}: {_v(v)}" for k, v in reg["rules"].items()]
    L += ["", "## Astro family (separate)", ""]
    L += [f"- {k}: {_v(v) if not isinstance(v, dict) else '; '.join(f'{a}: {b}' for a, b in v.items())}" for k, v in reg["astro"].items()]
    L += ["", "## Controls, floors, costs", "", "| Item | Value |", "|---|---|"]
    L += [f"| controls.{k} | {_v(v) if not isinstance(v, dict) else json.dumps(v)} |" for k, v in reg["controls"].items()]
    L += [f"| floors.{k} | {_v(v)} |" for k, v in reg["floors"].items()]
    L += [f"| alpha | {reg['alpha']} |"]
    L += [f"| costs.{k} | {_v(v) if not isinstance(v, dict) else json.dumps(v)} |" for k, v in reg["costs"].items()]
    L += ["", "## Test families", "", "| Family | Tests |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in reg["families"].items()]
    L += ["", "Holm correction runs within each of timing, trading and astro. Descriptive and information rows never pass.", ""]
    return "\n".join(L)


# ---- backtest report (after the development and, if run, the confirmation stage) ------------------------------------------------
def _f(x, nd=3) -> str:
    if x is None:
        return "-"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (int,)) and not isinstance(x, bool):
        return f"{x:,}"
    try:
        return f"{float(x):.{nd}f}" if abs(float(x)) < 1e6 else f"{float(x):.3g}"
    except (TypeError, ValueError):
        return str(x)


def _table(rows: list[dict], cols: list[tuple[str, str]]) -> list[str]:
    out = ["| " + " | ".join(h for h, _ in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_f(r.get(k)) if not isinstance(r.get(k), str) else r.get(k) for _, k in cols) + " |")
    return out


def write_reports() -> None:
    from app.gold_research.exp7 import run as R

    pre = json.loads(R.PREREG.read_text())
    dev = json.loads(R.DEV.read_text())
    conf = json.loads(R.CONF.read_text()) if R.CONF.exists() else None
    rows = dev["rows"]
    crow = {r["id"]: r for r in (conf or {}).get("rows", [])}
    confirmed = [i for i, r in crow.items() if r.get("passed")]
    by_fam = {f: [r for r in rows if r["family"] == f] for f in ("timing", "trading", "astro", "descriptive", "info")}
    tested = {f: [r for r in v if r.get("status") == "tested"] for f, v in by_fam.items()}
    untestable = [r for r in rows if str(r.get("status", "")).startswith("not testable")]
    below = [r for r in rows if r.get("status") == "below floor"]
    L = ["# Gann backtest report (Experiment 7)", "",
         "XAUUSD and BTCUSDT. Development and confirmation segments only; the sealed final-test periods (XAUUSD from 2023-06-24, "
         "BTCUSDT from 2025-06-16) were never read. Every setting was frozen in `GANN_PARAMETER_REGISTER.md` and the "
         f"pre-registration (`EXP7_preregistration.json`, sha `{pre['sha256'][:12]}`) was committed before any outcome.", "",
         "## Headline", "",
         f"- Tests registered: {sum(len(v) for v in pre['families'].values())} (timing {len(pre['families']['timing'])}, trading "
         f"{len(pre['families']['trading'])}, astro {len(pre['families']['astro'])}, descriptive {len(pre['families']['descriptive'])}).",
         f"- Actually tested in development: timing {len(tested['timing'])}, trading {len(tested['trading'])}, astro "
         f"{len(tested['astro'])}. Not testable (windows cover more than 90% of candles): {len(untestable)}. Below the "
         f"sample-size floor: {len(below)}.",
         f"- Development candidates (Holm-adjusted p < 0.05 and every check): {len(dev['candidates'])}"
         + (f": {', '.join(dev['candidates'])}." if dev["candidates"] else "."),
         f"- Confirmation: {conf['status'] if conf else 'not run yet'}"
         + (f"; confirmed: {', '.join(confirmed) if confirmed else 'none'}." if conf else "."),
         f"- Trial count for the deflated Sharpe ratio: {pre['prior_trials']:,} before, {pre['total_trials']:,} after.",
         "- Disclosure: Experiment 6 had already used the confirmation segments of both instruments once.", ""]
    L += ["## Coverage: the main structural finding", "",
          "A method whose windows cover more than 90% of candles cannot be tested: almost every turn falls inside it by "
          "construction. These were removed by the pre-registered rule, on counts alone:", ""]
    L += _table(sorted({(r['symbol'], r['tf'], r['method']): r for r in untestable}.values(), key=lambda r: (r['symbol'], r['tf'])),
                [("Instrument", "symbol"), ("TF", "tf"), ("Method", "method"), ("Coverage", "coverage")])
    L += ["", "## Timing family (time windows and price levels)", "",
          "Lift = outcome rate inside the Gann windows (or at Gann levels) divided by outside (or at control levels). p from "
          "coverage-matched random controls; Holm within the family.", ""]
    tcols = [("Test", "id"), ("Coverage", "coverage"), ("Lift", "lift"), ("Control", "control_mean"), ("p", "p"),
             ("Holm p", "p_holm"), ("Passed", "passed")]
    L += _table(sorted(tested["timing"], key=lambda r: (r.get("p_holm") or 1, r["id"])), tcols)
    L += ["", "## Trading family: Gann filters on the existing strategies (B to I)", ""]
    fr = [r for r in tested["trading"] if r.get("track") == "filter"]
    for r in fr:
        r["_base"] = (r.get("baseline") or {}).get("expectancy_r")
        r["_kept"] = (r.get("kept") or {}).get("expectancy_r") if isinstance(r.get("kept"), dict) else None
    L += _table(fr, [("Arm", "id"), ("Trades", "trades"), ("Baseline R", "_base"), ("Kept R", "_kept"),
                     ("Improvement R", "improvement_r"), ("At 2x costs", "improvement_r_2x_costs"), ("p", "p"),
                     ("Holm p", "p_holm"), ("Passed", "passed")])
    L += ["", "## Trading family: Gann-only rules (J1 to J6)", ""]
    jr = [r for r in tested["trading"] if r.get("track") == "gann_only"]
    for r in jr:
        m = r.get("metrics") or {}
        r.update({"_mean": m.get("expectancy_r"), "_wr": m.get("win_rate"), "_pf": m.get("profit_factor"),
                  "_dd": m.get("max_drawdown_r")})
    L += _table(jr, [("Rule", "id"), ("Trades", "trades"), ("Mean R", "_mean"), ("Win rate", "_wr"), ("PF", "_pf"),
                     ("Max DD (R)", "_dd"), ("Edge vs random", "edge"), ("At 2x costs", "mean_r_2x_costs"), ("p", "p"),
                     ("Holm p", "p_holm"), ("Passed", "passed")])
    L += ["", "## Astro family (separate, experimental)", ""]
    L += _table(tested["astro"], tcols)
    L += ["", "## Descriptive and information rows (cannot pass)", ""]
    L += _table([r for r in by_fam["descriptive"] + by_fam["info"] if r.get("lift") is not None],
                [("Row", "id"), ("Lift", "lift"), ("p", "p")])
    L += ["", "## Below the sample-size floor (decided on counts only)", ""]
    L += [", ".join(sorted(r["id"] for r in below)) or "none", ""]
    if conf and conf.get("rows"):
        L += ["## Confirmation (run once)", ""]
        L += _table(conf["rows"], [("Test", "id"), ("Lift / edge", "lift"), ("p", "p"), ("Holm p", "p_holm"), ("Passed", "passed")])
        L += [""]
    R.REPO_ROOT.joinpath("docs", "gann", "GANN_BACKTEST_REPORT.md").write_text("\n".join(L), encoding="utf8")
