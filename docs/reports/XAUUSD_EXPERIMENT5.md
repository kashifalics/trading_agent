# Experiment 5: strategy engine v2 on XAUUSD (owner-approved plan, 2026-11-13)

Plan: `docs/engine_v2/EXPERIMENT_PLAN.md`. Pre-registration (counts only, committed before any outcome): `docs/research/XAUUSD_exp5_preregistration.json` (sha256 `ed78f07b7f57e037…`). Development result: `docs/research/XAUUSD_exp5_development.json`.

**The sealed final-test period was not read.** Development used the training segment (2003-05-05 to 2020-02-08); validation (2020-02-08 to 2023-06-24) is read only for cells that pass development.

## Result

**No strategy passed.** Of 84 pre-registered cells (6 strategies × 2 directions × 7 timeframes), 51 had at least 100 development trades and were tested; **none met all development criteria**, so nothing was carried to validation and every strategy stays **NOT VALIDATED** in the product.

**In numbers:** 65,103 simulated trades across the tested cells, a trade-weighted mean of -0.150R per trade after the real spread. 13 of 51 cells had a positive mean, 10 of them on the long side: gold rose strongly over the training years, which favours long trades of any rule. No cell kept a positive mean after every pre-registered check.

Trials counted for the deflated Sharpe ratio: 2032 (experiments 1-5); the highest deflated Sharpe probability was 0.51 (needed: 0.95). CSCV probability of backtest overfitting across the tested cells: 0.17.

## Development results per tested cell (training segment, after real bid/ask; TP1 full exit, 96-candle horizon)

