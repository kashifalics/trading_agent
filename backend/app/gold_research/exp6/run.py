"""Experiment 6: do VSA and indicator confirmations improve the six strategies? (docs/engine_v2/EXPERIMENT_6_PLAN.md)

    python -m app.gold_research.exp6 rescore --symbol XAUUSD   verdicts per signal (no outcome)
    python -m app.gold_research.exp6 prereg                    counts only -> docs/research/EXP6_preregistration.json (commit it)
    python -m app.gold_research.exp6 develop                   development outcomes; refuses without the committed pre-registration
    python -m app.gold_research.exp6 confirm                   the confirmation segment, ONCE, only for arms that passed development
    python -m app.gold_research.exp6 report                    docs/reports/EXPERIMENT6_CONFIRMATIONS.md

An arm keeps a trade only when its category (or every category of the strategy's combination) is PASS; NEUTRAL, FAIL and UNAVAILABLE
are dropped. Every arm reuses the Experiment 5 baseline trades, so execution is identical by construction. Thresholds come from
config (fixed before any outcome); nothing is tuned. The sealed final-test periods are never read.
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl

from app.gold_research.exp5 import run as R5
from app.gold_research.exp6 import stats as S
from app.gold_research.exp6.rescore import tested_cells
from app.historical.config import REPO_ROOT
from app.historical.split import SPLIT_DIR, load_split
from app.strategy_engine.config import COMBOS, CONFIRM, VOLUME_RULES, VSA_T

SYMBOLS = ("XAUUSD", "BTCUSDT")
CATS = ("vsa", "momentum", "trend", "volatility")
ARMS = (*CATS, "combo")
MIN_KEPT, MIN_DROP_SHARE = 300, 0.10
DRAWS, ALPHA, YEAR_SHARE, MIN_YEAR_TRADES = 20_000, 0.05, 0.60, 20
WEEK = 7 * 86400
PREREG = SPLIT_DIR / "EXP6_preregistration.json"
DEV = SPLIT_DIR / "EXP6_development.json"
CONF = SPLIT_DIR / "EXP6_confirmation.json"
PLAN = REPO_ROOT / "docs" / "engine_v2" / "EXPERIMENT_6_PLAN.md"


def out_dir(symbol: str) -> Path:
    return R5.out_dir(symbol).parent / "exp6"


def _sha(doc: dict) -> str:
    return R5._sha(doc)


# ---- arms and counts ------------------------------------------------------------------------------------------------------------------
def with_combo(f: pl.DataFrame) -> pl.DataFrame:
    """combo = PASS only when every category of the row's strategy combination is PASS (UNAVAILABLE never passes)."""
    expr = pl.lit("FAIL")
    for strat, cats in COMBOS.items():
        ok = pl.all_horizontal([pl.col(c) == "PASS" for c in cats])
        expr = pl.when((pl.col("strategy") == strat) & ok).then(pl.lit("PASS")).otherwise(expr)
    return f.with_columns(combo=expr)


def arm_counts(f: pl.DataFrame, train_end: int) -> list[dict]:
    """Development SIGNALS kept and dropped per symbol, strategy and arm, and whether the arm enters the test family (counts only)."""
    f = with_combo(f) if "combo" not in f.columns else f
    dev = f.filter(pl.col("compatible") & pl.col("tested") & (pl.col("signal_ts") < train_end))
    rows = []
    for (sym, strat), g in sorted(dev.group_by(["symbol", "strategy"]), key=lambda x: x[0]):
        for arm in ARMS:
            kept = int((g[arm] == "PASS").sum())
            n = g.height
            rows.append({"symbol": sym, "strategy": strat, "arm": arm, "signals": n, "kept": kept, "dropped": n - kept,
                         "in_family": bool(kept >= MIN_KEPT and (n - kept) >= MIN_DROP_SHARE * n)})
    return rows


# ---- integrity guards -------------------------------------------------------------------------------------------------------------
def write_once(path: Path, doc: dict) -> None:
    if path.exists():
        raise RuntimeError(f"{path.name} exists: a frozen Experiment 6 file is never overwritten")
    path.write_text(json.dumps(doc, indent=1, default=float), encoding="utf8")


def require_committed(path: Path) -> None:
    try:
        rel = str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        raise RuntimeError(f"{path.name} must be committed before outcomes are computed (it is outside the repository)") from None
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=REPO_ROOT, capture_output=True).returncode == 0
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=REPO_ROOT, capture_output=True).returncode == 0
    if not (tracked and clean):
        raise RuntimeError(f"{path.name} must be committed (unchanged) before outcomes are computed")


