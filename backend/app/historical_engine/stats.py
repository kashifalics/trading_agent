import math

import numpy as np


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def mean_ci(x: np.ndarray, z: float = 1.96) -> dict | None:
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 2:
        return None
    m, sd = float(x.mean()), float(x.std(ddof=1))
    half = z * sd / math.sqrt(n)
    return {"mean": m, "ci_low": m - half, "ci_high": m + half, "std": sd, "n": n}


def freq(k: int, n: int) -> dict:
    ci = wilson_interval(k, n)
    return {"k": int(k), "n": int(n), "frequency": (k / n) if n else None,
            "ci_low": ci[0] if ci else None, "ci_high": ci[1] if ci else None}