| TF | Strategy | Side | Trades | Win | Avg win | Avg loss | Exp. R | 95% CI | PF | Max DD R | Edge vs random | BH q | DSR | Years + | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | Breakout and retest | long | 96 | 0.38 | +1.89 | -1.00 | +0.084 | [-0.243, +0.412] | 1.13 | 11.0 | +0.041 | 0.725 | 0.13 | 0.44 | failed |
| D1 | Breakout and retest | short | 84 | 0.30 | +1.79 | -1.00 | -0.171 | [-0.440, +0.099] | 0.76 | 22.8 | -0.033 | 0.844 | 0.00 | 0.38 | failed |
| D1 | Liquidity-sweep reversal | long | 74 | 0.42 | +1.64 | -0.99 | +0.112 | [-0.165, +0.389] | 1.20 | 7.0 | -0.059 | 0.887 | 0.22 | 0.56 | failed |
| D1 | Liquidity-sweep reversal | short | 67 | 0.34 | +1.71 | -1.00 | -0.069 | [-0.398, +0.260] | 0.89 | 14.7 | +0.025 | 0.761 | 0.04 | 0.50 | failed |
| H1 | Breakout and retest | long | 1,193 | 0.36 | +1.82 | -1.00 | +0.003 | [-0.072, +0.079] | 1.01 | 31.7 | +0.163 | 0.000 | 0.00 | 0.50 | failed |
| H1 | Breakout and retest | short | 1,119 | 0.34 | +1.84 | -1.01 | -0.037 | [-0.113, +0.039] | 0.94 | 82.3 | +0.153 | 0.001 | 0.00 | 0.39 | failed |
| H1 | Liquidity-sweep reversal | long | 1,333 | 0.37 | +1.54 | -1.00 | -0.065 | [-0.130, -0.001] | 0.90 | 93.0 | -0.008 | 0.844 | 0.00 | 0.33 | failed |
| H1 | Liquidity-sweep reversal | short | 1,328 | 0.33 | +1.68 | -1.00 | -0.109 | [-0.175, -0.044] | 0.84 | 167.4 | -0.012 | 0.875 | 0.00 | 0.22 | failed |
| H1 | Trend-following pullback | long | 465 | 0.36 | +1.59 | -1.00 | -0.060 | [-0.173, +0.053] | 0.91 | 42.5 | -0.034 | 0.924 | 0.00 | 0.44 | failed |
| H1 | Trend-following pullback | short | 423 | 0.33 | +1.72 | -1.00 | -0.103 | [-0.219, +0.014] | 0.85 | 45.6 | -0.054 | 0.924 | 0.00 | 0.22 | failed |
| H1 | Volatility expansion | long | 220 | 0.41 | +1.62 | -1.00 | +0.071 | [-0.100, +0.242] | 1.12 | 18.9 | +0.138 | 0.185 | 0.04 | 0.50 | failed |
| H1 | Volatility expansion | short | 255 | 0.29 | +1.77 | -1.00 | -0.187 | [-0.342, -0.031] | 0.74 | 55.4 | -0.105 | 0.924 | 0.00 | 0.35 | failed |
| H4 | Breakout and retest | long | 402 | 0.40 | +1.81 | -1.00 | +0.124 | [-0.014, +0.261] | 1.21 | 13.3 | +0.177 | 0.032 | 0.04 | 0.59 | failed |
| H4 | Breakout and retest | short | 324 | 0.40 | +1.84 | -1.00 | +0.123 | [-0.027, +0.273] | 1.20 | 12.1 | +0.265 | 0.003 | 0.06 | 0.71 | failed |
| H4 | Liquidity-sweep reversal | long | 396 | 0.42 | +1.59 | -0.99 | +0.103 | [-0.026, +0.233] | 1.18 | 15.6 | +0.059 | 0.446 | 0.03 | 0.72 | failed |
| H4 | Liquidity-sweep reversal | short | 384 | 0.35 | +1.69 | -1.00 | -0.045 | [-0.171, +0.080] | 0.93 | 41.1 | +0.053 | 0.446 | 0.00 | 0.50 | failed |
| H4 | Trend-following pullback | long | 190 | 0.46 | +1.66 | -0.99 | +0.221 | [+0.031, +0.412] | 1.41 | 8.3 | +0.030 | 0.725 | 0.46 | 0.67 | failed |
| H4 | Trend-following pullback | short | 133 | 0.37 | +1.58 | -0.98 | -0.037 | [-0.243, +0.168] | 0.94 | 11.7 | +0.027 | 0.725 | 0.01 | 0.47 | failed |
| H8 | Breakout and retest | long | 265 | 0.40 | +1.89 | -1.01 | +0.139 | [-0.048, +0.325] | 1.23 | 17.0 | +0.173 | 0.146 | 0.10 | 0.65 | failed |
| H8 | Breakout and retest | short | 184 | 0.39 | +1.85 | -1.00 | +0.115 | [-0.067, +0.298] | 1.19 | 13.0 | +0.247 | 0.026 | 0.10 | 0.59 | failed |
| H8 | Liquidity-sweep reversal | long | 210 | 0.44 | +1.60 | -1.00 | +0.140 | [-0.037, +0.318] | 1.25 | 10.6 | +0.040 | 0.659 | 0.17 | 0.65 | failed |
| H8 | Liquidity-sweep reversal | short | 187 | 0.30 | +1.70 | -1.00 | -0.181 | [-0.375, +0.013] | 0.74 | 42.9 | -0.111 | 0.924 | 0.00 | 0.35 | failed |
| H8 | Trend-following pullback | long | 103 | 0.46 | +1.72 | -1.00 | +0.241 | [-0.030, +0.511] | 1.44 | 9.2 | -0.022 | 0.844 | 0.51 | 0.59 | failed |
| H8 | Trend-following pullback | short | 67 | 0.37 | +1.47 | -0.94 | -0.040 | [-0.340, +0.260] | 0.93 | 11.2 | -0.012 | 0.844 | 0.05 | 0.44 | failed |
| M15 | Breakout and retest | long | 2,707 | 0.32 | +1.58 | -1.00 | -0.166 | [-0.211, -0.121] | 0.75 | 456.2 | +0.055 | 0.054 | 0.00 | 0.06 | failed |
| M15 | Breakout and retest | short | 2,490 | 0.30 | +1.84 | -1.00 | -0.137 | [-0.188, -0.086] | 0.80 | 355.7 | +0.097 | 0.001 | 0.00 | 0.17 | failed |
| M15 | Momentum continuation | long | 89 | 0.29 | +1.49 | -0.99 | -0.264 | [-0.489, -0.040] | 0.62 | 23.7 | -0.147 | 0.924 | 0.00 | 0.47 | failed |
| M15 | Liquidity-sweep reversal | long | 3,723 | 0.35 | +1.44 | -0.99 | -0.149 | [-0.186, -0.113] | 0.77 | 567.0 | -0.016 | 0.924 | 0.00 | 0.11 | failed |
| M15 | Liquidity-sweep reversal | short | 3,666 | 0.31 | +1.71 | -0.99 | -0.152 | [-0.194, -0.111] | 0.78 | 559.6 | -0.014 | 0.924 | 0.00 | 0.00 | failed |
| M15 | Trend-following pullback | long | 1,256 | 0.37 | +1.48 | -0.98 | -0.067 | [-0.134, +0.000] | 0.89 | 107.2 | +0.041 | 0.296 | 0.00 | 0.44 | failed |
| M15 | Trend-following pullback | short | 1,176 | 0.32 | +1.74 | -0.99 | -0.117 | [-0.190, -0.044] | 0.83 | 158.3 | +0.002 | 0.796 | 0.00 | 0.39 | failed |
| M15 | Volatility expansion | long | 567 | 0.34 | +1.61 | -1.00 | -0.110 | [-0.213, -0.008] | 0.83 | 76.1 | +0.064 | 0.296 | 0.00 | 0.39 | failed |
| M15 | Volatility expansion | short | 613 | 0.33 | +1.84 | -1.00 | -0.060 | [-0.166, +0.046] | 0.91 | 45.9 | +0.092 | 0.159 | 0.00 | 0.35 | failed |
| M30 | Breakout and retest | long | 2,097 | 0.35 | +1.69 | -1.00 | -0.068 | [-0.125, -0.011] | 0.90 | 151.9 | +0.141 | 0.000 | 0.00 | 0.22 | failed |
| M30 | Breakout and retest | short | 1,960 | 0.31 | +1.89 | -1.00 | -0.095 | [-0.153, -0.037] | 0.86 | 198.9 | +0.117 | 0.001 | 0.00 | 0.17 | failed |
| M30 | Liquidity-sweep reversal | long | 2,349 | 0.35 | +1.49 | -0.99 | -0.123 | [-0.170, -0.075] | 0.81 | 298.8 | -0.024 | 0.924 | 0.00 | 0.11 | failed |
| M30 | Liquidity-sweep reversal | short | 2,386 | 0.31 | +1.71 | -1.00 | -0.165 | [-0.214, -0.116] | 0.76 | 394.2 | -0.050 | 0.975 | 0.00 | 0.11 | failed |
| M30 | Trend-following pullback | long | 732 | 0.37 | +1.51 | -0.99 | -0.060 | [-0.147, +0.026] | 0.90 | 75.4 | -0.005 | 0.844 | 0.00 | 0.28 | failed |
| M30 | Trend-following pullback | short | 626 | 0.34 | +1.72 | -1.00 | -0.072 | [-0.171, +0.027] | 0.89 | 63.5 | +0.030 | 0.590 | 0.00 | 0.39 | failed |
| M30 | Volatility expansion | long | 406 | 0.35 | +1.63 | -1.00 | -0.075 | [-0.200, +0.050] | 0.88 | 52.1 | +0.054 | 0.446 | 0.00 | 0.50 | failed |
| M30 | Volatility expansion | short | 437 | 0.29 | +1.84 | -1.00 | -0.175 | [-0.302, -0.048] | 0.75 | 95.0 | -0.079 | 0.924 | 0.00 | 0.29 | failed |
| M5 | Breakout and retest | long | 4,190 | 0.32 | +1.40 | -1.00 | -0.219 | [-0.255, -0.183] | 0.67 | 922.6 | +0.083 | 0.000 | 0.00 | 0.06 | failed |
| M5 | Breakout and retest | short | 3,822 | 0.27 | +1.79 | -1.00 | -0.263 | [-0.303, -0.223] | 0.64 | 1013.2 | +0.065 | 0.011 | 0.00 | 0.00 | failed |
| M5 | Momentum continuation | long | 136 | 0.29 | +1.31 | -0.99 | -0.327 | [-0.507, -0.148] | 0.53 | 44.5 | -0.114 | 0.924 | 0.00 | 0.19 | failed |
| M5 | Momentum continuation | short | 124 | 0.37 | +1.81 | -0.97 | +0.063 | [-0.187, +0.313] | 1.10 | 14.7 | +0.217 | 0.159 | 0.08 | 0.71 | failed |
| M5 | Liquidity-sweep reversal | long | 7,153 | 0.34 | +1.26 | -0.97 | -0.202 | [-0.230, -0.175] | 0.68 | 1485.8 | +0.020 | 0.252 | 0.00 | 0.06 | failed |
| M5 | Liquidity-sweep reversal | short | 6,728 | 0.29 | +1.63 | -0.99 | -0.219 | [-0.249, -0.188] | 0.69 | 1471.0 | +0.002 | 0.761 | 0.00 | 0.00 | failed |
| M5 | Trend-following pullback | long | 2,379 | 0.33 | +1.29 | -0.96 | -0.209 | [-0.254, -0.164] | 0.67 | 504.5 | -0.025 | 0.924 | 0.00 | 0.06 | failed |
| M5 | Trend-following pullback | short | 2,206 | 0.29 | +1.68 | -0.98 | -0.204 | [-0.256, -0.151] | 0.71 | 450.2 | -0.028 | 0.924 | 0.00 | 0.06 | failed |
| M5 | Volatility expansion | long | 776 | 0.33 | +1.45 | -0.99 | -0.196 | [-0.278, -0.115] | 0.71 | 153.0 | +0.076 | 0.146 | 0.00 | 0.24 | failed |
| M5 | Volatility expansion | short | 807 | 0.28 | +1.79 | -1.00 | -0.236 | [-0.326, -0.146] | 0.68 | 205.1 | +0.070 | 0.201 | 0.00 | 0.24 | failed |

