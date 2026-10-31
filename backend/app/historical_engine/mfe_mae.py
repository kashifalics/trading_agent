import numpy as np

from app.feature_engineering.labels import Labels


def summarize_excursions(labels: Labels, idx: np.ndarray) -> dict:
    """MFE/MAE from the LONG perspective (short MFE = long MAE and vice-versa), in ATR units."""
    mfe, mae = labels.mfe_atr[idx], labels.mae_atr[idx]
    ok = ~(np.isnan(mfe) | np.isnan(mae))
    if not ok.any():
        return {"n": 0}
    mfe, mae = mfe[ok], mae[ok]
    return {"n": int(ok.sum()), "unit": "ATR", "mfe_mean": float(mfe.mean()), "mfe_median": float(np.median(mfe)),
            "mae_mean": float(mae.mean()), "mae_median": float(np.median(mae)),
            "mfe_p90": float(np.percentile(mfe, 90)), "mae_p90": float(np.percentile(mae, 90))}
