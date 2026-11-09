"""Trade outcomes on one timeframe, with the 1-minute path replayed wherever the order of events inside a candle matters.

Inputs per trade: direction, entry (market at a candle's open, or a limit order that waits up to `wait` candles), stop price.
Prices: longs buy at the ASK and exit at the BID; shorts sell at the BID and exit at the ASK, so every trade pays its real spread.

Resolution (brief Part 7):
  1. A vectorized pass over the trade's own timeframe finds the first candle where the stop could have been touched.
  2. That candle is replayed minute by minute from the M1 store. The best favourable move reached in the minutes BEFORE the stop
     minute counts; inside the stop minute itself the order is unknown, so it counts as a stop (conservative). The optimistic
     reading (favourable first) is stored too, so the share of trades the assumption changes can be reported.
  3. A limit order's fill candle is replayed the same way: in the fill minute adverse prices count and favourable ones do not
     (the favourable extreme may have printed before the fill).
  4. A stop minute that OPENS beyond the stop (weekend or news gap) loses more than 1R.

Output is compact, so any target and holding period can be evaluated afterwards without re-simulating:
  for each holding period h in HOLDS: mfe_h = best favourable move (R) reached before the stop and within h candles,
  stopped_h = the stop was hit within h, end_r_h = R at the close of candle h if neither happened. Then for target k:
  R(k, h) = k if mfe_h >= k, else stop_r if stopped_h, else end_r_h.
"""
from dataclasses import dataclass

import numpy as np
import polars as pl

from app.historical.store import M1
from app.historical.sync import bar_close, epoch

HOLDS = (12, 24, 48, 96)
HMAX = max(HOLDS)
MIN_RISK_ATR = 0.25
CELLS = 4_000_000  # padded matrix cells per batch (memory bound)


@dataclass
class Series:
    """One timeframe's bid/ask candles plus the M1 rows each candle covers."""

    tf: str
    t: np.ndarray
    bo: np.ndarray
    bh: np.ndarray
    bl: np.ndarray
    bc: np.ndarray
    ao: np.ndarray
    ah: np.ndarray
    al: np.ndarray
    ac: np.ndarray
    m1_lo: np.ndarray  # first M1 row of each candle
    m1_hi: np.ndarray  # one past the last M1 row
    m1: M1

    @property
    def n(self) -> int:
        return len(self.t)

    @classmethod
    def from_frame(cls, df: pl.DataFrame, tf: str, m1: M1) -> "Series":
        df = df.sort("ts")
        t = epoch(df["ts"])
        g = {f"{s[0]}{k[0]}": df[f"{s}_{k}"].to_numpy().astype(np.float64) for s in ("bid", "ask") for k in ("open", "high", "low", "close")}
        lo = np.searchsorted(m1.ts, t, side="left")
        hi = np.searchsorted(m1.ts, bar_close(tf, t), side="left")
        return cls(tf, t, g["bo"], g["bh"], g["bl"], g["bc"], g["ao"], g["ah"], g["al"], g["ac"], lo, hi, m1)


def _first(mask: np.ndarray, default: int) -> np.ndarray:
    return np.where(mask.any(1), mask.argmax(1), default)


def _minutes(m1: M1, start: np.ndarray, stop: np.ndarray, long: np.ndarray):
    """Padded M1 windows [start, stop) per trade: exit-side high/low/open (bid for longs, ask for shorts) and entry-side
    low/high/open (ask for longs, bid for shorts) as float prices, plus the validity mask."""
    width = int(max(1, (stop - start).max(initial=1)))
    J = start[:, None] + np.arange(width)
    valid = J < stop[:, None]
    J = np.minimum(J, len(m1.ts) - 1)
    p = m1.point
    bid, ask = m1.bid, m1.ask
    L = long[:, None]
    ex_hi = np.where(L, bid[J, 1], ask[J, 1]) * p
    ex_lo = np.where(L, bid[J, 2], ask[J, 2]) * p
    ex_op = np.where(L, bid[J, 0], ask[J, 0]) * p
    en_lo = np.where(L, ask[J, 2], bid[J, 2]) * p  # long limit fills when the ASK trades below it
    en_hi = np.where(L, ask[J, 1], bid[J, 1]) * p  # short limit fills when the BID trades above it
    en_op = np.where(L, ask[J, 0], bid[J, 0]) * p
    return J, valid, ex_hi, ex_lo, ex_op, en_lo, en_hi, en_op