Columns: win = share of trades with R > 0; Exp. R = mean R per trade; CI = cluster-robust 95% interval (weekly clusters); PF = profit factor; edge = mean R minus the matched random-entry control mean; BH q = Benjamini-Hochberg across the tested cells; DSR = deflated Sharpe probability; Years + = share of development years with a positive mean.

## Robustness (development)

| TF | Strategy | Side | Without best year | At 2× spread | 48-candle horizon | Entry one candle late | Optimistic intrabar | Open at horizon |
|---|---|---|---|---|---|---|---|---|
| D1 | Breakout and retest | long | +0.047 | +0.034 | +0.084 | +0.156 | +0.084 | 0.00 |
| D1 | Breakout and retest | short | -0.220 | -0.209 | -0.171 | -0.272 | -0.171 | 0.00 |
| D1 | Liquidity-sweep reversal | long | +0.058 | +0.087 | +0.140 | -0.067 | +0.112 | 0.01 |
| D1 | Liquidity-sweep reversal | short | -0.139 | -0.093 | -0.062 | -0.170 | -0.069 | 0.00 |
| H1 | Breakout and retest | long | -0.013 | -0.127 | +0.005 | +0.049 | +0.006 | 0.00 |
| H1 | Breakout and retest | short | -0.051 | -0.166 | -0.041 | -0.026 | -0.035 | 0.00 |
| H1 | Liquidity-sweep reversal | long | -0.074 | -0.150 | -0.062 | -0.064 | -0.063 | 0.02 |
| H1 | Liquidity-sweep reversal | short | -0.135 | -0.200 | -0.088 | -0.077 | -0.109 | 0.01 |
| H1 | Trend-following pullback | long | -0.075 | -0.140 | -0.039 | -0.024 | -0.060 | 0.01 |
| H1 | Trend-following pullback | short | -0.141 | -0.177 | -0.102 | -0.134 | -0.103 | 0.01 |
| H1 | Volatility expansion | long | +0.057 | -0.010 | +0.069 | -0.079 | +0.071 | 0.01 |
| H1 | Volatility expansion | short | -0.215 | -0.272 | -0.185 | -0.249 | -0.187 | 0.00 |
| H4 | Breakout and retest | long | +0.091 | +0.048 | +0.129 | +0.088 | +0.124 | 0.00 |
| H4 | Breakout and retest | short | +0.083 | +0.050 | +0.123 | +0.202 | +0.123 | 0.00 |
| H4 | Liquidity-sweep reversal | long | +0.099 | +0.057 | +0.093 | +0.098 | +0.103 | 0.02 |
| H4 | Liquidity-sweep reversal | short | -0.066 | -0.089 | -0.037 | -0.086 | -0.045 | 0.01 |
| H4 | Trend-following pullback | long | +0.213 | +0.187 | +0.161 | +0.101 | +0.221 | 0.04 |
| H4 | Trend-following pullback | short | -0.103 | -0.067 | +0.009 | -0.025 | -0.037 | 0.08 |
| H8 | Breakout and retest | long | +0.130 | +0.075 | +0.137 | +0.627 | +0.139 | 0.00 |
| H8 | Breakout and retest | short | +0.105 | +0.061 | +0.123 | +0.355 | +0.115 | 0.00 |
| H8 | Liquidity-sweep reversal | long | +0.066 | +0.106 | +0.125 | +0.115 | +0.140 | 0.00 |
| H8 | Liquidity-sweep reversal | short | -0.234 | -0.211 | -0.177 | -0.140 | -0.181 | 0.01 |
| H8 | Trend-following pullback | long | +0.150 | +0.219 | +0.237 | +0.271 | +0.241 | 0.02 |
| H8 | Trend-following pullback | short | -0.101 | -0.063 | -0.052 | -0.031 | -0.040 | 0.12 |
| M15 | Breakout and retest | long | -0.168 | -0.324 | -0.167 | -0.182 | -0.166 | 0.01 |
| M15 | Breakout and retest | short | -0.138 | -0.304 | -0.138 | -0.138 | -0.136 | 0.00 |
| M15 | Momentum continuation | long | -0.281 | -0.358 | -0.311 | -0.351 | -0.264 | 0.04 |
| M15 | Liquidity-sweep reversal | long | -0.154 | -0.269 | -0.153 | -0.154 | -0.149 | 0.03 |
| M15 | Liquidity-sweep reversal | short | -0.163 | -0.281 | -0.161 | -0.188 | -0.152 | 0.02 |
| M15 | Trend-following pullback | long | -0.071 | -0.172 | -0.080 | -0.083 | -0.067 | 0.05 |
| M15 | Trend-following pullback | short | -0.124 | -0.226 | -0.105 | -0.136 | -0.117 | 0.04 |
| M15 | Volatility expansion | long | -0.114 | -0.245 | -0.132 | -0.164 | -0.110 | 0.01 |
| M15 | Volatility expansion | short | -0.074 | -0.203 | -0.049 | -0.082 | -0.060 | 0.00 |
| M30 | Breakout and retest | long | -0.077 | -0.219 | -0.063 | -0.031 | -0.068 | 0.01 |
| M30 | Breakout and retest | short | -0.108 | -0.250 | -0.091 | -0.050 | -0.095 | 0.00 |
| M30 | Liquidity-sweep reversal | long | -0.130 | -0.226 | -0.108 | -0.124 | -0.122 | 0.03 |
| M30 | Liquidity-sweep reversal | short | -0.170 | -0.276 | -0.161 | -0.175 | -0.165 | 0.01 |
| M30 | Trend-following pullback | long | -0.074 | -0.149 | -0.041 | -0.090 | -0.060 | 0.05 |
| M30 | Trend-following pullback | short | -0.074 | -0.164 | -0.062 | -0.073 | -0.072 | 0.02 |
| M30 | Volatility expansion | long | -0.078 | -0.182 | -0.075 | -0.079 | -0.075 | 0.00 |
| M30 | Volatility expansion | short | -0.202 | -0.285 | -0.167 | -0.155 | -0.175 | 0.00 |
| M5 | Breakout and retest | long | -0.221 | -0.413 | -0.216 | -0.233 | -0.219 | 0.02 |
| M5 | Breakout and retest | short | -0.266 | -0.479 | -0.254 | -0.315 | -0.262 | 0.01 |
| M5 | Momentum continuation | long | -0.402 | -0.476 | -0.329 | -0.322 | -0.327 | 0.06 |
| M5 | Momentum continuation | short | +0.049 | -0.093 | +0.073 | +0.062 | +0.063 | 0.04 |
| M5 | Liquidity-sweep reversal | long | -0.205 | -0.369 | -0.194 | -0.212 | -0.202 | 0.08 |
| M5 | Liquidity-sweep reversal | short | -0.226 | -0.405 | -0.215 | -0.234 | -0.219 | 0.05 |
| M5 | Trend-following pullback | long | -0.230 | -0.352 | -0.195 | -0.202 | -0.209 | 0.10 |
| M5 | Trend-following pullback | short | -0.207 | -0.367 | -0.200 | -0.218 | -0.204 | 0.06 |
| M5 | Volatility expansion | long | -0.197 | -0.385 | -0.214 | -0.209 | -0.196 | 0.02 |
| M5 | Volatility expansion | short | -0.246 | -0.453 | -0.243 | -0.176 | -0.236 | 0.01 |

