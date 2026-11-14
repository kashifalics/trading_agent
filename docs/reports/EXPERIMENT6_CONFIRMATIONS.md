# Experiment 6: do VSA and indicator confirmations improve the six strategies? (2026-11-14)

No confirmation was promoted to a gate: none improved net results reproducibly on out-of-sample data.

36 arms entered the test family (counts only, decided before outcomes); 4 passed development; 0 passed the confirmation segment. Trials counted from here on: 2,115.

Method: [EXPERIMENT_6_PLAN.md](../engine_v2/EXPERIMENT_6_PLAN.md). An arm keeps a trade only when its confirmation is PASS; it is compared with the strategy without the filter and with 20,000 random filters keeping the same number of trades per timeframe, direction and year. R is net of the real spread (gold: Dukascopy bid/ask; BTCUSDT: the $2 round-trip model). Results are hypothetical research figures, not trading performance.

## Development (training segment)

| Symbol | Strategy | Arm | Trades | Kept | Baseline R | Kept R | Improvement | At 2x costs | Random-filter p | Holm p | Years improved | Result |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| XAUUSD | Breakout and retest | vsa | 20,933 | 2,621 | -0.140 | -0.151 | -0.011 | -0.012 | 0.9315 | 1.0000 | 0.33 | did not pass |
| XAUUSD | Breakout and retest | trend | 20,933 | 15,406 | -0.140 | -0.120 | +0.020 | +0.020 | 0.0004 | 0.0153 | 0.67 | passed development |
| XAUUSD | Breakout and retest | volatility | 20,933 | 16,062 | -0.140 | -0.144 | -0.004 | -0.005 | 0.5622 | 1.0000 | 0.44 | did not pass |
| XAUUSD | Breakout and retest | combo | 20,933 | 1,914 | -0.140 | -0.134 | +0.006 | +0.007 | 0.8097 | 1.0000 | 0.58 | did not pass |
| XAUUSD | Momentum continuation | momentum | 349 | 291 | -0.173 | -0.161 | +0.012 | +0.010 | 0.7082 | 1.0000 | 0.56 | did not pass |
| XAUUSD | Momentum continuation | volatility | 349 | 269 | -0.173 | -0.177 | -0.004 | -0.003 | 0.7804 | 1.0000 | 0.44 | did not pass |
| XAUUSD | Liquidity-sweep reversal | vsa | 29,984 | 11,659 | -0.164 | -0.152 | +0.012 | +0.018 | 0.0482 | 1.0000 | 0.61 | did not pass |
| XAUUSD | Liquidity-sweep reversal | momentum | 29,984 | 22,059 | -0.164 | -0.162 | +0.002 | +0.003 | 0.2544 | 1.0000 | 0.44 | did not pass |
| XAUUSD | Liquidity-sweep reversal | trend | 29,984 | 18,481 | -0.164 | -0.144 | +0.020 | +0.020 | 0.0009 | 0.0313 | 0.78 | passed development |
| XAUUSD | Liquidity-sweep reversal | volatility | 29,984 | 23,576 | -0.164 | -0.167 | -0.002 | -0.002 | 0.5818 | 1.0000 | 0.44 | did not pass |
| XAUUSD | Liquidity-sweep reversal | combo | 29,984 | 8,619 | -0.164 | -0.147 | +0.017 | +0.024 | 0.0432 | 1.0000 | 0.56 | did not pass |
| XAUUSD | Trend-following pullback | vsa | 9,756 | 1,735 | -0.130 | -0.127 | +0.003 | +0.000 | 0.4118 | 1.0000 | 0.50 | did not pass |
| XAUUSD | Trend-following pullback | momentum | 9,756 | 2,041 | -0.130 | -0.104 | +0.026 | +0.031 | 0.1374 | 1.0000 | 0.71 | did not pass |
| XAUUSD | Trend-following pullback | volatility | 9,756 | 7,406 | -0.130 | -0.145 | -0.015 | -0.015 | 0.9691 | 1.0000 | 0.39 | did not pass |
| XAUUSD | Trend-following pullback | combo | 9,756 | 366 | -0.130 | -0.113 | +0.017 | +0.019 | 0.4505 | 1.0000 | 0.44 | did not pass |
| XAUUSD | Volatility expansion | vsa | 4,081 | 1,296 | -0.142 | -0.199 | -0.056 | -0.059 | 0.8611 | 1.0000 | 0.36 | did not pass |
| XAUUSD | Volatility expansion | trend | 4,081 | 2,686 | -0.142 | -0.120 | +0.022 | +0.026 | 0.1482 | 1.0000 | 0.53 | did not pass |
| XAUUSD | Volatility expansion | volatility | 4,081 | 1,644 | -0.142 | -0.197 | -0.055 | -0.061 | 0.9505 | 1.0000 | 0.20 | did not pass |
| XAUUSD | Volatility expansion | combo | 4,081 | 619 | -0.142 | -0.288 | -0.145 | -0.154 | 0.9954 | 1.0000 | 0.11 | did not pass |
| BTCUSDT | Breakout and retest | vsa | 28,184 | 13,213 | -0.009 | -0.006 | +0.003 | +0.007 | 0.3398 | 1.0000 | 0.50 | did not pass |
| BTCUSDT | Breakout and retest | trend | 28,184 | 20,559 | -0.009 | +0.018 | +0.027 | +0.026 | 0.0000 | 0.0018 | 0.88 | passed development |
| BTCUSDT | Breakout and retest | volatility | 28,184 | 19,225 | -0.009 | -0.015 | -0.006 | -0.001 | 0.7990 | 1.0000 | 0.25 | did not pass |
| BTCUSDT | Breakout and retest | combo | 28,184 | 9,887 | -0.009 | +0.018 | +0.027 | +0.031 | 0.0103 | 0.3208 | 0.75 | did not pass |
| BTCUSDT | Liquidity-sweep reversal | vsa | 30,565 | 16,442 | -0.117 | -0.114 | +0.003 | +0.011 | 0.1613 | 1.0000 | 0.75 | did not pass |
| BTCUSDT | Liquidity-sweep reversal | momentum | 30,565 | 23,245 | -0.117 | -0.109 | +0.008 | +0.009 | 0.0155 | 0.4665 | 0.62 | did not pass |
| BTCUSDT | Liquidity-sweep reversal | trend | 30,565 | 17,520 | -0.117 | -0.082 | +0.035 | +0.036 | 0.0000 | 0.0018 | 0.88 | passed development |
| BTCUSDT | Liquidity-sweep reversal | volatility | 30,565 | 21,958 | -0.117 | -0.129 | -0.012 | -0.010 | 0.9929 | 1.0000 | 0.25 | did not pass |
| BTCUSDT | Liquidity-sweep reversal | combo | 30,565 | 12,686 | -0.117 | -0.105 | +0.011 | +0.019 | 0.0429 | 1.0000 | 0.88 | did not pass |
| BTCUSDT | Trend-following pullback | vsa | 7,439 | 1,810 | -0.078 | -0.103 | -0.024 | -0.032 | 0.8728 | 1.0000 | 0.43 | did not pass |
| BTCUSDT | Trend-following pullback | momentum | 7,439 | 1,851 | -0.078 | -0.144 | -0.065 | -0.061 | 0.9949 | 1.0000 | 0.00 | did not pass |
| BTCUSDT | Trend-following pullback | volatility | 7,439 | 5,353 | -0.078 | -0.094 | -0.016 | -0.016 | 0.9395 | 1.0000 | 0.25 | did not pass |
| BTCUSDT | Trend-following pullback | combo | 7,439 | 520 | -0.078 | -0.074 | +0.004 | +0.002 | 0.5136 | 1.0000 | 0.33 | did not pass |
| BTCUSDT | Volatility expansion | vsa | 4,273 | 2,732 | -0.048 | -0.038 | +0.010 | +0.018 | 0.2399 | 1.0000 | 0.50 | did not pass |
| BTCUSDT | Volatility expansion | trend | 4,273 | 2,872 | -0.048 | -0.005 | +0.043 | +0.043 | 0.0024 | 0.0784 | 1.00 | did not pass |
| BTCUSDT | Volatility expansion | volatility | 4,273 | 1,741 | -0.048 | -0.041 | +0.007 | +0.007 | 0.3531 | 1.0000 | 0.75 | did not pass |
| BTCUSDT | Volatility expansion | combo | 4,273 | 1,274 | -0.048 | -0.026 | +0.022 | +0.030 | 0.2500 | 1.0000 | 0.71 | did not pass |

