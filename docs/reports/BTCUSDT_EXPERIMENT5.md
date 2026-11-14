# Experiment 5: strategy engine v2 on BTCUSDT (owner-approved plan, 2026-11-13)

Plan: `docs/engine_v2/EXPERIMENT_PLAN.md`. Pre-registration (counts only, committed before any outcome): `docs/research/BTCUSDT_exp5_preregistration.json` (sha256 `5598d6813d247495…`). Development result: `docs/research/BTCUSDT_exp5_development.json`.

**The sealed final-test period was not read.** Development used the training segment (2017-08-17 to 2024-01-29); validation (2024-01-29 to 2025-06-16) is read only for cells that pass development.

## Result

**No strategy passed.** Of 84 pre-registered cells (6 strategies × 2 directions × 7 timeframes), 47 had at least 100 development trades and were tested; **none met all development criteria**, so nothing was carried to validation and every strategy stays **NOT VALIDATED** in the product.

**In numbers:** 70,651 simulated trades across the tested cells, a trade-weighted mean of -0.066R per trade after the $2 round-trip spread model (the archive has no bid/ask). 18 of 47 cells had a positive mean, 11 of them on the long side. No cell kept a positive mean after every pre-registered check.

**Trial count.** This run counted only its own 47 cells, but experiments 1-5 were run on gold: under the Experiment 6 plan every deflated Sharpe counts all 2,115 trials. Recomputed with 2,115 trials, the highest deflated Sharpe probability is 0.82 (H8 breakout retest short; needed: 0.95). The per-cell DSR column below uses 47 trials and therefore overstates every value.

**Overfitting probability (CSCV).** Not computed: the method needs 12 yearly blocks and BTCUSDT has fewer than 12 development years (about 7). Every cell therefore fails that check; 0 cell(s) failed on it alone, so the result does not depend on it.

## Development results per tested cell (training segment, after real bid/ask; TP1 full exit, 96-candle horizon)

