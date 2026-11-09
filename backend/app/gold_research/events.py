"""Every price-action pattern over a long history, found with the platform's own detectors, unchanged (docs/PATTERN_STUDY.md).

The detectors were written for a few thousand bars, and some loop to the end of the series, so a 20-year M5 history is processed in
chunks of CHUNK bars, each preceded by WARMUP bars of context. An event belongs to the chunk that contains its confirmation bar, so
nothing is counted twice. Events are causal: `idx` is the bar at whose close the pattern is known, and only the levels the detector
reports at that bar (never its later status) are used to place stops.

Support/resistance breakouts need levels "as of" a bar, so levels are recomputed every LEVEL_STEP bars from swings confirmed before
that point, and breakouts, retests and failed breakouts are taken from the following LEVEL_STEP bars only.
Trendlines are drawn by the platform but have no breakout definition, so they are not studied as entry signals.
"""
import hashlib
from collections.abc import Callable
from pathlib import Path

import numpy as np
import polars as pl

from app.candlestick.detectors import detect_candlestick_patterns
from app.core.events import Event
from app.feature_engineering.indicators import atr as atr_fn
from app.market_data.bars import Bars
from app.market_structure.bos import detect_structure_breaks
from app.market_structure.liquidity import detect_equal_levels, detect_liquidity_sweeps
from app.market_structure.swings import find_swings
from app.price_action.breaker_blocks import detect_breaker_blocks
from app.price_action.fvg import detect_fvg
from app.price_action.levels import BreakoutParams, detect_breakouts, detect_levels
from app.price_action.order_blocks import detect_order_blocks
from app.price_action.supply_demand import detect_supply_demand

CHUNK, WARMUP, LEVEL_STEP = 20_000, 1_000, 200
ATR_PERIOD = 14
ZONES = ("fvg", "order_block", "breaker_block", "demand_zone", "supply_zone")
FAMILY = {
    **{k: "candlestick" for k in ("bullish_engulfing", "bearish_engulfing", "pin_bar", "hammer", "shooting_star", "doji",
                                  "inside_bar", "outside_bar", "morning_star", "evening_star")},
    "BOS": "structure", "CHoCH": "structure", "liquidity_sweep": "structure", "equal_highs": "structure", "equal_lows": "structure",
    **{k: "zone" for k in ZONES},
    "breakout": "level", "retest": "level", "failed_breakout": "level",
}
DIRECTION = {"bullish": 1, "bearish": -1, "neutral": 0}
SCHEMA = {"pattern": pl.Utf8, "family": pl.Utf8, "direction": pl.Int8, "idx": pl.Int64, "stop_level": pl.Float64,
          "zone_lo": pl.Float64, "zone_hi": pl.Float64, "entry": pl.Utf8}


def bars_from_frame(df: pl.DataFrame, step: int) -> Bars:
    """Bid candles (what a broker chart shows) as the analysis series."""
    return Bars(t=(df["ts"].dt.epoch("s")).to_numpy().astype(np.int64), o=df["bid_open"].to_numpy(), h=df["bid_high"].to_numpy(),
                l=df["bid_low"].to_numpy(), c=df["bid_close"].to_numpy(), v=df["bid_volume"].to_numpy().astype(float), step=step)


def stop_level(e: Event, b: Bars, d: int) -> float:
    """Price that cancels the pattern (before any buffer). NaN = the pattern has no structural invalidation level."""
    k = e.kind
    if k in ZONES:
        return float(e.low if d > 0 else e.high)  # far edge of the zone
    if k in ("BOS", "CHoCH", "failed_breakout"):
        s = e.meta.get("breakout_idx") if k == "failed_breakout" else e.meta.get("swing_idx")
        s = e.idx if s is None else s
        return float(b.l[s:e.idx + 1].min() if d > 0 else b.h[s:e.idx + 1].max())  # origin of the move that confirmed it
    if k.startswith("equal_"):
        return float("nan")
    return float(e.low if d > 0 else e.high)  # candle range, sweep wick, or the far side of the broken band