Arms below the count rule (fewer than 300 kept development signals, or fewer than 10% dropped), not tested:

- XAUUSD Breakout and retest, momentum: 61,781 kept of 67,974 signals (below the count rule)
- XAUUSD Momentum continuation, vsa: 19 kept of 387 signals (below the count rule)
- XAUUSD Momentum continuation, trend: 365 kept of 387 signals (below the count rule)
- XAUUSD Momentum continuation, combo: 244 kept of 387 signals (below the count rule)
- XAUUSD Trend-following pullback, trend: 15,273 kept of 16,336 signals (below the count rule)
- XAUUSD Volatility expansion, momentum: 6,798 kept of 6,945 signals (below the count rule)
- BTCUSDT Breakout and retest, momentum: 99,148 kept of 107,685 signals (below the count rule)
- BTCUSDT Momentum continuation, vsa: 27 kept of 220 signals (below the count rule)
- BTCUSDT Momentum continuation, momentum: 197 kept of 220 signals (below the count rule)
- BTCUSDT Momentum continuation, trend: 212 kept of 220 signals (below the count rule)
- BTCUSDT Momentum continuation, volatility: 167 kept of 220 signals (below the count rule)
- BTCUSDT Momentum continuation, combo: 145 kept of 220 signals (below the count rule)
- BTCUSDT Trend-following pullback, trend: 11,733 kept of 12,435 signals (below the count rule)
- BTCUSDT Volatility expansion, momentum: 7,505 kept of 7,618 signals (below the count rule)

