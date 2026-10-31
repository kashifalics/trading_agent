# ML & analogue methodology

## What is predicted
Triple-barrier outcome on ATR-scaled barriers, entry at the **next bar's open**: class `+1` long TP (default +2 ATR) hit before SL (−1 ATR), `−1` short TP before SL, `0` neither within `horizon` bars (default 24) **or** a bar where both barriers are reachable (conservative: SL first). Each label records `t1`, the last bar it depends on.

## Features (22, scale-free, point-in-time — `feature_engineering/features.py`)
ATR-normalised returns (1/3/5/10/20), candle body/wick ratios, ATR%, short/long volatility ratio, regression slope, distance from EMA50, 50-bar range position, RSI14, structure trend, premium/discount position, and 20-bar counts of bullish/bearish FVGs, sweeps and structure breaks. A test recomputes features on truncated history and requires identical rows.

## Historical analogues (`historical_engine`)
Robust-scaled (median/IQR) Euclidean nearest neighbours among bars whose outcome window ended **before** the query bar (`j + horizon ≤ q`), with minimum separation between picks (default 12 bars) so adjacent bars do not inflate *n*. Reports for the neighbours **and** the unconditional base rate: TP-before-SL frequencies with Wilson 95% CIs, forward-return mean with CI and quantiles, MFE/MAE in ATR. `similarity = 1/(1+d/√f)` ranks resemblance only — **never a probability**. `sufficient` requires ≥ 30 analogues from a ≥ 200-bar library.

## Models
Logistic regression (baseline, standardised), LightGBM, XGBoost; 3-class with all classes always returned. Calibration: one-vs-rest isotonic (≥ 1,000 calibration rows) or Platt, renormalised, fit on a chronologically later slice than the model's training data (purged between).

## Validation protocol (`ml_engine/training.py`, `evaluation.py`)
* Chronological **expanding-window walk-forward** (default 5 folds after 40% warm-up).
* **Purge**: training rows whose label window reaches the test period are dropped; plus a small embargo.
* Per fold: fit on first 80% of the purged train set, calibrate on the last 20%, predict the untouched test block.
* Out-of-sample metrics: multiclass Brier and log-loss vs a **class-prior baseline** (Brier skill), reliability curves + ECE, prediction coverage, and a **non-overlapping trade simulation** (long/short when P ≥ 0.45 and leads the opposite by 0.10) net of spread: win rate, profit factor, expectancy (R) with 95% CI, max drawdown (R), per-trade Sharpe, breakdown by volatility tercile and structure regime.
* **Status gate** — `passed_minimum_checks` requires *all*: ≥ 1,000 OOS rows; ≥ 100 OOS trades; expectancy CI lower bound > 0 after costs; Brier skill > 0; ECE ≤ 0.08; positive expectancy in ≥ 60% of folds. Anything else is `research_only` with the failed reasons stored. Passing is a **minimum** bar, not proof of live edge.

## How a model affects decisions
Only `passed_minimum_checks` **and** calibrated models contribute weight (0.15) and populate `probabilities`. Research-only output is displayed, labelled, and weighted 0. Tests enforce this.

## Findings so far
Noise (random walks) is never promoted. On 3.2 years of real BTCUSDT (28.8k 1H and 7.2k 4H candles; `reports/BTCUSDT_ML_EVALUATION.md`) every model has **negative Brier skill** versus the class prior (-0.003 to -0.018), 42-68 OOS trades, no profitable model after costs, and none beats the simple baselines, so all stay `research_only`. Gross (no-cost) LightGBM/XGBoost 1H expectancy was +0.15/+0.18 R but with confidence intervals spanning zero (n of 52-68). The promotion gate additionally requires beating the best simple baseline. ML trade costs are percentages of price converted to R per row (`cost_frac`).
