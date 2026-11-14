"""What every strategy returns (DESIGN section 4). Strategies only describe the market event and its entry condition; prices of
stop and targets are computed by plan.py from the invalidation, so all six follow the same risk rules."""
from dataclasses import asdict, dataclass, field

import numpy as np

from app.strategy_engine.config import STRATEGY_NAMES
from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime


@dataclass
class Candidate:
    strategy: str
    direction: int  # +1 BUY, -1 SELL
    status: str  # ready | pending | forming | rejected
    entry_mode: str | None = None  # market | limit | stop
    entry: float | None = None
    entry_zone: tuple[float, float] | None = None
    invalidation: float | None = None
    signal_idx: int | None = None  # candle that confirmed the setup (signal time, de-duplication)
    trigger: str = ""  # the exact entry condition, in words
    reasons: list[str] = field(default_factory=list)  # conditions met
    missing: list[str] = field(default_factory=list)  # conditions not met (forming) or the rule that rejected it
    targets: list[tuple[float, str]] | None = None  # strategy-specific targets (range reversion)
    checks: list[tuple[str, bool, str]] = field(default_factory=list)  # (component: regime|htf|entry|structure, met, text)
    anchors: dict = field(default_factory=dict)  # the setup's key candles (indices) and levels, for the confirmation layer

    def tag(self, comps: list[str], anchors: dict | None = None, missing_comp: str = "entry",
            extra: list[tuple[str, bool, str]] = ()) -> "Candidate":
        """Pair each reason with its component (same order), add extra checks and the unmet ones, attach the key candles."""
        comps = (list(comps) + ["entry"] * len(self.reasons))[:len(self.reasons)]  # an untagged reason counts as an entry condition
        self.checks = [(c, True, r) for c, r in zip(comps, self.reasons)] + list(extra) + \
            [(missing_comp, False, m) for m in self.missing]
        if anchors is not None:
            self.anchors = {k: (int(v) if isinstance(v, (int, np.integer)) else [int(x) for x in v] if isinstance(v, (list, range))
                                else float(v)) for k, v in anchors.items()}
        return self

    @property
    def name(self) -> str:
        return STRATEGY_NAMES[self.strategy]

    @property
    def side(self) -> str:
        return "BUY" if self.direction > 0 else "SELL"

    def out(self) -> dict:
        d = asdict(self)
        d["name"], d["side"] = self.name, self.side
        return d


def side(d: int) -> str:
    return "BUY" if d > 0 else "SELL"


def fmt(x: float | None) -> str:
    if x is None:
        return "-"
    a = abs(x)
    return f"{x:,.2f}" if a >= 100 else f"{x:.5f}" if a < 10 else f"{x:.3f}"


def body(t: TFData, i: int) -> float:
    return abs(float(t.bars.c[i]) - float(t.bars.o[i]))


def rng(t: TFData, i: int) -> float:
    return float(t.bars.h[i]) - float(t.bars.l[i])


def close_pos(t: TFData, i: int) -> float:
    """Where the close sits in the candle's range: 0 = at the low, 1 = at the high."""
    r = rng(t, i)
    return 0.5 if r <= 0 else (float(t.bars.c[i]) - float(t.bars.l[i])) / r


def ok(x) -> bool:
    return x is not None and bool(np.isfinite(x))


class Strategy:
    key: str = ""
    regimes: tuple[str, ...] = ()

    def evaluate(self, t: TFData, regime: Regime, context: Regime | None, d: int) -> Candidate:  # pragma: no cover - interface
        raise NotImplementedError

    def no(self, d: int, why: str, status: str = "rejected", component: str = "entry", **kw) -> Candidate:
        return Candidate(self.key, d, status, missing=[why], checks=[(component, False, why)], **kw)
