# BTCUSDT machine-learning evaluation

_Generated from stored experiments. Models are evaluated, never promoted automatically: a model needs `passed_minimum_checks` (all gates below) to influence a decision or expose probabilities._

## Protocol

* Label: triple barrier on ATR, entry at the next open — long wins if +2 ATR is touched before −1 ATR within 24 bars, short mirrored; same-bar ambiguity resolves to the stop; classes {short-first, neither, long-first}.
* 22 point-in-time features (see `ML_METHODOLOGY.md`); features/labels leak-tested.
* **Expanding-window walk-forward**, 5 folds after a 40% warm-up; training rows whose label window reaches the test block are purged, plus a 6-bar embargo.
* Per fold: fit on the first 80% of the purged training window, calibrate probabilities (isotonic/Platt, one-vs-rest) on the chronologically later 20%, predict the untouched test block.
* Trades: long/short when the calibrated P ≥ 0.45 and leads the opposite side by ≥ 0.10; non-overlapping; costs converted to R.
* Brier skill = 1 − Brier/Brier(class-prior baseline); positive means better than always predicting historical frequencies.
* **Promotion gates (all required):** ≥ 1,000 OOS rows; ≥ 100 OOS trades; net expectancy CI lower bound > 0; Brier skill > 0; ECE ≤ 0.08; ≥ 60% of folds with positive expectancy; **and expectancy above every simple baseline** (≥ 30 trades).
* Cost columns: `gross` = no costs (predictive information only); `base` = 0.10% fee + 0.002% spread + 0.01% slippage per side.

## 1H

Dataset snapshot **`403cd411eaafb0ec`** · 28,799 candles · OOS window 2024-11-11 → 2026-10-30 · experiments #24, #26, #27, #29, #34, #38

| Model | Costs | OOS rows | Trades | Win rate | PF | Expectancy (R) | 95% CI (R) | Brier skill | ECE | Coverage | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| logistic | gross | 17,196 | 63 | 27.0% | 0.67 | -0.238 | [-0.550, +0.074] | -0.0073 | 0.032 | 0.37% | **research only** |
| logistic | base | 17,196 | 63 | 23.8% | 0.38 | -0.599 | [-0.907, -0.292] | -0.0073 | 0.032 | 0.37% | **research only** |
| lightgbm | gross | 17,196 | 68 | 38.2% | 1.24 | +0.147 | [-0.202, +0.496] | -0.0029 | 0.027 | 0.40% | **research only** |
| lightgbm | base | 17,196 | 68 | 38.2% | 0.61 | -0.374 | [-0.731, -0.017] | -0.0029 | 0.027 | 0.40% | **research only** |
| xgboost | gross | 17,196 | 52 | 40.4% | 1.31 | +0.184 | [-0.215, +0.582] | -0.0032 | 0.022 | 0.30% | **research only** |
| xgboost | base | 17,196 | 52 | 40.4% | 0.70 | -0.258 | [-0.657, +0.140] | -0.0032 | 0.022 | 0.30% | **research only** |

**Simple baselines on the identical OOS rows** (same labels, same `base` costs):

| Baseline | Trades | Win rate | PF | Expectancy (R) | Σ R |
|---|---|---|---|---|---|
| class-prior model (always predicts historical frequencies) | 0 | — | — | — | Brier skill = 0 by definition |
| momentum_ret20 | 1195 | 31.5% | 0.50 | -0.478 | -571.4 |
| structure_trend | 1195 | 31.3% | 0.50 | -0.483 | -576.8 |
| always_long | 1195 | 34.1% | 0.55 | -0.413 | -493.9 |
| rule-based engine, same period (its own stops/targets) | 553 | 43.4% | 0.67 | -0.225 | -124.6 |

R is net P&L ÷ stop distance in all rows, but barrier-based rows (models, simple baselines) use the label's fixed 2:1 bracket while the rule engine uses its own plan, so only the sign/magnitude of expectancy is comparable.

**Reasons each model is not promoted (if any):**

* `logistic` → research_only: only 63 out-of-sample trades (< 100); net expectancy (after spread) not significantly > 0; no Brier skill vs class-prior baseline; does not beat the best simple baseline (baseline expectancy -0.413R vs model -0.599R); expectancy positive in < 60% of walk-forward folds
* `lightgbm` → research_only: only 68 out-of-sample trades (< 100); net expectancy (after spread) not significantly > 0; no Brier skill vs class-prior baseline; expectancy positive in < 60% of walk-forward folds
* `xgboost` → research_only: only 52 out-of-sample trades (< 100); net expectancy (after spread) not significantly > 0; no Brier skill vs class-prior baseline; expectancy positive in < 60% of walk-forward folds

LightGBM walk-forward folds (`base` costs):