| TF | Strategy | Side | Trades | Win | Avg win | Avg loss | Exp. R | 95% CI | PF | Max DD R | Edge vs random | BH q | DSR | Years + | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | Breakout and retest | long | 24 | 0.29 | +1.74 | -1.00 | -0.200 | [-0.780, +0.380] | 0.72 | 10.0 | -0.353 | 1.000 | 0.07 | 0.33 | failed |
| D1 | Breakout and retest | short | 17 | 0.24 | +1.93 | -1.00 | -0.312 | [-0.909, +0.286] | 0.59 | 6.0 | -0.380 | 1.000 | 0.07 | 0.33 | failed |
| H1 | Breakout and retest | long | 749 | 0.42 | +1.89 | -1.00 | +0.221 | [+0.116, +0.327] | 1.38 | 19.9 | +0.226 | 0.000 | 0.22 | 0.88 | failed |
| H1 | Breakout and retest | short | 613 | 0.38 | +1.88 | -1.00 | +0.085 | [-0.023, +0.192] | 1.14 | 21.1 | +0.088 | 0.338 | 0.00 | 0.62 | failed |
| H1 | Liquidity-sweep reversal | long | 698 | 0.36 | +1.63 | -1.00 | -0.054 | [-0.150, +0.042] | 0.92 | 53.5 | -0.031 | 1.000 | 0.00 | 0.62 | failed |
| H1 | Liquidity-sweep reversal | short | 716 | 0.34 | +1.70 | -1.00 | -0.089 | [-0.182, +0.003] | 0.86 | 67.1 | -0.067 | 1.000 | 0.00 | 0.25 | failed |
| H1 | Trend-following pullback | long | 237 | 0.39 | +1.70 | -0.99 | +0.066 | [-0.103, +0.234] | 1.11 | 15.0 | +0.033 | 0.866 | 0.02 | 0.71 | failed |
| H1 | Trend-following pullback | short | 236 | 0.33 | +1.73 | -0.99 | -0.081 | [-0.238, +0.077] | 0.88 | 34.5 | -0.073 | 1.000 | 0.00 | 0.50 | failed |
| H1 | Volatility expansion | long | 107 | 0.36 | +1.93 | -0.99 | +0.078 | [-0.204, +0.359] | 1.12 | 11.4 | +0.085 | 0.769 | 0.09 | 0.50 | failed |
| H1 | Volatility expansion | short | 106 | 0.42 | +1.69 | -1.00 | +0.116 | [-0.140, +0.373] | 1.20 | 10.7 | +0.092 | 0.760 | 0.17 | 0.50 | failed |
| H4 | Breakout and retest | long | 209 | 0.41 | +1.86 | -1.00 | +0.161 | [-0.045, +0.367] | 1.27 | 10.7 | +0.146 | 0.375 | 0.17 | 0.75 | failed |
| H4 | Breakout and retest | short | 153 | 0.42 | +1.85 | -1.00 | +0.192 | [-0.043, +0.427] | 1.33 | 8.7 | +0.171 | 0.375 | 0.29 | 0.57 | failed |
| H4 | Liquidity-sweep reversal | long | 187 | 0.42 | +1.61 | -0.99 | +0.095 | [-0.090, +0.281] | 1.17 | 11.0 | +0.069 | 0.760 | 0.07 | 0.62 | failed |
| H4 | Liquidity-sweep reversal | short | 169 | 0.39 | +1.64 | -1.00 | +0.034 | [-0.161, +0.229] | 1.06 | 13.8 | +0.078 | 0.734 | 0.02 | 0.57 | failed |
| H4 | Trend-following pullback | long | 78 | 0.51 | +1.72 | -0.98 | +0.406 | [+0.101, +0.710] | 1.85 | 6.0 | +0.238 | 0.338 | 0.85 | 0.86 | failed |
| H4 | Trend-following pullback | short | 72 | 0.40 | +1.49 | -0.97 | +0.021 | [-0.270, +0.312] | 1.04 | 9.5 | -0.002 | 0.948 | 0.08 | 0.67 | failed |
| H8 | Breakout and retest | long | 122 | 0.40 | +1.83 | -1.00 | +0.136 | [-0.124, +0.396] | 1.23 | 10.8 | +0.141 | 0.575 | 0.18 | 0.71 | failed |
| H8 | Breakout and retest | short | 81 | 0.53 | +1.98 | -1.00 | +0.580 | [+0.226, +0.934] | 2.24 | 6.2 | +0.570 | 0.015 | 0.96 | 0.67 | failed |
| H8 | Liquidity-sweep reversal | long | 102 | 0.38 | +1.67 | -1.00 | +0.020 | [-0.237, +0.277] | 1.03 | 11.8 | -0.018 | 0.965 | 0.05 | 0.43 | failed |
| H8 | Liquidity-sweep reversal | short | 96 | 0.38 | +1.65 | -1.00 | -0.008 | [-0.291, +0.276] | 0.99 | 10.1 | +0.020 | 0.947 | 0.04 | 0.43 | failed |
| H8 | Trend-following pullback | long | 44 | 0.48 | +1.81 | -1.00 | +0.341 | [-0.121, +0.803] | 1.65 | 6.1 | +0.102 | 0.848 | 0.65 | 0.43 | failed |
| M15 | Breakout and retest | long | 2,973 | 0.34 | +1.87 | -1.00 | -0.023 | [-0.072, +0.026] | 0.97 | 131.9 | +0.054 | 0.168 | 0.00 | 0.25 | failed |
| M15 | Breakout and retest | short | 2,544 | 0.34 | +1.88 | -1.00 | -0.017 | [-0.071, +0.038] | 0.97 | 123.1 | +0.031 | 0.560 | 0.00 | 0.62 | failed |
| M15 | Liquidity-sweep reversal | long | 3,207 | 0.33 | +1.66 | -1.00 | -0.134 | [-0.177, -0.090] | 0.80 | 459.4 | -0.077 | 1.000 | 0.00 | 0.12 | failed |
| M15 | Liquidity-sweep reversal | short | 3,036 | 0.33 | +1.74 | -1.00 | -0.092 | [-0.138, -0.047] | 0.86 | 280.4 | -0.067 | 1.000 | 0.00 | 0.25 | failed |
| M15 | Trend-following pullback | long | 822 | 0.36 | +1.70 | -0.99 | -0.036 | [-0.129, +0.058] | 0.94 | 69.9 | -0.000 | 0.948 | 0.00 | 0.25 | failed |
| M15 | Trend-following pullback | short | 808 | 0.32 | +1.77 | -0.99 | -0.115 | [-0.209, -0.021] | 0.83 | 112.3 | -0.095 | 1.000 | 0.00 | 0.25 | failed |
| M15 | Volatility expansion | long | 473 | 0.33 | +1.73 | -1.00 | -0.093 | [-0.204, +0.018] | 0.86 | 45.5 | -0.055 | 1.000 | 0.00 | 0.12 | failed |
| M15 | Volatility expansion | short | 464 | 0.34 | +1.73 | -0.99 | -0.054 | [-0.171, +0.063] | 0.92 | 42.8 | -0.030 | 1.000 | 0.00 | 0.25 | failed |
| M30 | Breakout and retest | long | 1,490 | 0.35 | +1.89 | -1.00 | +0.022 | [-0.047, +0.092] | 1.03 | 37.0 | +0.060 | 0.338 | 0.00 | 0.50 | failed |
| M30 | Breakout and retest | short | 1,177 | 0.33 | +1.91 | -1.00 | -0.029 | [-0.112, +0.054] | 0.96 | 81.5 | -0.000 | 0.948 | 0.00 | 0.38 | failed |
| M30 | Liquidity-sweep reversal | long | 1,542 | 0.35 | +1.67 | -0.99 | -0.070 | [-0.133, -0.007] | 0.89 | 136.4 | -0.026 | 1.000 | 0.00 | 0.25 | failed |
| M30 | Liquidity-sweep reversal | short | 1,546 | 0.34 | +1.74 | -1.00 | -0.075 | [-0.138, -0.012] | 0.89 | 126.3 | -0.051 | 1.000 | 0.00 | 0.25 | failed |
| M30 | Trend-following pullback | long | 423 | 0.35 | +1.71 | -0.99 | -0.043 | [-0.164, +0.079] | 0.93 | 39.1 | -0.029 | 1.000 | 0.00 | 0.25 | failed |
| M30 | Trend-following pullback | short | 388 | 0.35 | +1.71 | -0.99 | -0.036 | [-0.168, +0.096] | 0.94 | 25.5 | -0.009 | 0.965 | 0.00 | 0.38 | failed |
| M30 | Volatility expansion | long | 228 | 0.35 | +1.93 | -1.00 | +0.027 | [-0.156, +0.211] | 1.04 | 24.9 | +0.031 | 0.866 | 0.01 | 0.62 | failed |
| M30 | Volatility expansion | short | 246 | 0.37 | +1.75 | -1.00 | +0.007 | [-0.154, +0.168] | 1.01 | 20.7 | +0.012 | 0.947 | 0.00 | 0.62 | failed |
| M5 | Breakout and retest | long | 9,569 | 0.34 | +1.86 | -1.01 | -0.039 | [-0.071, -0.007] | 0.94 | 462.8 | +0.109 | 0.000 | 0.00 | 0.38 | failed |
| M5 | Breakout and retest | short | 8,463 | 0.34 | +1.92 | -1.01 | -0.012 | [-0.046, +0.021] | 0.98 | 255.1 | +0.128 | 0.000 | 0.00 | 0.50 | failed |
| M5 | Momentum continuation | long | 106 | 0.23 | +1.63 | -0.99 | -0.393 | [-0.598, -0.187] | 0.48 | 41.6 | -0.330 | 1.000 | 0.00 | 0.25 | failed |
| M5 | Momentum continuation | short | 84 | 0.25 | +1.80 | -1.00 | -0.300 | [-0.551, -0.049] | 0.60 | 33.2 | -0.252 | 1.000 | 0.00 | 0.25 | failed |
| M5 | Liquidity-sweep reversal | long | 9,617 | 0.34 | +1.60 | -1.00 | -0.126 | [-0.153, -0.100] | 0.81 | 1251.9 | -0.053 | 1.000 | 0.00 | 0.12 | failed |
| M5 | Liquidity-sweep reversal | short | 9,649 | 0.31 | +1.74 | -1.00 | -0.140 | [-0.166, -0.113] | 0.80 | 1353.7 | -0.072 | 1.000 | 0.00 | 0.12 | failed |
| M5 | Trend-following pullback | long | 2,197 | 0.33 | +1.63 | -0.98 | -0.128 | [-0.179, -0.077] | 0.81 | 287.8 | -0.077 | 1.000 | 0.00 | 0.00 | failed |
| M5 | Trend-following pullback | short | 2,134 | 0.32 | +1.77 | -0.98 | -0.090 | [-0.147, -0.033] | 0.86 | 220.1 | -0.048 | 1.000 | 0.00 | 0.25 | failed |
| M5 | Volatility expansion | long | 1,225 | 0.35 | +1.72 | -1.00 | -0.049 | [-0.126, +0.028] | 0.92 | 77.9 | +0.023 | 0.769 | 0.00 | 0.50 | failed |
| M5 | Volatility expansion | short | 1,424 | 0.34 | +1.75 | -1.00 | -0.074 | [-0.141, -0.006] | 0.89 | 121.1 | -0.016 | 1.000 | 0.00 | 0.25 | failed |

