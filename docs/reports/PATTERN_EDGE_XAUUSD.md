# XAUUSD - pattern edge study (all timeframes)

_Generated from experiment #49 by `python -m app.research.run_patterns report`. Nothing here is hand-entered._

## Method (so the numbers can be trusted - or doubted)

* Every pattern fires at the **close** of a bar; the trade enters at the **next open** with +2 ATR target / -1 ATR stop / 24-bar limit (same-bar ambiguity = stop). R = P&L / stop distance.
* Costs: round trip **0.020%** of price, converted to R per trade (BTC: 0.10% fee/side + slippage; gold: spread + slippage). *Gross* = no costs.
* **Lift** = pattern mean R minus the mean R of taking the same direction on *every* bar of the same period (removes drift: a rising market makes every long look good).
* **Execution realism:** entries assume a fill at the next bar's open. That is optimistic on very short timeframes, so a pattern must ALSO keep a significant positive lift when the entry is delayed by one more bar. (An earlier run produced eight 1-minute 'confirmations' on gold that vanished after a one-bar delay; they were fill-price artifacts and are now filtered out.)
* Overlapping signals of one pattern are skipped. Discovery on the first 60% of history (label windows never reach the held-out part); confirmation on the last 40%.
* 596 hypotheses with enough discovery events were tested. Discovery keeps only those with Benjamini-Hochberg FDR q < 0.2 and positive lift; confirmation applies a Holm correction (alpha 0.05) over the candidates. **Confirmed** = survives both. **Tradeable** = confirmed AND positive net expectancy out of sample.
* The engine is unit-tested to find a planted effect and to produce ~0 confirmations from pure noise.

## Result

| Hypotheses tested | Discovery candidates | Out-of-sample testable | **Confirmed (gross lift)** | **Tradeable (net of costs)** |
|---|---|---|---|---|
| 596 | 30 | 30 | **0** | **0** |

Patterns that passed discovery and Holm-corrected confirmation but **failed the one-bar-delay check** (artifacts that need an unattainable fill): **8**.

## What this study can and cannot detect (statistical power)

| TF | Median discovery events per pattern | Smallest lift reliably detectable (80% power, p~0.005) |
|---|---|---|
| 1m | 39 | 0.78 R per trade |
| 3m | 100 | 0.49 R per trade |
| 5m | 67 | 0.59 R per trade |
| 15m | 201 | 0.34 R per trade |
| 30m | 402 | 0.24 R per trade |
| 1H | 386 | 0.25 R per trade |
| 2H | 126 | 0.43 R per trade |
| 4H | 64 | 0.61 R per trade |
| 1D | 40 | 0.77 R per trade |

Typical R standard deviation: 1.42. **A pattern whose true advantage is smaller than this would NOT be found - 'nothing confirmed' means 'no large edge', not 'no edge at all'.**

## Timeframes studied

| TF | Bars | From | To | Hypotheses |
|---|---|---|---|---|
| 1m | 31,078 | 2026-10-01 | 2026-10-30 | 90 |
| 3m | 10,359 | 2026-10-01 | 2026-10-30 | 90 |
| 5m | 31,847 | 2026-05-29 | 2026-10-30 | 90 |
| 15m | 32,108 | 2025-07-20 | 2026-10-30 | 90 |
| 30m | 31,255 | 2024-04-08 | 2026-10-30 | 90 |
| 1H | 29,482 | 2021-11-28 | 2026-10-30 | 90 |
| 2H | 14,393 | 2021-11-29 | 2026-10-30 | 42 |
| 4H | 6,858 | 2021-11-29 | 2026-10-30 | 42 |
| 1D | 3,630 | 2012-11-16 | 2026-10-30 | 42 |
| 1W | 718 | 2013-01-21 | 2026-10-19 | 42 |

Timeframes not listed (1M and above) have too little history for any statistical statement; 1W has very low power.

## Patterns that passed out-of-sample confirmation

**None.** No pattern kept a statistically significant advantage out of sample after correcting for the number of patterns tested.

## Strongest discovery candidates and what happened out of sample

Shown even when they failed, so you can see how much looks like an edge in-sample and then disappears.

