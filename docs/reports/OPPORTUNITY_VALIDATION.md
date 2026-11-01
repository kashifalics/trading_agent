# Trade Opportunities — strategy validation

_Generated 2026-11-01 15:53 UTC from stored experiments; config version `2026-11-02.1`. Nothing here was tuned: the rules and thresholds were fixed before the first run._

## Method

* The setup rules (`app/opportunities/setup.py`, the same function the live scan calls) are replayed bar by bar using only information available at each bar.
* A trade is opened at the **next bar's open** after a *fresh* trigger (confirmation on the latest bar), with the setup's structural stop and first target; the time stop is 2x the style's expected holding.
* Same-bar stop/target ambiguity is resolved against the trade (stop first). One position at a time; 1% of equity risked.
* Costs: BTCUSDT 0.10% taker fee + 0.01% slippage per side + 0.002% spread (0.222% round trip); XAUUSD 0.005% slippage per side + 0.01% spread (0.020% round trip).
* The first 60% of each series is *development* (reported, not used for decisions); the last 40% is *out-of-sample (OOS)*. Status uses OOS trades only.
* **validated** needs >= 100 OOS trades, bootstrap 95% CI of net expectancy above 0, p < 0.05, >= 2/3 of OOS sub-periods positive and better than random entries; **negative** = CI entirely below 0; otherwise **no_edge**.
* Not covered by this replay: the evidence score and the analogue search (they are not entry rules), calendar-month higher-timeframe filters (1W entries have no HTF filter), and non-UTC daily/weekly anchoring.

## Summary

16 instrument/style/timeframe combinations tested: **16 no_edge**.

## BTCUSDT

| Style | TF | Trades dev / OOS | OOS net E[R] (95% CI) | OOS win | OOS PF | OOS gross E[R] | OOS long / short E[R] | Random-entry E[R] | OOS max DD (R) | Net return (full) | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| scalping | 5m | 0 / 0 | n/a n/a | n/a | n/a | n/a | n/a / n/a | -1.443 | n/a | +0.0% | **no_edge** |
| scalping | 15m | 0 / 0 | n/a n/a | n/a | n/a | n/a | n/a / n/a | -0.736 | n/a | +0.0% | **no_edge** |
| intraday | 15m | 1 / 0 | n/a n/a | n/a | n/a | n/a | n/a / n/a | -0.736 | n/a | +0.5% | **no_edge** |
| intraday | 1H | 2 / 2 | +0.817 n/a | 1.00 | n/a | +0.898 | +1.12 / +0.52 | -0.216 | 0.0 | +4.4% | **no_edge** |
| swing | 4H | 8 / 4 | -0.012 n/a | 0.50 | 0.97 | +0.037 | n/a / -0.01 | -0.040 | 1.7 | -2.9% | **no_edge** |
| swing | 1D | 20 / 16 | +0.206 [-0.50, +1.00] | 0.50 | 1.39 | +0.259 | +0.17 / +0.35 | -0.052 | 2.8 | +7.5% | **no_edge** |
| long_term | 1D | 21 / 16 | +0.206 [-0.50, +1.00] | 0.50 | 1.39 | +0.259 | +0.17 / +0.35 | +0.047 | 2.8 | +6.3% | **no_edge** |
| long_term | 1W | 2 / 9 | +0.352 n/a | 0.67 | 2.03 | +0.376 | +0.81 / -0.56 | +0.025 | 1.0 | +9.3% | **no_edge** |

Experiments: #64, #52, #54, #56, #58, #61, #65, #66. Dataset snapshots hash the exact stored candles (e.g. BTCUSDT 1D `7ef27612d2e716ca`).

<details><summary>Reasons per combination</summary>

