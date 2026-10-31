# BTCUSDT quantitative validation — summary

_Generated from stored experiments by `python -m app.research.run_milestone report`. Statements below are rule-derived from the numbers in the detailed reports; no result was selected or tuned._

## What was tested

Whether the existing BTCUSDT analysis stack (price-action rule engine; LightGBM/logistic/XGBoost models) carries statistically meaningful predictive information on ≥ 3 years of Binance 1H and 4H candles, after realistic transaction costs, using chronological out-of-sample evaluation and simple baselines.

## Data

* 1H: 28,799 completed candles, 2023-07-19 → 2026-10-31, coverage **100.0%**, 0 missing, 0 invalid. Snapshot `403cd411eaafb0ec`.
* 4H: 7,199 completed candles, 2023-07-20 → 2026-10-31, coverage **100.0%**, 0 missing, 0 invalid. Snapshot `38593a5b717ee874`.

## Results

| Timeframe | Evidence | Result |
|---|---|---|
| 1H | Rule engine, `base` costs | 914 trades, expectancy -0.261 R, PF 0.60, return -91.4%, max DD 91.5% → **NEGATIVE net expectancy** |
| 1H | Rule engine, zero costs (gross) | expectancy -0.048 R, PF 0.90, p(edge>0) 0.891 |
| 1H | Buy & hold / SMA200 trend | +165.7% (DD 53.7%) / -33.5% (DD 66.5%) |
| 1H | Random entries (mean of 10) | -71.4%, expectancy -0.275 R |
| 4H | Rule engine, `base` costs | 235 trades, expectancy -0.054 R, PF 0.90, return -13.3%, max DD 22.7% → **NO EVIDENCE OF EDGE** |
| 4H | Rule engine, zero costs (gross) | expectancy +0.041 R, PF 1.06, p(edge>0) 0.293 |
| 4H | Buy & hold / SMA200 trend | +160.5% (DD 53.4%) / +150.7% (DD 32.1%) |
| 4H | Random entries (mean of 10) | -3.6%, expectancy -0.030 R |
| 1H | ML `logistic` (walk-forward OOS, `base` costs) | Brier skill -0.0073, 63 trades, expectancy -0.599 R → **research only** |
| 1H | ML `lightgbm` (walk-forward OOS, `base` costs) | Brier skill -0.0029, 68 trades, expectancy -0.374 R → **research only** |
| 1H | ML `xgboost` (walk-forward OOS, `base` costs) | Brier skill -0.0032, 52 trades, expectancy -0.258 R → **research only** |
| 4H | ML `logistic` (walk-forward OOS, `base` costs) | Brier skill -0.0182, 46 trades, expectancy -0.477 R → **research only** |
| 4H | ML `lightgbm` (walk-forward OOS, `base` costs) | Brier skill -0.0131, 53 trades, expectancy -0.377 R → **research only** |
| 4H | ML `xgboost` (walk-forward OOS, `base` costs) | Brier skill -0.0109, 42 trades, expectancy -0.176 R → **research only** |

## Conclusions (rule-derived)

* Rule engine showing a statistically positive net edge: **none**.
* Models meeting every promotion gate: **none — all remain research-only**.
* Predictions continue to expose **no probability** unless a calibrated model has passed the gates; the decision policy is unchanged.

## Caveats

* A negative or null result on one asset and one historical path is not proof that no edge exists anywhere; it shows these fixed rules/models did not demonstrate one here at these costs.
* Costs dominate at hourly horizons: compare the `zero_cost` and `base` rows to see how much gross signal quality (if any) is consumed.
* Multiple models/scenarios were evaluated; a single positive cell among many would need correction for multiple comparisons.
* The rule engine was not changed to improve these numbers; parameters are defaults.

## Reproducibility

Each run is stored in the `experiments` table with its dataset snapshot id, full configuration, code hash and library versions. Re-run any of them with `python -m app.research.reproduce <experiment_id>`; it refuses to run if the stored candles no longer match the snapshot and reports any numeric difference.

Experiments: #5, #6, #7, #8, #10, #24, #26, #27, #29, #34, #38, #15, #16, #17, #18, #22, #39, #40, #41, #42, #43, #44
