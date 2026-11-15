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
