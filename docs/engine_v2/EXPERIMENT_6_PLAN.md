# Experiment 6 plan: do VSA and indicator confirmations improve the six strategies?

Status: draft for the owner's review, 2026-11-13. It tests the design in [CONFIRMATION_DESIGN.md](CONFIRMATION_DESIGN.md).
Nothing in this plan has been run.

**Question.** For each strategy, does keeping only the trades whose confirmation category is PASS improve net results? The test
is made against the strategy without the filter, and against random filters that drop the same share of trades.

## 1. Rules that do not change

- **Sealed data.** The XAUUSD sealed final test (from 2023-06-24) is never read: the store refuses it. The BTCUSDT final 15% is
  sealed the same way, before anything is looked at.
- **Fixed thresholds.** Every threshold is the value in CONFIRMATION_DESIGN.md sections 5 and 7. Nothing is tuned on any data.
- **Pre-registration before outcomes.** The pre-registration (section 6) is committed before any filtered outcome is
  computed.
- **Promotion is not validation.** A filter that passes becomes a gate (design section 8). Its strategy stays NOT VALIDATED
  unless it meets Experiment 5's own criteria (section 8 below).
- **Same execution as Experiment 5.** Every arm reuses the baseline trades, so execution is identical by construction.

## 2. Data

| | XAUUSD | BTCUSDT |
|---|---|---|
| Source | Dukascopy M1 bid/ask, already on disk | Binance public archive, spot 1-minute klines (`data.binance.vision`, monthly files from 2017-08 to the last complete month), each file checked against its published checksum |
| Volume | Dukascopy venue volume (bid + ask), research only | Binance base volume and taker-buy volume, the same source as the live engine |
| Development | 2003-05 to 2020-02-07: Experiment 5's training trades | first 70% of 1-minute candles |
| Confirmation (once) | 2020-02-08 to 2023-06-24 | next 15% |
| Sealed | from 2023-06-24 | last 15% |
| Costs | real bid/ask from the data | the owner's broker spread, $2 round trip (applied as bid/ask = price ∓ $1) |
| Cost sensitivity | 2× the spread | $4 round trip; Binance taker fee 0.1% per side (reported) |

**Notes on the data:**
- **BTCUSDT split.** Made 70/15/15 by 1-minute candle count, boundaries moved to the next Monday 00:00 UTC. It is written to
  `docs/research/BTCUSDT_split.json` with the archive checksums and committed before any event is generated.
- **Archive timestamps.** They are milliseconds before 2025 and microseconds from 2025; both are normalised.
- **Disclosure.** Experiments 1-4 used the XAUUSD confirmation segment, so it is not pristine; their trials are counted
  (section 7). Experiment 5's gold development results per strategy cell were published before this plan. The confirmation
  filters are new and fixed here, before any filtered outcome exists.

## 3. Baseline trades

- **XAUUSD.** Experiment 5's development trades for its 51 tested cells (strategy × direction × timeframe with ≥ 100 signals),
  65,103 trades. Each has its outcome under Experiment 5's primary setting: the plan's stop, TP1 (rounded down to 0.1R), a
  96-candle horizon, and one trade at a time per cell.
- **BTCUSDT.** The same 84-cell run as Experiment 5 (6 strategies × 2 directions × 7 timeframes, M5 to D1 plus H8). The same
  ≥ 100-signal count rule, the same outcome setting, the same simulator. This baseline is a strategy test in its own right: it
  is reported like Experiment 5, and its cells are counted as trials.
- **Re-scoring.** Each trade is scored at its signal candle by re-running the strategy at that candle, using the engine's
  point-in-time view. The result must reproduce the stored signal (same direction, entry and stop; a mismatch stops the run)
  and adds its key candles, so the confirmation matrix can be computed.

## 4. Arms

Per strategy and instrument, five arms. A trade is kept only when the named category (or every category in the combination)
is PASS. NEUTRAL, FAIL and UNAVAILABLE are dropped.

| Arm | Keeps a trade when |
|---|---|
| VSA | VSA is PASS |
| Trend | trend is PASS |
| Momentum | momentum is PASS |
| Volatility | volatility is PASS |
| Combination | every category in the strategy's required combination (design section 7) is PASS |

That makes 6 strategies × 5 arms × 2 instruments = 60 registered arms. Trades are pooled across the strategy's timeframes and
both directions; results by timeframe and by direction are reported, not tested.

