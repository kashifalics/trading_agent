# XAUUSD independent research audit

_Generated 2026-11-09T17:59:13+00:00 by `python -m app.gold_research audit` from the stored training-period files. Scope: training period only (2003-05-05 to 2020-02-08); validation not yet run; final test sealed and not read. Nothing here changes the frozen split, reads the sealed final-test period or promotes anything. Analysis only._

## Summary

* **Multiple testing.** 1,452 pre-registered training tests. BH keeps 52 at q < 0.10 and 37 at q < 0.05; only 12 survive Bonferroni and 12 survive Holm. Storey's estimate says about 88% of all tests are pure noise and the estimated false-discovery rate among the 52 candidates is 8% (about 4.2 expected false ones).
* **Profitability is the weak point.** Tests are about beating matched random trades; on raw profit after the spread only 27 of 1,452 tests reach nominal p < 0.05 (about 73 would by chance) and 2 survive BH.
* **Backtest overfitting.** Choosing the best of these tests in one half of the training years and checking it in the other half (CSCV, 12,870 splits of 16 year blocks): probability of overfitting 38% on edge and 18% on mean R; the selected test's out-of-sample result is below zero in 58% of splits (mean R).

## 1. Multiple testing and overfitting

| Measure | Value |
|---|---|
| Tests (pattern / combination / multi-timeframe x timeframe x direction, >= 100 trades) | 1,452 |
| Benjamini-Hochberg q < 0.10 (the frozen candidates) / q < 0.05 | 52 / 37 |
| Bonferroni p < 0.05/1452 | 12 |
| Holm (alpha 0.05) | 12 |
| Storey pi0 (share of true nulls, lambda 0.5) | 0.877 |
| Estimated FDR at the candidate threshold | 8.1% |
| Tests with a positive edge (any size) | 56.1% |
| Profit tests (mean R > 0): nominal p < 0.05 / BH q < 0.10 | 27 / 2 |

Tests are correlated (the same trades feed a pattern, its combinations and its multi-timeframe variants), so the effective number of independent tests is smaller than the count; BH stays valid under the positive dependence this creates, Bonferroni and Holm are conservative.

**Probability of backtest overfitting (CSCV).** Per-year totals for every test; all ways of splitting the 16 year blocks (2003-2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019-2020) into two halves; in each, the best test in one half is ranked in the other.

| Selection metric | Strategies | Splits | PBO | Median logit | Selected: in-sample mean | Selected: out-of-sample mean | P(out-of-sample < 0) |
|---|---|---|---|---|---|---|---|
| edge | 1,430 | 12,870 | 38.4% | +1.21 | +0.498 | +0.022 | 37% |
| mean_r | 1,430 | 12,870 | 18.0% | +1.57 | +0.458 | -0.045 | 58% |

**Reproducibility.** The 52 frozen candidates recomputed from the current training files:

52 of 52 reproduce exactly (same trade count and edge).

## Candidate: H1 round50_reaction long

Training: 530 trades, win rate 36%, mean R +0.075 +/- 0.082 (p = 0.180 for mean R > 0), matched long controls -0.193, edge +0.268 +/- 0.077, profit factor 1.12, 170 independent time clusters.

* Deflated Sharpe ratio (per trade, 530 observations): Sharpe per trade 0.0524 versus 0.1390, the best a no-edge test would show by luck among 1,452; probability the true Sharpe is above that: 2.2%.
* Deflated Sharpe ratio (per time cluster, 170 observations): Sharpe per trade 0.0524 versus 0.1877, the best a no-edge test would show by luck among 1,452; probability the true Sharpe is above that: 3.7%.

**2. Cost stress (training trades).** Spread multiplied on every trade; slippage charged on entry and exit.

