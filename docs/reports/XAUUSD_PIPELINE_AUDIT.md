# XAUUSD research pipeline: final technical and statistical audit

_2026-11-10. Reproducible: `backend/app/gold_research/pipeline_audit.py` (results in `data/historical/research/XAUUSD/pipeline_audit.json`).
Scope:_
- _Training-period files and candles._
- _The timestamps (not the outcomes) of validation-period trades, for the purging check._
- _Facts about validation that were already reported._

_The sealed final-test period was not read (no seal log exists). No split, model or production file was changed. Analysis only._

## Verdict

- **No sign that information from later periods reached any decision.** Splits, purging, walk-forward folds, feature generation and both multiple-testing corrections behave as specified.
- **The p-values are, if anything, slightly conservative.** Run on gold's real training history with each minute's direction randomised, the full pipeline finds 1 candidate in 630 tests.
- **The probabilities are well calibrated but barely informative.**
- **One real design flaw: the data-gap rule.** It removed 31% of H4 and 63% of D1 training signals, mostly around US holidays, and left D1 with no trades after August 2012. The conclusions for M5–H1 stand. The longer-timeframe evidence is thinner than it looked, and the rule must be fixed before any experiment on long holding periods.

## 1. Splits, purging, embargo, features, model validation

| Check | Method | Result |
|---|---|---|
| Split fractions | clean-M1 counts in the frozen split file | training 70.07%, validation 14.96%, final test 14.97%; both boundaries Saturday 00:00 UTC; hash `c2e8d3f8...` unchanged |
| Purging, training | latest entry + 96 candles, per stored file | every outcome window ends inside training (latest: 2020-02-07 22:00 UTC; training ends 2020-02-08) |
| Purging, validation | first entry and latest window end (timestamps only) | every validation entry is after the training end; every window ends inside validation; segment labels correct |
| Sealed period | research folder and seal log | no final-test outputs; no seal log, so the sealed period has never been read |
| Model walk-forward folds | `purged_folds` re-run on the M15, H1, H4 datasets | in all 5 expanding and 5 rolling folds of each timeframe, every training row's outcome window ends before its test block |
| Feature look-ahead | 67 features for 27,659 H4 training rows, computed on full training history and on history cut at 2012-01-02 | **0 differences** |
| Nested selection | code path | hyperparameters chosen on the last 20% (purged) of each outer training block; the model type chosen by training out-of-fold log loss |
| Calibration | code path | isotonic, fitted only on earlier folds' out-of-fold predictions; the final calibrator uses training out-of-fold predictions only |

**Embargo.**
- Nothing is embargoed between training and validation. Purging by each trade's own exit makes it unnecessary for labels, and features use only past candles.
- The walk-forward never trains on rows after a test block, so no embargo is needed there either.
- The `purged_folds` docstring claims such an embargo exists. The docstring is wrong; the behaviour is correct.

## 2. Multiple-testing corrections and calibration

| Check | Result |
|---|---|
| Benjamini-Hochberg re-implemented independently, on the 1,452 stage-1 p-values | max difference 0.0; stored q-values identical; the 52 candidates recounted exactly |
| Holm re-implemented, on the 60 validation tests with enough trades | max difference 0.0 |
| **Null on real data:** training M1 with each minute's move randomly signed (volatility, sessions and gaps kept; direction destroyed), full pipeline, H1 and H4 | 630 tests, **1 candidate** at q < 0.10 (H1 demand-to-supply flip, short). p < 0.05 in 3.0% of tests (5% expected); mean edge −0.012R; median absolute edge 0.038R |
| Uniformity of null p-values | Kolmogorov-Smirnov p = 0.0002: not uniform, in the conservative direction (too few small p-values). The clustered standard errors are, if anything, slightly too wide |

Earlier checks (see `XAUUSD_RESEARCH_AUDIT.md`):
- Storey's pi0 = 0.88.
- Estimated false-discovery rate among the 52 candidates: 8%.
- Probability of backtest overfitting (CSCV over 16 year blocks): 38% when selecting on edge, 18% when selecting on mean R.

Tests are positively correlated, because a pattern, its combinations and its multi-timeframe variants share trades. BH remains valid under this dependence.

**Calibration (training, cross-fitted out-of-fold):**

| Model | Rows | Base rate | Mean predicted | ECE | Reliability (predicted to observed, rows) |
|---|---|---|---|---|---|
| H4 random forest | 27,175 | 28.9% | 29.0% | 0.010 | 0.06→0.085 (868), 0.14→0.15 (704), 0.28→0.29 (10,799), 0.32→0.31 (14,804) |
| H1 XGBoost | 117,554 | 26.8% | 26.6% | 0.004 | 0.06→0.055 (2,147), 0.16→0.175 (11,610), 0.27→0.27 (72,614), 0.31→0.31 (31,103), **0.41→0.30 (80)** |