Columns: win = share of trades with R > 0; Exp. R = mean R per trade; CI = cluster-robust 95% interval (weekly clusters); PF = profit factor; edge = mean R minus the matched random-entry control mean; BH q = Benjamini-Hochberg across the tested cells; DSR = deflated Sharpe probability; Years + = share of development years with a positive mean.

## Robustness (development)

| TF | Strategy | Side | Without best year | At 2× spread | 48-candle horizon | Entry one candle late | Optimistic intrabar | Open at horizon |
|---|---|---|---|---|---|---|---|---|
| D1 | Breakout and retest | long | -0.558 | -0.207 | -0.200 | +0.250 | -0.200 | 0.00 |
| D1 | Breakout and retest | short | -0.469 | -0.317 | -0.312 | +0.400 | -0.312 | 0.00 |
| H1 | Breakout and retest | long | +0.183 | +0.198 | +0.223 | +0.610 | +0.221 | 0.00 |
| H1 | Breakout and retest | short | +0.034 | +0.063 | +0.083 | +0.171 | +0.085 | 0.00 |
| H1 | Liquidity-sweep reversal | long | -0.067 | -0.071 | -0.063 | -0.095 | -0.054 | 0.01 |
| H1 | Liquidity-sweep reversal | short | -0.134 | -0.105 | -0.099 | -0.086 | -0.089 | 0.02 |
| H1 | Trend-following pullback | long | +0.039 | +0.054 | +0.040 | -0.125 | +0.066 | 0.03 |
| H1 | Trend-following pullback | short | -0.089 | -0.092 | -0.096 | -0.104 | -0.081 | 0.01 |
| H1 | Volatility expansion | long | +0.045 | +0.064 | +0.074 | +0.017 | +0.078 | 0.01 |
| H1 | Volatility expansion | short | +0.086 | +0.102 | +0.066 | +0.044 | +0.116 | 0.01 |
| H4 | Breakout and retest | long | +0.134 | +0.148 | +0.158 | +0.460 | +0.161 | 0.00 |
| H4 | Breakout and retest | short | +0.123 | +0.181 | +0.188 | +0.624 | +0.192 | 0.01 |
| H4 | Liquidity-sweep reversal | long | +0.075 | +0.086 | +0.072 | +0.050 | +0.095 | 0.04 |
| H4 | Liquidity-sweep reversal | short | -0.081 | +0.027 | +0.035 | +0.005 | +0.034 | 0.04 |
| H4 | Trend-following pullback | long | +0.352 | +0.401 | +0.370 | +0.437 | +0.406 | 0.03 |
| H4 | Trend-following pullback | short | -0.037 | +0.016 | +0.047 | +0.152 | +0.021 | 0.11 |
| H8 | Breakout and retest | long | +0.058 | +0.128 | +0.136 | +0.158 | +0.136 | 0.00 |
| H8 | Breakout and retest | short | +0.368 | +0.572 | +0.550 | +0.217 | +0.580 | 0.00 |
| H8 | Liquidity-sweep reversal | long | -0.015 | +0.014 | +0.025 | +0.041 | +0.020 | 0.02 |
| H8 | Liquidity-sweep reversal | short | -0.036 | -0.012 | -0.006 | +0.004 | -0.008 | 0.01 |
| H8 | Trend-following pullback | long | +0.166 | +0.338 | +0.378 | +0.436 | +0.341 | 0.00 |
| M15 | Breakout and retest | long | -0.045 | -0.070 | -0.019 | +0.062 | -0.021 | 0.00 |
| M15 | Breakout and retest | short | -0.019 | -0.063 | -0.016 | +0.020 | -0.016 | 0.00 |
| M15 | Liquidity-sweep reversal | long | -0.136 | -0.167 | -0.144 | -0.126 | -0.134 | 0.02 |
| M15 | Liquidity-sweep reversal | short | -0.094 | -0.127 | -0.089 | -0.089 | -0.091 | 0.01 |
| M15 | Trend-following pullback | long | -0.067 | -0.058 | -0.030 | -0.026 | -0.036 | 0.03 |
| M15 | Trend-following pullback | short | -0.119 | -0.138 | -0.132 | -0.091 | -0.115 | 0.03 |
| M15 | Volatility expansion | long | -0.147 | -0.126 | -0.087 | -0.045 | -0.093 | 0.01 |
| M15 | Volatility expansion | short | -0.110 | -0.086 | -0.063 | -0.127 | -0.048 | 0.01 |
| M30 | Breakout and retest | long | +0.001 | -0.012 | +0.022 | +0.232 | +0.022 | 0.00 |
| M30 | Breakout and retest | short | -0.052 | -0.062 | -0.032 | +0.102 | -0.026 | 0.00 |
| M30 | Liquidity-sweep reversal | long | -0.074 | -0.094 | -0.070 | -0.067 | -0.068 | 0.02 |
| M30 | Liquidity-sweep reversal | short | -0.091 | -0.100 | -0.069 | -0.115 | -0.075 | 0.01 |
| M30 | Trend-following pullback | long | -0.085 | -0.058 | -0.028 | +0.043 | -0.043 | 0.03 |
| M30 | Trend-following pullback | short | -0.042 | -0.052 | -0.019 | +0.109 | -0.036 | 0.03 |
| M30 | Volatility expansion | long | -0.007 | +0.003 | +0.041 | +0.207 | +0.027 | 0.00 |
| M30 | Volatility expansion | short | +0.001 | -0.018 | -0.004 | +0.042 | +0.007 | 0.01 |
| M5 | Breakout and retest | long | -0.053 | -0.121 | -0.037 | -0.009 | -0.036 | 0.00 |
| M5 | Breakout and retest | short | -0.032 | -0.092 | -0.013 | +0.029 | -0.011 | 0.00 |
| M5 | Momentum continuation | long | -0.422 | -0.419 | -0.384 | -0.276 | -0.393 | 0.04 |
| M5 | Momentum continuation | short | -0.485 | -0.324 | -0.306 | -0.242 | -0.300 | 0.00 |
| M5 | Liquidity-sweep reversal | long | -0.129 | -0.180 | -0.125 | -0.119 | -0.125 | 0.01 |
| M5 | Liquidity-sweep reversal | short | -0.142 | -0.198 | -0.138 | -0.115 | -0.139 | 0.01 |
| M5 | Trend-following pullback | long | -0.136 | -0.162 | -0.127 | -0.115 | -0.127 | 0.04 |
| M5 | Trend-following pullback | short | -0.093 | -0.127 | -0.084 | -0.066 | -0.090 | 0.03 |
| M5 | Volatility expansion | long | -0.066 | -0.105 | -0.045 | -0.084 | -0.049 | 0.01 |
| M5 | Volatility expansion | short | -0.085 | -0.127 | -0.081 | -0.118 | -0.074 | 0.01 |