def guard_once(path: Path) -> None:
    if path.exists():
        raise RuntimeError(f"the Experiment 6 confirmation runs once: {path.name} exists")


# ---- one arm --------------------------------------------------------------------------------------------------------------------------
def _year(ts: np.ndarray) -> np.ndarray:
    return ts.astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970


def _pf_sharpe(m: dict) -> tuple[float, float]:
    return (m.get("profit_factor") or 0.0), (m.get("sharpe_per_trade") or -np.inf)


def evaluate_arm(r: np.ndarray, keep: np.ndarray, *, strata: np.ndarray, ts: np.ndarray, spread_r: np.ndarray, stopped: np.ndarray,
                 r_fee: np.ndarray | None = None, draws: int = DRAWS, seed: int = 6) -> dict:
    """Kept vs dropped vs baseline for one arm, the random-filter p and the development checks (Holm is applied across the family)."""
    r, keep, ts, spread_r, stopped = (np.asarray(x) for x in (r, keep, ts, spread_r, stopped))
    keep = keep.astype(bool)
    base, kept, drop = R5.metrics(r, ts, spread_r), R5.metrics(r[keep], ts[keep], spread_r[keep]), R5.metrics(r[~keep], ts[~keep], spread_r[~keep])
    imp = (kept.get("expectancy_r", np.nan) - base.get("expectancy_r", np.nan)) if keep.any() else float("nan")
    p = S.random_filter_p(r, keep, strata, draws, seed)
    wk = ts // WEEK
    ci = S.cluster_ci(r[keep], wk[keep], r[~keep], wk[~keep]) if keep.any() and (~keep).any() else (float("nan"), float("nan"))
    yrs = _year(ts)
    by_year = {}
    for y in np.unique(yrs):
        m = yrs == y
        if (keep & m).sum() >= MIN_YEAR_TRADES:
            by_year[int(y)] = float(r[keep & m].mean() - r[m].mean())
    pos_years = sum(v > 0 for v in by_year.values()) / len(by_year) if by_year else 0.0
    r2 = r - spread_r
    imp_2x = float(r2[keep].mean() - r2.mean()) if keep.any() else float("nan")
    imp_fee = float(r_fee[keep].mean() - r_fee.mean()) if r_fee is not None and keep.any() else None
    (pf_k, sh_k), (pf_b, sh_b) = _pf_sharpe(kept), _pf_sharpe(base)
    fe = {"stop_share_kept": float(stopped[keep].mean()) if keep.any() else None,
          "stop_share_dropped": float(stopped[~keep].mean()) if (~keep).any() else None}
    checks = {"kept_beats_baseline": bool(np.isfinite(imp) and imp > 0), "pf_sharpe_not_worse": bool(pf_k >= pf_b and sh_k >= sh_b),
              "positive_years_60pct": bool(pos_years >= YEAR_SHARE), "positive_at_2x_costs": bool(np.isfinite(imp_2x) and imp_2x > 0),
              "at_least_300_trades": bool(keep.sum() >= MIN_KEPT)}
    return {"kept": kept, "dropped": drop, "baseline": base, "improvement_r": imp, "improvement_r_2x_costs": imp_2x,
            "improvement_r_fee": imp_fee, "p_random": p, "ci_kept_minus_dropped": list(ci), "improvement_by_year": by_year,
            "positive_year_share": pos_years, "false_entry": fe, "checks": checks}


# ---- loading the baseline trades with their verdicts ---------------------------------------------------------------------------------
def _verdicts(symbol: str) -> pl.DataFrame:
    parts = [pl.read_parquet(p) for p in sorted(out_dir(symbol).glob("verdicts_*.parquet"))]
    if not parts:
        raise RuntimeError(f"{symbol}: no verdict files (run: rescore --symbol {symbol})")
    return with_combo(pl.concat(parts))


def _trades(symbol: str, segment: str, strategies: set[str]) -> pl.DataFrame:
    parts = []
    for tf in R5.TFS:
        p = R5.out_dir(symbol) / f"trades_{tf}_{segment}.parquet"
        if not p.exists():
            continue
        tr = pl.read_parquet(p).filter(pl.col("compatible") & pl.col("strategy").is_in(list(strategies)))
        cells = tested_cells(symbol, tf)
        tr = tr.filter(pl.Series([(s, int(d)) in cells for s, d in zip(tr["strategy"].to_list(), tr["direction"].to_list())], dtype=pl.Boolean))
        if tr.height:
            parts.append(tr.with_columns(tf=pl.lit(tf), r=pl.Series(R5.r_of(tr)),
                                         stopped=(pl.col(f"mfe_{R5.HOLD}") < pl.col("k")) & pl.col(f"stopped_{R5.HOLD}")))
    return pl.concat(parts, how="diagonal") if parts else pl.DataFrame()


