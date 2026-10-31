"""Re-run a stored experiment and compare. Usage: python -m app.research.reproduce <experiment_id>"""
import math
import sys

from app.database.init_db import init_db
from app.database.models import Experiment
from app.database.session import session_scope
from app.research.experiments import code_version
from app.research.ml_eval import run_ml_experiment
from app.research.strategy_eval import run_backtest_experiment

IGNORE = {"trades_compact", "folds", "calibration", "by_regime", "config", "baselines"}


def _flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        if k in IGNORE and prefix == "":
            continue
        if isinstance(v, dict):
            out.update(_flatten(v, f"{prefix}{k}."))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[f"{prefix}{k}"] = float(v)
    return out


def compare(old: dict, new: dict, rel: float = 1e-9) -> list[str]:
    a, b = _flatten(old), _flatten(new)
    diffs = [f"{k}: stored={a[k]!r} rerun={b.get(k)!r}" for k in a
             if k not in b or not math.isclose(a[k], b[k], rel_tol=rel, abs_tol=1e-12)]
    return diffs


def reproduce(experiment_id: int) -> dict:
    with session_scope() as s:
        e = s.get(Experiment, experiment_id)
        if e is None:
            raise SystemExit(f"experiment {experiment_id} not found")
        spec = e.config["spec"]
        stored, ds, kind, name, ver = e.results, e.dataset, e.kind, e.name, e.code_version
        if kind == "backtest":
            new, snap = run_backtest_experiment(s, spec)
        elif kind == "ml":
            new, snap = run_ml_experiment(s, spec)
        else:
            raise SystemExit(f"reproduce supports backtest and ml experiments, not '{kind}'")
    cur = code_version()
    diffs = compare(stored, new)
    return {"experiment": experiment_id, "name": name, "snapshot_id": snap["snapshot_id"],
            "snapshot_matches": snap["snapshot_id"] == ds["snapshot_id"],
            "code_hash_matches": cur["source_sha256"] == ver["source_sha256"],
            "numeric_fields_compared": len(_flatten(stored)), "differences": diffs, "reproduced": not diffs}


if __name__ == "__main__":
    init_db()
    r = reproduce(int(sys.argv[1]))
    print(r)
    sys.exit(0 if r["reproduced"] else 1)
