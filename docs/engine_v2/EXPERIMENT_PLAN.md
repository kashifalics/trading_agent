# Experiment 5: strategy engine v2. Plan for approval

**Status: proposed, not run.** No v2 strategy has been backtested. Nothing in this plan runs until the owner approves it in
writing. The sealed XAUUSD final-test period (from 2023-06-24) is not read by anything here.

## 1. Questions

1. Does any of the six v2 strategies (`DESIGN.md`, section 4) have a positive expected result after realistic costs, beyond what
   matched random entries give?
2. Does the regime classifier separate conditions in a useful way? That is, do the strategies perform differently, as designed,
   inside and outside their compatible regimes?

## 2. Data and segments

| Data | Use |
|---|---|
| Dukascopy XAUUSD M1 bid/ask, 2003-05 to 2020-02-07 (training segment of the frozen split) | development: walk-forward |
| XAUUSD 2020-02-08 to 2023-06-24 (validation segment) | confirmation only, once per frozen candidate set |
| XAUUSD from 2023-06-24 (sealed final test) | **not used.** A one-time final test needs a separate pre-registration and a separate approval |
| Dukascopy EURUSD and GBPUSD M1 bid/ask (free download, not on disk yet) | cross-instrument check. Before anything is looked at, a 70/15/15 split is frozen with the existing split tool, and the last 15% is sealed the same way |

**Honest disclosure.** Experiments 1-4 already used the XAUUSD validation segment to confirm their candidates. The v2 rules are new
hypotheses, but that segment is no longer pristine, so the multiple-testing correction below counts the earlier trials too.

## 3. Frozen candidate universe

**What is tested:**
- Six strategies × two directions × the signal timeframes M5, M15, M30, H1, H4, H8, D1 = **84 cells** per instrument.
- M1/M3: costs dominate and the data volume is large, so they are reported descriptively only.
- W1/MN1: too few trades, so they are not tested.
- Parameters exactly as in `DESIGN.md` (frozen by the git commit that adds this file). No variants are tested.

**Cell rules:**
- A cell is tested only if it has ≥ 100 trades in the development segment. This rule counts trades, never outcomes.
- Each tested cell reports its minimum detectable effect.
- Breakdowns by regime, session, year and direction are descriptive, not extra tests.

**Trial count for the deflated Sharpe:** 84 × instruments, plus the 1,981 trials of Experiments 1-4.

## 4. Simulation (same simulator as the gold study, `gold_research/sim.py`)

- **Execution:**
  - Signals are evaluated on completed candles.
  - Execution starts at the next M1 bar's open (signal-to-execution delay of 1 minute).
  - Long positions fill at the ask and exit at the bid; shorts mirror this.
- **Limit and stop orders:**
  - A limit order fills only if price trades through it by 1 tick.
  - A stop order fills at the worse of the stop and the bar's open.
  - Any order unfilled at expiry counts as missed and is reported.
- **Intrabar resolution:** M1 bars inside every signal-TF bar.
  - When the stop and a target touch in the same minute, the stop counts.
  - The optimistic result is reported beside it.
- **Exits:** the stop, or TP1 with the full position (main result). The partial-exit variant is descriptive only: one third each at
  TP1/TP2/TP3, stop moved to entry after TP1.
- **Time stop:** none in the main result, matching the paper forward test. A 48-bar time stop is reported as a sensitivity.
- **Costs:**
  - Real Dukascopy spread on every trade.
  - Slippage scenarios of 0, 0.1 and 0.3 × the median spread.
  - Commission 0 (spread broker).
  - Swap: a scenario of ±0.02R per night held, because no free swap history exists.
  - Cost sensitivity: everything re-run with 2× spread.
- **Leakage controls:**
  - Price-action events are used only from their confirmation bar onward (existing look-ahead tests).
  - Trades are purged by their own exit time at segment boundaries.
  - Walk-forward folds: expanding yearly folds inside the training segment, with an embargo of the longest holding period.

## 5. Baselines

- **Matched random entries:** about 10 per signal. Same timeframe, direction, entry type, stop distance in ATR and target R
  multiples; same hour of the week and the same volatility percentile; same segment.
- **The v1 engine** on the same data: its replay already exists.
- **Always-in-direction-of-HTF-trend:** entries at random times, with the same stops and targets.

## 6. Statistics and acceptance criteria (all must hold)

**In development (walk-forward, out-of-fold):**
- Expectancy after costs > 0, and above the matched random baseline, with BH q < 0.10 across the 84 cells.

**In validation (one run, frozen):**
- ≥ 100 trades.
- Expectancy after costs > 0, with the 95% block-bootstrap CI (clusters = weeks) above 0.
- Profit factor ≥ 1.2.
- Better than the matched random baseline (Holm-adjusted p < 0.05 across the cells carried from development).

**Robustness:**
- Positive in ≥ 60% of development years.
- Still positive after removing the best year.
- Still positive at 2× spread.
- Not carried by one direction only (reported).

**Overfitting:** deflated Sharpe ≥ 0.95 counting all trials (section 3), and CSCV probability of backtest overfitting ≤ 0.2.

**Win rate is never a criterion.** An 80% win rate with negative expectancy fails.

**Reported for every tested cell:**
- trades, win rate, average win and average loss, expectancy R with CI, profit factor;
- Sharpe, Sortino, maximum drawdown in R, recovery factor;
- long/short, regime, session and year breakdowns;
- cost sensitivity, deflated Sharpe, and the result against each baseline.

## 7. Regime-classifier usefulness (descriptive, same runs)

For every strategy, report expectancy inside its compatible regimes against outside them, with CIs. The classifier is called useful
only if compatible-regime expectancy exceeds incompatible-regime expectancy in development and validation alike. Even then, its
thresholds are not tuned on these results.

## 8. What happens after

- **A passing cell:** it goes into a separate, pre-registered proposal for the one-time sealed final test (owner approval), then a
  paper forward test with frozen parameters. Only after sufficient forward evidence (≥ 100 closed trades, CI above 0) may it be
  labelled VALIDATED in the product.
- **No passing cell:** the result is published as it is, as with Experiments 1-4, and every v2 strategy stays INSUFFICIENT EVIDENCE /
  NOT VALIDATED.
- **No re-runs with changed parameters on the same data.** Any change is a new experiment with a new plan and a new trial count.

## 9. Cost and runtime

$0: Dukascopy data is free and everything runs on this PC. The estimate is about 6-12 hours of computation for XAUUSD (84 cells with
M1 resolution), plus the FX download (several hours, rate-limited politely).

**Approval requested for:** (a) downloading Dukascopy EURUSD/GBPUSD M1 and freezing their splits, (b) running sections 4-7 on the
development and validation segments.