def _arm_rows(symbol: str, tr: pl.DataFrame, ver: pl.DataFrame, arms: list[dict], draws: int) -> list[dict]:
    j = tr.join(ver.select("tf", "idx", "strategy", "direction", *ARMS), on=["tf", "idx", "strategy", "direction"], how="inner")
    out = []
    for a in arms:
        g = j.filter(pl.col("strategy") == a["strategy"])
        if g.height == 0:
            out.append({**a, "trades": 0})
            continue
        r = g["r"].to_numpy()
        ts = g["entry_ts"].to_numpy().astype(np.int64)
        strata_key = (g["tf"] + "|" + g["direction"].cast(pl.Utf8) + "|" + pl.Series(_year(ts)).cast(pl.Utf8)).to_numpy()
        _, strata = np.unique(strata_key, return_inverse=True)
        spread_r = (g["spread_entry"] / g["risk_px"]).to_numpy()
        fee = S.cost_scenarios(r, g["spread_entry"].to_numpy(), g["risk_px"].to_numpy(), g["entry_px"].to_numpy())["r_fee"] \
            if symbol == "BTCUSDT" else None
        res = evaluate_arm(r, (g[a["arm"]] == "PASS").to_numpy(), strata=strata, ts=ts, spread_r=spread_r,
                           stopped=g["stopped"].to_numpy(), r_fee=fee, draws=draws)
        keep = (g[a["arm"]] == "PASS").to_numpy()
        res["by_regime"] = {k: {"kept": float(np.mean(r[keep & m])) if (keep & m).any() else None, "baseline": float(np.mean(r[m]))}
                            for k in g["regime"].unique().to_list() for m in [(g["regime"] == k).to_numpy()]}
        res["by_tf"] = {k: {"kept": float(np.mean(r[keep & m])) if (keep & m).any() else None, "baseline": float(np.mean(r[m])),
                            "kept_trades": int((keep & m).sum())} for k in g["tf"].unique().to_list() for m in [(g["tf"] == k).to_numpy()]}
        res["by_direction"] = {("long" if k > 0 else "short"): {"kept": float(np.mean(r[keep & m])) if (keep & m).any() else None,
                                                                 "baseline": float(np.mean(r[m]))}
                               for k in g["direction"].unique().to_list() for m in [(g["direction"] == k).to_numpy()]}
        out.append({**a, "trades": int(g.height), **res})
    return out


# ---- stages -----------------------------------------------------------------------------------------------------------------------------
def prereg(log=print) -> dict:
    if PREREG.exists():
        raise RuntimeError(f"{PREREG.name} exists: not overwritten")
    rows = []
    for sym in SYMBOLS:
        f = _verdicts(sym)
        train_end = int(datetime.fromisoformat(load_split(sym)["train"]["end_exclusive"]).timestamp())
        rows += arm_counts(f, train_end)
    family = [r for r in rows if r["in_family"]]
    prior = json.loads(R5.dev_path("XAUUSD").read_text())["trials_counted_for_deflated_sharpe"]
    btc_pre = R5.load_prereg("BTCUSDT")
    btc_cells = sum(1 for x in btc_pre["tests"] if x["status"] == "run")
    plan_commit = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(PLAN.relative_to(REPO_ROOT)).replace("\\", "/")],
                                 cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    thresholds = json.dumps({"CONFIRM": CONFIRM, "VSA_T": VSA_T, "COMBOS": COMBOS, "VOLUME_RULES": VOLUME_RULES}, sort_keys=True, default=str)
    doc = {"experiment": 6, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code_commit": R5._git_head(),
           "plan_commit": plan_commit, "thresholds_sha256": hashlib.sha256(thresholds.encode()).hexdigest(),
           "splits": {s: load_split(s)["sha256"] for s in SYMBOLS},
           "exp5_preregistrations": {s: R5.load_prereg(s)["sha256"] for s in SYMBOLS},
           "rule": f"an arm keeps a trade only on PASS; family = arms with >= {MIN_KEPT} kept development signals and >= "
                   f"{MIN_DROP_SHARE:.0%} dropped (counts only, before outcomes)",
           "test": f"random-filter p, {DRAWS:,} stratified draws (timeframe x direction x year); Holm across the family at {ALPHA}",
           "arms": rows, "family": [f"{r['symbol']}|{r['strategy']}|{r['arm']}" for r in family],
           "prior_trials": prior, "new_trials": {"btcusdt_baseline_cells": btc_cells, "experiment6_arms": len(family)},
           "total_trials": prior + btc_cells + len(family)}
    doc["sha256"] = _sha(doc)
    write_once(PREREG, doc)
    log(f"pre-registration: {len(rows)} arms, {len(family)} in the family; total trials {doc['total_trials']}")
    return doc


