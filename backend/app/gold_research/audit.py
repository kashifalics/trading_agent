"""Independent research audit of the gold pattern study (requested before the final test). Analysis only.

Reads ONLY training-period outputs (trades_*_train, pool_*_train, events_*_train, discovery_stage1.json) plus train+validation
candle data for the missing-data analysis. It never reads the sealed final-test period, never changes the split, never promotes.

    python -m app.gold_research audit      -> docs/reports/XAUUSD_RESEARCH_AUDIT.md and data/historical/research/XAUUSD/audit.json
"""
import json
import math
import re
from datetime import datetime, timezone
from itertools import combinations

import numpy as np
import polars as pl
from scipy import stats

from app.gold_research import combos, sim, study
from app.gold_research import stats as Stt
from app.gold_research.events import bars_from_frame
from app.historical.config import CLEAN, REPO_ROOT, TF_SECONDS
from app.historical.split import SPLIT_DIR, load_split
from app.historical.store import load_m1, load_tf

CANDIDATES = [("H1", "round50_reaction", "long"), ("M30", "displacement", "long"), ("M30", "bos+displacement", "long")]
PAIR_NAMES = {name: b for name, _a, b, _w in combos.PAIRS}
SPREAD_MULTS = (1.0, 1.25, 1.5)
SLIPPAGE = (0.0, 0.05, 0.10, 0.20)  # $ per side, on entry and exit


def parse_key(key: str) -> tuple[str, str, str, str, str | None]:
    """'tf|pattern|direction' (patterns may contain '|') -> (tf, pattern, direction, trigger, flag)."""
    parts = key.split("|")
    tf, direction, pattern = parts[0], parts[-1], "|".join(parts[1:-1])
    if pattern in PAIR_NAMES:
        return tf, pattern, direction, PAIR_NAMES[pattern], f"combo:{pattern}"
    if "|" in pattern:
        trig, prof = pattern.split("|", 1)
        return tf, pattern, direction, trig, f"mtf:{prof}"
    return tf, pattern, direction, pattern, None


def _year(ts: np.ndarray) -> np.ndarray:
    return ts.astype("datetime64[s]").astype("datetime64[Y]").astype(np.int64) + 1970


def select(prim: pl.DataFrame, trigger: str, direction: str, flag: str | None) -> pl.DataFrame:
    d = 1 if direction == "long" else -1
    g = prim.filter((pl.col("pattern") == trigger) & (pl.col("direction") == d))
    return g.filter(pl.col(flag)) if flag else g


# ------------------------------------------------------------------ 1. multiple testing and overfitting
def storey_pi0(p: np.ndarray, lam: float = 0.5) -> float:
    return float(min(1.0, (p > lam).sum() / ((1 - lam) * len(p))))


def deflated_sharpe(sr: float, n: int, skew: float, kurt: float, n_trials: int, null_var: float) -> dict:
    """Bailey and Lopez de Prado: probability that the true Sharpe exceeds the largest Sharpe that n_trials strategies with NO edge
    would show by luck. The variance of a zero-skill trial's Sharpe estimate is its sampling variance (about 1/T for T trades),
    averaged over the trials' sample sizes. (The cross-sectional variance of the trials' Sharpes is not used: here the trials differ
    systematically because of costs, which would inflate the benchmark.)"""
    N = n_trials
    v = null_var
    g = 0.5772156649
    sr0 = math.sqrt(v) * ((1 - g) * stats.norm.ppf(1 - 1 / N) + g * stats.norm.ppf(1 - 1 / (N * math.e)))
    den = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    z = (sr - sr0) * math.sqrt(max(n - 1, 1)) / den
    return {"sharpe_per_trade": sr, "expected_max_sharpe_of_trials": sr0, "trials": N, "observations": n,
            "deflated_sharpe_probability": float(stats.norm.cdf(z))}


