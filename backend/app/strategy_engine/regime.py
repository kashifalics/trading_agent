"""Market-regime classifier (DESIGN section 3): TRENDING, RANGING, CONSOLIDATING, HIGH_VOLATILITY or UNKNOWN, from completed
candles only. The result lists every input and which criteria were met; it carries no probability."""
from dataclasses import asdict, dataclass, field

import numpy as np

from app.strategy_engine.config import MIN_BARS, REGIME
from app.strategy_engine.context import TFData

LABELS = {"TRENDING": "Trending", "RANGING": "Ranging", "CONSOLIDATING": "Consolidating", "HIGH_VOLATILITY": "High volatility / abnormal",
          "UNKNOWN": "Unknown"}


@dataclass
class Regime:
    label: str  # TRENDING | RANGING | CONSOLIDATING | HIGH_VOLATILITY | UNKNOWN
    direction: int = 0  # +1 / -1 for TRENDING, else 0
    subtype: str | None = None  # UNKNOWN: insufficient_data | transitional
    reason: str = ""
    metrics: dict = field(default_factory=dict)
    criteria: list[dict] = field(default_factory=list)

    def out(self) -> dict:
        d = asdict(self)
        d["name"] = LABELS[self.label] + (f" {'up' if self.direction > 0 else 'down'}" if self.label == "TRENDING" else "")
        d["criteria_met"] = sum(1 for c in self.criteria if c["met"])
        return d


def _f(x) -> float | None:
    return None if x is None or not np.isfinite(x) else float(x)


def classify(t: TFData | None) -> Regime:
    if t is None or t.n < MIN_BARS:
        n = 0 if t is None else t.n
        return Regime("UNKNOWN", 0, "insufficient_data", f"only {n} complete candles (at least {MIN_BARS} needed): no regime, no strategy")
    i, p = t.last, REGIME
    a, prev_a = t.atr[i], t.atr[i - 1]
    if not np.isfinite(a) or a <= 0 or not np.isfinite(t.adx[i]):
        return Regime("UNKNOWN", 0, "insufficient_data", "indicators not yet defined on this history")
    slope = (t.ema50[i] - t.ema50[i - 10]) / a
    span = (t.bars.h[i - 49:i + 1].max() - t.bars.l[i - 49:i + 1].min()) / a
    bar_range = (t.bars.h[i] - t.bars.l[i]) / prev_a if np.isfinite(prev_a) and prev_a > 0 else 0.0
    di = 1 if t.pdi[i] > t.mdi[i] else -1
    aligned = (t.ema20[i] > t.ema50[i]) if di > 0 else (t.ema20[i] < t.ema50[i])
    m = {"adx": _f(t.adx[i]), "plus_di": _f(t.pdi[i]), "minus_di": _f(t.mdi[i]), "er": _f(t.er[i]), "ema50_slope_atr": _f(slope),
         "atr": _f(a), "atr_pct": _f(t.atr_pct[i]), "bb_width": _f(t.bbw[i]), "bb_width_pct": _f(t.bbw_pct[i]), "span_50_atr": _f(span),
         "last_bar_atr": _f(bar_range)}

    def crit(name: str, met: bool, value) -> dict:
        return {"name": name, "met": bool(met), "value": value}

    atr_pct = t.atr_pct[i]
    abnormal = [crit(f"ATR percentile >= {p['atr_pct_abnormal']}", np.isfinite(atr_pct) and atr_pct >= p["atr_pct_abnormal"], m["atr_pct"]),
                crit(f"last candle >= {p['shock_bar_atr']} ATR", bar_range >= p["shock_bar_atr"], m["last_bar_atr"])]
    if any(c["met"] for c in abnormal):
        return Regime("HIGH_VOLATILITY", 0, None, "abnormal volatility: " + "; ".join(c["name"] for c in abnormal if c["met"]), m, abnormal)
    trend = [crit(f"ADX >= {p['trend_adx']}", t.adx[i] >= p["trend_adx"], m["adx"]),
             crit(f"efficiency ratio >= {p['trend_er']}", np.isfinite(t.er[i]) and t.er[i] >= p["trend_er"], m["er"]),
             crit("EMA20/EMA50 aligned with the dominant DI", aligned, None),
             crit(f"|EMA50 slope| >= {p['trend_slope_atr']} ATR per 10 bars in the DI direction",
                  np.isfinite(slope) and slope * di >= p["trend_slope_atr"], m["ema50_slope_atr"])]
    if all(c["met"] for c in trend):
        return Regime("TRENDING", di, None, f"{'up' if di > 0 else 'down'}trend: ADX {m['adx']:.0f}, ER {m['er']:.2f}, EMA50 slope "
                                            f"{slope:+.2f} ATR", m, trend)
    bbw_pct = t.bbw_pct[i]
    consol = [crit(f"Bollinger-width percentile <= {p['consol_bbw_pct']}", np.isfinite(bbw_pct) and bbw_pct <= p["consol_bbw_pct"],
                   m["bb_width_pct"]),
              crit(f"ADX < {p['consol_adx']}", t.adx[i] < p["consol_adx"], m["adx"])]
    if all(c["met"] for c in consol):
        return Regime("CONSOLIDATING", 0, None, f"compression: Bollinger width in the lowest {bbw_pct:.0%} of 200 bars, ADX {m['adx']:.0f}",
                      m, consol)
    rng = [crit(f"ADX < {p['range_adx']}", t.adx[i] < p["range_adx"], m["adx"]),
           crit(f"efficiency ratio < {p['range_er']}", np.isfinite(t.er[i]) and t.er[i] < p["range_er"], m["er"]),
           crit(f"50-bar span {p['range_span_min_atr']}-{p['range_span_max_atr']} ATR",
                p["range_span_min_atr"] <= span <= p["range_span_max_atr"], m["span_50_atr"])]
    if all(c["met"] for c in rng):
        return Regime("RANGING", 0, None, f"range: ADX {m['adx']:.0f}, ER {m['er']:.2f}, span {span:.1f} ATR", m, rng)
    return Regime("UNKNOWN", 0, "transitional", "no regime rule fully met (transitional conditions): "
                  f"ADX {m['adx']:.0f}, ER {(m['er'] or 0):.2f}", m, trend + consol + rng)
