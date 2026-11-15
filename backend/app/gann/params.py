"""Every Gann setting in one frozen object (spec section 4.2). Its sha256 goes into the Experiment 7 pre-registration, so any
change after outcomes are seen is visible as a new trial."""
import hashlib
import json
from dataclasses import asdict, dataclass

from app.gann.angles import RATES
from app.gann.time_cycles import COUNTS, FRACS, SEASONAL


@dataclass(frozen=True)
class GannParams:
    counts: tuple = COUNTS
    fracs: tuple = FRACS
    tol_frac: float = 0.025  # time window half-width = max(1, round(tol_frac x count)) units
    major_k: float = 5.0  # major anchor: reversal of at least major_k x ATR
    per_kind: int = 2  # anchors used at each candle: the latest 2 highs and 2 lows
    sq9_steps: int = 8  # Square of Nine: +-8 steps of 45 degrees (+-720)
    sq9_step_deg: float = 45.0
    sq9_time_max: int = 400  # Square of Nine time counts: cardinal-cross numbers up to 400
    price_tol_atr: float = 0.1  # price tolerance: 0.1 x ATR, at least one tick
    rates: tuple = RATES
    seasonal: tuple = SEASONAL
    seasonal_tol_days: int = 2
    anniv_tol_days: int = 2
    anniv_years: tuple = (1, 2, 3)
    symmetry_ratios: tuple = (0.5, 1.0, 2.0)  # projected swing = ratio x the previous swing
    fixed_scale: float = 1.0  # dollars per calendar day (D1 only)
    tick: float = 0.01
    atr_n: int = 14

    def to_dict(self) -> dict:
        return json.loads(json.dumps(asdict(self)))

    def sha(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()