def _breakouts(b: Bars, swings, atr: np.ndarray) -> list[Event]:
    n, out = len(b), []
    tail = 20  # bars after a window so retests (12) and failures (5) of its breakouts can still resolve
    for w in range(LEVEL_STEP, n, LEVEL_STEP):
        end = min(n, w + LEVEL_STEP)
        levels = detect_levels(b, swings, atr, as_of=w - 1)
        if not levels:
            continue
        sub = b.upto(min(n, end + tail))
        p = BreakoutParams(lookback_bars=len(sub) - w)  # the detector scans the last lookback_bars bars, i.e. from bar w
        for e in detect_breakouts(sub, levels, atr[:len(sub)], p):
            origin = e.idx if e.kind == "breakout" else e.meta.get("breakout_idx", e.idx)
            if w <= origin < end:
                out.append(e)
    return out


def chunk_events(b: Bars, atr: np.ndarray) -> tuple[list[Event], np.ndarray]:
    swings = find_swings(b)
    breaks, trend = detect_structure_breaks(b, swings)
    obs = detect_order_blocks(b, breaks, atr)
    evs = (detect_candlestick_patterns(b) + breaks + detect_liquidity_sweeps(b, swings) + detect_equal_levels(b, swings, atr)
           + detect_fvg(b, atr) + obs + detect_breaker_blocks(b, obs) + detect_supply_demand(b, atr) + _breakouts(b, swings, atr))
    return evs, trend


def find_events(b: Bars, atr: np.ndarray | None = None, log: Callable[[str], None] = lambda m: None,
                label: str = "", cache_dir: Path | None = None) -> tuple[pl.DataFrame, np.ndarray]:
    """All pattern events of one series (global bar indices) and the structure trend (-1/0/1) known at each bar's close.

    With cache_dir, every chunk is saved (write-then-rename) under a name that includes a hash of the exact candles and ATR it was
    computed from, so an interrupted run resumes and a later run on a longer history reuses only chunks whose data is identical
    (detection is causal: a chunk depends only on its own candles and its warm-up)."""
    n = len(b)
    atr = atr_fn(b.h, b.l, b.c, ATR_PERIOD) if atr is None else atr
    trend = np.zeros(n, dtype=np.int8)
    parts: list[pl.DataFrame] = []
    for s in range(0, n, CHUNK):
        a, e = max(0, s - WARMUP), min(n, s + CHUNK)
        f = None
        if cache_dir is not None:
            h = hashlib.blake2b(digest_size=12)
            for arr in (b.t[a:e], b.o[a:e], b.h[a:e], b.l[a:e], b.c[a:e], np.nan_to_num(atr[a:e])):
                h.update(np.ascontiguousarray(arr).tobytes())
            f = Path(cache_dir) / f"chunk_{s:09d}_{e - a}_{h.hexdigest()}.parquet"  # content hash: reused only for identical data
            if f.exists() and f.with_suffix(".trend.npy").exists():
                parts.append(pl.read_parquet(f))
                trend[s:e] = np.load(f.with_suffix(".trend.npy"))
                log(f"{label} patterns: bars {e:,}/{n:,} (cached chunk)")
                continue
        sub = b.slice(a, e)
        evs, tr = chunk_events(sub, atr[a:e])
        trend[s:e] = tr[s - a:]
        rows = {k: [] for k in SCHEMA}
        for ev in evs:
            if ev.idx + a < s or ev.kind not in FAMILY:
                continue
            d = DIRECTION.get(ev.direction, 0)
            zone = ev.kind in ZONES
            rows["pattern"].append(ev.kind)
            rows["family"].append(FAMILY[ev.kind])
            rows["direction"].append(d)
            rows["idx"].append(ev.idx + a)
            rows["stop_level"].append(stop_level(ev, sub, d) if d else float("nan"))
            rows["zone_lo"].append(float(ev.low) if zone else float("nan"))
            rows["zone_hi"].append(float(ev.high) if zone else float("nan"))
            rows["entry"].append("zone_retest" if zone else "next_open")
        part = pl.DataFrame(rows, schema=SCHEMA)
        parts.append(part)
        if f is not None:
            f.parent.mkdir(parents=True, exist_ok=True)
            np.save(f.with_suffix(".trend.npy"), tr[s - a:].astype(np.int8))
            tmp = f.with_suffix(".part")
            part.write_parquet(tmp)
            tmp.replace(f)  # the parquet appears last, so a chunk only counts as done when both files exist
        log(f"{label} patterns: bars {e:,}/{n:,}, {sum(p.height for p in parts):,} events")
    out = pl.concat(parts) if parts else pl.DataFrame(schema=SCHEMA)
    return out.sort("idx"), trend
