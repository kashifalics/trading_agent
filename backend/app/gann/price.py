"""Gann price divisions (methodology 4.2) and the Square of Twelve twelfths (4.8, experimental)."""
import math

import numpy as np

DIVS = (1 / 8, 1 / 4, 1 / 3, 3 / 8, 1 / 2, 5 / 8, 2 / 3, 3 / 4, 7 / 8)
EXT = (1.125, 1.25, 1.5, 2.0)


def _decimals(tick: float) -> int:
    return max(0, -math.floor(math.log10(tick) + 1e-12))


def round_tick(x, tick: float):
    """Nearest multiple of the instrument tick, with float noise removed."""
    d = _decimals(tick)
    if isinstance(x, np.ndarray):
        return np.round(np.round(x / tick) * tick, d)
    return round(round(x / tick) * tick, d)


def divisions(low: float, high: float, tick: float, ext: bool = True, down: bool = False) -> list[tuple[float, float]]:
    """(fraction, price) of the range eighths and thirds, plus extensions beyond the end of the move, sorted by price.
    down=True: the move ran from `high` to `low`, so extensions lie below `low`."""
    rng = high - low
    out = [(f, round_tick(low + f * rng, tick)) for f in DIVS]
    if ext:
        out += [(f, round_tick(high - f * rng if down else low + f * rng, tick)) for f in EXT]
    return sorted(out, key=lambda x: x[1])


def twelfths(low: float, high: float, tick: float) -> list[tuple[float, float]]:
    """Square of Twelve read as twelfths of a range (modern interpretation, experimental)."""
    return [(j / 12, round_tick(low + j / 12 * (high - low), tick)) for j in range(1, 12)]


def swing_ratios(p: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For alternating swing extremes: |dP_k| / |dP_k-1| and dt_k / dt_k-1."""
    dp = np.abs(np.diff(np.asarray(p, dtype=float)))
    dt = np.diff(np.asarray(t, dtype=float))
    return dp[1:] / dp[:-1], dt[1:] / dt[:-1]
