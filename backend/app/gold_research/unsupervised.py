"""Phase 6: discovery of unnamed patterns (brief Part 5). Fitted on the training period only, then frozen; tested exactly like named
patterns (same simulator, matched controls, statistics) as their own discovery stage, then validated in the shared Holm family.

* Candle-shape sequences: every candle gets one of 27 symbols (direction up / down / flat; body small / medium / large in ATR;
  close in the lower / middle / upper third). The most frequent 2- and 3-candle sequences in TRAINING (chosen by count, never by
  outcome) become patterns `seq2_*` / `seq3_*`.
* Shape clusters: K-means (k = 24) on the last 8 candles' shape in ATR units, fitted on a sample of training candles; the candle
  where a new cluster starts is a `kmeans_c*` event. The fitted model is saved with its SHA-256 and reused unchanged later.
Direction is unknown for unnamed shapes, so each occurrence is tested both long and short (both count as tests). The stop is
1 ATR (no structural level), entry at the next open. Runs on H1 and H4 (laptop budget).
"""
import hashlib
from collections import Counter

import joblib
import numpy as np
import polars as pl
from sklearn.cluster import KMeans

from app.feature_engineering.indicators import atr as atr_fn
from app.gold_research.events import SCHEMA, bars_from_frame
from app.historical.config import TF_SECONDS
from app.historical.store import load_tf

UNSUP_TFS = ("H1", "H4")
K, WINDOW, SEED = 24, 8, 7
TOP_SEQ = {2: 60, 3: 90}
MIN_SEQ_COUNT = 300
FAMILY = "Discovered (unsupervised)"


def symbols(o, h, lo, c, a) -> np.ndarray:
    """27-symbol candle code: direction (u/d/f) + body size (s/m/l) + close location (1/2/3, bottom to top third)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        rng = np.where(h - lo > 0, h - lo, np.nan)
        body = np.abs(c - o)
        d = np.where(body <= 0.1 * rng, "f", np.where(c > o, "u", "d"))
        size = np.select([body < 0.3 * a, body > 0.9 * a], ["s", "l"], "m")
        loc = np.select([(c - lo) / rng < 1 / 3, (c - lo) / rng > 2 / 3], ["1", "3"], "2")
    out = np.char.add(np.char.add(d.astype(str), size.astype(str)), loc.astype(str))
    return np.where(np.isfinite(a) & np.isfinite(rng), out, "")


def sequences(sym: np.ndarray, n: int) -> np.ndarray:
    s = sym.astype(object)
    out = s.copy()
    for k in range(1, n):
        prev = np.r_[[""] * k, s[:-k]] if k < len(s) else np.array([""] * len(s), dtype=object)
        out = np.where((prev == "") | (out == ""), "", prev + "-" + out)
    return out


def shape_matrix(o, h, lo, c, a) -> np.ndarray:
    """Last WINDOW candles: body, upper wick, lower wick and close-to-close move, each in ATR of the current candle."""
    with np.errstate(invalid="ignore", divide="ignore"):
        feats = [(c - o) / a, (h - np.maximum(o, c)) / a, (np.minimum(o, c) - lo) / a, np.r_[0.0, np.diff(c)] / a]
    cols = []
    for f in feats:
        for k in range(WINDOW):
            cols.append(np.r_[np.full(k, np.nan), f[:len(f) - k]] if k else f)
    return np.clip(np.stack(cols, 1), -5, 5)


def model_path(symbol: str, tf: str):
    from app.gold_research.study import out_dir
    return out_dir(symbol) / "models" / f"unsupervised_{tf}.joblib"


def fit(symbol: str, tf: str, log=print) -> dict:
    """Training period only: frequent sequences (by count) and K-means clusters. Saved once; never refitted silently."""
    p = model_path(symbol, tf)
    if p.exists():
        log(f"{tf}: unsupervised model already frozen ({p.name}), reused")
        return joblib.load(p)
    df = load_tf(symbol, tf, upto="train")
    b = bars_from_frame(df, TF_SECONDS[tf])
    a = atr_fn(b.h, b.l, b.c, 14)
    sym = symbols(b.o, b.h, b.l, b.c, a)
    chosen = {}
    for n, top in TOP_SEQ.items():
        cnt = Counter(x for x in sequences(sym, n) if x)
        chosen[n] = [s for s, k in cnt.most_common(top) if k >= MIN_SEQ_COUNT]
    X = shape_matrix(b.o, b.h, b.l, b.c, a)
    ok = np.isfinite(X).all(1)
    rng = np.random.default_rng(SEED)
    idx = np.flatnonzero(ok)
    sample = rng.choice(idx, min(len(idx), 150_000), replace=False)
    km = KMeans(n_clusters=K, random_state=SEED, n_init=4).fit(X[sample])
    model = {"tf": tf, "sequences": chosen, "kmeans": km, "window": WINDOW, "fitted_on": "training period only",
             "train_end": str(df["ts"].max())}
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, p)
    model["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    log(f"{tf}: unsupervised model frozen: {sum(len(v) for v in chosen.values())} sequences, {K} clusters")
    return model


def events(b, a: np.ndarray, model: dict) -> pl.DataFrame:
    """Unnamed-pattern events of a series with a frozen model; every occurrence twice (long and short), 1-ATR stop."""
    sym = symbols(b.o, b.h, b.l, b.c, a)
    rows = {"pattern": [], "idx": []}
    for n, chosen in model["sequences"].items():
        seq = sequences(sym, n)
        for s in chosen:
            i = np.flatnonzero(seq == s)
            rows["pattern"] += [f"seq{n}_{s}"] * len(i)
            rows["idx"] += i.tolist()
    X = shape_matrix(b.o, b.h, b.l, b.c, a)
    ok = np.isfinite(X).all(1)
    lab = np.full(len(X), -1)
    lab[ok] = model["kmeans"].predict(X[ok])
    onset = (lab >= 0) & (lab != np.r_[-1, lab[:-1]])
    i = np.flatnonzero(onset)
    rows["pattern"] += [f"kmeans_c{k:02d}" for k in lab[i]]
    rows["idx"] += i.tolist()
    n = len(rows["idx"])
    base = pl.DataFrame({"pattern": rows["pattern"], "idx": np.asarray(rows["idx"], dtype=np.int64)})
    out = pl.concat([base.with_columns(direction=pl.lit(d, pl.Int8)) for d in (1, -1)])
    return out.with_columns(family=pl.lit(FAMILY), stop_level=pl.lit(float("nan")), zone_lo=pl.lit(float("nan")),
                            zone_hi=pl.lit(float("nan")), entry=pl.lit("next_open")).select(list(SCHEMA)).sort("idx") if n else \
        pl.DataFrame(schema=SCHEMA)