| Spread | Slippage / side | Mean R | 95% CI | Win % | Profit factor | p (mean > 0) |
|---|---|---|---|---|---|---|
| x1 | $0.00 | +0.075 | -0.085 to +0.235 | 36% | 1.12 | 0.180 |
| x1 | $0.05 | +0.032 | -0.130 to +0.193 | 36% | 1.05 | 0.351 |
| x1 | $0.10 | -0.012 | -0.176 to +0.152 | 36% | 0.98 | 0.557 |
| x1 | $0.20 | -0.099 | -0.267 to +0.069 | 36% | 0.87 | 0.875 |
| x1.25 | $0.00 | +0.031 | -0.131 to +0.192 | 36% | 1.05 | 0.356 |
| x1.25 | $0.05 | -0.013 | -0.177 to +0.151 | 36% | 0.98 | 0.561 |
| x1.25 | $0.10 | -0.056 | -0.222 to +0.110 | 36% | 0.92 | 0.746 |
| x1.25 | $0.20 | -0.143 | -0.313 to +0.027 | 36% | 0.82 | 0.949 |
| x1.5 | $0.00 | -0.014 | -0.178 to +0.150 | 36% | 0.98 | 0.565 |
| x1.5 | $0.05 | -0.057 | -0.223 to +0.109 | 36% | 0.92 | 0.750 |
| x1.5 | $0.10 | -0.101 | -0.269 to +0.068 | 36% | 0.87 | 0.879 |
| x1.5 | $0.20 | -0.187 | -0.360 to -0.015 | 36% | 0.77 | 0.983 |

Break-even: the mean turns to zero with about $0.17 of extra cost per round trip (median spread $0.40, median risk $2.68).

**4. Long-term drift.**

* Matched random LONG trades (same entry type, stop size, session, volatility, year): -0.193R; the candidate's edge over them: +0.268R.
* The same signals traded SHORT (mirror stop, 2R, 48 candles): 530 trades, mean R -0.352 +/- 0.066.
* The bearish version of the pattern: 471 trades, mean R -0.155, edge +0.095
* In the 4 training years when gold fell: 2013 (-28%): n=30, mean R +0.40, 2014 (-2%): n=19, mean R +0.26, 2015 (-10%): n=19, mean R +1.21, 2018 (-2%): n=22, mean R -0.32.

Random market entries at the candidate's typical stop size, long versus short, by year (training):

| Year | Random long mean R | Random short mean R |
|---|---|---|
| 2003 | -0.423 | -0.504 |
| 2004 | -0.465 | -0.461 |
| 2005 | -0.457 | -0.488 |
| 2006 | -0.148 | -0.263 |
| 2007 | -0.271 | -0.338 |
| 2008 | -0.120 | -0.177 |
| 2009 | -0.151 | -0.268 |
| 2010 | -0.152 | -0.309 |
| 2011 | -0.062 | -0.161 |
| 2012 | -0.195 | -0.084 |
| 2013 | -0.289 | -0.033 |
| 2014 | -0.141 | -0.103 |
| 2015 | -0.202 | -0.016 |
| 2016 | -0.134 | -0.085 |
| 2017 | -0.095 | -0.151 |
| 2018 | -0.148 | -0.000 |
| 2019 | -0.125 | -0.143 |
| 2020 | +0.031 | -0.108 |

**5. Stability.** Positive mean R in 9 of 17 training years.

| Year | Trades | Win % | Mean R | Edge | Gold that year |
|---|---|---|---|---|---|
| 2004 | 21 | 10% | -0.71 | -0.24 | 5% |
| 2005 | 2 | 0% | -1.00 | -0.39 | 18% |
| 2006 | 65 | 37% | +0.06 | +0.33 | 23% |
| 2007 | 46 | 28% | -0.18 | +0.11 | 31% |
| 2008 | 24 | 50% | +0.49 | +0.65 | 6% |
| 2009 | 72 | 31% | -0.09 | +0.11 | 25% |
| 2010 | 37 | 41% | +0.22 | +0.43 | 29% |
| 2011 | 61 | 46% | +0.37 | +0.42 | 10% |
| 2012 | 38 | 32% | -0.09 | +0.11 | 7% |
| 2013 | 30 | 47% | +0.40 | +0.62 | -28% |
| 2014 | 19 | 42% | +0.26 | +0.39 | -2% |
| 2015 | 19 | 74% | +1.21 | +1.35 | -10% |
| 2016 | 30 | 23% | -0.33 | -0.15 | 8% |
| 2017 | 31 | 39% | +0.14 | +0.25 | 13% |
| 2018 | 22 | 23% | -0.32 | -0.19 | -2% |
| 2019 | 4 | 25% | -0.25 | -0.17 | 18% |
| 2020 | 9 | 44% | +0.13 | +0.20 | 3% |

| session | Trades | Mean R | Edge |
|---|---|---|---|
| asia | 128 | +0.06 | +0.30 |
| london | 100 | -0.01 | +0.28 |
| new_york | 139 | +0.16 | +0.33 |
| overlap | 147 | +0.10 | +0.19 |
| rollover | 16 | -0.25 | +0.12 |