* intraday 15m: only 0 out-of-sample trades (< 100): no conclusion possible
* intraday 1H: only 2 out-of-sample trades (< 100): no conclusion possible
* long_term 1D: only 16 out-of-sample trades (< 100): no conclusion possible
* long_term 1W: only 9 out-of-sample trades (< 100): no conclusion possible
* scalping 15m: only 0 out-of-sample trades (< 100): no conclusion possible
* scalping 5m: only 0 out-of-sample trades (< 100): no conclusion possible
* swing 1D: only 16 out-of-sample trades (< 100): no conclusion possible
* swing 4H: only 4 out-of-sample trades (< 100): no conclusion possible

</details>

## XAUUSD

| Style | TF | Trades dev / OOS | OOS net E[R] (95% CI) | OOS win | OOS PF | OOS gross E[R] | OOS long / short E[R] | Random-entry E[R] | OOS max DD (R) | Net return (full) | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| scalping | 5m | 12 / 9 | +0.103 n/a | 0.67 | 1.30 | +0.168 | n/a / +0.10 | -0.389 | 2.9 | -1.0% | **no_edge** |
| scalping | 15m | 35 / 16 | -0.553 [-0.89, -0.16] | 0.31 | 0.22 | -0.430 | -1.02 / -0.40 | -0.265 | 9.8 | -8.0% | **no_edge** |
| intraday | 15m | 25 / 11 | -0.391 [-0.80, +0.03] | 0.45 | 0.30 | -0.357 | -1.02 / -0.25 | -0.265 | 4.7 | -8.2% | **no_edge** |
| intraday | 1H | 67 / 27 | +0.047 [-0.38, +0.51] | 0.48 | 1.09 | +0.084 | -0.11 / +0.14 | -0.080 | 6.4 | +6.8% | **no_edge** |
| swing | 4H | 50 / 52 | +0.058 [-0.23, +0.35] | 0.54 | 1.12 | +0.072 | +0.08 / -1.00 | -0.004 | 5.2 | -4.9% | **no_edge** |
| swing | 1D | 12 / 19 | -0.181 [-0.57, +0.23] | 0.47 | 0.66 | -0.176 | -0.08 / -1.00 | +0.066 | 5.2 | -5.0% | **no_edge** |
| long_term | 1D | 12 / 20 | -0.222 [-0.61, +0.18] | 0.45 | 0.60 | -0.217 | -0.14 / -1.00 | +0.055 | 6.2 | -7.1% | **no_edge** |
| long_term | 1W | 1 / 4 | -0.588 n/a | 0.25 | 0.22 | -0.586 | -0.59 / n/a | +0.090 | 2.4 | -0.8% | **no_edge** |

Experiments: #51, #53, #55, #57, #59, #60, #62, #63. Dataset snapshots hash the exact stored candles (e.g. XAUUSD 5m `14c3b87fa6ec52b5`).

<details><summary>Reasons per combination</summary>

* intraday 15m: only 11 out-of-sample trades (< 100): no conclusion possible
* intraday 1H: only 27 out-of-sample trades (< 100): no conclusion possible
* long_term 1D: only 20 out-of-sample trades (< 100): no conclusion possible
* long_term 1W: only 4 out-of-sample trades (< 100): no conclusion possible
* scalping 15m: only 16 out-of-sample trades (< 100): no conclusion possible
* scalping 5m: only 9 out-of-sample trades (< 100): no conclusion possible
* swing 1D: only 19 out-of-sample trades (< 100): no conclusion possible
* swing 4H: only 52 out-of-sample trades (< 100): no conclusion possible

</details>

## How to read this

* *OOS net E[R]* is the average result per trade in multiples of the risk taken, after costs, on data the rules were never adjusted on. 0 means break-even.
* A wide CI that spans 0 means the data cannot distinguish the rules from a coin flip. With few trades the CI is wide: **"no_edge" with a small sample is absence of evidence, not evidence of absence.**
* *Gross* (zero-cost) expectancy shows whether costs alone are the problem. *Random-entry* expectancy is what the same execution model earns with no skill.
* Results on one instrument over a finite history are not a guarantee about the future.
