"""Experiment 7 filter track (spec 4.4): do Gann conditions at a trade's own signal candle improve the existing strategies?

Every arm reuses the Experiment 5 baseline trades (the set Experiment 6 used), so execution is identical by construction; an
arm only keeps or drops trades. The Gann state is read at the signal candle with the price known then: the limit price for
limit entries, the signal candle's close for market entries. Each arm is compared with Experiment 6's random filter keeping
the same share per timeframe x direction x year.
"""
from datetime import datetime

import numpy as np
import polars as pl

from app.gann import state as G
from app.gann.params import GannParams
from app.gold_research.exp5 import run as R5
from app.gold_research.exp6 import run as R6
from app.gold_research.exp6 import stats as S6
from app.gold_research.exp7 import params as P
from app.gold_research.exp7 import stats as S
from app.gold_research.exp7 import timing as T
from app.historical.split import load_split

ARMS = P.ARMS
STRATEGIES = ("breakout_retest", "momentum_continuation", "range_reversion", "sweep_reversal", "trend_pullback",
              "volatility_expansion")
TIME_CYCLES = ("t_cycle_bars", "t_cycle_days", "t_fraction", "t_anniversary", "t_sq9_time")
TIME_ANGLES = ("t_balance_swing", "t_balance_atr", "t_balance_fixed")
PRICE_FAMILY = {"division": "divisions", "twelfth": "divisions", "square9": "square9", "sq4": "square9",
                "angle_swing": "angles", "angle_atr": "angles", "symmetry": "symmetry"}


class LineIndex:
    """Fast lookup of the lines known at a candle (every LineSet is built per segment with shared x0/x1)."""

    def __init__(self, ls: S.LineSet):
        self.ls = ls
        if not len(ls.p0):
            self.x0 = self.x1 = self.off = np.array([], dtype=np.int64)
            self.order = np.array([], dtype=np.int64)
            return
        self.order = np.lexsort((ls.x1, ls.x0))
        x0, x1 = ls.x0[self.order], ls.x1[self.order]
        first = np.r_[True, (x0[1:] != x0[:-1]) | (x1[1:] != x1[:-1])]
        self.x0, self.x1 = x0[first], x1[first]
        self.off = np.r_[np.flatnonzero(first), len(x0)]

    def values_at(self, i: int) -> np.ndarray:
        if not len(self.x0):
            return np.array([])
        k = int(np.searchsorted(self.x0, i, side="right")) - 1  # segments of one LineSet never overlap
        if k < 0 or i >= self.x1[k]:
            return np.array([])
        j = self.order[self.off[k]:self.off[k + 1]]
        return self.ls.p0[j] + self.ls.slope[j] * (i - self.ls.aidx[j])


def support_ok(vals: np.ndarray, ref: float, d: int, tol: float) -> bool:
    """A level on the trade's supporting side within tolerance: at or below the entry for longs, at or above for shorts."""
    if not len(vals):
        return False
    return bool(np.any((vals <= ref) & (ref - vals <= tol))) if d > 0 else bool(np.any((vals >= ref) & (vals - ref <= tol)))


def gann_at_signals(symbol: str, tf: str, segment: str, trades: pl.DataFrame) -> pl.DataFrame:
    """Gann columns for each trade, at its signal candle `idx`, in the trades' order."""
    b = T._bars(symbol, tf, segment)
    p = GannParams()
    pn = G.panel(b, p, daily=tf == "D1")
    lines = T.line_sets(b, p)
    ix = {m: LineIndex(ls) for m, ls in lines.items()}
    atr = pn["atr"].to_numpy()
    tcols = {c: pn[c].to_numpy() for c in (*TIME_CYCLES, "t_seasonal", *TIME_ANGLES)}
    side_s, side_a = pn["side_swing"].to_numpy(), pn["side_atr"].to_numpy()
    out = {k: [] for k in ("t_cycle_bars", "t_balance_swing", "t_balance_atr", "side_swing", "side_atr", "div_ok", "sq9_ok",
                           "families", "ref_px")}
    limit = trades["limit"].to_numpy() if "limit" in trades.columns else np.full(trades.height, np.nan)
    modes = trades["entry_mode"].to_list() if "entry_mode" in trades.columns else ["market"] * trades.height
    for idx, d, lim, mode in zip(trades["idx"].to_list(), trades["direction"].to_list(), limit, modes):
        ref = float(lim) if mode == "limit" and lim is not None and np.isfinite(lim) else float(b.c[idx])
        tol = float(np.maximum(p.price_tol_atr * atr[idx], p.tick)) if np.isfinite(atr[idx]) else -np.inf
        vals = {m: x.values_at(idx) for m, x in ix.items()}
        fam = set()
        if any(tcols[c][idx] for c in TIME_CYCLES):
            fam.add("cycles")
        if tcols["t_seasonal"][idx]:
            fam.add("seasonal")
        if any(tcols[c][idx] for c in TIME_ANGLES):
            fam.add("angles")
        for m, v in vals.items():
            if len(v) and np.any(np.abs(v - ref) <= tol):
                fam.add(PRICE_FAMILY[m])
        out["t_cycle_bars"].append(bool(tcols["t_cycle_bars"][idx]))
        out["t_balance_swing"].append(bool(tcols["t_balance_swing"][idx]))
        out["t_balance_atr"].append(bool(tcols["t_balance_atr"][idx]))
        out["side_swing"].append(float(side_s[idx]))
        out["side_atr"].append(float(side_a[idx]))
        out["div_ok"].append(support_ok(vals.get("division", np.array([])), ref, int(d), tol))
        out["sq9_ok"].append(support_ok(vals.get("square9", np.array([])), ref, int(d), tol))
        out["families"].append(len(fam))
        out["ref_px"].append(ref)
    return pl.DataFrame(out)


