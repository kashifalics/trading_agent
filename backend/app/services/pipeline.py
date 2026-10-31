"""Pure analytical pipeline: bars (+ optional MTF bars / model) -> decision. No DB, no network."""
from dataclasses import dataclass

import numpy as np

from app.core.events import Event
from app.feature_engineering.features import compute_features
from app.feature_engineering.labels import LabelConfig, triple_barrier
from app.historical_engine.analogues import (
    AnalogueConfig,
    AnalogueResult,
    find_analogues,
)
from app.market_data.bars import Bars
from app.ml_engine.inference import predict_row
from app.multi_timeframe.analysis import MTFConfig, analyze_mtf
from app.prediction.decision_engine import (
    Decision,
    DecisionConfig,
    DecisionInputs,
    decide,
)
from app.price_action.engine import PriceActionResult, analyze_price_action


@dataclass
class PipelineOutput:
    decision: Decision
    pa: PriceActionResult
    analogues: AnalogueResult | None
    mtf: dict | None
    ml: dict | None
    n_bars: int


def slim_event(e: Event) -> dict:
    return {"kind": e.kind, "direction": e.direction, "time": e.to_dict()["time"], "start_time": e.to_dict()["start_time"],
            "ts": e.ts, "start_ts": e.start_ts, "price": e.price, "low": e.low, "high": e.high, "status": e.status,
            "evidence": e.evidence}


def run_pipeline(*, symbol: str, timeframe: str, bars: Bars, quality: dict, label_cfg: LabelConfig,
                 min_rr: float = 1.5, mtf_cfg: MTFConfig | None = None, mtf_bars: dict[str, Bars] | None = None,
                 ml_bundle: dict | None = None, ml_meta: dict | None = None, price_calibrated: bool = True,
                 analogue_cfg: AnalogueConfig | None = None) -> PipelineOutput:
    pa = analyze_price_action(bars)
    analogues: AnalogueResult | None = None
    ml: dict | None = None
    X = None
    if len(bars) >= 100:
        _, X = compute_features(bars, pa)
        labels = triple_barrier(bars, pa.atr, label_cfg)
        analogues = find_analogues(bars, X, labels, cfg=analogue_cfg)
        if ml_bundle is not None and ml_meta is not None:
            probs = predict_row(ml_bundle, X[-1])
            if probs:
                ml = {**probs, **ml_meta}
    mtf = None
    if mtf_cfg and mtf_cfg.roles() and mtf_bars:
        mtf_bars = {**mtf_bars}
        mtf_bars.setdefault(mtf_cfg.entry or timeframe, bars)
        mtf = analyze_mtf(mtf_cfg, mtf_bars, as_of_epoch=int(bars.t[-1]) + bars.step if len(bars) else None)
    d = decide(DecisionInputs(symbol, timeframe, bars, pa, quality, mtf, analogues, ml, price_calibrated),
               DecisionConfig(min_rr=min_rr))
    return PipelineOutput(d, pa, analogues, mtf, ml, len(bars))


def overlay_events(pa: PriceActionResult, n_bars: int, limit_bars: int = 400, cap: int = 300) -> list[dict]:
    evs = [e for e in pa.all_events() if e.idx >= n_bars - limit_bars]
    evs = [e for e in evs if e.kind not in ("doji", "inside_bar", "outside_bar")][-cap:]
    return [slim_event(e) for e in evs]


def swing_points(pa: PriceActionResult, n_bars: int, bars: Bars, limit_bars: int = 400) -> list[dict]:
    return [{"kind": s.kind, "label": s.label, "price": s.price, "ts": int(bars.t[s.idx]), "confirm_ts": int(bars.t[s.confirm_idx])}
            for s in pa.swings if s.idx >= n_bars - limit_bars and s.confirm_idx < n_bars]


__all__ = ["run_pipeline", "overlay_events", "swing_points", "PipelineOutput", "np"]