## Regime classifier usefulness (descriptive)

| TF | Strategy | Side | Inside compatible regimes: exp. R | Outside them: trades | Outside: exp. R |
|---|---|---|---|---|---|
| D1 | Breakout and retest | long | -0.200 | 6 | +1.950 |
| D1 | Breakout and retest | short | -0.312 | 2 | -1.000 |
| H1 | Breakout and retest | long | +0.221 | 147 | +0.195 |
| H1 | Breakout and retest | short | +0.085 | 176 | +0.180 |
| H1 | Liquidity-sweep reversal | long | -0.054 | 151 | +0.020 |
| H1 | Liquidity-sweep reversal | short | -0.089 | 159 | -0.044 |
| H1 | Trend-following pullback | long | +0.066 | 0 | — |
| H1 | Trend-following pullback | short | -0.081 | 0 | — |
| H1 | Volatility expansion | long | +0.078 | 71 | +0.111 |
| H1 | Volatility expansion | short | +0.116 | 81 | +0.043 |
| H4 | Breakout and retest | long | +0.161 | 43 | +0.047 |
| H4 | Breakout and retest | short | +0.192 | 30 | +0.357 |
| H4 | Liquidity-sweep reversal | long | +0.095 | 36 | +0.437 |
| H4 | Liquidity-sweep reversal | short | +0.034 | 45 | -0.036 |
| H4 | Trend-following pullback | long | +0.406 | 0 | — |
| H4 | Trend-following pullback | short | +0.021 | 0 | — |
| H8 | Breakout and retest | long | +0.136 | 21 | -0.005 |
| H8 | Breakout and retest | short | +0.580 | 12 | +0.242 |
| H8 | Liquidity-sweep reversal | long | +0.020 | 18 | +0.122 |
| H8 | Liquidity-sweep reversal | short | -0.008 | 25 | -0.056 |
| H8 | Trend-following pullback | long | +0.341 | 0 | — |
| M15 | Breakout and retest | long | -0.023 | 494 | +0.082 |
| M15 | Breakout and retest | short | -0.017 | 615 | -0.032 |
| M15 | Liquidity-sweep reversal | long | -0.134 | 794 | -0.061 |
| M15 | Liquidity-sweep reversal | short | -0.092 | 755 | -0.099 |
| M15 | Trend-following pullback | long | -0.036 | 0 | — |
| M15 | Trend-following pullback | short | -0.115 | 0 | — |
| M15 | Volatility expansion | long | -0.093 | 295 | -0.166 |
| M15 | Volatility expansion | short | -0.054 | 286 | +0.086 |
| M30 | Breakout and retest | long | +0.022 | 274 | +0.156 |
| M30 | Breakout and retest | short | -0.029 | 330 | +0.041 |
| M30 | Liquidity-sweep reversal | long | -0.070 | 341 | -0.052 |
| M30 | Liquidity-sweep reversal | short | -0.075 | 359 | +0.005 |
| M30 | Trend-following pullback | long | -0.043 | 0 | — |
| M30 | Trend-following pullback | short | -0.036 | 0 | — |
| M30 | Volatility expansion | long | +0.027 | 146 | -0.046 |
| M30 | Volatility expansion | short | +0.007 | 165 | -0.113 |
| M5 | Breakout and retest | long | -0.039 | 1443 | +0.024 |
| M5 | Breakout and retest | short | -0.012 | 1779 | +0.000 |
| M5 | Momentum continuation | long | -0.393 | 274 | -0.130 |
| M5 | Momentum continuation | short | -0.300 | 280 | -0.222 |
| M5 | Liquidity-sweep reversal | long | -0.126 | 2426 | -0.065 |
| M5 | Liquidity-sweep reversal | short | -0.140 | 2516 | -0.057 |
| M5 | Trend-following pullback | long | -0.128 | 0 | — |
| M5 | Trend-following pullback | short | -0.090 | 0 | — |
| M5 | Volatility expansion | long | -0.049 | 734 | -0.159 |
| M5 | Volatility expansion | short | -0.074 | 831 | -0.115 |

