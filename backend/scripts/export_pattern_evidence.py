"""Export the latest stored pattern studies to backend/app/data/pattern_evidence.json (what /patterns/scan serves).

Run from backend/ with DATABASE_URL pointing at the research database:
    python scripts/export_pattern_evidence.py
Only measured numbers are exported; every entry carries its experiment id and dataset snapshot ids."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

from sqlalchemy import select  # noqa: E402

from app.database.models import Experiment  # noqa: E402
from app.database.session import session_scope  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "pattern_evidence.json"


def compact(r: dict) -> dict:
    i, o = r["is"] or {}, r["oos"] or {}
    rnd = lambda v: None if v is None else round(float(v), 4)  # noqa: E731
    return {"i_n": i.get("n"), "i_lift": rnd(i.get("lift_r")), "o_n": o.get("n"), "o_win": rnd(o.get("win_rate")),
            "o_gross": rnd(o.get("gross_r")), "o_net": rnd(o.get("net_r")), "o_lift": rnd(o.get("lift_r")),
            "o_holm": rnd(r.get("oos_holm_p")), "cand": bool(r.get("candidate")), "cg": bool(r.get("confirmed_gross")),
            "cn": bool(r.get("confirmed_net"))}


def main() -> None:
    out = {"meta": {"generated_at": datetime.now(timezone.utc).isoformat(), "experiments": {}, "method": "docs/reports/PATTERN_EDGE_*.md"},
           "symbols": {}}
    with session_scope() as s:
        for sym in ("BTCUSDT", "XAUUSD"):
            e = s.scalars(select(Experiment).where(Experiment.name == f"patterns:{sym}").order_by(Experiment.id.desc()).limit(1)).first()
            if e is None:
                print(f"no study for {sym}")
                continue
            out["meta"]["experiments"][sym] = {"id": e.id, "summary": e.results["summary"], "cost_round_trip_frac": e.config["cost_round_trip_frac"],
                                               "snapshots": {tf: v["snapshot_id"] for tf, v in e.dataset["snapshots"].items()}}
            tfs: dict = {}
            for r in e.results["rows"]:
                tfs.setdefault(r["tf"], {})[f"{r['pattern']}:{r['side']}"] = compact(r)
            out["symbols"][sym] = tfs
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
