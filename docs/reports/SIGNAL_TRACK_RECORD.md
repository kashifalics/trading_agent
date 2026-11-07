# Signal engine — historical track record

_Generated 2026-11-07T14:57 UTC · config 2026-11-07.1 · method: docs/SIGNAL_ENGINE.md (Track record)._

Every number below comes from replaying the exact live engine on stored candles, net of the configured spread. Development = first 60% of each period, out-of-sample (OOS) = last 40%. The confluence score is **not** a win probability; the calibration column shows how far score/100 is from the observed hit rate.

| Instrument | TF | Period (OOS from) | Trades (OOS) | OOS TP1 hit | OOS expectancy R [95% CI] | OOS PF | Random entries R | Status |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 15m | 2026-07-30 → 2026-11-01 (2026-09-25) | 117 (50) | 24% | -0.011 [-0.50, +0.55] | 0.99 | -0.078 | **no_edge** |
| BTCUSDT | 1D | 2023-07-29 → 2026-10-31 (2025-07-12) | 12 (4) | 0% | -1.001 | — | — | **no_edge** |
| BTCUSDT | 1H | 2025-12-24 → 2026-11-01 (2026-06-29) | 123 (55) | 16% | -0.439 [-0.77, -0.08] | 0.48 | -0.024 | **no_edge** |
| BTCUSDT | 4H | 2023-08-08 → 2026-11-01 (2025-07-17) | 136 (48) | 19% | -0.325 [-0.71, +0.11] | 0.6 | +0.003 | **no_edge** |
| BTCUSDT | 5m | 2026-10-11 → 2026-11-01 (2026-10-24) | 87 (33) | 15% | -0.496 [-0.92, -0.02] | 0.43 | +0.104 | **no_edge** |
| XAUUSD | 15m | 2026-06-23 → 2026-10-30 (2026-09-08) | 151 (60) | 20% | -0.393 [-0.71, -0.05] | 0.53 | -0.174 | **no_edge** |
| XAUUSD | 1D | 2021-12-14 → 2026-10-30 (2024-11-16) | 26 (10) | 70% | +1.092 [+0.17, +1.89] | 4.63 | +0.077 | **no_edge** |
| XAUUSD | 1H | 2025-07-21 → 2026-10-30 (2026-04-27) | 143 (51) | 18% | -0.341 [-0.72, +0.08] | 0.59 | -0.151 | **no_edge** |
| XAUUSD | 4H | 2021-12-31 → 2026-10-30 (2024-11-23) | 175 (78) | 35% | +0.147 [-0.22, +0.54] | 1.22 | -0.079 | **no_edge** |
| XAUUSD | 5m | 2026-10-01 → 2026-10-30 (2026-10-19) | 57 (25) | 32% | +0.052 [-0.56, +0.73] | 1.07 | -0.096 | **no_edge** |

## Reading this table

* Pooled over every instrument and timeframe: **1027 trades, -0.048 R per trade** after spread.
* Out-of-sample 95% CI entirely **below** zero (the rules lost money there, even if the sample is under the 100-trade bar for a formal verdict): BTCUSDT 1H (-0.77 to -0.08 R), BTCUSDT 5m (-0.92 to -0.02 R), XAUUSD 15m (-0.71 to -0.05 R).
* Out-of-sample 95% CI entirely **above** zero but too few trades to validate: XAUUSD 1D (+0.17 to +1.89 R).
* Does a higher score mean better trades? Expectancy by score band (last 400 trades kept per series): 60-69: -0.078 R (n=594), 70-79: +0.009 R (n=386), 80-100: -0.143 R (n=47). A score that does not rise with outcomes is a checklist of setup quality, not a forecast.
* Verdict rules require >= 100 out-of-sample trades; no series reached that, so nothing is `validated` and no win probability is shown.

## Details per instrument and timeframe

### BTCUSDT 15m

Verdict: **no_edge** — only 50 out-of-sample trades (< 100): no conclusion possible.

| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 32 | 22% | -0.139 |
| 70-79 | 16 | 31% | +0.371 |
| 80-100 | 2 | 0% | -1.008 |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 49 | 22% | -0.118 |
| countertrend_zone | 6 | 17% | -0.504 |
| liquidity_sweep_reversal | 7 | 29% | -0.091 |
| trend_pullback | 55 | 29% | +0.144 |

Calibration (OOS): Brier of score/100 = 0.364 vs 0.182 for the base rate.

### BTCUSDT 1D

Verdict: **no_edge** — only 4 out-of-sample trades (< 100): no conclusion possible.

Timeframes missing from the replay (scored 0, as live): 1M.
| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 3 | 0% | -1.000 |
| 70-79 | 1 | 0% | -1.001 |
| 80-100 | 0 | — | — |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 4 | 50% | +0.665 |
| countertrend_zone | 2 | 0% | -1.001 |
| liquidity_sweep_reversal | 3 | 0% | -1.000 |
| trend_pullback | 3 | 0% | -1.001 |

