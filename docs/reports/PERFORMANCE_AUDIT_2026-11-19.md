# Live performance audit — 2026-11-19

## Executive summary

This audit uses a read-only snapshot of the production paper-trading API, generated at **2026-11-19 05:02 UTC**. The 646 closed
forward-test trades cover **2026-11-07 21:31 through 2026-11-19 04:48 UTC**.

**The all-signals forward test is effectively flat, not demonstrably profitable or losing:** net expectancy is **−0.0008R per
trade**, profit factor **1.00**, and the nominal 95% trade-level interval is **−0.188R to +0.187R**. The evidence does not
establish an edge. Many individual trades lose, but the average winner is large enough that the overall result is almost exactly
at break-even.

The active paper account is a different sample: **208 closed account-taken trades**, +0.231R per trade, with a nominal 95% interval
of **−0.116R to +0.578R**. Its simulated balance is **$12,467.84** from $10,000 (**+24.68% realized**); current equity is
$13,025.31, including +$557.47 unrealized. That is a positive paper result, but it is not statistically conclusive, is not a
broker result, and should not be confused with the full-signal record.

## Overall forward-test results

| Metric | Result |
|---|---:|
| Closed signals | 646 |
| Positive / non-positive outcomes | 162 / 484 |
| Win rate | 25.08% |
| Average winning outcome | +3.425R |
| Average non-winning outcome | −1.147R |
| Net expectancy | −0.0008R per trade |
| Nominal 95% interval for expectancy | −0.188R to +0.187R |
| Profit factor | 0.999 |
| Cumulative net result | −0.485R |
| Average gross result before configured spread | +0.1231R per trade |
| Average configured spread cost | −0.1238R per trade |
| Gross stop exits worse than −1R | 4 of 646 |

The observed win/loss sizes imply a break-even win rate of about **25.1%**. The observed 25.08% is essentially that threshold,
leaving no margin for estimation error or real-world costs. The especially telling result is that gross expectancy is slightly
positive, but the configured spread cost consumes all of it. Four gross exits were worse than −1R, so large gap losses alone do
not explain the flat aggregate result.

### Results by direction

| Direction | Trades | Win rate | Expectancy | Total |
|---|---:|---:|---:|---:|
| BUY | 159 | 15.09% | −0.500R | −79.56R |
| SELL | 487 | 28.34% | +0.162R | +79.08R |

The aggregate is a near-cancellation between a substantially negative BUY sample and a positive SELL sample. This is a strong
diagnostic signal, not proof that short trades are intrinsically better: instruments, dates, and setups differ between groups.
For example, BUY results were negative in BTCUSDT (40 trades, −0.534R), USOIL (49, −0.490R), and US30 (25, −1.062R), while
SELL results varied by instrument. The next test should control for instrument, timeframe, and setup rather than simply remove
one direction based on this sample.

### Largest negative and positive groups

| Breakdown | Trades | Expectancy | Total | Interpretation |
|---|---:|---:|---:|---|
| USOIL | 152 | −0.236R | −35.89R | Largest negative instrument contribution |
| BOS retest | 270 | −0.128R | −34.64R | Largest negative setup contribution |
| 30m | 38 | −0.626R | −23.77R | Poor result, but still a small sample |
| Trend pullback | 320 | +0.084R | +26.75R | Slightly positive overall; BUY and SELL differ sharply |
| BTCUSDT | 244 | +0.110R | +26.94R | Positive in this short snapshot |
| 15m | 61 | +0.286R | +17.42R | Positive, not enough evidence to validate |

Within the BOS-retest group, SELL trades (207) were +0.032R while BUY trades (63) were −0.654R. Trend-pullback SELL trades
(235) were +0.272R while BUY trades (85) were −0.438R. This supports investigating direction/setup interactions; it does not
establish that a filter will work out of sample.

The score bands are not reliably monotonic: scores 60–69 (441 trades) averaged −0.091R, scores 70–79 (181) +0.226R, and
scores 80–100 (24) −0.059R. The top band is too small to interpret, and these retrospective bands are not a validated entry
filter.

