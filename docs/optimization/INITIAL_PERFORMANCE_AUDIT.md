# Initial performance audit — 2026-11-19

## Executive finding

This is the audit-first baseline for the requested optimization work. It uses a read-only production paper-trading snapshot taken at
**2026-11-19 05:12 UTC**. No strategy, risk, account, or trade state was changed.

The **−25.79R** result is the Trade History page's default **most recent 100 closed trades**, not the lifetime forward-test result.
Those trades closed from **2026-11-18 02:29 through 2026-11-19 05:06 UTC**. The production record then contained 647 closed
signals in total, with cumulative net result **−1.60R** and expectancy **−0.0025R per trade**—effectively flat and not evidence
of a reliable edge. The recent 100-trade drawdown is real, but it is a concentrated short-window result.

In that recent window, the observed 22% target-hit rate was below the roughly 28% break-even rate implied by the sample's average
net win and loss. Losses were concentrated in short timeframes and a few instruments/setups; configured spread made the result
worse, but the window was already negative before spread. Several stopped trades recorded substantial favorable excursion before
their stop exit. These observations identify research questions, not proof that any one filter or exit change would work.

The user's 70% win-rate figure is treated as a research aspiration, not a promise, a pass criterion, or a reason to fit rules to
this sample. The existing research reference remains negative out of sample. Keep all strategies labelled **Not validated**.

## Snapshot and populations

| Population | Trades | Win rate | Net result / expectancy | Other observations |
|---|---:|---:|---:|---|
| All closed forward-test signals | 647 | 25.04% | −1.601R total; −0.00247R/trade | PF 0.997; nominal trade-level 95% CI −0.189R to +0.185R |
| Most recent 100 closed signals | 100 | 22% | −25.788R total; −0.2579R/trade | 22 targets, 78 stops; max drawdown 31R; longest stop streak 14 |
| Most recent 50 closed signals | 50 | — | −14.37R | Nested in the last-100 window |
| Most recent 200 closed signals | 200 | — | +6.31R | Includes the recent 100-trade drawdown |
| Active paper-account trades | 208 | — | +0.231R/trade; +48.0R total | Different, risk-limited subset; nominal 95% CI −0.116R to +0.578R |

Across all 647 signals, average gross result was **+0.1213R/trade** and configured spread drag was **0.1238R/trade**. Four
gross stop exits were worse than −1R. At the snapshot there were six open and no pending signal trades. The all-signal book and
the paper account are distinct populations: 40 of the last 100 signals were taken by the account and those account-taken trades
had **+$443.63** combined P&L. The account's positive result does not validate the strategy.

The previous [live performance audit](../reports/PERFORMANCE_AUDIT_2026-11-19.md) is an earlier 05:02 UTC snapshot with 646
closed signals. Its figures are retained as a historical snapshot; use this report for the refreshed 647-trade and last-100
comparison.

## What best explains the recent losses

### 1. The recent win/loss mix did not meet its own payoff break-even rate

The last 100 contained **22 target exits and 78 stop exits**. Average net result was approximately **+2.99R per target exit**
versus **−1.17R per stop exit**. At those observed payoff sizes, break-even requires about a **28.2%** win rate; the observed
rate was 22%. This is the direct arithmetic explanation for the negative recent-window expectancy. It does not explain why each
setup failed.

The recent signals' planned TP1 reward:risk had a median of **2.24R**, a 90th percentile of **5.5R**, and a maximum of **28.2R**;
11 of 100 were planned above 5R. Recomputing TP1 distance against the actual simulated fill and stop gives a median of **2.62R**,
a 90th percentile of **13.2R**, and a maximum of **97.9R**; 23 were above 5R and 16 above 10R. The fill-adjusted tail can be
inflated when the fill is close to the stop, so it is not a clean measure of target realism. Still, the very distant structural
targets are a credible hypothesis for the low hit rate and should be tested against a pre-specified, cost-aware alternative.
The current data cannot establish that nearer targets would improve net expectancy.

### 2. Some stopped trades had favorable excursion, but no profit-protection rule

Of the 78 recent stop exits, 23 recorded maximum favorable excursion (MFE) of at least +1R and six recorded at least +2R. The
median stop-trade MFE was **+0.414R** and the 90th percentile was **+1.675R**. The paper simulator holds the original stop and
closes at TP1 or stop; it does not take partial profits or trail the stop.

This makes exit management a worthwhile experiment, not a proven fix. MFE is reconstructed from candle highs/lows; the stored
trade does not retain the within-candle price sequence. A favorable high and the stop low may have occurred in the same candle,
so MFE does not prove that the excursion could have been captured or that moving a stop would have produced a better result.

### 3. Losses cluster in particular timeframes, instruments, and setups

Within the last 100, the reported net contributions included **1m −11.94R, 3m −11.65R, 30m −5.55R**; **XAUUSD −12.82R,
USOIL −8.79R, BTCUSDT −7.63R**; and **trend pullback −17.63R (45 trades), BOS retest −13.17R (47 trades)**. These
breakdowns overlap and must not be added as independent causes. They are descriptive slices of one short, correlated period,
not validated instrument or setup filters.

### 4. Directional bias and higher-timeframe alignment were insufficient

There were **94 SELL trades (−18.47R)** and six BUY trades (−7.32R). The tiny BUY count cannot support a directional rule.
Among 100 trades, 84 had both recorded higher-timeframe biases aligned with the trade direction; those trades still lost
**22.48R**, with 65 stop exits. Simple higher-timeframe alignment therefore did not protect this sample. The V1 paper engine
uses higher-timeframe bias as part of a quality score, not as a guarantee of success.

### 5. Late entries are not supported as the main explanation