## Cells not tested (37: fewer than 100 development signals, decided on counts only)

M5 Range mean reversion long (4), M5 Range mean reversion short (1), M15 Momentum continuation long (33), M15 Momentum continuation short (38), M15 Range mean reversion long (0), M15 Range mean reversion short (1), M30 Momentum continuation long (22), M30 Momentum continuation short (16), M30 Range mean reversion long (0), M30 Range mean reversion short (0), H1 Momentum continuation long (11), H1 Momentum continuation short (9), H1 Range mean reversion long (0), H1 Range mean reversion short (0), H4 Momentum continuation long (12), H4 Momentum continuation short (6), H4 Range mean reversion long (0), H4 Range mean reversion short (0), H4 Volatility expansion long (77), H4 Volatility expansion short (86), H8 Trend-following pullback short (80), H8 Momentum continuation long (4), H8 Momentum continuation short (3), H8 Range mean reversion long (0), H8 Range mean reversion short (0), H8 Volatility expansion long (38), H8 Volatility expansion short (37), D1 Trend-following pullback long (32), D1 Trend-following pullback short (25), D1 Momentum continuation long (0), D1 Momentum continuation short (3), D1 Range mean reversion long (0), D1 Range mean reversion short (0), D1 Liquidity-sweep reversal long (59), D1 Liquidity-sweep reversal short (54), D1 Volatility expansion long (13), D1 Volatility expansion short (16)