## Regime classifier usefulness (descriptive)

| TF | Strategy | Side | Inside compatible regimes: exp. R | Outside them: trades | Outside: exp. R |
|---|---|---|---|---|---|
| D1 | Breakout and retest | long | +0.084 | 16 | +0.362 |
| D1 | Breakout and retest | short | -0.171 | 15 | -0.407 |
| D1 | Liquidity-sweep reversal | long | +0.112 | 18 | +0.566 |
| D1 | Liquidity-sweep reversal | short | -0.069 | 11 | +0.191 |
| H1 | Breakout and retest | long | +0.003 | 283 | +0.016 |
| H1 | Breakout and retest | short | -0.037 | 321 | -0.079 |
| H1 | Liquidity-sweep reversal | long | -0.065 | 293 | -0.036 |
| H1 | Liquidity-sweep reversal | short | -0.109 | 240 | -0.099 |
| H1 | Trend-following pullback | long | -0.060 | 0 | — |
| H1 | Trend-following pullback | short | -0.103 | 0 | — |
| H1 | Volatility expansion | long | +0.071 | 147 | +0.165 |
| H1 | Volatility expansion | short | -0.187 | 174 | +0.018 |
| H4 | Breakout and retest | long | +0.124 | 80 | +0.241 |
| H4 | Breakout and retest | short | +0.123 | 79 | -0.029 |
| H4 | Liquidity-sweep reversal | long | +0.103 | 89 | -0.054 |
| H4 | Liquidity-sweep reversal | short | -0.045 | 54 | -0.056 |
| H4 | Trend-following pullback | long | +0.221 | 0 | — |
| H4 | Trend-following pullback | short | -0.037 | 0 | — |
| H8 | Breakout and retest | long | +0.139 | 60 | -0.013 |
| H8 | Breakout and retest | short | +0.115 | 39 | -0.035 |
| H8 | Liquidity-sweep reversal | long | +0.140 | 41 | +0.014 |
| H8 | Liquidity-sweep reversal | short | -0.181 | 38 | +0.124 |
| H8 | Trend-following pullback | long | +0.241 | 0 | — |
| H8 | Trend-following pullback | short | -0.040 | 0 | — |
| M15 | Breakout and retest | long | -0.166 | 492 | -0.119 |
| M15 | Breakout and retest | short | -0.137 | 569 | -0.235 |
| M15 | Momentum continuation | long | -0.264 | 160 | -0.191 |
| M15 | Liquidity-sweep reversal | long | -0.149 | 726 | -0.141 |
| M15 | Liquidity-sweep reversal | short | -0.152 | 630 | -0.093 |
| M15 | Trend-following pullback | long | -0.067 | 0 | — |
| M15 | Trend-following pullback | short | -0.117 | 0 | — |
| M15 | Volatility expansion | long | -0.110 | 358 | -0.076 |
| M15 | Volatility expansion | short | -0.060 | 372 | -0.137 |
| M30 | Breakout and retest | long | -0.068 | 397 | -0.097 |
| M30 | Breakout and retest | short | -0.095 | 464 | -0.033 |
| M30 | Liquidity-sweep reversal | long | -0.123 | 510 | -0.135 |
| M30 | Liquidity-sweep reversal | short | -0.165 | 472 | -0.069 |
| M30 | Trend-following pullback | long | -0.060 | 0 | — |
| M30 | Trend-following pullback | short | -0.072 | 0 | — |
| M30 | Volatility expansion | long | -0.075 | 253 | -0.146 |
| M30 | Volatility expansion | short | -0.175 | 270 | -0.187 |
| M5 | Breakout and retest | long | -0.219 | 1807 | -0.190 |
| M5 | Breakout and retest | short | -0.263 | 1966 | -0.214 |
| M5 | Momentum continuation | long | -0.327 | 444 | -0.160 |
| M5 | Momentum continuation | short | +0.063 | 401 | -0.190 |
| M5 | Liquidity-sweep reversal | long | -0.202 | 1093 | -0.161 |
| M5 | Liquidity-sweep reversal | short | -0.219 | 992 | -0.141 |
| M5 | Trend-following pullback | long | -0.209 | 0 | — |
| M5 | Trend-following pullback | short | -0.204 | 0 | — |
| M5 | Volatility expansion | long | -0.196 | 483 | -0.234 |
| M5 | Volatility expansion | short | -0.236 | 536 | -0.212 |

## Cells not tested (33: fewer than 100 development signals, decided on counts only)

M5 Range mean reversion long (0), M5 Range mean reversion short (0), M15 Momentum continuation short (75), M15 Range mean reversion long (1), M15 Range mean reversion short (2), M30 Momentum continuation long (63), M30 Momentum continuation short (46), M30 Range mean reversion long (0), M30 Range mean reversion short (0), H1 Momentum continuation long (54), H1 Momentum continuation short (19), H1 Range mean reversion long (0), H1 Range mean reversion short (0), H4 Momentum continuation long (24), H4 Momentum continuation short (14), H4 Range mean reversion long (0), H4 Range mean reversion short (0), H4 Volatility expansion long (84), H4 Volatility expansion short (89), H8 Momentum continuation long (18), H8 Momentum continuation short (14), H8 Range mean reversion long (0), H8 Range mean reversion short (0), H8 Volatility expansion long (95), H8 Volatility expansion short (76), D1 Trend-following pullback long (61), D1 Trend-following pullback short (56), D1 Momentum continuation long (1), D1 Momentum continuation short (6), D1 Range mean reversion long (0), D1 Range mean reversion short (0), D1 Volatility expansion long (28), D1 Volatility expansion short (18)


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