| TF | Pattern | Side | IS n | IS lift (R) | IS FDR q | OOS n | OOS win | OOS gross R | OOS net R | OOS lift (R) | OOS p | Holm p | Lift if entry 1 bar later |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | demand_zone_formed | long | 107 | +1.346 | 0.000 | 69 | 72% | +1.193 | +0.440 | +1.220 | 0.000 | 0.000 | +0.192 (p 0.14) |
| 1m | supply_zone_formed | short | 66 | +1.346 | 0.000 | 59 | 78% | +1.415 | +0.846 | +1.338 | 0.000 | 0.000 | +0.257 (p 0.10) |
| 1m | order_block_formed | short | 396 | +0.408 | 0.000 | 272 | 43% | +0.330 | -0.304 | +0.253 | 0.003 | 0.056 | +0.067 (p 0.22) |
| 1m | donchian20_breakout | long | 379 | +0.400 | 0.000 | 238 | 44% | +0.344 | -0.310 | +0.371 | 0.000 | 0.002 | +0.013 (p 0.44) |
| 1m | order_block_formed | long | 384 | +0.394 | 0.000 | 239 | 44% | +0.323 | -0.351 | +0.351 | 0.000 | 0.004 | -0.040 (p 0.67) |
| 1m | breaker_block_formed | long | 316 | +0.432 | 0.000 | 185 | 44% | +0.343 | -0.258 | +0.370 | 0.000 | 0.011 | -0.005 (p 0.52) |
| 1m | donchian20_breakout | short | 390 | +0.385 | 0.000 | 270 | 46% | +0.432 | -0.182 | +0.356 | 0.000 | 0.001 | -0.043 (p 0.69) |
| 1m | choch | short | 317 | +0.396 | 0.000 | 207 | 44% | +0.348 | -0.314 | +0.271 | 0.005 | 0.092 | +0.126 (p 0.11) |
| 1m | choch | long | 320 | +0.368 | 0.000 | 203 | 46% | +0.395 | -0.262 | +0.423 | 0.000 | 0.001 | +0.077 (p 0.22) |
| 1m | breaker_block_formed | short | 291 | +0.391 | 0.000 | 198 | 46% | +0.452 | -0.157 | +0.375 | 0.000 | 0.005 | +0.129 (p 0.11) |
| 1m | inside_bar_breakout | long | 286 | +0.384 | 0.000 | 194 | 39% | +0.222 | -0.452 | +0.249 | 0.009 | 0.153 | -0.026 (p 0.60) |
| 1m | inside_bar_breakout | short | 302 | +0.333 | 0.003 | 207 | 43% | +0.324 | -0.330 | +0.247 | 0.009 | 0.153 | +0.063 (p 0.26) |
| 1m | sma200_cross | short | 172 | +0.385 | 0.020 | 131 | 40% | +0.272 | -0.268 | +0.195 | 0.064 | 0.829 | +0.232 (p 0.03) |
| 5m | order_block_formed | short | 374 | +0.249 | 0.023 | 276 | 36% | +0.112 | -0.142 | +0.035 | 0.342 | 1.000 | -0.053 (p 0.73) |
| 1m | ema20_50_cross | long | 166 | +0.372 | 0.023 | 112 | 39% | +0.220 | -0.337 | +0.247 | 0.038 | 0.532 | +0.131 (p 0.17) |
| 1m | bos | long | 214 | +0.324 | 0.026 | 131 | 42% | +0.314 | -0.341 | +0.341 | 0.004 | 0.092 | -0.086 (p 0.77) |
| 1m | fvg_formed | short | 323 | +0.264 | 0.026 | 222 | 42% | +0.337 | -0.297 | +0.260 | 0.004 | 0.092 | +0.008 (p 0.47) |
| 1H | hour_02utc | short | 387 | +0.230 | 0.034 | 248 | 31% | -0.065 | -0.129 | -0.026 | 0.616 | 1.000 | -0.002 (p 0.51) |
| 1H | hour_19utc | long | 383 | +0.230 | 0.037 | 248 | 35% | +0.095 | +0.033 | +0.023 | 0.401 | 1.000 | -0.083 (p 0.82) |
| 1m | bos | short | 239 | +0.286 | 0.047 | 164 | 43% | +0.342 | -0.270 | +0.265 | 0.011 | 0.179 | +0.106 (p 0.17) |
| 30m | bos | short | 169 | +0.332 | 0.053 | 140 | 29% | -0.121 | -0.209 | -0.150 | 0.901 | 1.000 | -0.090 (p 0.78) |
| 3m | fvg_formed | short | 175 | +0.324 | 0.061 | 112 | 43% | +0.334 | -0.010 | +0.267 | 0.029 | 0.439 | +0.234 (p 0.05) |
| 1H | hour_13utc | short | 388 | +0.209 | 0.064 | 248 | 29% | -0.112 | -0.174 | -0.073 | 0.800 | 1.000 | -0.019 (p 0.59) |
| 1H | hour_21utc | long | 119 | +0.363 | 0.112 | 229 | 35% | +0.075 | +0.011 | +0.003 | 0.486 | 1.000 | -0.103 (p 0.87) |
| 5m | hour_16utc | short | 66 | +0.454 | 0.141 | 45 | 38% | +0.206 | +0.033 | +0.129 | 0.277 | 1.000 | -0.030 (p 0.56) |
| 1m | bullish_engulfing | long | 238 | +0.236 | 0.143 | 148 | 30% | -0.054 | -0.746 | -0.026 | 0.592 | 1.000 | -0.143 (p 0.91) |
| 1m | sma200_cross | long | 177 | +0.278 | 0.143 | 132 | 36% | +0.122 | -0.413 | +0.150 | 0.119 | 1.000 | -0.088 (p 0.77) |
| 1H | hour_20utc | long | 363 | +0.189 | 0.153 | 247 | 36% | +0.117 | +0.054 | +0.045 | 0.311 | 1.000 | +0.047 (p 0.31) |
| 1m | rsi_oversold_exit | long | 128 | +0.313 | 0.163 | 85 | 36% | +0.124 | -0.450 | +0.151 | 0.170 | 1.000 | -0.239 (p 0.95) |
| 5m | choch | short | 282 | +0.206 | 0.180 | 212 | 38% | +0.170 | -0.088 | +0.094 | 0.174 | 1.000 | +0.035 (p 0.36) |

Full catalogue (every pattern x timeframe with its statistics): `docs/reports/data/PATTERN_EDGE_XAUUSD.csv`.

## Reading guide

* A pattern with high win rate but negative lift is just the market's drift or the 2:1 bracket - not information.
* Many tests means some will look good by chance: a lone p < 0.05 means nothing here; only Holm-corrected out-of-sample results count.
* Short timeframes pay the same fee on much smaller moves, so net results degrade sharply as the timeframe shrinks.