## Transaction-cost and timeframe diagnostic

The following are per-trade averages. “Spread cost” is the configured round-trip spread divided by the trade's initial risk.

| Timeframe | Trades | Gross R | Spread cost | Net R |
|---|---:|---:|---:|---:|
| 1m | 211 | +0.128 | 0.173 | −0.045 |
| 3m | 152 | +0.117 | 0.126 | −0.009 |
| 5m | 146 | +0.061 | 0.091 | −0.030 |
| 15m | 61 | +0.397 | 0.111 | +0.286 |
| 30m | 38 | −0.558 | 0.067 | −0.626 |
| 1H | 19 | +0.564 | 0.049 | +0.516 |

The 1m, 3m, and 5m cohorts make up **509 of 646 trades (78.8%)** and together contribute about **−15.33R**. At 1m, the
average spread charge alone exceeds the average gross result. The 30m cohort is also notably weak before costs, but with only 38
trades it is not yet a reliable estimate. Positive results on 15m and higher timeframes have comparatively small samples.

## Paper-account result — separate from the forward test

The active account took 208 closed trades; the API reported 616 signals not taken for that account, five active account positions,
and six open plus one pending trade in the full forward-test record. The account's realized-balance drawdown was **$1,080.47**.
Its 208-trade expectancy is positive, but the nominal 95% interval crosses zero. Position limits and signal selection can create
a different sample from “every signal”; a positive account balance over this short period does not validate the underlying rules.
The reported open-trade profit is unrealized and can change.

## Historical reference and interpretation

The existing out-of-sample replay reference is **414 trades at −0.188R per trade**. It is negative and consistent with “no proven
edge,” but it is not a like-for-like comparison with this live paper sample: the instruments, timeframes, market period, and
selection differ.

The most supportable explanation for the weak full-signal performance is:

1. **The payoff edge is too thin.** The realized win/loss mix is almost exactly at break-even.
2. **Spread consumes the small gross advantage.** Average gross R is +0.1231R and average configured spread drag is 0.1238R;
   this is most acute on 1m–5m trades.
3. **Results are concentrated in weak cohorts.** BUY trades, USOIL, BOS retests, and especially 30m trades account for large
   negative contributions. These categories overlap, so their losses must not be added as independent causes.
4. **The account and signal book are not the same population.** The paper account's positive result comes from a selected subset
   and is still uncertain; it does not contradict the nearly flat all-signals result.

This audit does **not** show that any individual open trade is certain to lose. At the snapshot, the paper account itself had
positive realized and unrealized P&L. These are simulated paper trades only: no broker orders or real-money fills are involved.

## Recommended next validation

Before changing live rules, run a pre-specified, cost-aware holdout/forward test that separately reports BUY and SELL by
instrument × timeframe × setup, especially for USOIL and BOS retests. Include realistic spread and slippage assumptions and
account for trades clustered in the same market period. Do not select score thresholds or disable cohorts using this same
outcome sample; freeze any proposed change and evaluate it on new unseen data. Keep the existing “not validated” status until
the evidence bar in the paper-trading methodology is met.

## Method and limitations

- Read-only production API snapshot; all 646 closed rows were fetched across paginated results. No account settings or trades were
  changed.
- R outcomes are net of the configured spread. The report's gross and spread figures were reconstructed from each row's
  `r_gross`, `r_net`, `spread`, and `risk`.
- Expectancy intervals are nominal normal trade-level 95% intervals, matching the app's metric convention. They assume
  independent trades; cross-timeframe and same-session clustering can make them too narrow.
- The simulator uses configured spreads and accounts for gaps, but does not model ordinary slippage, commissions, financing,
  liquidity constraints, or actual broker execution.
- See [Paper trading methodology](../PAPER_TRADING.md), [historical signal track record](SIGNAL_TRACK_RECORD.md), and
  [quantitative validation summary](QUANTITATIVE_VALIDATION_SUMMARY.md) for definitions and historical tests.