def _batches(n: int, width: int):
    size = max(1, CELLS // max(1, width))
    for s in range(0, n, size):
        yield slice(s, min(n, s + size))


def fill_minutes(m1: M1, lo: np.ndarray, hi: np.ndarray, d: np.ndarray, limit: np.ndarray,
                 through: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """First minute in [lo, hi) a limit order trades through (by more than `through` in price, 0 = any amount), and its fill price
    (the limit, or the minute's open if it opened beyond it). Returns (absolute M1 row, price); row -1 if no minute fills."""
    thr_all = np.zeros(len(lo)) if through is None else through
    n = len(lo)
    row, px = np.full(n, -1, dtype=np.int64), np.full(n, np.nan)
    width = int(max(1, (hi - lo).max(initial=1)))
    for b in _batches(n, width):
        long = d[b] > 0
        J, valid, *_, en_lo, en_hi, en_op = _minutes(m1, lo[b], hi[b], long)
        L = limit[b, None]
        thr = thr_all[b, None]
        hit = np.where(long[:, None], en_lo < L - thr, en_hi > L + thr) & valid
        f = _first(hit, -1)
        ok = f >= 0
        r = np.arange(len(f))
        fo = en_op[r, np.maximum(f, 0)]
        row[b] = np.where(ok, J[r, np.maximum(f, 0)], -1)
        px[b] = np.where(ok, np.where(long, np.minimum(limit[b], fo), np.maximum(limit[b], fo)), np.nan)
    return row, px


def scan_minutes(m1: M1, start: np.ndarray, stop: np.ndarray, d: np.ndarray, P: np.ndarray, R: np.ndarray,
                 skip_first_fav: np.ndarray) -> dict[str, np.ndarray]:
    """Replay minutes [start, stop) of one candle per trade. Returns the absolute stop minute (-1 if none), the best favourable
    R before it (or over the whole range if no stop), the optimistic variant, and the stop R (gap-aware)."""
    n = len(start)
    out = {"stop_row": np.full(n, -1, dtype=np.int64), "fav": np.full(n, -np.inf), "fav_opt": np.full(n, -np.inf),
           "stop_r": np.full(n, np.nan)}
    width = int(max(1, (stop - start).max(initial=1)))
    for b in _batches(n, width):
        long = d[b] > 0
        J, valid, ex_hi, ex_lo, ex_op, *_ = _minutes(m1, start[b], stop[b], long)
        p, r = P[b, None], R[b, None]
        L = long[:, None]
        fav = np.where(L, ex_hi - p, p - ex_lo) / r
        adv = np.where(L, p - ex_lo, ex_hi - p) / r
        fav = np.where(valid, fav, -np.inf)
        fav[skip_first_fav[b], 0] = -np.inf
        hit = (adv >= 1.0) & valid
        s = _first(hit, -1)
        stopped = s >= 0
        cols = np.arange(fav.shape[1])
        before = cols[None, :] < np.where(stopped, s, fav.shape[1])[:, None]
        f_pre = np.where(before, fav, -np.inf).max(1)
        rows = np.arange(len(s))
        sc = np.maximum(s, 0)
        f_at = fav[rows, sc]
        gap = np.where(long, P[b] - ex_op[rows, sc], ex_op[rows, sc] - P[b]) / R[b]
        first_is_fill = skip_first_fav[b] & (s == 0)
        out["stop_row"][b] = np.where(stopped, J[rows, sc], -1)
        out["fav"][b] = f_pre
        out["fav_opt"][b] = np.where(stopped, np.maximum(f_pre, f_at), f_pre)
        out["stop_r"][b] = np.where(stopped, -np.maximum(1.0, np.where(first_is_fill, 1.0, gap)), np.nan)
    return out


@dataclass
class Orders:
    """What to simulate. entry_bar: candle whose OPEN is the market entry, or the first candle the limit order is live."""

    d: np.ndarray  # +1 long, -1 short
    entry_bar: np.ndarray
    stop: np.ndarray  # stop price (already buffered)
    atr: np.ndarray  # ATR at the decision candle (risk floor)
    limit: np.ndarray | None = None  # limit price (NaN = market order)
    cancel: np.ndarray | None = None  # limit cancelled if a candle CLOSES beyond this before the fill
    wait: int = 50
    through: np.ndarray | None = None  # conservative fill: price must trade beyond the limit by this much (None/0 = touch)


def simulate(S: Series, o: Orders, batch: int = 40_000, holds: tuple[int, ...] = HOLDS,
             hit_targets: tuple[float, ...] = ()) -> dict[str, np.ndarray]:
    """holds: holding periods (candles) to store; hit_targets: R targets whose first candle is stored as hit_<k> (absolute candle
    index, -1 if the target was not reached before the stop within max(holds))."""
    hmax = max(holds)
    n = len(o.d)
    d = o.d.astype(np.int64)
    long = d > 0
    is_lim = np.zeros(n, dtype=bool) if o.limit is None else np.isfinite(o.limit)
    e = np.full(n, -1, dtype=np.int64)
    P = np.full(n, np.nan)
    fill_row = np.full(n, -1, dtype=np.int64)
    mk = ~is_lim & (o.entry_bar >= 0) & (o.entry_bar < S.n)
    eb = np.clip(o.entry_bar, 0, S.n - 1)
    e[mk] = o.entry_bar[mk]
    P[mk] = np.where(long, S.ao[eb], S.bo[eb])[mk]
    fill_row[mk] = S.m1_lo[eb][mk]
    if is_lim.any():  # candle-level: first candle the limit could fill, unless a close went through the cancel level first
        li = np.flatnonzero(is_lim)
        J = o.entry_bar[li, None] + np.arange(o.wait)
        real = (J < S.n) & (o.entry_bar[li, None] >= 0)
        Jc = np.clip(J, 0, S.n - 1)
        lim, can = o.limit[li, None], o.cancel[li, None]
        thr = np.zeros((len(li), 1)) if o.through is None else o.through[li, None]
        Ll = long[li, None]
        touch = np.where(Ll, S.al[Jc] < lim - thr, S.bh[Jc] > lim + thr) & real
        cancel = np.where(Ll, S.bc[Jc] < can, S.bc[Jc] > can) & real
        ft, fc = _first(touch, o.wait), _first(cancel, o.wait)
        ok = (ft < o.wait) & (ft <= fc)
        fb = o.entry_bar[li] + ft
        fi = li[ok]
        rows, px = fill_minutes(S.m1, S.m1_lo[fb[ok]], S.m1_hi[fb[ok]], d[fi], o.limit[fi],
                                None if o.through is None else o.through[fi])
        good = rows >= 0
        e[fi[good]], P[fi[good]], fill_row[fi[good]] = fb[ok][good], px[good], rows[good]
    raw = np.where(long, P - o.stop, o.stop - P)
    R = np.where(raw > 0, np.maximum(raw, MIN_RISK_ATR * o.atr), np.nan)
    live = (e >= 0) & np.isfinite(R) & (e + hmax <= S.n)
    out = {"fill_bar": e, "fill_ts": np.where(fill_row >= 0, S.m1.ts[np.clip(fill_row, 0, len(S.m1.ts) - 1)], -1), "entry_px": P,
           "risk_px": R, "stop_r": np.full(n, np.nan), "stop_bar": np.full(n, -1, dtype=np.int64), "simulated": live,
           "stop_ts": np.full(n, -1, dtype=np.int64)}
    for k in hit_targets:
        out[f"hit_{k:g}"] = np.full(n, -1, dtype=np.int64)
    for h in holds:
        out[f"mfe_{h}"], out[f"mfe_opt_{h}"] = np.full(n, np.nan, np.float32), np.full(n, np.nan, np.float32)
        out[f"stopped_{h}"], out[f"end_r_{h}"] = np.zeros(n, dtype=bool), np.full(n, np.nan, np.float32)
    w = np.flatnonzero(live)
    for s in range(0, len(w), batch):
        i = w[s:s + batch]
        _resolve(S, i, d[i], e[i], P[i], R[i], is_lim[i], fill_row[i], out, holds, hit_targets)
    return out


def _resolve(S: Series, i, d, e, P, R, is_lim, fill_row, out, holds=HOLDS, hit_targets=()) -> None:
    HMAX = max(holds)  # noqa: N806  (local window length)
    long = d > 0
    m = len(i)
    J = e[:, None] + np.arange(HMAX)
    L = long[:, None]
    hi = np.where(L, S.bh[J], S.ah[J])
    lo = np.where(L, S.bl[J], S.al[J])
    fav = np.where(L, hi - P[:, None], P[:, None] - lo) / R[:, None]
    adv = np.where(L, P[:, None] - lo, hi - P[:, None]) / R[:, None]
    stop_bar = np.full(m, HMAX)
    fav_pre = np.full(m, -np.inf)
    fav_opt = np.full(m, -np.inf)
    stop_r = np.full(m, np.nan)
    stop_row = np.full(m, -1, dtype=np.int64)
    if is_lim.any():  # the fill candle, minute by minute from the fill minute
        k = np.flatnonzero(is_lim)
        sc = scan_minutes(S.m1, fill_row[k], S.m1_hi[e[k]], d[k], P[k], R[k], np.ones(len(k), dtype=bool))
        st = sc["stop_row"] >= 0
        fav[k, 0] = np.where(st, -np.inf, sc["fav"])
        adv[k, 0] = np.where(st, 1.0, 0.0)
        ks = k[st]
        stop_bar[ks], fav_pre[ks], fav_opt[ks], stop_r[ks] = 0, sc["fav"][st], sc["fav_opt"][st], sc["stop_r"][st]
        stop_row[ks] = sc["stop_row"][st]
    need = stop_bar == HMAX
    sb = _first(adv >= 1.0, HMAX)
    q = np.flatnonzero(need & (sb < HMAX))
    if len(q):  # the first candle that touched the stop, minute by minute
        b = e[q] + sb[q]
        sc = scan_minutes(S.m1, S.m1_lo[b], S.m1_hi[b], d[q], P[q], R[q], np.zeros(len(q), dtype=bool))
        st = sc["stop_row"] >= 0
        # A candle can touch the stop on its high/low while no single clean minute does only if data were inconsistent; then the
        # candle-level reading (stop, nothing favourable inside that candle) is kept.
        stop_bar[q] = sb[q]
        fav_pre[q] = np.where(st, sc["fav"], -np.inf)
        fav_opt[q] = np.where(st, sc["fav_opt"], -np.inf)
        stop_r[q] = np.where(st, sc["stop_r"], -1.0)
        stop_row[q] = np.where(st, sc["stop_row"], S.m1_hi[b] - 1)  # no single minute: the candle's last minute (conservative)
    cols = np.arange(HMAX)
    rows = np.arange(m)
    out["stop_bar"][i] = np.where(stop_bar < HMAX, e + stop_bar, -1)
    out["stop_r"][i] = stop_r
    out["stop_ts"][i] = np.where(stop_row >= 0, S.m1.ts[np.clip(stop_row, 0, len(S.m1.ts) - 1)], -1)
    for k in hit_targets:
        th = _first(fav >= k, HMAX)
        in_stop_candle = (stop_bar < HMAX) & (fav_pre >= k)
        out[f"hit_{k:g}"][i] = np.where(th < stop_bar, e + th, np.where(in_stop_candle, e + stop_bar, -1))
    for h in holds:
        upto = np.minimum(stop_bar, h)
        f_bars = np.where(cols[None, :] < upto[:, None], fav, -np.inf).max(1)
        stopped = stop_bar < h
        out[f"mfe_{h}"][i] = np.where(stopped, np.maximum(f_bars, fav_pre), f_bars)
        out[f"mfe_opt_{h}"][i] = np.where(stopped, np.maximum(f_bars, fav_opt), f_bars)
        out[f"stopped_{h}"][i] = stopped
        last = e + h - 1
        close = np.where(long, S.bc[last], S.ac[last])
        out[f"end_r_{h}"][i] = np.where(long, close - P, P - close) / R
    del rows


def r_multiple(o: dict, k: float, h: int, optimistic: bool = False) -> np.ndarray:
    """R of every simulated trade for target k (in R) and holding period h (candles)."""
    mfe = o[f"mfe_opt_{h}" if optimistic else f"mfe_{h}"]
    r = np.where(mfe >= k, k, np.where(o[f"stopped_{h}"], o["stop_r"], o[f"end_r_{h}"]))
    return np.where(o["simulated"], r, np.nan)
