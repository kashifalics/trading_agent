"""Triple-barrier labels (ATR-scaled), entry at the NEXT bar's open.

For bar i with ATR a: entry = open[i+1]; long TP = entry + tp*a, long SL = entry - sl*a (short mirrored),
scanned over bars i+1 .. i+horizon. If SL and TP are both reachable inside one bar the SL is assumed
first (conservative). Rows whose horizon is not fully observed are NaN/0-flagged (`valid` False).
"""
from dataclasses import dataclass

import numpy as np

from app.market_data.bars import Bars


@dataclass(frozen=True)
class LabelConfig:
    horizon: int = 24
    tp_atr: float = 2.0
    sl_atr: float = 1.0


@dataclass
class Labels:
    cfg: LabelConfig
    valid: np.ndarray  # bool: label fully observed
    y: np.ndarray  # +1 long TP first, -1 short TP first, 0 neither (timeout / SL-first both sides)
    long_result: np.ndarray  # +1 TP first, -1 SL first, 0 timeout
    short_result: np.ndarray
    t1: np.ndarray  # last bar index the label depends on (for purging)
    fwd_ret_atr: np.ndarray  # (close[i+H]-entry)/ATR
    mfe_atr: np.ndarray  # long perspective: max favourable excursion
    mae_atr: np.ndarray  # long perspective: max adverse excursion


def _first(mask: np.ndarray) -> float:
    idx = np.flatnonzero(mask)
    return float(idx[0]) if len(idx) else np.inf


def triple_barrier(b: Bars, atr: np.ndarray, cfg: LabelConfig = LabelConfig()) -> Labels:
    n, H = len(b), cfg.horizon
    valid = np.zeros(n, bool)
    long_r = np.zeros(n, np.int8)
    short_r = np.zeros(n, np.int8)
    t1 = np.arange(n) + H
    fwd = np.full(n, np.nan)
    mfe = np.full(n, np.nan)
    mae = np.full(n, np.nan)
    for i in range(n - H - 1 + 1):
        a = atr[i]
        if i + H >= n or np.isnan(a) or a <= 0:
            continue
        entry = b.o[i + 1] if i + 1 < n else np.nan
        hi, lo = b.h[i + 1:i + 1 + H], b.l[i + 1:i + 1 + H]
        if len(hi) < H or np.isnan(entry):
            continue
        valid[i] = True
        # long
        f_tp, f_sl = _first(hi >= entry + cfg.tp_atr * a), _first(lo <= entry - cfg.sl_atr * a)
        long_r[i] = 1 if f_tp < f_sl else -1 if f_sl < np.inf else 0
        s_tp, s_sl = _first(lo <= entry - cfg.tp_atr * a), _first(hi >= entry + cfg.sl_atr * a)
        short_r[i] = 1 if s_tp < s_sl else -1 if s_sl < np.inf else 0
        if long_r[i] == 1:
            t1[i] = i + 1 + int(f_tp)
        elif short_r[i] == 1:
            t1[i] = i + 1 + int(s_tp)
        fwd[i] = (b.c[i + H] - entry) / a
        mfe[i] = (hi.max() - entry) / a
        mae[i] = (entry - lo.min()) / a
    y = np.where(long_r == 1, 1, np.where(short_r == 1, -1, 0)).astype(np.int8)
    return Labels(cfg, valid, y, long_r, short_r, t1, fwd, mfe, mae)