- **Calibration is good.** The one overconfident bin holds 80 rows.
- **Discrimination is weak.** Almost every prediction lies between 0.27 and 0.32, which is why ROC-AUC is 0.55–0.59 and even the top decile cannot overcome costs.

## 3. Problems found

| # | Severity | Finding | Effect | Fix (for any new experiment) |
|---|---|---|---|---|
| 1 | **High for long holds** | Most "material gaps" since 2012 are **US-holiday closures and early closes**, for example Thanksgiving and 4 July (23 h from Thursday 18:00 New York) and the 13:00 early closes, which the calendar did not know. A trade was dropped if any such gap fell anywhere in its *maximum* 96-candle window, even after the trade had already exited. | Training signals dropped: M5 3%, M15 7%, M30 9%, H1 13%, **H4 31%, D1 63%**. D1 has no trades after 2012-08 and none in validation. Controls were not filtered the same way. Not a leak; M5–H1 conclusions unaffected; H4/D1 evidence thinner and tilted to non-holiday periods. | Add the US metals holiday calendar as scheduled closures; store each trade's real exit time; drop a trade only if an unscheduled gap falls between its entry and its exit; apply the same rule to controls |
| 2 | Medium | Some of the reported "7.2% missing data" is the holiday closures above, not missing data | Overstates missing data slightly | Same calendar fix |
| 3 | Medium (realism) | Limit orders fill when price merely trades through the limit, with no queue position. No overnight swap is charged. | Slightly optimistic for limit entries; increasingly optimistic as holds lengthen | Conservative fill variant (price must trade beyond the limit by the spread); financing-cost scenarios |
| 4 | Low | The model feature `structural_regime` is computed with an empty trend input, so "trend transition" never appears | A wasted feature; no leakage | Pass the real structure trend |
| 5 | Low | The `purged_folds` docstring claims an embargo that is neither applied nor needed | Documentation only | Correct the docstring |
| 6 | Low | The real-data sign-flip null planned in Phase 1 had not been run before this audit | Gap in evidence, now closed (section 2) | Keep it as a standard check |

## 4. Why H4 predictions are closest to break-even (training data only)

Average R per trade for every pattern trade with the main setting (2R target, 48 candles). "Before costs" adds each trade's own spread back.

| TF | Trades | Spread cost (R) | Net R | Before costs | Median risk |
|---|---|---|---|---|---|
| M5 | 4,502,519 | 0.54 | −0.538 | +0.003 | $0.98 |
| M15 | 1,459,294 | 0.33 | −0.340 | −0.013 | $1.54 |
| M30 | 723,990 | 0.24 | −0.235 | +0.002 | $2.16 |
| H1 | 356,126 | 0.17 | −0.156 | +0.013 | $3.05 |
| H4 | 81,982 | 0.08 | −0.045 | +0.039 | $6.20 |
| D1 (2003–2012 only) | 9,236 | 0.05 | +0.018 | +0.066 | $13.81 |

Splitting H4 and D1 by direction and period:

| | H4 long | H4 short | H4 long 2013+ | H4 short 2013+ | D1 long | D1 short |
|---|---|---|---|---|---|---|
| Before costs | +0.091 | −0.017 | +0.006 | +0.029 | +0.306 | −0.194 |

**Explanation:**
1. **Before costs, every timeframe from M5 to H1 is zero within ±0.02R.** Their losses are the spread, and the spread is a larger share of risk the smaller the stop: 0.54R on M5 against 0.08R on H4.
2. **H4's small positive pre-cost result is gold's 2003–2012 bull market.** Longs gain and shorts lose. After 2013 the gap disappears.
3. **The matched controls are drawn in the same direction and year, so they remove this drift.** That is why pattern edges are about zero.
4. **The H4 model's validation top decile (−0.01R) reflects H4's low cost share, not predictive skill** (validation ROC-AUC 0.558).

**Lesson for the next experiment:**
- Longer timeframes and holds make costs small enough that a modest real edge *could* survive.
- They also expose results to trend drift, so evidence must come from comparison with direction-matched controls and from both directions.

## Limitations of this audit

- The truncation check covers H4 features at one cut date; other timeframes use the same code path.
- The sign-flip null covers H1 and H4. It removes direction but keeps volatility clustering, so it tests false positives from structure and costs, not every possible artefact.
- Calibration and fold checks use the training period only, by design.