def _family(pre: dict) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = {}
    for key in pre["family"]:
        sym, strat, arm = key.split("|")
        by.setdefault(sym, []).append({"symbol": sym, "strategy": strat, "arm": arm})
    return by


def _gate(rows: list[dict], stage: str) -> None:
    ps = {f"{r['symbol']}|{r['strategy']}|{r['arm']}": r.get("p_random", 1.0) for r in rows if r.get("trades")}
    adj = S.holm_dict(ps)
    for r in rows:
        k = f"{r['symbol']}|{r['strategy']}|{r['arm']}"
        r["p_holm"] = adj.get(k)
        if stage == "development":
            r["passed"] = bool(r.get("trades") and all(r["checks"].values()) and r["p_holm"] is not None and r["p_holm"] < ALPHA)
        else:
            r["passed"] = bool(r.get("trades") and r["checks"]["kept_beats_baseline"] and r["checks"]["positive_at_2x_costs"]
                               and r["p_holm"] is not None and r["p_holm"] < ALPHA)
        r["promotable"] = bool(r["passed"] and not (r["symbol"] == "XAUUSD" and (r["arm"] == "vsa" or (r["arm"] == "combo"
                                                                                                      and "vsa" in COMBOS[r["strategy"]]))))


def develop(log=print, draws: int = DRAWS) -> dict:
    require_committed(PREREG)
    pre = json.loads(PREREG.read_text())
    rows = []
    for sym, arms in _family(pre).items():
        ver = _verdicts(sym)
        tr = _trades(sym, "train", {a["strategy"] for a in arms})
        if tr.height == 0:
            raise RuntimeError(f"{sym}: no Experiment 5 development trades (run: exp5 develop --symbol {sym})")
        rows += _arm_rows(sym, tr, ver, arms, draws)
        log(f"{sym}: {len(arms)} arms evaluated on {tr.height:,} baseline trades")
    _gate(rows, "development")
    out = {"experiment": 6, "stage": "development", "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "preregistration_sha256": pre["sha256"], "arms": rows, "passed": [f"{r['symbol']}|{r['strategy']}|{r['arm']}" for r in rows if r["passed"]]}
    out["sha256"] = _sha(out)
    write_once(DEV, out)
    log(f"development: {len(rows)} arms, {len(out['passed'])} passed")
    return out


def confirm(log=print, draws: int = DRAWS) -> dict:
    guard_once(CONF)
    require_committed(DEV)
    dev = json.loads(DEV.read_text())
    carried = [{"symbol": r["symbol"], "strategy": r["strategy"], "arm": r["arm"]} for r in dev["arms"] if r.get("passed")]
    out = {"experiment": 6, "stage": "confirmation", "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "development_sha256": dev["sha256"]}
    if not carried:
        out |= {"status": "not run: no arm passed development", "arms": []}
    else:
        rows = []
        for sym in sorted({a["symbol"] for a in carried}):
            arms = [a for a in carried if a["symbol"] == sym]
            strategies = {a["strategy"] for a in arms}
            v_start = int(datetime.fromisoformat(load_split(sym)["validation"]["start"]).timestamp())
            for tf in R5.TFS:
                p = R5.out_dir(sym) / f"events_{tf}.parquet"
                if p.exists():
                    ev = pl.read_parquet(p).filter((pl.col("signal_ts") >= v_start) & pl.col("strategy").is_in(list(strategies)))
                    if ev.height:
                        R5.simulate(sym, tf, "validation", ev, log)
            rows += _arm_rows(sym, _trades(sym, "validation", strategies), _verdicts(sym), arms, draws)
        _gate(rows, "confirmation")
        out |= {"status": "run once", "arms": rows, "passed": [f"{r['symbol']}|{r['strategy']}|{r['arm']}" for r in rows if r["passed"]]}
    out["sha256"] = _sha(out)
    write_once(CONF, out)
    log(f"confirmation: {out['status']}")
    return out