Calibration (OOS): Brier of score/100 = 0.469 vs 0.000 for the base rate.

### BTCUSDT 1H

Verdict: **no_edge** — only 55 out-of-sample trades (< 100): no conclusion possible.

| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 38 | 16% | -0.492 |
| 70-79 | 17 | 18% | -0.321 |
| 80-100 | 0 | — | — |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 63 | 30% | -0.008 |
| countertrend_zone | 5 | 40% | +1.124 |
| liquidity_sweep_reversal | 7 | 14% | -0.573 |
| trend_pullback | 48 | 27% | -0.050 |

Calibration (OOS): Brier of score/100 = 0.389 vs 0.137 for the base rate.

### BTCUSDT 4H

Verdict: **no_edge** — only 48 out-of-sample trades (< 100): no conclusion possible.

| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 17 | 18% | -0.362 |
| 70-79 | 24 | 21% | -0.233 |
| 80-100 | 7 | 14% | -0.551 |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 65 | 31% | +0.018 |
| countertrend_zone | 4 | 0% | -1.001 |
| liquidity_sweep_reversal | 24 | 12% | -0.541 |
| trend_pullback | 43 | 19% | -0.408 |

Calibration (OOS): Brier of score/100 = 0.429 vs 0.152 for the base rate.

### BTCUSDT 5m

Verdict: **no_edge** — only 33 out-of-sample trades (< 100): no conclusion possible.

| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 29 | 17% | -0.422 |
| 70-79 | 4 | 0% | -1.036 |
| 80-100 | 0 | — | — |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 40 | 20% | -0.019 |
| countertrend_zone | 8 | 25% | -0.059 |
| liquidity_sweep_reversal | 2 | 0% | -1.028 |
| trend_pullback | 37 | 27% | +0.144 |

Calibration (OOS): Brier of score/100 = 0.373 vs 0.129 for the base rate.

### XAUUSD 15m

Verdict: **no_edge** — only 60 out-of-sample trades (< 100): no conclusion possible.

| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 37 | 14% | -0.599 |
| 70-79 | 22 | 32% | -0.015 |
| 80-100 | 1 | 0% | -1.066 |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 58 | 29% | -0.008 |
| countertrend_zone | 14 | 21% | -0.160 |
| liquidity_sweep_reversal | 11 | 18% | -0.412 |
| trend_pullback | 68 | 34% | +0.114 |

Calibration (OOS): Brier of score/100 = 0.381 vs 0.160 for the base rate.

### XAUUSD 1D

Verdict: **no_edge** — only 10 out-of-sample trades (< 100): no conclusion possible.

Timeframes missing from the replay (scored 0, as live): 1M.
| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 7 | 57% | +0.675 |
| 70-79 | 3 | 100% | +2.065 |
| 80-100 | 0 | — | — |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 9 | 56% | +0.756 |
| liquidity_sweep_reversal | 5 | 40% | +0.308 |
| trend_pullback | 12 | 42% | +0.238 |

Calibration (OOS): Brier of score/100 = 0.204 vs 0.210 for the base rate.

### XAUUSD 1H

Verdict: **no_edge** — only 51 out-of-sample trades (< 100): no conclusion possible.

| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 35 | 17% | -0.419 |
| 70-79 | 15 | 20% | -0.116 |
| 80-100 | 1 | 0% | -1.018 |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 58 | 28% | +0.009 |
| countertrend_zone | 1 | 0% | -1.022 |
| liquidity_sweep_reversal | 15 | 33% | +0.041 |
| trend_pullback | 69 | 26% | -0.084 |

Calibration (OOS): Brier of score/100 = 0.393 vs 0.145 for the base rate.

### XAUUSD 4H

Verdict: **no_edge** — only 78 out-of-sample trades (< 100): no conclusion possible.

| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 22 | 23% | -0.293 |
| 70-79 | 46 | 43% | +0.351 |
| 80-100 | 10 | 20% | +0.174 |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 61 | 34% | +0.103 |
| countertrend_zone | 6 | 33% | +0.034 |
| liquidity_sweep_reversal | 29 | 38% | +0.176 |
| trend_pullback | 79 | 30% | -0.018 |

Calibration (OOS): Brier of score/100 = 0.368 vs 0.226 for the base rate.

### XAUUSD 5m

Verdict: **no_edge** — only 25 out-of-sample trades (< 100): no conclusion possible.

| Score band (OOS) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| 60-69 | 18 | 39% | +0.310 |
| 70-79 | 5 | 20% | -0.423 |
| 80-100 | 2 | 0% | -1.086 |

| Setup type (all) | Trades | TP1 hit | Expectancy R |
|---|---|---|---|
| bos_retest | 17 | 18% | -0.399 |
| countertrend_zone | 10 | 20% | -0.395 |
| liquidity_sweep_reversal | 3 | 33% | +0.039 |
| trend_pullback | 27 | 15% | -0.579 |

Calibration (OOS): Brier of score/100 = 0.363 vs 0.218 for the base rate.
