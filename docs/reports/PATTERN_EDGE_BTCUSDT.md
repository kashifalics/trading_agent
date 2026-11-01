# BTCUSDT - pattern edge study (all timeframes)

_Generated from experiment #48 by `python -m app.research.run_patterns report`. Nothing here is hand-entered._

## Method (so the numbers can be trusted - or doubted)

* Every pattern fires at the **close** of a bar; the trade enters at the **next open** with +2 ATR target / -1 ATR stop / 24-bar limit (same-bar ambiguity = stop). R = P&L / stop distance.
* Costs: round trip **0.222%** of price, converted to R per trade (BTC: 0.10% fee/side + slippage; gold: spread + slippage). *Gross* = no costs.
* **Lift** = pattern mean R minus the mean R of taking the same direction on *every* bar of the same period (removes drift: a rising market makes every long look good).
* **Execution realism:** entries assume a fill at the next bar's open. That is optimistic on very short timeframes, so a pattern must ALSO keep a significant positive lift when the entry is delayed by one more bar. (An earlier run produced eight 1-minute 'confirmations' on gold that vanished after a one-bar delay; they were fill-price artifacts and are now filtered out.)
* Overlapping signals of one pattern are skipped. Discovery on the first 60% of history (label windows never reach the held-out part); confirmation on the last 40%.
* 637 hypotheses with enough discovery events were tested. Discovery keeps only those with Benjamini-Hochberg FDR q < 0.2 and positive lift; confirmation applies a Holm correction (alpha 0.05) over the candidates. **Confirmed** = survives both. **Tradeable** = confirmed AND positive net expectancy out of sample.
* The engine is unit-tested to find a planted effect and to produce ~0 confirmations from pure noise.

## Result

| Hypotheses tested | Discovery candidates | Out-of-sample testable | **Confirmed (gross lift)** | **Tradeable (net of costs)** |
|---|---|---|---|---|
| 637 | 0 | 0 | **0** | **0** |

Patterns that passed discovery and Holm-corrected confirmation but **failed the one-bar-delay check** (artifacts that need an unattainable fill): **0**.

## What this study can and cannot detect (statistical power)

| TF | Median discovery events per pattern | Smallest lift reliably detectable (80% power, p~0.005) |
|---|---|---|
| 1m | 39 | 0.82 R per trade |
| 3m | 38 | 0.83 R per trade |
| 5m | 63 | 0.64 R per trade |
| 15m | 187 | 0.37 R per trade |
| 30m | 374 | 0.26 R per trade |
| 1H | 359 | 0.27 R per trade |
| 2H | 122 | 0.46 R per trade |
| 4H | 64 | 0.64 R per trade |
| 1D | 41 | 0.80 R per trade |

Typical R standard deviation: 1.49. **A pattern whose true advantage is smaller than this would NOT be found - 'nothing confirmed' means 'no large edge', not 'no edge at all'.**

## Timeframes studied

| TF | Bars | From | To | Hypotheses |
|---|---|---|---|---|
| 1m | 29,999 | 2026-10-11 | 2026-11-01 | 90 |
| 3m | 29,999 | 2026-08-31 | 2026-11-01 | 90 |
| 5m | 29,999 | 2026-07-20 | 2026-11-01 | 90 |
| 15m | 29,999 | 2025-12-24 | 2026-11-01 | 90 |
| 30m | 29,999 | 2025-02-14 | 2026-11-01 | 90 |
| 1H | 28,813 | 2023-07-19 | 2026-11-01 | 90 |
| 2H | 14,399 | 2023-07-20 | 2026-11-01 | 42 |
| 4H | 7,203 | 2023-07-20 | 2026-11-01 | 42 |
| 1D | 3,363 | 2017-08-17 | 2026-10-31 | 42 |
| 1W | 479 | 2017-08-21 | 2026-10-19 | 42 |

Timeframes not listed (1M and above) have too little history for any statistical statement; 1W has very low power.

## Patterns that passed out-of-sample confirmation

**None.** No pattern kept a statistically significant advantage out of sample after correcting for the number of patterns tested.

## Strongest discovery candidates and what happened out of sample

Shown even when they failed, so you can see how much looks like an edge in-sample and then disappears.

| TF | Pattern | Side | IS n | IS lift (R) | IS FDR q | OOS n | OOS win | OOS gross R | OOS net R | OOS lift (R) | OOS p | Holm p | Lift if entry 1 bar later |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | no candidate passed discovery | | | | | | | | | | | |

Full catalogue (every pattern x timeframe with its statistics): `docs/reports/data/PATTERN_EDGE_BTCUSDT.csv`.

## Reading guide

* A pattern with high win rate but negative lift is just the market's drift or the 2:1 bracket - not information.
* Many tests means some will look good by chance: a lone p < 0.05 means nothing here; only Holm-corrected out-of-sample results count.
* Short timeframes pay the same fee on much smaller moves, so net results degrade sharply as the timeframe shrinks.