## Confirmation segment (run once)

| Symbol | Strategy | Arm | Trades | Kept | Baseline R | Kept R | Improvement | At 2x costs | Random-filter p | Holm p | Years improved | Result |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| BTCUSDT | Breakout and retest | trend | 7,703 | 5,510 | +0.049 | +0.054 | +0.005 | +0.005 | 0.3284 | 0.9069 | 0.50 | did not pass |
| BTCUSDT | Liquidity-sweep reversal | trend | 6,915 | 3,868 | -0.035 | -0.018 | +0.017 | +0.017 | 0.1226 | 0.4904 | 1.00 | did not pass |
| XAUUSD | Breakout and retest | trend | 7,235 | 5,331 | -0.121 | -0.113 | +0.008 | +0.009 | 0.3023 | 0.9069 | 0.50 | did not pass |
| XAUUSD | Liquidity-sweep reversal | trend | 8,821 | 5,340 | -0.139 | -0.140 | -0.001 | +0.002 | 0.5983 | 0.9069 | 0.50 | did not pass |

## By confirmation

Arms tested in development, how many kept trades that did better than the unfiltered strategy, how many passed every development check, and how many were confirmed on fresh data.

| Confirmation | Arms tested | Improved in development | Passed development | Confirmed | Mean improvement (R per trade) |
|---|---:|---:|---:|---:|---:|
| VSA | 8 | 5 | 0 | 0 | -0.008 |
| Momentum | 5 | 4 | 0 | 0 | -0.004 |
| Trend | 6 | 6 | 4 | 0 | +0.028 |
| Volatility | 9 | 1 | 0 | 0 | -0.012 |
| Combination | 8 | 7 | 0 | 0 | -0.005 |

Market regime of the arms that passed development (mean R per trade, development segment):

| Arm | Regime | Unfiltered | Kept |
|---|---|---:|---:|
| XAUUSD Breakout and retest, trend | consolidating | -0.104 | -0.068 |
| XAUUSD Breakout and retest, trend | ranging | -0.122 | -0.095 |
| XAUUSD Breakout and retest, trend | trending | -0.120 | -0.111 |
| XAUUSD Breakout and retest, trend | unknown | -0.153 | -0.132 |
| XAUUSD Liquidity-sweep reversal, trend | ranging | -0.124 | -0.100 |
| XAUUSD Liquidity-sweep reversal, trend | trending | -0.198 | -0.180 |
| XAUUSD Liquidity-sweep reversal, trend | unknown | -0.171 | -0.150 |
| BTCUSDT Breakout and retest, trend | consolidating | +0.012 | +0.014 |
| BTCUSDT Breakout and retest, trend | ranging | -0.014 | +0.025 |
| BTCUSDT Breakout and retest, trend | trending | +0.031 | +0.044 |
| BTCUSDT Breakout and retest, trend | unknown | -0.024 | +0.005 |
| BTCUSDT Liquidity-sweep reversal, trend | ranging | -0.076 | -0.050 |
| BTCUSDT Liquidity-sweep reversal, trend | trending | -0.117 | -0.091 |
| BTCUSDT Liquidity-sweep reversal, trend | unknown | -0.132 | -0.093 |

## What this means

- A gate changes BUY/SELL into WAIT only for a promoted category, on the instrument it passed on. Every other category stays evidence on the signal card, marked "did not pass Experiment 6" when it was tested.
- Passing here does not validate a strategy: that still needs Experiment 5's criteria and the owner's approval for the one-time sealed final test.
- Gold VSA uses Dukascopy venue volume; live gold uses broker tick counts, and their only overlap is sealed, so gold VSA is research only.
- EURUSD and GBPUSD are not tested yet (their history is still incomplete).
