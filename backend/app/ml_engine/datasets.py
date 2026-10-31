from dataclasses import dataclass

import numpy as np

from app.feature_engineering.features import compute_features
from app.feature_engineering.labels import LabelConfig, Labels, triple_barrier
from app.market_data.bars import Bars
from app.price_action.engine import analyze_price_action

CLASSES = ["short_tp_first", "neither", "long_tp_first"]  # y_cls = y + 1


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray  # 0,1,2
    row_idx: np.ndarray  # bar index of each row (chronological)
    t1: np.ndarray  # last bar index each label depends on
    atr: np.ndarray  # ATR at each row
    labels: Labels
    feature_names: list[str]
    bars: Bars


def build_dataset(b: Bars, cfg: LabelConfig = LabelConfig()) -> Dataset:
    pa = analyze_price_action(b)
    names, X = compute_features(b, pa)
    labels = triple_barrier(b, pa.atr, cfg)
    keep = labels.valid & np.all(np.isfinite(X), axis=1)
    rows = np.flatnonzero(keep)
    return Dataset(X=X[rows], y=(labels.y[rows] + 1).astype(int), row_idx=rows, t1=labels.t1[rows],
                   atr=pa.atr[rows], labels=labels, feature_names=names, bars=b)