**Count rule, decided from counts only.** An arm enters the test family only if it keeps ≥ 300 development signals and drops
≥ 10% of them. Signals are counted rather than filled trades, because whether a limit order fills depends on the price path.
Counts are known before outcomes, so the family is fixed in the pre-registration. The ≥ 300 kept-trades criterion (section 6)
is checked after simulation.

## 5. Measures

**Tested.** Per arm, the net expectancy of the kept trades: mean R after costs.

**Reported** for the baseline, the kept trades and the dropped trades:
- trades, win rate (TP1 before stop), net expectancy, profit factor;
- per-trade Sharpe (mean / standard deviation of R);
- maximum drawdown in R, with trades in time order;
- false-entry reduction: the share of stop-outs among kept versus dropped trades;
- results by regime, timeframe, direction, year and cost level.

## 6. Statistics and pass criteria

**Random-filter control.** 20,000 random subsets of the strategy's baseline trades, each the same size as the kept set within
every stratum (timeframe × direction × year). The p-value is (1 + number of random means ≥ the kept mean) / 20,001. Taking
20,000 subsets lets Holm's strictest threshold (0.05 / 60) be reached.

**Uncertainty.** The 95% confidence interval of (kept − dropped) mean R uses standard errors clustered by ISO week.

**Development pass: all six must hold.**
1. The kept mean is above the baseline mean.
2. Holm-adjusted p < 0.05 against random filters, across the whole test family (both instruments).
3. The kept profit factor and Sharpe are at least the baseline's.
4. Kept minus baseline mean is positive in ≥ 60% of development years with ≥ 20 kept trades.
5. The improvement stays positive at doubled costs.
6. ≥ 300 kept trades (already enforced by the count rule).

**Confirmation pass**, one frozen run on the confirmation segment, for the arms that passed development:
- the same sign of improvement;
- p < 0.05 against random filters, Holm across the arms carried forward;
- an improvement still positive at doubled costs.

**Retention.** An arm that drops trades without improving expectancy and risk-adjusted results fails, whatever its trade-count
reduction.

## 7. Pre-registration file and trial count

`docs/research/EXP6_preregistration.json` is committed before any filtered outcome is computed. It holds:
- the code commit;
- the SHA-256 of the threshold section of `config.py`;
- the XAUUSD and BTCUSDT split hashes;
- kept and dropped development counts per arm;
- the test family after the count rule;
- the Holm order rule;
- this plan's commit.

**Trials.** 2,032 trials are counted before this experiment. This plan adds the BTCUSDT baseline cells tested and every arm in
the family. The new total is used by every deflated Sharpe calculation from here on.

## 8. What a result changes

- **Passes development and confirmation:** the category is added to `config.GATES` for that strategy on that instrument, in a
  commit citing the report. Gold arms that include VSA (the VSA arm and five of the six combinations) are tested and counted, but
  cannot be promoted, by design.
- **Strategy plus its passing filter also meets Experiment 5's development and validation criteria** (positive net expectancy,
  beats matched random entries, deflated Sharpe ≥ 0.95, positive in ≥ 60% of years): it becomes a candidate for a separate,
  pre-registered sealed final-test proposal, which needs the owner's approval. Until then its research status stays NOT
  VALIDATED.
- **Anything else:** the category stays evidence only, and the card says "did not pass Experiment 6".
- **No change to existing rules.** No result changes the mandatory checks or the strategies' own rules.

## 9. Order of work and outputs

1. **Build.** Design modules and tests, with no outcome data read.
2. **BTCUSDT data.** Download and verify checksums, build the timeframes, freeze the split (commit).
3. **Events.** BTCUSDT events up to the end of its confirmation segment (signals only, no outcomes). Every gold and BTCUSDT
   event is re-scored with the confirmation matrix.
4. **Pre-registration** (commit).
5. **Development run.** `docs/research/EXP6_development.json` (commit).
6. **Confirmation run, once.** `docs/research/EXP6_confirmation.json` (commit).
7. **Report.** `docs/reports/EXPERIMENT6_CONFIRMATIONS.md`, stating which confirmation helped, which did not, and the evidence
   for each, every number with its sample size, period and cost level. Then the gate commit, if any arm passed.

**EURUSD and GBPUSD** join later through an addendum with identical rules, once their history is complete and their own split
is frozen.