| Fold | Test from | Test to | Test rows | Trades | Expectancy (R) | Brier |
|---|---|---|---|---|---|---|
| 1 | 2024-11-11 | 2025-04-04 | 3439 | 5 | -0.355 | 0.6674 |
| 2 | 2025-04-04 | 2025-08-25 | 3439 | 31 | -0.139 | 0.6611 |
| 3 | 2025-08-25 | 2026-01-16 | 3439 | 16 | -0.477 | 0.6625 |
| 4 | 2026-01-16 | 2026-06-08 | 3439 | 5 | -0.809 | 0.6722 |
| 5 | 2026-06-09 | 2026-10-30 | 3440 | 11 | -0.695 | 0.6671 |

## 4H

Dataset snapshot **`38593a5b717ee874`** · 7,199 candles · OOS window 2024-11-14 → 2026-10-27 · experiments #39, #40, #41, #42, #43, #44

| Model | Costs | OOS rows | Trades | Win rate | PF | Expectancy (R) | 95% CI (R) | Brier skill | ECE | Coverage | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| logistic | gross | 4,257 | 46 | 26.1% | 0.65 | -0.258 | [-0.631, +0.115] | -0.0182 | 0.050 | 1.08% | **research only** |
| logistic | base | 4,257 | 46 | 23.9% | 0.47 | -0.477 | [-0.849, -0.104] | -0.0182 | 0.050 | 1.08% | **research only** |
| lightgbm | gross | 4,257 | 53 | 28.3% | 0.74 | -0.186 | [-0.542, +0.170] | -0.0131 | 0.036 | 1.25% | **research only** |
| lightgbm | base | 4,257 | 53 | 28.3% | 0.56 | -0.377 | [-0.737, -0.018] | -0.0131 | 0.036 | 1.25% | **research only** |
| xgboost | gross | 4,257 | 42 | 33.3% | 1.02 | +0.014 | [-0.417, +0.445] | -0.0109 | 0.031 | 0.99% | **research only** |
| xgboost | base | 4,257 | 42 | 33.3% | 0.78 | -0.176 | [-0.611, +0.259] | -0.0109 | 0.031 | 0.99% | **research only** |

**Simple baselines on the identical OOS rows** (same labels, same `base` costs):

| Baseline | Trades | Win rate | PF | Expectancy (R) | Σ R |
|---|---|---|---|---|---|
| class-prior model (always predicts historical frequencies) | 0 | — | — | — | Brier skill = 0 by definition |
| momentum_ret20 | 317 | 36.9% | 0.88 | -0.091 | -28.7 |
| structure_trend | 317 | 37.2% | 0.89 | -0.077 | -24.3 |
| always_long | 317 | 36.9% | 0.87 | -0.093 | -29.4 |
| rule-based engine, same period (its own stops/targets) | 143 | 44.8% | 0.77 | -0.138 | -19.7 |

R is net P&L ÷ stop distance in all rows, but barrier-based rows (models, simple baselines) use the label's fixed 2:1 bracket while the rule engine uses its own plan, so only the sign/magnitude of expectancy is comparable.

**Reasons each model is not promoted (if any):**

* `logistic` → research_only: only 46 out-of-sample trades (< 100); net expectancy (after spread) not significantly > 0; no Brier skill vs class-prior baseline; does not beat the best simple baseline (baseline expectancy -0.077R vs model -0.477R); expectancy positive in < 60% of walk-forward folds
* `lightgbm` → research_only: only 53 out-of-sample trades (< 100); net expectancy (after spread) not significantly > 0; no Brier skill vs class-prior baseline; does not beat the best simple baseline (baseline expectancy -0.077R vs model -0.377R); expectancy positive in < 60% of walk-forward folds
* `xgboost` → research_only: only 42 out-of-sample trades (< 100); net expectancy (after spread) not significantly > 0; no Brier skill vs class-prior baseline; does not beat the best simple baseline (baseline expectancy -0.077R vs model -0.176R); expectancy positive in < 60% of walk-forward folds

LightGBM walk-forward folds (`base` costs):

| Fold | Test from | Test to | Test rows | Trades | Expectancy (R) | Brier |
|---|---|---|---|---|---|---|
| 1 | 2024-11-14 | 2025-04-05 | 851 | 6 | -0.750 | 0.6838 |
| 2 | 2025-04-05 | 2025-08-27 | 851 | 14 | -0.573 | 0.6769 |
| 3 | 2025-08-27 | 2026-01-16 | 852 | 0 | — | 0.6712 |
| 4 | 2026-01-16 | 2026-06-07 | 851 | 20 | -0.170 | 0.6743 |
| 5 | 2026-06-07 | 2026-10-27 | 852 | 13 | -0.314 | 0.6743 |
