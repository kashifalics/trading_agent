"""Nearest-neighbour search over scale-free features.

The similarity score is 1/(1 + d/sqrt(f)) in (0, 1] where d is the Euclidean distance between
robust-scaled feature vectors. It ranks resemblance only. IT IS NOT A PROBABILITY.
"""
import numpy as np


def robust_scale_params(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    med = np.nanmedian(X, axis=0)
    q75, q25 = np.nanpercentile(X, 75, axis=0), np.nanpercentile(X, 25, axis=0)
    scale = (q75 - q25) / 1.349
    scale = np.where(scale < 1e-9, np.nanstd(X, axis=0), scale)
    return med, np.where(scale < 1e-9, 1.0, scale)


def scale(X: np.ndarray, med: np.ndarray, sc: np.ndarray, clip: float = 5.0) -> np.ndarray:
    return np.clip((X - med) / sc, -clip, clip)


def knn(query: np.ndarray, lib: np.ndarray, lib_idx: np.ndarray, k: int, min_separation: int = 1,
        weights: np.ndarray | None = None) -> list[tuple[int, float, float]]:
    """Top-k (bar_index, distance, similarity) with at least `min_separation` bars between picks
    (adjacent bars are near-duplicates and would overstate the sample size)."""
    w = np.ones(lib.shape[1]) if weights is None else weights
    d = np.sqrt((((lib - query) ** 2) * w).sum(axis=1))
    order = np.argsort(d)
    picked: list[tuple[int, float, float]] = []
    taken: list[int] = []
    f = lib.shape[1]
    for o in order:
        idx = int(lib_idx[o])
        if any(abs(idx - t) < min_separation for t in taken):
            continue
        taken.append(idx)
        picked.append((idx, float(d[o]), float(1.0 / (1.0 + d[o] / np.sqrt(f)))))
        if len(picked) >= k:
            break
    return picked
