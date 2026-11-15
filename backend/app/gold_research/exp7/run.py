"""Experiment 7 stages (docs/gann/GANN_ENGINE_DESIGN.md section 4).

    python -m app.gold_research.exp7 register   EXP7_parameters.json + docs/gann/GANN_PARAMETER_REGISTER.md (commit both)
    python -m app.gold_research.exp7 prereg     EXP7_preregistration.json; refuses unless the register is committed (commit it)
    python -m app.gold_research.exp7 develop    development segment only; refuses without the committed pre-registration
    python -m app.gold_research.exp7 confirm    the confirmation segment, ONCE, only for development candidates
    python -m app.gold_research.exp7 report     docs/gann/GANN_BACKTEST_REPORT.md and GANN_LIMITATIONS.md

Development loads use upto="train", confirmation loads upto="validation"; nothing else can be loaded here. The sealed final-test
periods are never read, and windows or levels that would fall in them are never evaluated.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.gold_research.exp6 import stats as S6
from app.gold_research.exp6.run import require_committed
from app.gold_research.exp7 import params as P
from app.historical import store
from app.historical.config import REPO_ROOT
from app.historical.split import SPLIT_DIR, load_split

PARAMS = SPLIT_DIR / "EXP7_parameters.json"
PREREG = SPLIT_DIR / "EXP7_preregistration.json"
DEV = SPLIT_DIR / "EXP7_development.json"
CONF = SPLIT_DIR / "EXP7_confirmation.json"
REGISTER_MD = REPO_ROOT / "docs" / "gann" / "GANN_PARAMETER_REGISTER.md"
EXP6_PREREG = SPLIT_DIR / "EXP6_preregistration.json"
SEGMENTS = ("train", "validation")
FAMILIES = ("timing", "trading", "astro")  # "descriptive" rows never pass


def load(symbol: str, tf: str, segment: str):
    """Candles of the development (train) or confirmation (validation) data only."""
    if segment not in SEGMENTS:
        raise ValueError(f"Experiment 7 reads only {SEGMENTS}; got {segment!r}")
    return store.load_tf(symbol, tf, upto=segment)


def write_once(path: Path, doc: dict) -> None:
    if path.exists():
        raise RuntimeError(f"{path.name} exists: a frozen Experiment 7 file is never overwritten")
    path.write_text(json.dumps(doc, indent=1, default=float), encoding="utf8")


def guard_once(path: Path) -> None:
    if path.exists():
        raise RuntimeError(f"the Experiment 7 confirmation runs once: {path.name} exists")


def _sha(doc: dict) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=float).encode()).hexdigest()


def _git_head() -> str | None:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
    return r.stdout.strip() or None


def write_register(log=print) -> dict:
    reg = P.register()
    write_once(PARAMS, reg)
    from app.gold_research.exp7.report import register_markdown

    REGISTER_MD.write_text(register_markdown(reg), encoding="utf8")
    log(f"register written: sha {reg['sha'][:12]}; commit {PARAMS.name} and {REGISTER_MD.name}")
    return reg


def prereg_doc() -> dict:
    ids = P.test_ids()
    prior = json.loads(EXP6_PREREG.read_text())["total_trials"]
    new = {k: len(v) for k, v in ids.items()}
    doc = {"experiment": 7, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code_commit": _git_head(),
           "register_sha": P.register()["sha"], "gann_sha": P.GannParams().sha(),
           "splits": {s: load_split(s)["sha256"] for s in P.SYMBOLS},
           "exp6_preregistration_sha256": json.loads(EXP6_PREREG.read_text())["sha256"],
           "families": ids, "alpha": P.ALPHA, "draws": P.DRAWS, "level_draws": P.LEVEL_DRAWS,
           "rule": "Holm within each family (timing, trading, astro) at development and again across the carried candidates at "
                   "confirmation; descriptive rows never pass; floors and the coverage rule look at counts only",
           "prior_trials": prior, "new_trials": new, "total_trials": prior + sum(new.values()),
           "disclosure": "Experiment 6 already used the XAUUSD and BTCUSDT confirmation segments once (4 arms)."}
    doc["sha256"] = _sha(doc)
    return doc


def prereg(log=print) -> dict:
    require_committed(PARAMS)
    if json.loads(PARAMS.read_text())["sha"] != P.register()["sha"]:
        raise RuntimeError("the committed register differs from the code's register: a changed setting is a new trial")
    doc = prereg_doc()
    write_once(PREREG, doc)
    log(f"pre-registration: {sum(doc['new_trials'].values())} tests; total trials {doc['total_trials']}")
    return doc


def gate(rows: list[dict], stage: str) -> None:
    """Holm within each family; a row passes only if it was tested, its effect is in the claimed direction, every extra check
    holds and its Holm-adjusted p < alpha."""
    for fam in FAMILIES:
        fr = [r for r in rows if r["family"] == fam and r.get("status") == "tested" and r.get("p") is not None]
        adj = S6.holm_dict({r["id"]: r["p"] for r in fr})
        for r in fr:
            r["p_holm"] = adj[r["id"]]
    for r in rows:
        r.setdefault("p_holm", None)
        r["passed"] = bool(r["family"] in FAMILIES and r.get("status") == "tested" and r.get("effect_ok")
                           and all((r.get("checks") or {}).values()) and r["p_holm"] is not None and r["p_holm"] < P.ALPHA)
        r["stage"] = stage


def _run_rows(segment: str, only: set[str] | None, draws: int, log) -> list[dict]:
    from app.gold_research.exp7 import filters, rules, timing

    rows = timing.run_all(segment, draws, only=only, log=log, level_draws=P.CONTROLS["level_draws"])
    rows += filters.run(segment, draws, only=only, log=log)
    rows += rules.run(segment, draws, only=only, log=log)
    rows += timing.run_astro(segment, draws, only=only, log=log)
    return rows


def develop(log=print, draws: int | None = None) -> dict:
    require_committed(PREREG)
    pre = json.loads(PREREG.read_text())
    rows = _run_rows("train", None, draws or pre["draws"], log)
    gate(rows, "development")
    out = {"experiment": 7, "stage": "development", "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "preregistration_sha256": pre["sha256"], "rows": rows,
           "candidates": [r["id"] for r in rows if r["passed"]]}
    out["sha256"] = _sha(out)
    write_once(DEV, out)
    log(f"development: {len(rows)} rows, {len(out['candidates'])} candidates")
    return out


def confirm(log=print, draws: int | None = None) -> dict:
    guard_once(CONF)
    require_committed(DEV)
    dev = json.loads(DEV.read_text())
    pre = json.loads(PREREG.read_text())
    carried = set(dev["candidates"])
    out = {"experiment": 7, "stage": "confirmation", "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "development_sha256": dev["sha256"]}
    if not carried:
        out |= {"status": "not run: no candidate passed development", "rows": []}
    else:
        rows = _run_rows("validation", carried, draws or pre["draws"], log)
        gate(rows, "confirmation")
        out |= {"status": "run once", "rows": rows, "passed": [r["id"] for r in rows if r["passed"]]}
    out["sha256"] = _sha(out)
    write_once(CONF, out)
    log(f"confirmation: {out['status']}")
    return out
