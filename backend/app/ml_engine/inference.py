from pathlib import Path

import joblib
import numpy as np

from app.database.models import ModelVersion


def load_bundle(mv: ModelVersion) -> dict | None:
    if not mv.artifact_path or not Path(mv.artifact_path).exists():
        return None
    return joblib.load(mv.artifact_path)


def predict_row(bundle: dict, x: np.ndarray) -> dict | None:
    """Calibrated class probabilities for one feature row (same feature order as training)."""
    if not np.all(np.isfinite(x)):
        return None
    P = bundle["calibrator"].transform(bundle["model"].predict_proba(x.reshape(1, -1)))[0]
    return {"p_short_tp_first": float(P[0]), "p_neither": float(P[1]), "p_long_tp_first": float(P[2])}