| vol level | Trades | Mean R | Edge |
|---|---|---|---|
| extreme | 93 | +0.13 | +0.28 |
| high | 124 | +0.09 | +0.29 |
| low | 94 | +0.15 | +0.33 |
| normal | 178 | -0.02 | +0.19 |
| very_low | 41 | +0.17 | +0.36 |

| trend regime | Trades | Mean R | Edge |
|---|---|---|---|
| moderate_bearish | 87 | +0.37 | +0.57 |
| moderate_bullish | 152 | +0.06 | +0.28 |
| none | 95 | -0.17 | +0.02 |
| strong_bearish | 11 | -0.73 | -0.53 |
| strong_bullish | 11 | +0.36 | +0.55 |
| weak_bearish | 84 | +0.01 | +0.20 |
| weak_bullish | 90 | +0.19 | +0.35 |

| structural regime | Trades | Mean R | Edge |
|---|---|---|---|
| distribution_like | 4 | -0.25 | -0.17 |
| none | 187 | +0.23 | +0.41 |
| reaccumulation_like | 6 | +1.00 | +1.05 |
| redistribution_like | 3 | -1.00 | -0.77 |
| trend_transition | 330 | -0.01 | +0.19 |

**7. Execution realism.**

* Entry: next candle open after the signal candle closes (ask for longs); 1-candle-late edge in training +0.250R (n=470).
* Stop: signal candle low - 0.1 ATR (at least 0.25 ATR from entry), exit at bid; stop minute that opens beyond the stop fills at that open. Target: 2R limit at the bid; touch fills (no queue modelling).
* Risk per trade: median $2.68 (0.81 ATR), 5th percentile $1.07; 0.0% of trades risk under $0.50 and 3.2% under $1.00 (stops that close can be below a broker's minimum stop distance).
* Spread as a share of risk: median 14.1%, 95th percentile 40.3%.
* Stops filled beyond the stop price (gaps): 4.9%; worst -1.14R.
* Intrabar assumption (stop counted first inside a minute): flipping it changes 0.00% of results.
* Entries during the 17:00-19:00 New York rollover (wide spreads): 3.0%, mean R -0.25.
* Overlapping positions if every signal were taken: median 2, maximum 15.
* Stopped out within 12 / 24 / 48 / 96 candles: 65% / 75% / 81% / 84%.

## Candidate: M30 displacement long

Training: 1,872 trades, win rate 42%, mean R +0.060 +/- 0.031 (p = 0.028 for mean R > 0), matched long controls -0.048, edge +0.107 +/- 0.032, profit factor 1.11, 697 independent time clusters.

* Deflated Sharpe ratio (per trade, 1,872 observations): Sharpe per trade 0.0479 versus 0.1390, the best a no-edge test would show by luck among 1,452; probability the true Sharpe is above that: 0.0%.
* Deflated Sharpe ratio (per time cluster, 697 observations): Sharpe per trade 0.0479 versus 0.1877, the best a no-edge test would show by luck among 1,452; probability the true Sharpe is above that: 0.0%.

**2. Cost stress (training trades).** Spread multiplied on every trade; slippage charged on entry and exit.

| Spread | Slippage / side | Mean R | 95% CI | Win % | Profit factor | p (mean > 0) |
|---|---|---|---|---|---|---|
| x1 | $0.00 | +0.060 | -0.002 to +0.121 | 42% | 1.11 | 0.028 |
| x1 | $0.05 | +0.041 | -0.020 to +0.103 | 42% | 1.08 | 0.092 |
| x1 | $0.10 | +0.023 | -0.038 to +0.084 | 41% | 1.04 | 0.226 |
| x1 | $0.20 | -0.013 | -0.074 to +0.048 | 41% | 0.98 | 0.660 |
| x1.25 | $0.00 | +0.043 | -0.018 to +0.104 | 42% | 1.08 | 0.084 |
| x1.25 | $0.05 | +0.025 | -0.036 to +0.086 | 42% | 1.05 | 0.211 |
| x1.25 | $0.10 | +0.007 | -0.054 to +0.068 | 41% | 1.01 | 0.413 |
| x1.25 | $0.20 | -0.029 | -0.090 to +0.032 | 40% | 0.95 | 0.828 |
| x1.5 | $0.00 | +0.027 | -0.034 to +0.088 | 42% | 1.05 | 0.197 |
| x1.5 | $0.05 | +0.008 | -0.052 to +0.069 | 41% | 1.02 | 0.393 |
| x1.5 | $0.10 | -0.010 | -0.071 to +0.051 | 41% | 0.98 | 0.622 |
| x1.5 | $0.20 | -0.046 | -0.107 to +0.015 | 40% | 0.92 | 0.930 |

Break-even: the mean turns to zero with about $0.33 of extra cost per round trip (median spread $0.36, median risk $5.91).

**4. Long-term drift.**

* Matched random LONG trades (same entry type, stop size, session, volatility, year): -0.048R; the candidate's edge over them: +0.107R.
* The same signals traded SHORT (mirror stop, 2R, 48 candles): 1,872 trades, mean R -0.120 +/- 0.029.
* The bearish version of the pattern: 1,834 trades, mean R -0.084, edge -0.023
* In the 4 training years when gold fell: 2013 (-28%): n=134, mean R -0.25, 2014 (-2%): n=112, mean R -0.01, 2015 (-10%): n=117, mean R -0.04, 2018 (-2%): n=123, mean R +0.06.

Random market entries at the candidate's typical stop size, long versus short, by year (training):

| Year | Random long mean R | Random short mean R |
|---|---|---|
| 2003 | -0.106 | -0.329 |
| 2004 | -0.129 | -0.288 |
| 2005 | -0.126 | -0.289 |
| 2006 | -0.019 | -0.162 |
| 2007 | -0.043 | -0.170 |
| 2008 | -0.054 | -0.041 |
| 2009 | -0.029 | -0.176 |
| 2010 | -0.083 | -0.171 |
| 2011 | +0.003 | -0.157 |
| 2012 | -0.166 | +0.003 |
| 2013 | -0.173 | +0.096 |
| 2014 | -0.126 | -0.020 |
| 2015 | -0.155 | +0.070 |
| 2016 | -0.087 | -0.055 |
| 2017 | -0.009 | -0.140 |
| 2018 | -0.088 | -0.011 |
| 2019 | -0.077 | -0.175 |
| 2020 | +0.371 | -0.184 |

**5. Stability.** Positive mean R in 9 of 18 training years.

| Year | Trades | Win % | Mean R | Edge | Gold that year |
|---|---|---|---|---|---|
| 2003 | 6 | 17% | -0.70 | -0.68 | 22% |
| 2004 | 18 | 33% | -0.22 | -0.13 | 5% |
| 2005 | 21 | 52% | +0.14 | +0.16 | 18% |
| 2006 | 72 | 49% | +0.19 | +0.18 | 23% |
| 2007 | 102 | 51% | +0.28 | +0.33 | 31% |
| 2008 | 186 | 41% | +0.08 | +0.12 | 6% |
| 2009 | 152 | 45% | +0.16 | +0.18 | 25% |
| 2010 | 174 | 41% | -0.02 | -0.03 | 29% |
| 2011 | 132 | 45% | +0.11 | +0.08 | 10% |
| 2012 | 134 | 38% | -0.09 | -0.01 | 7% |
| 2013 | 134 | 28% | -0.25 | -0.09 | -28% |
| 2014 | 112 | 40% | -0.01 | +0.08 | -2% |
| 2015 | 117 | 36% | -0.04 | +0.09 | -10% |
| 2016 | 128 | 38% | -0.00 | +0.09 | 8% |
| 2017 | 119 | 54% | +0.33 | +0.35 | 13% |
| 2018 | 123 | 42% | +0.06 | +0.14 | -2% |
| 2019 | 133 | 46% | +0.20 | +0.24 | 18% |
| 2020 | 9 | 33% | -0.06 | -0.52 | 3% |

| session | Trades | Mean R | Edge |
|---|---|---|---|
| asia | 264 | +0.28 | +0.33 |
| london | 408 | +0.03 | +0.11 |
| new_york | 216 | +0.01 | +0.05 |
| overlap | 923 | +0.04 | +0.07 |
| rollover | 61 | -0.18 | -0.13 |

| vol level | Trades | Mean R | Edge |
|---|---|---|---|
| extreme | 357 | +0.03 | +0.07 |
| high | 460 | -0.01 | +0.02 |
| low | 238 | +0.23 | +0.31 |
| normal | 709 | +0.04 | +0.09 |
| very_low | 108 | +0.22 | +0.26 |

| trend regime | Trades | Mean R | Edge |
|---|---|---|---|
| moderate_bearish | 233 | +0.05 | +0.13 |
| moderate_bullish | 493 | +0.07 | +0.12 |
| none | 340 | +0.05 | +0.09 |
| strong_bearish | 3 | +0.00 | +0.03 |
| strong_bullish | 118 | +0.13 | +0.17 |
| weak_bearish | 288 | +0.02 | +0.07 |
| weak_bullish | 397 | +0.06 | +0.10 |

| structural regime | Trades | Mean R | Edge |
|---|---|---|---|
| accumulation_like | 1 | -1.00 | -0.76 |
| distribution_like | 4 | +0.99 | +1.02 |
| none | 571 | +0.12 | +0.17 |
| reaccumulation_like | 23 | +0.02 | +0.09 |
| redistribution_like | 14 | -0.13 | -0.08 |
| trend_transition | 1259 | +0.03 | +0.08 |

**7. Execution realism.**

* Entry: next candle open after the signal candle closes (ask for longs); 1-candle-late edge in training +0.053R (n=1,858).
* Stop: signal candle low - 0.1 ATR (at least 0.25 ATR from entry), exit at bid; stop minute that opens beyond the stop fills at that open. Target: 2R limit at the bid; touch fills (no queue modelling).
* Risk per trade: median $5.91 (2.45 ATR), 5th percentile $2.97; 0.0% of trades risk under $0.50 and 0.0% under $1.00 (stops that close can be below a broker's minimum stop distance).
* Spread as a share of risk: median 6.0%, 95th percentile 12.4%.
* Stops filled beyond the stop price (gaps): 3.2%; worst -2.16R.
* Intrabar assumption (stop counted first inside a minute): flipping it changes 0.00% of results.
* Entries during the 17:00-19:00 New York rollover (wide spreads): 3.3%, mean R -0.18.
* Overlapping positions if every signal were taken: median 1, maximum 7.
* Stopped out within 12 / 24 / 48 / 96 candles: 31% / 39% / 52% / 64%.

## Candidate: M30 bos+displacement long

Training: 806 trades, win rate 43%, mean R +0.119 +/- 0.050 (p = 0.008 for mean R > 0), matched long controls -0.044, edge +0.163 +/- 0.050, profit factor 1.23, 453 independent time clusters.

* Deflated Sharpe ratio (per trade, 806 observations): Sharpe per trade 0.0930 versus 0.1390, the best a no-edge test would show by luck among 1,452; probability the true Sharpe is above that: 9.1%.
* Deflated Sharpe ratio (per time cluster, 453 observations): Sharpe per trade 0.0930 versus 0.1877, the best a no-edge test would show by luck among 1,452; probability the true Sharpe is above that: 2.0%.

**2. Cost stress (training trades).** Spread multiplied on every trade; slippage charged on entry and exit.

| Spread | Slippage / side | Mean R | 95% CI | Win % | Profit factor | p (mean > 0) |
|---|---|---|---|---|---|---|
| x1 | $0.00 | +0.119 | +0.022 to +0.217 | 43% | 1.23 | 0.008 |
| x1 | $0.05 | +0.101 | +0.003 to +0.198 | 43% | 1.19 | 0.022 |
| x1 | $0.10 | +0.082 | -0.015 to +0.179 | 43% | 1.15 | 0.050 |
| x1 | $0.20 | +0.045 | -0.053 to +0.142 | 42% | 1.08 | 0.184 |
| x1.25 | $0.00 | +0.102 | +0.005 to +0.199 | 43% | 1.19 | 0.020 |
| x1.25 | $0.05 | +0.083 | -0.014 to +0.181 | 43% | 1.16 | 0.047 |
| x1.25 | $0.10 | +0.065 | -0.033 to +0.162 | 43% | 1.12 | 0.097 |
| x1.25 | $0.20 | +0.027 | -0.070 to +0.124 | 42% | 1.05 | 0.292 |
| x1.5 | $0.00 | +0.085 | -0.013 to +0.182 | 43% | 1.16 | 0.045 |
| x1.5 | $0.05 | +0.066 | -0.031 to +0.163 | 43% | 1.12 | 0.093 |
| x1.5 | $0.10 | +0.047 | -0.050 to +0.144 | 42% | 1.08 | 0.171 |
| x1.5 | $0.20 | +0.010 | -0.087 to +0.107 | 42% | 1.02 | 0.422 |

Break-even: the mean turns to zero with about $0.64 of extra cost per round trip (median spread $0.37, median risk $5.74).

**4. Long-term drift.**

* Matched random LONG trades (same entry type, stop size, session, volatility, year): -0.044R; the candidate's edge over them: +0.163R.
* The same signals traded SHORT (mirror stop, 2R, 48 candles): 806 trades, mean R -0.169 +/- 0.044.
* The bearish version of the pattern: 763 trades, mean R -0.093, edge -0.036
* In the 4 training years when gold fell: 2013 (-28%): n=51, mean R -0.38, 2014 (-2%): n=52, mean R +0.08, 2015 (-10%): n=53, mean R +0.10, 2018 (-2%): n=44, mean R +0.16.

Random market entries at the candidate's typical stop size, long versus short, by year (training):

| Year | Random long mean R | Random short mean R |
|---|---|---|
| 2003 | -0.106 | -0.329 |
| 2004 | -0.129 | -0.288 |
| 2005 | -0.126 | -0.289 |
| 2006 | -0.019 | -0.162 |
| 2007 | -0.043 | -0.170 |
| 2008 | -0.054 | -0.041 |
| 2009 | -0.029 | -0.176 |
| 2010 | -0.083 | -0.171 |
| 2011 | +0.003 | -0.157 |
| 2012 | -0.166 | +0.003 |
| 2013 | -0.173 | +0.096 |
| 2014 | -0.126 | -0.020 |
| 2015 | -0.155 | +0.070 |
| 2016 | -0.087 | -0.055 |
| 2017 | -0.009 | -0.140 |
| 2018 | -0.088 | -0.011 |
| 2019 | -0.077 | -0.175 |
| 2020 | +0.371 | -0.184 |

**5. Stability.** Positive mean R in 13 of 18 training years.

| Year | Trades | Win % | Mean R | Edge | Gold that year |
|---|---|---|---|---|---|
| 2003 | 3 | 0% | -1.03 | -1.02 | 22% |
| 2004 | 6 | 17% | -0.39 | -0.33 | 5% |
| 2005 | 11 | 73% | +0.59 | +0.57 | 18% |
| 2006 | 36 | 31% | -0.16 | -0.20 | 23% |
| 2007 | 60 | 57% | +0.42 | +0.45 | 31% |
| 2008 | 85 | 51% | +0.33 | +0.38 | 6% |
| 2009 | 67 | 48% | +0.30 | +0.32 | 25% |
| 2010 | 85 | 44% | +0.00 | +0.01 | 29% |
| 2011 | 52 | 48% | +0.22 | +0.18 | 10% |
| 2012 | 46 | 24% | -0.34 | -0.24 | 7% |
| 2013 | 51 | 24% | -0.38 | -0.22 | -28% |
| 2014 | 52 | 42% | +0.08 | +0.18 | -2% |
| 2015 | 53 | 40% | +0.10 | +0.24 | -10% |
| 2016 | 53 | 43% | +0.19 | +0.28 | 8% |
| 2017 | 46 | 54% | +0.42 | +0.42 | 13% |
| 2018 | 44 | 43% | +0.16 | +0.23 | -2% |
| 2019 | 52 | 38% | +0.07 | +0.10 | 18% |
| 2020 | 4 | 50% | +0.17 | -0.41 | 3% |

| session | Trades | Mean R | Edge |
|---|---|---|---|
| asia | 136 | +0.36 | +0.40 |
| london | 198 | +0.02 | +0.10 |
| new_york | 83 | -0.01 | +0.02 |
| overlap | 355 | +0.15 | +0.18 |
| rollover | 34 | -0.23 | -0.20 |

| vol level | Trades | Mean R | Edge |
|---|---|---|---|
| extreme | 141 | +0.08 | +0.10 |
| high | 174 | +0.05 | +0.08 |
| low | 126 | +0.35 | +0.43 |
| normal | 309 | +0.03 | +0.08 |
| very_low | 56 | +0.41 | +0.44 |

| trend regime | Trades | Mean R | Edge |
|---|---|---|---|
| moderate_bearish | 20 | +0.18 | +0.26 |
| moderate_bullish | 320 | +0.17 | +0.21 |
| none | 105 | +0.02 | +0.07 |
| strong_bearish | 2 | +0.50 | +0.58 |
| strong_bullish | 105 | +0.16 | +0.20 |
| weak_bearish | 61 | +0.03 | +0.09 |
| weak_bullish | 193 | +0.09 | +0.12 |

| structural regime | Trades | Mean R | Edge |
|---|---|---|---|
| accumulation_like | 1 | -1.00 | -0.76 |
| distribution_like | 3 | +1.65 | +1.61 |
| none | 448 | +0.16 | +0.20 |
| reaccumulation_like | 13 | +0.21 | +0.30 |
| redistribution_like | 9 | +0.09 | +0.15 |
| trend_transition | 332 | +0.05 | +0.10 |

**7. Execution realism.**

* Entry: next candle open after the signal candle closes (ask for longs); 1-candle-late edge in training +0.107R (n=802).
* Stop: signal candle low - 0.1 ATR (at least 0.25 ATR from entry), exit at bid; stop minute that opens beyond the stop fills at that open. Target: 2R limit at the bid; touch fills (no queue modelling).
* Risk per trade: median $5.74 (2.49 ATR), 5th percentile $2.94; 0.0% of trades risk under $0.50 and 0.0% under $1.00 (stops that close can be below a broker's minimum stop distance).
* Spread as a share of risk: median 6.4%, 95th percentile 13.2%.
* Stops filled beyond the stop price (gaps): 3.7%; worst -2.16R.
* Intrabar assumption (stop counted first inside a minute): flipping it changes 0.00% of results.
* Entries during the 17:00-19:00 New York rollover (wide spreads): 4.2%, mean R -0.23.
* Overlapping positions if every signal were taken: median 1, maximum 6.
* Stopped out within 12 / 24 / 48 / 96 candles: 30% / 38% / 52% / 65%.

## 3. Missing scheduled data

Period: 2003-05-05 to 2023-06-24 (training + validation; the sealed final-test period is excluded). Scheduled-open minutes 7,251,779; missing 521,778 (7.20%), of which 62,442 in material gaps (30+ minutes, excluded from research) and 47,314 on 24-26 Dec / 1-2 Jan.

| year | Scheduled minutes | Missing | Share missing |
|---|---|---|---|
| 2003 | 238,679 | 135,460 | 56.75% |
| 2004 | 361,500 | 152,234 | 42.11% |
| 2005 | 358,800 | 86,592 | 24.13% |
| 2006 | 358,860 | 34,040 | 9.49% |
| 2007 | 360,180 | 21,300 | 5.91% |
| 2008 | 361,560 | 7,030 | 1.94% |
| 2009 | 360,180 | 5,874 | 1.63% |
| 2010 | 360,120 | 4,174 | 1.16% |
| 2011 | 358,800 | 2,957 | 0.82% |
| 2012 | 360,240 | 4,664 | 1.29% |
| 2013 | 360,180 | 7,874 | 2.19% |
| 2014 | 360,180 | 8,741 | 2.43% |
| 2015 | 360,180 | 6,417 | 1.78% |
| 2016 | 360,120 | 5,756 | 1.60% |
| 2017 | 358,860 | 6,072 | 1.69% |
| 2018 | 360,180 | 6,257 | 1.74% |
| 2019 | 360,180 | 6,831 | 1.90% |
| 2020 | 361,560 | 6,065 | 1.68% |
| 2021 | 360,120 | 5,774 | 1.60% |
| 2022 | 358,800 | 4,167 | 1.16% |
| 2023 | 172,500 | 3,499 | 2.03% |

| session | Scheduled minutes | Missing | Share missing |
|---|---|---|---|
| asia | 2,522,339 | 201,763 | 8.00% |
| london | 1,576,500 | 83,222 | 5.28% |
| new_york | 1,576,500 | 159,503 | 10.12% |
| overlap | 1,261,200 | 29,189 | 2.31% |
| rollover | 315,240 | 48,101 | 15.26% |

| weekday | Scheduled minutes | Missing | Share missing |
|---|---|---|---|
| 1 | 1,450,380 | 117,841 | 8.12% |
| 2 | 1,450,380 | 91,507 | 6.31% |
| 3 | 1,450,380 | 89,637 | 6.18% |
| 4 | 1,450,380 | 99,937 | 6.89% |
| 5 | 1,072,020 | 84,019 | 7.84% |
| 7 | 378,239 | 38,837 | 10.27% |

| vol level | Scheduled minutes | Missing | Share missing |
|---|---|---|---|
| extreme | 874,380 | 53,771 | 6.15% |
| high | 1,322,520 | 86,944 | 6.57% |
| low | 1,465,080 | 100,759 | 6.88% |
| normal | 2,572,500 | 178,170 | 6.93% |
| unknown | 15,359 | 10,273 | 66.89% |
| very_low | 1,001,940 | 91,861 | 9.17% |

| trend regime | Scheduled minutes | Missing | Share missing |
|---|---|---|---|
| moderate_bearish | 1,505,280 | 81,105 | 5.39% |
| moderate_bullish | 1,869,180 | 125,089 | 6.69% |
| none | 1,128,960 | 105,175 | 9.32% |
| strong_bearish | 223,140 | 8,143 | 3.65% |
| strong_bullish | 309,660 | 15,020 | 4.85% |
| unknown | 59 | 50 | 84.75% |
| weak_bearish | 1,036,920 | 75,488 | 7.28% |
| weak_bullish | 1,178,580 | 111,708 | 9.48% |

## 6. Look-ahead and leakage checks

Training ends 2020-02-08T00:00:00+00:00.

| TF | Trades | Last entry | Last outcome window end | Inside training | Segments in file |
|---|---|---|---|---|---|
| D1 | 9,236 | 2012-08-17T00:00 | 2012-11-21T00:00 | yes | train |
| H1 | 356,126 | 2020-02-03T18:00 | 2020-02-07T18:00 | yes | train |
| H4 | 81,982 | 2020-01-03T20:00 | 2020-01-19T20:00 | yes | train |
| M15 | 1,459,294 | 2020-02-06T21:00 | 2020-02-07T21:00 | yes | train |
| M30 | 723,990 | 2020-02-05T19:30 | 2020-02-07T19:30 | yes | train |
| M5 | 4,502,519 | 2020-02-07T14:00 | 2020-02-07T22:00 | yes | train |

* Validation or final-test outputs present in the research folder: none.
* Final-test seal log exists (any read of the sealed period would be recorded): no: the sealed period has never been read.
* Stage-1 discovery generated 2026-11-09T16:34:38+00:00; it is tied to the frozen split (hash matches: True).
* Model training outputs present: not yet (models are trained by stage 2 after validation trades are simulated, on training rows only).
* Every data read in the research code goes through the sealed loader; call sites and the segment they request:

  * `audit.py`: `134: df = load_tf(symbol, tf, upto="train")`; `135: S = sim.Series.from_frame(df, tf, load_m1(symbol, upto="train"))`; `194: h1 = load_tf(symbol, "H1", upto="validation")`; `342: d1 = load_tf(symbol, "D1", upto="train").with_columns(year=pl.col("ts").dt.year()).group_by("year").agg(`
  * `combos.py`: `81: df = load_tf(symbol, tf, upto=segment, final_test=final_test)`
  * `ml.py`: `86: df = load_tf(symbol, tf, upto=segment, final_test=final_test)`
  * `study.py`: `130: df = load_tf(symbol, tf, upto=segment, final_test=final_test)`; `131: m1 = load_m1(symbol, upto=segment, final_test=final_test)`
  * `unsupervised.py`: `75: df = load_tf(symbol, tf, upto="train")`

* Design guarantees, each covered by a test: detectors are causal (prefix versus full history); higher-timeframe candles are used only after they close; regime thresholds are fixed in ATR units or trailing percentiles (nothing fitted on later data); controls are drawn from the same segment; models use purged walk-forward folds with nested parameter choice and cross-fitted calibration inside training; the unnamed-pattern model is fitted on training candles only.
* Researcher-side disclosures: earlier exploratory studies on Twelve Data candles (2024-2026) touched the final-test period. The chart, Wyckoff and harmonic families were commissioned before stage-1 results existed. The unnamed-pattern stage (phase 6) was written after the stage-1 training results had been seen; its design is generic (no parameters tuned to those results) but it is not blind.

## Limitations of this audit

* Training data only: validation had not run when this audit was produced; its results are reported separately and decide the candidates.
* PBO uses year blocks of unequal size and treats every test as a strategy, including correlated variants.
* The deflated Sharpe ratio assumes independent observations; the cluster version is the conservative reading.
* Slippage is a flat dollar assumption; real slippage grows in fast markets and at the rollover.
* One data source (Dukascopy); broker spreads, minimum stop distances and swap differ.