For the recent window, median signal-detection delay was about **28 seconds** and the 90th percentile about **66 seconds**.
Market-entry drift had median **−0.034R** and 90th percentile **+0.178R**; none exceeded the engine's +0.3R chase limit.
There was one detection-delay outlier of roughly **65 minutes** that should be traced, but the typical delays and drift do not
explain the broad drawdown.

## Audit of the other failure hypotheses

| Hypothesis | Finding from current evidence |
|---|---|
| Stops are inside ordinary market noise | **Not established.** There were 78 stop exits in the recent 100, but that alone does not show the structural invalidation was too tight. V1 uses structural/invalidation-based stops with an ATR buffer and a minimum-distance rule. Four of all 647 gross stop exits exceeded −1R. The stored outcomes do not preserve enough intra-trade market path to attribute each stop to normal noise. |
| TP1 is too distant or unrealistic | **Plausible and testable, not proven.** Recent planned TP1 distances are often well above 2R, with a long upper tail; the observed target-hit rate is below its sample payoff break-even rate. Compare alternatives on new unseen data rather than selecting a target from this same window. |
| Entries arrive too late | **Not supported as the main driver.** Typical delay and fill drift were modest; review the single long-delay outlier separately. |
| Consolidation/chop causes false signals | **Unresolved.** The stored V1 trade record does not provide a sufficiently complete, auditable consolidation/regime label for this sample. Do not substitute V2 regime classifications: V2 is a separate engine and does not generate these V1 paper trades. |
| Higher-timeframe confirmation is missing or ineffective | **Alignment alone was insufficient.** Most recent trades had both recorded higher-timeframe biases aligned and still lost. This does not rule out more specific confirmation tests. |
| Multiple strategies conflict or issue duplicate trades | **No direct evidence of this as the principal cause.** The paper trades come from the legacy V1 Signals path, not the separate V2 strategy engine. V1 records one active/pending trade per instrument and timeframe, while other timeframes can still create overlapping exposure. The recent loss data do not establish that a conflicting signal caused an exit. |
| Costs are the sole reason for losses | **Rejected for the recent 100; costs are still material.** Recent gross expectancy was **−0.1033R/trade** before configured spread; average spread drag was **0.1546R/trade**, taking net expectancy to **−0.2579R/trade**. Thus this sample was negative before spread, and costs amplified it. The all-signal record was nearly flat before cost and slightly negative after cost. |
| Economic news or session timing caused the losses | **Unresolved.** V1 has no economic-news filter, and the paper records do not link trades to a news calendar. Session breakdowns are observational and confounded by this concentrated period; they do not prove a session rule. News-driven losses cannot be ruled in or out. |
| Fill or stop/target sequencing is incorrect | **No general sequencing defect demonstrated.** The simulator uses next-eligible-candle market fills, gap-aware live-paper stop exits, and conservatively resolves a candle touching both SL and TP as a stop. Existing tests cover these cases. The trade records do not flag same-candle collisions, so their frequency and contribution cannot be quantified from this snapshot. Ordinary slippage, commissions, financing, liquidity, and broker fills are not simulated. |
| The strategy trades too frequently or duplicates correlated risk | **Concentration is a credible amplifier, causality unproven.** The 100 closes span about 27 hours (roughly 3.7 closes/hour). V1 prevents a second live trade on the same instrument/timeframe, but allows separate timeframes on the same instrument; the paper account also has a five-position limit, not a market-correlation limit. The record does not provide an exposure-adjusted or cluster-robust result. |

## Data and interpretation limits

- The Trade History UI defaults to **Last 100** and computes its summary and running R only from the displayed rows. See the
  [history page](<../../frontend/src/app/(terminal)/history/page.tsx>). Its −25.79R is therefore a rolling-window figure, not
  lifetime performance.
- The production paper service records actionable signals from the older V1 engine and separately applies account position and
  daily-loss limits. See the [paper service](../../backend/app/paper/service.py). Do not combine account-only dollar P&L with
  all-signal R results.
- The nominal confidence intervals treat trades as independent. Repeated instruments, overlapping timeframes, and a
  concentrated market window violate that assumption and can make the intervals too optimistic.
- The configured spread is charged in R. The simulator does not model ordinary slippage, commissions, financing, liquidity
  constraints, or actual broker execution. This is a paper simulation, not broker performance.
- The historical out-of-sample reference remains **414 trades at −0.188R expectancy**. It is not a like-for-like cohort, but it
  reinforces that no edge has been demonstrated.
- All results are snapshots and can change as new trades close. The closed trade book is not a forecast of the next trade.

## Safe next steps

1. Preserve this report as the pre-change baseline; do not modify strategy logic on the strength of the same sample used to
   discover these patterns.
2. Define candidate tests in advance for TP1 distance, profit-protection/partial-exit rules, and correlation-aware exposure.
   Include spread and realistic slippage/cost sensitivity, and evaluate by instrument, timeframe, setup, and market period.
3. Replay candidates on development data, then evaluate once on genuinely unseen, time-ordered data. Keep the sealed XAUUSD
   final-test data untouched until the pre-specified candidate and evaluation procedure are frozen.
4. Keep strategy status **Not validated** unless a separate validation gate is met. A win-rate goal does not replace positive
   expectancy after costs, drawdown controls, and out-of-sample evidence.
5. Do not push or deploy optimization changes without explicit approval.

References: [paper trading methodology](../PAPER_TRADING.md), [signal engine](../SIGNAL_ENGINE.md), [historical signal track
record](../reports/SIGNAL_TRACK_RECORD.md), and the earlier [live performance snapshot](../reports/PERFORMANCE_AUDIT_2026-11-19.md).
