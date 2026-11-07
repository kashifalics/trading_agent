"""Measured track record of the signal engine, written by `python -m app.research.run_signal_track_record export`.

A win probability is exposed ONLY when the rules for that instrument x timeframe passed out-of-sample validation (`validated`) and
the plan's score band has >= MIN_BUCKET out-of-sample trades; it is then the observed out-of-sample TP1 hit rate of that band.
"""
import json
from pathlib import Path

TRACK_PATH = Path(__file__).resolve().parents[1] / "data" / "signal_track_record.json"
MIN_BUCKET = 100
_cache: dict = {"key": None, "data": None}


def load(path: Path | None = None) -> dict:
    p = path or TRACK_PATH
    if not p.exists():
        return {"meta": {}, "results": {}}
    key = (str(p), p.stat().st_mtime)
    if _cache["key"] != key:
        _cache.update(key=key, data=json.loads(p.read_text(encoding="utf8")))
    return _cache["data"]


def bucket_of(score: int | None) -> str | None:
    if score is None or score < 60:
        return None
    return "60-69" if score < 70 else "70-79" if score < 80 else "80-100"


def lookup(symbol: str, tf: str, score: int | None = None, path: Path | None = None) -> dict:
    r = load(path).get("results", {}).get(symbol, {}).get(tf)
    if not r:
        return {"available": False, "status": "untested", "win_probability": None,
                "summary": f"No historical replay of these rules exists for {symbol} {tf} yet"}
    oos = r.get("oos") or {}
    out = {"available": True, "status": r["status"], "summary": r["summary"], "period": r.get("period"),
           "oos": {k: oos.get(k) for k in ("n_trades", "tp1_hit_rate", "expectancy_r", "profit_factor", "expectancy_r_ci_low",
                                            "expectancy_r_ci_high")},
           "buckets": r.get("oos_buckets"), "win_probability": None}
    b = bucket_of(score)
    band = (r.get("oos_buckets") or {}).get(b) if b else None
    if r["status"] == "validated" and band and band.get("n", 0) >= MIN_BUCKET:
        out["win_probability"] = band.get("tp1_hit_rate")
        out["win_probability_basis"] = f"out-of-sample TP1 hit rate of {band['n']} past signals scoring {b}"
    return out