def arm_keep(t: pl.DataFrame) -> dict[str, np.ndarray]:
    d = t["direction"].to_numpy()
    g = t["families"].to_numpy() >= 2
    return {"B": t["t_cycle_bars"].to_numpy().astype(bool), "C": t["div_ok"].to_numpy().astype(bool),
            "D-swing": t["t_balance_swing"].to_numpy().astype(bool), "D-atr": t["t_balance_atr"].to_numpy().astype(bool),
            "E-swing": t["side_swing"].to_numpy() == d, "E-atr": t["side_atr"].to_numpy() == d,
            "F": t["sq9_ok"].to_numpy().astype(bool), "G": g, "H": g & (t["vsa"] == "PASS").to_numpy(),
            "I": g & (t["trend"] == "PASS").to_numpy()}


def _ensure_validation_trades(symbol: str, log) -> None:
    """Confirmation only: simulate the confirmation-segment baseline trades of every strategy (Experiment 6 simulated two)."""
    v0 = int(datetime.fromisoformat(load_split(symbol)["validation"]["start"]).timestamp())
    for tf in R5.TFS:
        f = R5.out_dir(symbol) / f"trades_{tf}_validation.parquet"
        have = set(pl.read_parquet(f, columns=["strategy"])["strategy"].unique().to_list()) if f.exists() else set()
        if set(STRATEGIES) <= have:
            continue
        ev = pl.read_parquet(R5.out_dir(symbol) / f"events_{tf}.parquet").filter(pl.col("signal_ts") >= v0)
        if ev.height:
            R5.simulate(symbol, tf, "validation", ev, log)


def run(segment: str, draws: int, only: set | None = None, log=print) -> list[dict]:
    rows = []
    for sym in P.SYMBOLS:
        ids = {a: f"F|{sym}|{a}" for a in ARMS}
        if only is not None and not any(i in only for i in ids.values()):
            continue
        if segment == "validation":
            _ensure_validation_trades(sym, log)
        tr = R6._trades(sym, segment, set(STRATEGIES))
        ver = R6._verdicts(sym).select("tf", "idx", "strategy", "direction", "vsa", "trend")
        j = tr.join(ver, on=["tf", "idx", "strategy", "direction"], how="left").with_columns(
            pl.col("vsa").fill_null("UNAVAILABLE"), pl.col("trend").fill_null("UNAVAILABLE"))
        parts = []
        for tf in sorted(j["tf"].unique().to_list()):
            g = j.filter(pl.col("tf") == tf)
            parts.append(pl.concat([g, gann_at_signals(sym, tf, segment, g)], how="horizontal"))
            log(f"filters {sym} {tf}: Gann state at {g.height:,} signals")
        j = pl.concat(parts, how="vertical")
        keep = arm_keep(j)
        r = j["r"].to_numpy()
        ts = j["entry_ts"].dt.epoch("s").to_numpy().astype(np.int64) if j["entry_ts"].dtype != pl.Int64 else \
            j["entry_ts"].to_numpy().astype(np.int64)
        key = (j["tf"] + "|" + j["direction"].cast(pl.Utf8) + "|" + pl.Series(R6._year(ts)).cast(pl.Utf8)).to_numpy()
        _, strata = np.unique(key, return_inverse=True)
        spread_r = (j["spread_entry"] / j["risk_px"]).to_numpy()
        fee = S6.cost_scenarios(r, j["spread_entry"].to_numpy(), j["risk_px"].to_numpy(), j["entry_px"].to_numpy())["r_fee"] \
            if sym == "BTCUSDT" else None
        for arm in ARMS:
            rid = ids[arm]
            if only is not None and rid not in only:
                continue
            k = keep[arm]
            row = {"id": rid, "family": "trading", "symbol": sym, "method": arm, "track": "filter", "trades": int(j.height),
                   "kept": int(k.sum())}
            if k.sum() < P.FLOORS["filters_kept"]:
                rows.append({**row, "status": "below floor"})
                continue
            res = R6.evaluate_arm(r, k, strata=strata, ts=ts, spread_r=spread_r, stopped=j["stopped"].to_numpy(), r_fee=fee,
                                  draws=draws)
            kept_mean = res["kept"].get("expectancy_r")
            checks = res["checks"] if segment == "train" else {
                "kept_beats_baseline": res["checks"]["kept_beats_baseline"],
                "kept_mean_r_positive": bool(kept_mean is not None and kept_mean > 0),
                "positive_at_2x_costs": res["checks"]["positive_at_2x_costs"]}
            rows.append({**row, **{k2: v for k2, v in res.items() if k2 != "checks"}, "status": "tested", "p": res["p_random"],
                         "effect_ok": res["checks"]["kept_beats_baseline"], "checks": checks})
        log(f"filters {sym}: {len(ARMS)} arms on {j.height:,} baseline trades")
    return rows
