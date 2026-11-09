"""Pattern library registry (brief Part 4): one PatternSpec per pattern, with its exact definition, confirmation, invalidation (stop
rule), entry type and status. docs/PATTERN_LIBRARY.md is generated from this registry, so the document and the code cannot drift.

Detectors are vectorized numpy functions over one chunk of candles. They return Hits: for each occurrence the index of the candle
whose CLOSE confirms it (only candles <= that index are used), its direction (+1 / -1 / 0), the invalidation price (NaN when the
pattern has none), and the zone bounds for zone patterns.
"""
from dataclasses import dataclass, field

import numpy as np

FAMILIES = {
    "A": "Candlestick", "B": "Market structure", "C": "Liquidity", "D": "Fair value gaps and imbalance",
    "E": "Order blocks and supply/demand", "F": "Support and resistance", "G": "Classical chart patterns", "H": "Wyckoff-style events",
    "I": "Fibonacci and harmonic", "J": "Volatility and momentum", "K": "Combinations",
}


@dataclass(frozen=True)
class PatternSpec:
    id: str
    family: str  # key of FAMILIES
    name: str
    direction: str  # bullish | bearish | neutral | both
    definition: str
    confirmation: str = "the close of the last candle of the pattern"
    invalidation: str = "beyond the pattern's extreme (low for bullish, high for bearish)"
    entry: str = "next_open"  # next_open | zone_limit
    status: str = "implemented"  # implemented | scoped_out
    reason: str = ""


REGISTRY: dict[str, PatternSpec] = {}


def spec(**kw) -> PatternSpec:
    s = PatternSpec(**kw)
    if s.id in REGISTRY:
        raise ValueError(f"duplicate pattern id {s.id}")
    REGISTRY[s.id] = s
    return s


@dataclass
class Hits:
    """Occurrences found by a detector (chunk-local indices)."""

    pattern: list[str] = field(default_factory=list)
    idx: list[np.ndarray] = field(default_factory=list)
    direction: list[np.ndarray] = field(default_factory=list)
    stop: list[np.ndarray] = field(default_factory=list)
    zone_lo: list[np.ndarray] = field(default_factory=list)
    zone_hi: list[np.ndarray] = field(default_factory=list)

    def add(self, pid: str, mask: np.ndarray, direction, stop, zone_lo=None, zone_hi=None) -> None:
        if pid not in REGISTRY:
            raise KeyError(f"pattern {pid} is not registered")
        i = np.flatnonzero(mask)
        if len(i) == 0:
            return
        n = len(mask)

        def pick(x, default=np.nan):
            if x is None:
                return np.full(len(i), default)
            x = np.asarray(x, dtype=float)
            return np.full(len(i), float(x)) if x.ndim == 0 else x[i] if len(x) == n else x
        self.pattern.append(pid)
        self.idx.append(i)
        self.direction.append(pick(direction).astype(np.int8))
        self.stop.append(pick(stop))
        self.zone_lo.append(pick(zone_lo))
        self.zone_hi.append(pick(zone_hi))

    def add_points(self, pid: str, idx, direction, stop, zone_lo=None, zone_hi=None) -> None:
        """Occurrences given as index lists (direction / stop / zone per occurrence)."""
        if pid not in REGISTRY:
            raise KeyError(f"pattern {pid} is not registered")
        i = np.asarray(idx, dtype=np.int64)
        if len(i) == 0:
            return
        f = lambda x: np.full(len(i), np.nan) if x is None else np.asarray(x, dtype=float)  # noqa: E731
        self.pattern.append(pid)
        self.idx.append(i)
        self.direction.append(np.asarray(direction, dtype=np.int8))
        self.stop.append(f(stop))
        self.zone_lo.append(f(zone_lo))
        self.zone_hi.append(f(zone_hi))

    def extend(self, other: "Hits") -> None:
        for a in ("pattern", "idx", "direction", "stop", "zone_lo", "zone_hi"):
            getattr(self, a).extend(getattr(other, a))

    def rows(self):
        """(pattern, idx, direction, stop, zone_lo, zone_hi) arrays, concatenated."""
        if not self.idx:
            e = np.array([])
            return [], e.astype(np.int64), e.astype(np.int8), e, e, e
        pats = [p for p, i in zip(self.pattern, self.idx) for _ in range(len(i))]
        return (pats, np.concatenate(self.idx), np.concatenate(self.direction), np.concatenate(self.stop),
                np.concatenate(self.zone_lo), np.concatenate(self.zone_hi))


class Points:
    """Collects single occurrences per pattern, then adds them to Hits in one go."""

    def __init__(self) -> None:
        self.d: dict[str, list] = {}

    def put(self, pid: str, i: int, direction: int, stop: float, zone_lo: float = np.nan, zone_hi: float = np.nan) -> None:
        self.d.setdefault(pid, []).append((i, direction, stop, zone_lo, zone_hi))

    def flush(self, H: Hits) -> Hits:
        for pid, rows in self.d.items():
            a = list(zip(*rows))
            H.add_points(pid, a[0], a[1], a[2], a[3], a[4])
        self.d.clear()
        return H


def library_markdown() -> str:
    L = ["# Pattern library", "", "_Generated from `backend/app/patterns/registry.py`; do not edit by hand._", "",
         "Every definition uses only candles up to the confirming candle. Notation: body = |close - open|, range = high - low, "
         "upper / lower = wicks, ATR = 14-candle Wilder ATR, prior trend = close one candle back versus six candles back.", ""]
    total = {"implemented": 0, "scoped_out": 0}
    for fam, title in FAMILIES.items():
        specs = [s for s in REGISTRY.values() if s.family == fam]
        if not specs:
            continue
        L += [f"## {fam}. {title}", "", "| Id | Pattern | Direction | Definition | Confirmation | Invalidation (stop) | Entry | Status |",
              "|---|---|---|---|---|---|---|---|"]
        for s in specs:
            total[s.status] += 1
            st = "implemented" if s.status == "implemented" else f"scoped out: {s.reason}"
            L.append(f"| `{s.id}` | {s.name} | {s.direction} | {s.definition} | {s.confirmation} | {s.invalidation} | {s.entry} | {st} |")
        L.append("")
    L.insert(4, f"{total['implemented']} patterns implemented, {total['scoped_out']} scoped out with a reason.")
    L.insert(5, "")
    return "\n".join(L) + "\n"