def cscv_pbo(sums: np.ndarray, counts: np.ndarray, min_blocks: int = 12) -> dict:
    """Probability of backtest overfitting by combinatorially symmetric cross-validation (Bailey et al.).
    sums / counts: (blocks x strategies) per-block totals. Every split of the S blocks into two halves; the strategy that is best
    in one half is ranked in the other; PBO = share of splits where it lands in the bottom half."""
    S, N = sums.shape
    keep = (counts > 0).sum(0) >= min_blocks
    sums, counts = sums[:, keep], counts[:, keep]
    idx = list(combinations(range(S), S // 2))
    M = np.zeros((len(idx), S))
    for i, c in enumerate(idx):
        M[i, list(c)] = 1.0
    with np.errstate(invalid="ignore", divide="ignore"):
        is_perf = (M @ sums) / (M @ counts)
        oos_perf = ((1 - M) @ sums) / ((1 - M) @ counts)
    is_perf = np.where(np.isfinite(is_perf), is_perf, -np.inf)
    best = is_perf.argmax(1)
    rows = np.arange(len(idx))
    o = oos_perf[rows, best]
    valid = np.isfinite(oos_perf)
    below = (np.where(valid, oos_perf, np.inf) < o[:, None]).sum(1)
    ties = (np.where(valid, oos_perf, np.nan) == o[:, None]).sum(1)
    omega = (below + 0.5 * ties) / valid.sum(1)
    omega = np.clip(omega, 1e-6, 1 - 1e-6)
    lam = np.log(omega / (1 - omega))
    return {"splits": len(idx), "blocks": S, "strategies": int(keep.sum()), "pbo": float((lam <= 0).mean()),
            "median_logit": float(np.median(lam)), "selected_is_mean": float(np.mean(is_perf[rows, best])),
            "selected_oos_mean": float(np.nanmean(o)), "prob_selected_oos_below_zero": float(np.nanmean(o < 0))}


# ------------------------------------------------------------------ helpers on candidate trades
def cost_stress(g: pl.DataFrame) -> list[dict]:
    r, risk, spread = g["r"].to_numpy(), g["risk_px"].to_numpy(), g["spread_entry"].to_numpy().astype(float)
    cl = Stt.cluster_ids(g["entry_ts"].to_numpy(), study.PRIMARY_HOLD * TF_SECONDS[g["_tf"][0]])
    out = []
    for m in SPREAD_MULTS:
        for s in SLIPPAGE:
            adj = r - (m - 1.0) * spread / risk - 2 * s / risk
            ok = np.isfinite(adj)
            st = Stt.clustered_mean(adj[ok], cl[ok])
            pos, neg = adj[ok][adj[ok] > 0].sum(), -adj[ok][adj[ok] < 0].sum()
            out.append({"spread_x": m, "slippage_per_side": s, "n": st["n"], "mean_r": st["mean"], "se": st["se"],
                        "ci_low": st["mean"] - 1.96 * st["se"], "ci_high": st["mean"] + 1.96 * st["se"], "p_positive": st["p"],
                        "win_rate": float((adj[ok] > 0).mean()), "profit_factor": float(pos / neg) if neg > 0 else None})
    ok = np.isfinite(r)
    breakeven = float(np.mean(r[ok]) / np.mean(1 / risk[ok]))  # extra round-trip $ per trade that brings the mean to zero
    out.append({"breakeven_extra_cost_usd_round_trip": breakeven, "median_spread_usd": float(np.median(spread[ok])),
                "median_risk_usd": float(np.median(risk[ok]))})
    return out


def breakdown(g: pl.DataFrame, col: str, tf: str) -> list[dict]:
    rows = []
    for (k,), x in g.group_by([col], maintain_order=True):
        e = study._edge(x, tf, study.PRIMARY_HOLD)
        rows.append({col: str(k), "n": e.get("n", 0), "win_rate": e.get("win_rate"), "mean_r": e.get("mean_r"), "edge": e.get("edge"),
                     "edge_se": e.get("edge_se")})
    return sorted(rows, key=lambda r: r[col])


def sell_mirror(symbol: str, tf: str, g: pl.DataFrame) -> dict:
    """Same signals, traded SHORT: entry at the next open (bid), stop the same distance above, 2R target, 48 candles."""
    df = load_tf(symbol, tf, upto="train")
    S = sim.Series.from_frame(df, tf, load_m1(symbol, upto="train"))
    b = bars_from_frame(df.sort("ts"), TF_SECONDS[tf])
    from app.feature_engineering.indicators import atr as atr_fn
    a = atr_fn(b.h, b.l, b.c, 14)
    idx = g["idx"].to_numpy()
    eb = idx + 1
    px = S.bo[np.clip(eb, 0, S.n - 1)]
    risk = g["risk_px"].to_numpy()
    res = sim.simulate(S, sim.Orders(d=np.full(len(idx), -1), entry_bar=np.where(eb < S.n, eb, -1), stop=px + risk, atr=a[idx]))
    r = sim.r_multiple(res, study.PRIMARY_TARGET, study.PRIMARY_HOLD)
    ok = np.isfinite(r)
    ts = np.where(res["fill_ts"] > 0, res["fill_ts"], S.t[idx])
    st = Stt.clustered_mean(r[ok], Stt.cluster_ids(ts[ok], study.PRIMARY_HOLD * TF_SECONDS[tf]))
    return {"n": st["n"], "mean_r": st["mean"], "se": st["se"], "win_rate": float((r[ok] > 0).mean()) if ok.any() else None}


def realism(g: pl.DataFrame, tf: str, row: dict) -> dict:
    risk = g["risk_px"].to_numpy()
    spread = g["spread_entry"].to_numpy().astype(float)
    r = g["r"].to_numpy()
    ts = g["entry_ts"].to_numpy()
    sr = g["stop_r"].to_numpy()
    hold_s = study.PRIMARY_HOLD * TF_SECONDS[tf]
    order = np.argsort(ts)
    starts, ends = ts[order], ts[order] + hold_s
    conc = np.searchsorted(starts, starts, side="right") - np.searchsorted(ends, starts, side="right")
    roll = (g["session"] == "rollover").to_numpy()
    return {
        "entry": "next candle open after the signal candle closes (ask for longs); 1-candle-late edge in training "
                 f"{row['late'].get('edge', float('nan')):+.3f}R (n={row['late'].get('n', 0):,})",
        "stop": "signal candle low - 0.1 ATR (at least 0.25 ATR from entry), exit at bid; stop minute that opens beyond the stop "
                "fills at that open",
        "target": "2R limit at the bid; touch fills (no queue modelling)",
        "risk_usd_median": float(np.median(risk)), "risk_usd_p5": float(np.percentile(risk, 5)),
        "risk_atr_median": float(np.median(g["risk_atr"].to_numpy())),
        "share_risk_below_0_50_usd": float((risk < 0.5).mean()), "share_risk_below_1_usd": float((risk < 1.0).mean()),
        "spread_over_risk_median": float(np.median(spread / risk)), "spread_over_risk_p95": float(np.percentile(spread / risk, 95)),
        "share_gap_through_stop": float(np.nanmean(sr < -1.0001)), "worst_stop_r": float(np.nanmin(sr)),
        "intrabar_optimistic_share_changed": row.get("optimistic_share_changed"),
        "share_entries_in_rollover": float(roll.mean()),
        "rollover_mean_r": float(np.nanmean(r[roll])) if roll.any() else None,
        "max_concurrent_positions": int(conc.max()) if len(conc) else 0, "median_concurrent_positions": float(np.median(conc)) if len(conc) else 0,
        "stopped_within": {h: float(g[f"stopped_{h}"].mean()) for h in sim.HOLDS if f"stopped_{h}" in g.columns},
    }


# ------------------------------------------------------------------ 3. missing data
def missing_data(symbol: str, log=print) -> dict:
    """Missing scheduled minutes in TRAINING and VALIDATION only (the sealed period is not looked at)."""
    from app.gold_research import regimes
    from app.historical.build import open_minutes
    sp = load_split(symbol)
    v_end = datetime.fromisoformat(sp["validation"]["end_exclusive"])
    first = datetime.fromisoformat(sp["train"]["start"])
    gaps = pl.read_parquet(CLEAN / symbol / "gaps.parquet").filter(pl.col("start") < v_end)
    mins = gaps.with_columns(pl.int_ranges(0, pl.col("minutes")).alias("k")).explode("k").with_columns(
        (pl.col("start") + pl.duration(minutes=pl.col("k"))).alias("ts")).filter((pl.col("ts") >= first) & (pl.col("ts") < v_end)).select(
        "ts", "holiday", "material")  # from the first traded minute: earlier months are feed filler, not missing trading
    sched = open_minutes(first, v_end, symbol)
    h1 = load_tf(symbol, "H1", upto="validation")
    b = bars_from_frame(h1, 3600)
    from app.feature_engineering.indicators import atr as atr_fn
    a = atr_fn(b.h, b.l, b.c, 14)
    from app.market_structure.bos import detect_structure_breaks
    from app.market_structure.swings import find_swings
    reg = regimes.compute(b.t, b.o, b.h, b.l, b.c, a, detect_structure_breaks(b, find_swings(b))[1])
    hour = pl.DataFrame({"h": b.t + 3600, "vol_level": np.asarray(reg["vol_level"]),  # known once the H1 candle has closed
                         "trend_regime": np.asarray(reg["trend_regime"])}).sort("h")

    def label(df: pl.DataFrame) -> pl.DataFrame:
        ny = pl.col("ts").dt.convert_time_zone("America/New_York")
        return df.with_columns(year=pl.col("ts").dt.year(), session=ny.dt.hour(), weekday=ny.dt.weekday(),
                               h=pl.col("ts").dt.epoch("s")).sort("h").join_asof(hour, on="h", strategy="backward").with_columns(
            session=pl.when((pl.col("session") >= 3) & (pl.col("session") < 8)).then(pl.lit("london"))
            .when((pl.col("session") >= 8) & (pl.col("session") < 12)).then(pl.lit("overlap"))
            .when((pl.col("session") >= 12) & (pl.col("session") < 17)).then(pl.lit("new_york"))
            .when((pl.col("session") >= 17) & (pl.col("session") < 19)).then(pl.lit("rollover")).otherwise(pl.lit("asia")),
            vol_level=pl.col("vol_level").fill_null("unknown"), trend_regime=pl.col("trend_regime").fill_null("unknown"))

    M, Sd = label(mins), label(sched)
    out = {"period": f"{first.date()} to {v_end.date()} (training + validation; the sealed final-test period is excluded)",
           "scheduled_minutes": Sd.height, "missing_minutes": M.height, "missing_share": M.height / max(Sd.height, 1),
           "material_missing_minutes": int(M["material"].sum()), "holiday_missing_minutes": int(M["holiday"].sum())}
    for col in ("year", "session", "weekday", "vol_level", "trend_regime"):
        a_ = M.group_by(col).len().rename({"len": "missing"})
        b_ = Sd.group_by(col).len().rename({"len": "scheduled"})
        j = b_.join(a_, on=col, how="left").with_columns(pl.col("missing").fill_null(0)).with_columns(
            share=pl.col("missing") / pl.col("scheduled")).sort(col)
        out[f"by_{col}"] = j.to_dicts()
    log("missing-data analysis done")
    return out


# ------------------------------------------------------------------ 6. leakage evidence
def leakage_evidence(symbol: str, frames: dict) -> dict:
    sp = load_split(symbol)
    t_end = int(datetime.fromisoformat(sp["train"]["end_exclusive"]).timestamp())
    o = study.out_dir(symbol)
    ev = {"train_end": sp["train"]["end_exclusive"], "timeframes": {}}
    for tf, tr in frames.items():
        e = tr["entry_ts"].to_numpy()
        ev["timeframes"][tf] = {"trades": tr.height, "last_entry": datetime.fromtimestamp(int(e.max()), timezone.utc).isoformat(),
                                "last_outcome_window_end": datetime.fromtimestamp(int(e.max() + sim.HMAX * TF_SECONDS[tf]), timezone.utc).isoformat(),
                                "outcome_windows_inside_training": bool(e.max() + sim.HMAX * TF_SECONDS[tf] <= t_end + 7 * 86400),
                                "segments_in_file": sorted(set(tr["segment"].to_list()))}
    files = sorted(p.name for p in o.glob("*"))
    ev["validation_or_test_outputs_present"] = [f for f in files if re.search(r"(validation|_test|final_test)", f)]
    ev["seal_log_exists"] = (SPLIT_DIR / f"{symbol}_seal_log.md").exists()
    disc = json.loads((o / "discovery_stage1.json").read_text())
    ev["stage1_generated"] = disc["generated"]
    ev["stage1_split_sha256_matches"] = disc["split_sha256"] == sp["sha256"]
    ev["ml_training_present"] = (o / "ml_training.json").exists()
    code = {}
    for p in sorted((REPO_ROOT / "backend" / "app" / "gold_research").glob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf8").splitlines(), 1):
            if re.search(r"load_(tf|m1)\(", line) and "def " not in line:
                code.setdefault(p.name, []).append(f"{i}: {line.strip()[:140]}")
    ev["loader_call_sites"] = code
    return ev


# ------------------------------------------------------------------ main
def run(symbol: str = "XAUUSD", log=print) -> dict:
    stage1 = json.loads((study.out_dir(symbol) / "discovery_stage1.json").read_text())
    frozen = json.loads(study.candidates_path(symbol, 1).read_text())
    keys = frozen["tested_keys"]
    rows1 = {f"{r['tf']}|{r['pattern']}|{r['direction']}": r for r in stage1["rows"]}
    tested = [rows1[k] for k in keys]
    p = np.array([r["primary"]["p_edge"] for r in tested])
    edges = np.array([r["primary"]["edge"] for r in tested])
    q = Stt.bh(p)
    pp = np.array([r["primary"]["p_profit"] for r in tested])
    pi0 = storey_pi0(p)
    t_star = float(p[q < study.FDR_Q].max()) if (q < study.FDR_Q).any() else 0.0
    R = int((q < study.FDR_Q).sum())
    mt = {"tests": len(p), "bh_q_lt_0_10": R, "bh_q_lt_0_05": int((q < 0.05).sum()), "bonferroni_0_05": int((p < 0.05 / len(p)).sum()),
          "holm_0_05": int((Stt.holm(p) < 0.05).sum()), "storey_pi0": pi0, "estimated_true_effects": (1 - pi0) * len(p),
          "estimated_fdr_at_candidate_threshold": float(min(1.0, pi0 * len(p) * t_star / max(R, 1))),
          "expected_false_candidates": float(min(R, pi0 * len(p) * t_star)), "share_positive_edge": float((edges > 0).mean()),
          "profit_tests_bh_q_lt_0_10": int((Stt.bh(pp) < 0.10).sum()), "profit_tests_nominal_p_lt_0_05": int((pp < 0.05).sum()),
          "expected_nominal_profit_hits_under_null": 0.05 * len(pp)}
    log(f"multiple testing: {mt}")
    by_tf: dict[str, list] = {}
    for k in keys:
        by_tf.setdefault(parse_key(k)[0], []).append(k)
    sp = load_split(symbol)
    years_all = np.arange(2003, int(sp["train"]["end_exclusive"][:4]) + 1)
    blocks = [list(years_all[:2])] + [[y] for y in years_all[2:-2]] + [list(years_all[-2:])]  # 16 blocks: 2003-04 ... 2019-20
    sums_e = np.zeros((len(blocks), len(keys)))
    sums_r = np.zeros((len(blocks), len(keys)))
    cnts = np.zeros((len(blocks), len(keys)))
    sharpe = np.full(len(keys), np.nan)
    col_of = {k: i for i, k in enumerate(keys)}
    repro, cand, frames_meta = [], {}, {}
    for tf, (tr, pool) in study.load_frames(symbol, sorted(by_tf), "train", log):
        log(f"{tf}: matching controls for {tr.height:,} trades")
        prim = study._with_ctrl(tr, pool, study.PRIMARY_TARGET, study.PRIMARY_HOLD)
        extra = tr.select("idx", "risk_atr", "stop_r", *[f"stopped_{h}" for h in sim.HOLDS])
        prim = pl.concat([prim, extra], how="horizontal").with_columns(_tf=pl.lit(tf), year=pl.Series(_year(prim["entry_ts"].to_numpy())))
        frames_meta[tf] = prim.select("entry_ts", "segment")
        for k in by_tf[tf]:
            _, pat, dirn, trig, flag = parse_key(k)
            g = select(prim, trig, dirn, flag)
            if g.height == 0:
                continue
            e = study._edge(g, tf, study.PRIMARY_HOLD)
            old = rows1[k]["primary"]
            if rows1[k]["status"] == "candidate":
                repro.append({"key": k, "n_then": old["n"], "n_now": e.get("n"), "edge_then": old["edge"], "edge_now": e.get("edge"),
                              "mean_r_then": old["mean_r"], "mean_r_now": e.get("mean_r")})
            r = g["r"].to_numpy()
            dlt = r - g["ctrl_mean"].to_numpy()
            ok = np.isfinite(r) & np.isfinite(dlt)
            yrs = g["year"].to_numpy()
            j = col_of[k]
            for bi, bl in enumerate(blocks):
                m = ok & np.isin(yrs, bl)
                sums_e[bi, j], sums_r[bi, j], cnts[bi, j] = dlt[m].sum(), r[m].sum(), m.sum()
            if ok.sum() > 2:
                sharpe[j] = r[ok].mean() / r[ok].std(ddof=1)
            if (tf, pat, dirn) in CANDIDATES:
                cand[(tf, pat, dirn)] = g
        del prim
    pbo = {"edge": cscv_pbo(sums_e, cnts), "mean_r": cscv_pbo(sums_r, cnts)}
    counts_per_test = np.array([rows1[k]["primary"]["n"] for k in keys], dtype=float)
    clusters_per_test = np.array([rows1[k]["primary"].get("clusters") or rows1[k]["primary"]["n"] for k in keys], dtype=float)
    log(f"PBO: {pbo}")
    out_c = []
    for tf, pat, dirn in CANDIDATES:
        g = cand[(tf, pat, dirn)]
        row = rows1[f"{tf}|{pat}|{dirn}"]
        r = g["r"].to_numpy()
        ok = np.isfinite(r)
        null_var = float(np.mean(1.0 / np.maximum(counts_per_test, 2)))
        null_var_cl = float(np.mean(1.0 / np.maximum(clusters_per_test, 2)))
        sr_ = float(r[ok].mean() / r[ok].std(ddof=1))
        sk, ku = float(stats.skew(r[ok])), float(stats.kurtosis(r[ok], fisher=False))
        dsr = deflated_sharpe(sr_, int(ok.sum()), sk, ku, len(keys), null_var)
        dsr_clusters = deflated_sharpe(sr_, row["primary"]["clusters"], sk, ku, len(keys), null_var_cl)
        opp = rows1.get(f"{tf}|{pat}|{'short' if dirn == 'long' else 'long'}", {}).get("primary", {})
        pool = pl.read_parquet(study.out_dir(symbol) / f"pool_{tf}_train.parquet")
        pr = pool.filter(pl.col("entry") == "market").with_columns(r=pl.Series(study._r(pool.filter(pl.col("entry") == "market"),
                                                                                         study.PRIMARY_TARGET, study.PRIMARY_HOLD)))
        rb = int(np.median(g["risk_b"].to_numpy()))
        drift = (pr.filter(pl.col("risk_b") == rb).with_columns(year=pl.col("period").str.slice(0, 4))
                 .group_by(["year", "direction"]).agg(pl.col("r").mean().alias("mean_r"), pl.len().alias("n")).sort(["year", "direction"]))
        dw = drift.pivot(on="direction", index="year", values="mean_r").rename({"1": "random_long", "-1": "random_short"}).sort("year")
        d1 = load_tf(symbol, "D1", upto="train").with_columns(year=pl.col("ts").dt.year()).group_by("year").agg(
            (pl.col("bid_close").last() / pl.col("bid_open").first() - 1).alias("gold_year_return")).sort("year")
        yr = pl.DataFrame(breakdown(g, "year", tf)).with_columns(pl.col("year").cast(pl.Int32))
        yr = yr.join(d1.with_columns(pl.col("year").cast(pl.Int32)), on="year", how="left")
        down = yr.filter(pl.col("gold_year_return") < 0)
        ent = {
            "candidate": f"{tf} {pat} {dirn}", "training": row["primary"], "late": row["late"],
            "deflated_sharpe_per_trade_obs": dsr, "deflated_sharpe_cluster_obs": dsr_clusters,
            "stress": cost_stress(g), "realism": realism(g, tf, row),
            "drift": {"matched_long_control_mean_r": row["primary"]["ctrl_mean_r"],
                      "edge_over_matched_long_controls": row["primary"]["edge"],
                      "opposite_direction_pattern": {k: opp.get(k) for k in ("n", "mean_r", "edge", "edge_se")} if opp else None,
                      "same_signals_traded_short": sell_mirror(symbol, tf, g),
                      "random_long_vs_short_by_year": dw.to_dicts(),
                      "down_years": down.to_dicts()},
            "stability": {"year": yr.to_dicts(), "years_positive": int((yr["mean_r"] > 0).sum()), "years": yr.height,
                          "session": breakdown(g, "session", tf), "vol_level": breakdown(g, "vol_level", tf),
                          "trend_regime": breakdown(g, "trend_regime", tf), "structural_regime": breakdown(g, "structural_regime", tf)},
        }
        out_c.append(ent)
        log(f"candidate {ent['candidate']} audited")
    trades_by_tf = {tf: m for tf, m in frames_meta.items()}
    res = {"symbol": symbol, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "scope": "training period only (2003-05-05 to 2020-02-08); validation not yet run; final test sealed and not read",
           "multiple_testing": mt, "pbo": pbo, "pbo_blocks": [f"{b[0]}-{b[-1]}" if len(b) > 1 else str(b[0]) for b in blocks],
           "reproducibility": repro, "candidates": out_c, "missing_data": missing_data(symbol, log),
           "leakage": leakage_evidence(symbol, trades_by_tf)}
    (study.out_dir(symbol) / "audit.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf8")
    from app.gold_research.audit_report import render
    doc = REPO_ROOT / "docs" / "reports" / f"{symbol}_RESEARCH_AUDIT.md"
    doc.write_text(render(res), encoding="utf8")
    log(f"audit written: {doc}")
    return res
