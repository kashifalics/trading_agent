"""Experiment 6 re-scoring (EXPERIMENT_6_PLAN.md section 3): every Experiment 5 signal of a tested cell, re-evaluated at its own
signal candle with the engine's point-in-time view, must reproduce the stored signal (direction, entry mode, entry and stop); its
key candles then give the confirmation verdicts. Reads signals and candles only: no outcome."""
import numpy as np
import polars as pl

from app.gold_research.events import bars_from_frame
from app.gold_research.exp5 import run as R5
from app.historical.config import INSTRUMENTS, TF_SECONDS
from app.historical.store import load_tf
from app.price_action.engine import analyze_price_action
from app.strategy_engine import confirm
from app.strategy_engine.config import CHAINS, GROUPS
from app.strategy_engine.context import TFData
from app.strategy_engine.plan import build_plan
from app.strategy_engine.regime import classify
from app.strategy_engine.strategies import STRATEGIES

CATS = ("vsa", "momentum", "trend", "volatility")


class RescoreMismatch(RuntimeError):
    pass


def check_signal(ev: dict, status: str, plan: dict | None, direction: int) -> None:
    """The re-evaluated setup must be the stored signal: same side, a live candidate, same entry mode, entry and stop."""
    where = f"{ev.get('strategy')} idx {ev.get('idx')}"
    if direction != int(ev["direction"]):
        raise RescoreMismatch(f"{where}: direction {direction} != stored {ev['direction']}")
    live = status == "ready" or (status == "pending" and ev["entry_mode"] == "limit")
    if not live or plan is None:
        raise RescoreMismatch(f"{where}: no live plan on re-evaluation (status {status})")
    tol = 1e-9 * max(1.0, abs(float(ev["limit"])))
    if plan["entry_mode"] != ev["entry_mode"] or abs(plan["entry"] - float(ev["limit"])) > tol or abs(plan["stop_loss"] - float(ev["stop"])) > tol:
        raise RescoreMismatch(f"{where}: plan {plan['entry_mode']} {plan['entry']} / {plan['stop_loss']} != stored "
                              f"{ev['entry_mode']} {ev['limit']} / {ev['stop']}")


def tested_cells(symbol: str, tf: str) -> set[tuple[str, int]]:
    pre = R5.load_prereg(symbol)
    return {(x["strategy"], 1 if x["direction"] == "long" else -1) for x in pre["tests"] if x["tf"] == tf and x["status"] == "run"}


def verdicts(symbol: str, tf: str, upto: str = "validation", log=print) -> pl.DataFrame:
    ev = pl.read_parquet(R5.out_dir(symbol) / f"events_{tf}.parquet")
    cells = tested_cells(symbol, tf)
    ev = ev.filter(pl.col("compatible"))
    ev = ev.filter(pl.Series([(s, int(d)) in cells for s, d in zip(ev["strategy"].to_list(), ev["direction"].to_list())]))
    schema = {"symbol": pl.Utf8, "tf": pl.Utf8, "idx": pl.Int64, "strategy": pl.Utf8, "direction": pl.Int64, "signal_ts": pl.Int64,
              "compatible": pl.Boolean, "tested": pl.Boolean, **{c: pl.Utf8 for c in CATS}}
    if ev.height == 0:
        return pl.DataFrame(schema=schema)
    inst = INSTRUMENTS[symbol]
    df = load_tf(symbol, tf, upto=upto).sort("ts")
    b = bars_from_frame(df, TF_SECONDS[tf], volume="both")
    eng = R5.HIST[tf]
    t = TFData.build(eng, b, analyze_price_action(b), calendar=inst.calendar,
                     vtype="base" if inst.source == "binance" else "venue")
    close_ts = R5._close_ts(df, tf)
    lv = R5._levels(symbol, upto, close_ts)
    ctx = R5._context(symbol, tf, upto, close_ts)
    spread = (df["ask_close"] - df["bid_close"]).to_numpy()
    group = GROUPS[CHAINS[eng].group]
    prec = R5.PRECISION[symbol]
    rows = []
    for n, e in enumerate(ev.iter_rows(named=True)):
        i = int(e["idx"])
        levels = {k: (float(v[i]) if np.isfinite(v[i]) else None) for k, v in lv.items()}
        v = t.at(i, levels=levels)
        reg = classify(v)
        c = STRATEGIES[e["strategy"]].evaluate(v, reg, ctx[i], int(e["direction"]))
        plan = build_plan(c, v, group=group, precision=prec, spread=float(spread[i]), price_now=None)[0] \
            if c.status in ("ready", "pending") else None
        check_signal(e, c.status, plan, c.direction)
        d = c.direction
        rows.append({"symbol": symbol, "tf": tf, "idx": i, "strategy": e["strategy"], "direction": d, "signal_ts": int(e["signal_ts"]),
                     "compatible": True, "tested": True,
                     "vsa": confirm.vsa_verdict(c.strategy, v, d, c.anchors)[0],
                     "momentum": confirm.momentum_verdict(c.strategy, v, d)[0],
                     "trend": confirm.trend_verdict(v, d)[0],
                     "volatility": confirm.volatility_verdict(c.strategy, v, d, c.anchors)[0]})
        if n and n % 5000 == 0:
            log(f"{symbol} {tf}: re-scored {n:,}/{ev.height:,} signals")
    return pl.DataFrame(rows, schema=schema)