## Method and deviations fixed before any outcome

- **entries**: the engine's READY plans enter at the next candle's open (ask to buy, bid to sell); pending LIMIT plans are limit orders that fill only when price trades 1 tick through, cancelled by a close beyond the invalidation, waiting the group's expiry; pending STOP entries (strategies A and C) are not simulated as orders: the engine re-detects them as READY at the close beyond the trigger, which is simulated (a slightly worse price than an intrabar stop fill)
- **stop**: the plan's stop (invalidation + 0.1 ATR + the candle's spread), checked on bid/ask 1-minute paths, stop first inside a minute
- **target**: TP1 only, full position, measured at its R from the actual fill rounded DOWN to 0.1R (conservative); partial exits descriptive
- **horizon**: 96 candles (the longest horizon the control pools store) stands in for 'no time stop'; trades still open are valued at the close of candle 96 and their share is reported; 48 candles = sensitivity
- **overlap**: one trade at a time per cell (strategy x direction x timeframe): a signal while the cell's previous trade is open is skipped
- **controls**: the gold study's matched random-entry pools (same segment, entry type, risk or distance/width bucket, direction, NY session, volatility, period); H8 pool built with the same builder
- **walk forward**: no parameter is fitted, so every development year is already out of sample: the walk-forward reduces to the yearly breakdown
- **ci method**: cluster-robust SE with weekly clusters (the study's tested method) instead of a block bootstrap
- **regime usefulness**: the same strategies outside their compatible regimes are simulated for description only

## Limitations

- EURUSD and GBPUSD were not tested: Dukascopy refused or throttled most download requests during the release; the download resumes and the FX part can run when it completes (same pre-registered rules).
- The training segment was examined by experiments 1-4 (other rules); the deflated Sharpe counts all their trials.
- Slippage beyond the real spread, commission and swap are not in the main result; the 2× spread column is the cost stress test.
- Historical performance, even when positive, does not guarantee future results.
