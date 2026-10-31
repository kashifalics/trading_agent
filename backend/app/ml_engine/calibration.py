import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

MIN_POS = 15


class ProbabilityCalibrator:
    """One-vs-rest calibrator (isotonic when enough data, else Platt/sigmoid), rows renormalised.
    Fit ONLY on data that is chronologically after the model's training window."""

    def __init__(self, n_classes: int = 3):
        self.n_classes = n_classes
        self.maps: list = [None] * n_classes
        self.method = "identity"

    def fit(self, P: np.ndarray, y: np.ndarray) -> "ProbabilityCalibrator":
        use_iso = len(y) >= 1000
        self.method = "isotonic" if use_iso else "sigmoid"
        for k in range(self.n_classes):
            yk = (y == k).astype(int)
            if yk.sum() < MIN_POS or (1 - yk).sum() < MIN_POS:
                self.maps[k] = None
                continue
            if use_iso:
                self.maps[k] = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(P[:, k], yk)
            else:
                z = np.log(np.clip(P[:, k], 1e-6, 1 - 1e-6) / (1 - np.clip(P[:, k], 1e-6, 1 - 1e-6)))
                self.maps[k] = LogisticRegression(C=1e4).fit(z.reshape(-1, 1), yk)
        return self

    def transform(self, P: np.ndarray) -> np.ndarray:
        out = np.empty_like(P, dtype=float)
        for k in range(self.n_classes):
            m = self.maps[k]
            if m is None:
                out[:, k] = P[:, k]
            elif isinstance(m, IsotonicRegression):
                out[:, k] = m.predict(P[:, k])
            else:
                z = np.log(np.clip(P[:, k], 1e-6, 1 - 1e-6) / (1 - np.clip(P[:, k], 1e-6, 1 - 1e-6)))
                out[:, k] = m.predict_proba(z.reshape(-1, 1))[:, 1]
        out = np.clip(out, 1e-6, None)
        return out / out.sum(axis=1, keepdims=True)
