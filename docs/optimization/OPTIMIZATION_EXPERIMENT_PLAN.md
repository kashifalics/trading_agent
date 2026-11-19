# Performance optimization experiment plan

**Status: proposed; experiment execution and strategy changes are not authorized by this document.**

This plan follows the initial production performance audit and defines how to investigate the loss hypotheses without tuning on the
same outcomes used to discover them. It is an offline research plan, not a production-engine change. The sealed XAUUSD final-test
period is out of scope and must remain unread.

## 1. Decision baseline and scope

Use the read-only **2026-11-19 05:12 UTC** snapshot in
[INITIAL_PERFORMANCE_AUDIT.md](INITIAL_PERFORMANCE_AUDIT.md) as the current production baseline:

- 647 closed forward-test signals: **−1.601R** total, **−0.00247R/trade**.
- Most recent 100: **−25.788R**, 22% target exits, 78% stop exits; it is not lifetime performance.
- The refreshed account-taken subset is a distinct, risk-limited sample and must not be pooled with all-signal R results.
- The earlier 646-trade, 05:02 UTC figures in
  [PERFORMANCE_AUDIT_2026-11-19.md](../reports/PERFORMANCE_AUDIT_2026-11-19.md) remain a historical snapshot.

This short live-paper sample is **exploratory**. It has already been inspected and cannot serve as an untouched confirmation set for
filters or parameter selection. The historic XAUUSD validation segment also has prior use in earlier research; any reuse must
disclose and account for that testing history. The 70% win-rate objective is aspirational only. The research question is whether a
frozen candidate improves cost-adjusted expectancy and risk without leakage, not whether a threshold can be fit to produce a
particular win rate.

Scope is limited to the analysis-only platform. No broker order placement, account changes, paid data/API dependencies, pushing,
merging, or deployment is included.

## 2. System and evidence boundaries

### Production forward-test population

The existing [paper-trading service](../../backend/app/paper/service.py) records actionable plans from the legacy V1 Signals path.
The [paper simulator](../../backend/app/paper/simulator.py) executes those plans. The stored trade includes its point-in-time plan
snapshot, entry/stop/TP1, signal and detection times, fill and close times, setup type, session, costs, R outcome, MFE and MAE.
The current simulator exits at stop or TP1 only. The last-100 audit already found that target distance and unprotected favorable
excursion deserve further study, but those observations do not prove a better exit policy.

Do not silently treat V1 forward trades as results of the separate V2 strategy engine. V1 records setup labels such as
`trend_pullback` and `bos_retest`; the original V2 research has six named strategy families, and the current V2 implementation also
contains CRT as a later, separately unvalidated strategy. Report V1 and V2 results as separate populations and versions.

The [V2 regime classifier](../../backend/app/strategy_engine/regime.py) emits point-in-time TRENDING, RANGING,
CONSOLIDATING, HIGH_VOLATILITY, or UNKNOWN labels from completed candles. It was not attached to the V1 production trades.
Historical V1 regime attribution therefore requires a causal re-score of the exact decision-time candle, with replay checks, rather
than assigning present-day or later regime labels. VSA/volume inputs require the same point-in-time and source-reliability checks;
spot FX, gold, US30, and oil tick/venue volume must not be represented as centralized market-wide volume.

### Data-access and evidence checks before calculations

1. Inventory available candle coverage, provider/source, timezone, gaps, spread fields, and plan/snapshot completeness for each
   candidate trade. Do not infer price path from a summary statistic.
2. Use only data dated no later than the trade's decision for its entry features and regime; use only later bars for outcome and
   excursion calculations. Reconstruct indicators on completed bars and prove they reproduce stored signal fields.
3. Keep the 647-row production sample read-only. Do not reset the paper account, modify signal rows, change settings, backfill trades,
   or re-label historical outcomes.
4. For historical replay use the repository's guarded historical loader and non-sealed authorized segments only. Do not enumerate,
   open, hash, query, or derive statistics from sealed final-test files. Stop if a data source cannot prove it is non-sealed.
5. If intrabar bars are unavailable or incomplete, mark the diagnostic unavailable/censored; do not substitute a coarser series
   without recording its resolution and uncertainty.

## 3. Root-cause hypotheses to carry into research

The initial audit establishes several descriptive findings, not validated interventions:

1. **Recent payoff shortfall:** the last 100's observed 22% target-hit rate was below the approximate 28.2% break-even rate from its
   observed average winner and loser.
2. **Target distance:** recent planned TP1 reward:risk had a long upper tail. Some target prices were structurally distant. Test
   whether a different pre-specified target rule improves net expectancy; do not assume that a nearer target does.
3. **Potentially recoverable excursion:** 23/78 stopped trades had recorded MFE ≥1R and 6/78 ≥2R. Candle high/low MFE does not
   reveal intrabar order; it cannot establish that a stop adjustment or partial exit was executable.
4. **Cohort concentration:** recent losses cluster in 1m/3m/30m, XAUUSD/USOIL/BTCUSDT, and trend-pullback/BOS-retest labels.
   These slices overlap and are not independent causes.
5. **HTF alignment:** 84 trades with both recorded higher-timeframe biases aligned still lost 22.48R. Alignment is not itself a
   demonstrated protective gate.
6. **Costs:** recent gross expectancy was already −0.1033R/trade before configured spread, and spread drag further reduced it by
   0.1546R/trade. Costs are material but do not independently explain the recent losses.
7. **Entry timing:** typical signal delay and market-fill drift do not support lateness as the main explanation; investigate the
   single long-delay outlier.
8. **Still unresolved:** decision-time regime and consolidation attribution, reliable news-event alignment, same-instrument
   multi-timeframe exposure, expiry sensitivity, and the frequency of ambiguous same-candle stop/target collisions.

These are not causal conclusions. Strategy disablement, stop widening, target caps, directional restrictions, and universal
indicator gates are not justified by these observations.

## 4. Trade-level diagnostic specification

Create the offline diagnostic first and freeze its definitions before examining subgroup outcomes. Preserve one row per recorded
signal and include:

| Field group | Required values and rules |
|---|---|
| Identity and plan | Trade ID; V1/V2 engine and config version; instrument; timeframe; setup/strategy; direction; planned entry/zone; actual fill; initial stop; TP1-TP3 where present; invalidation; planned and fill-adjusted target distances in R; signal, detection, fill, expiry, and close timestamps; order type and status. |
| Excursion | MFE/MAE in price and R from actual fill over eligible post-fill bars; first favorable-movement time; first passage of fixed R thresholds; TP1/TP2/TP3 approach and touch; stop passage; holding duration. Keep unfilled, expired, open, and incomplete-path rows distinct from closed outcomes. |
| Ambiguity | Record candle resolution and data granularity for every barrier event. Same-candle stop/target or excursion order is ambiguous at that resolution; apply the pre-registered conservative stop-first convention to headline results and report the count. |
| Costs and fills | Configured/observed spread where available, spread in R, modelled commission/slippage scenarios, planned-to-fill drift, gap and chase status, limit touch/fill rules, and data source. Never label unmodelled costs as zero actual cost. |
| Decision-time context | V1 signal evidence snapshot; causal V2 feature/regime re-score where reconstructable; higher-timeframe bias as it existed at signal time; setup/confirmation states; session; volume reliability/source; spread and target room; news risk only if a reliable historical calendar and timestamp join are available. |
| Correlation/exposure | Overlapping open/pending trades by instrument and time; direction conflicts; same-market multi-timeframe clusters; cluster identifier for week/session and market event when supportable. Do not count correlated trades as independent evidence. |

Definitions:

- MFE is the maximum direction-adjusted favorable movement after fill; MAE is the maximum adverse movement after fill. Divide by
  absolute fill-to-initial-stop distance for R measures. Keep gross excursion separate from spread-adjusted realized R.
- “TP reached” means the eligible price series crossed the exact stored target under the specified side-aware execution rule.
  “TP approached” is a separate, pre-registered distance-to-target metric; descriptive quantiles must not be retrospectively turned
  into a pass/fail threshold.
- “Stop before target” is known only when the available bar resolution orders the events. If both boundaries fall in the same
  unresolved candle, label ambiguous and apply stop-first in the conservative primary result.
- Entry, regime, volume, session, and confirmation features must use only data available at the signal decision. Outcome bars may
  inform excursions, never the entry gate.

The initial excursion report should answer which stopped trades later had favorable excursion, which showed little favorable
movement, how often TP levels were approached/reached, and how findings vary by V1 setup, instrument, timeframe, and session.
Use counts and uncertainty intervals; mark small cells descriptive only. Historical data coverage may prevent full timing or
barrier-order reconstruction. Missing evidence is reported as unavailable, not imputed.

## 5. Registered experiment matrix

Each arm must be implemented in an **offline research harness** with a reproducible dataset snapshot, code commit, frozen
configuration, and output. Production V1 and V2 decision code remains unchanged until a separate reviewed proposal passes all gates.

| Arm | Isolated question | Control |
|---|---|---|
| A — Baseline | Reproduce the existing strategy and execution rules | Must match the frozen baseline trade list and R within documented rounding |
| B — Entry only | Do strategy-specific location/structure/confirmation states improve selection? | Same stop, target, costs, and sizing as A |
| C — Stop only | Do structural, sweep-extreme, invalidation, ATR, or volatility-adjusted structural stops improve outcomes without changing entry? | Same entries and target policy as A; never widen solely to avoid a stop |
| D — Target/exit only | Compare frozen fixed-R, ATR, structural, liquidity/swing targets; full exit, partial schedules, trailing/structure exits, and breakeven-after-TP1 variants | Same entries and initial stop as A; weighted realized trade-level R including all remaining-position losses |
| E — Regime only | Does a fixed strategy-compatible regime rule improve results? | Same entry, stop, target, and costs as A |
| F — Session only | Does a fixed session/high-spread rule improve results? | Same entry, stop, target, and costs as A |
| G — Combined | Does the frozen combination of independently eligible changes retain its gains? | Compare with A and each eligible isolated arm |
| H — Strategy-specific | Evaluate each supported strategy family independently, with instrument/timeframe cells fixed before outcome analysis | Use matched baseline/random controls and adequate counts |

For V1, test only its actual existing setup classes and available causal attributes; do not map V1 setup labels to V2 strategies by
name similarity. For V2, include the six documented families separately and list CRT separately as an untested later addition.
Range mean-reversion's existing V2 status is insufficient evidence; low-count cells are descriptive, not a reason to synthesize
trades or lower count requirements.

Indicators such as EMA, ADX/DMI, RSI, MACD, ATR/percentiles, Bollinger/Keltner, VSA, and existing structure/Gann outputs may enter
candidate confirmation only if implemented and causally available in the chosen engine. Treat correlated indicators as one
evidence family or compare against a same-trade-count/random-filter control; do not count several correlated readings as several
independent confirmations. Gann projections must be confirmed by price action. No new paid source is permitted. No reliable news
history means news filtering is not testable, not presumed.

## 6. Time splits, leakage controls, and statistics

1. **Development:** use only authorized non-sealed data. If a data set has a frozen split, preserve it. For additional instruments,
   freeze chronological boundaries from timestamp counts and data hashes before calculating any trade outcome; seal their final
   segment under the existing repository procedure.
2. **Walk-forward:** use expanding chronological folds. Purge training trades whose holding/outcome windows overlap a test segment
   and embargo by at least the maximum outcome horizon used by the experiment. Fit scaling, thresholds, or calibration only on
   the applicable training fold.
3. **Confirmation:** carry forward only frozen candidate rules and run the eligible confirmation segment once. Because previous
   XAUUSD work used its validation segment, disclose those trials and apply a multiple-testing correction; do not call it pristine.
4. **Sealed final test:** do not read it as part of this task. Any future one-time final test requires a separate preregistration,
   clear candidate freeze, and explicit owner approval.
5. **Execution:** preserve causal candle timing, bid/ask sides, spread, commissions where applicable, slippage sensitivity,
   execution delay, conservative limit fills, gap handling, position-overlap rules, and stop-first ambiguity. Report base and
   stress costs. Do not compare variants with different execution assumptions.
6. **Inference:** use confidence intervals and block/bootstrap or clustered uncertainty by week/session rather than assuming
   every trade is independent. Correct the frozen test family for multiple comparisons (Holm/BH as selected in the preregistration).
   Report minimum detectable effects and inadequate-power cells.
7. **Sensitivity:** report stability by year/fold, instrument, timeframe, direction, setup, regime, session, and costs. Do not tune
   on validation, repeatedly re-run a confirmation set, or select a threshold by its best observed subgroup.

Use the established repository validation bars as the starting proposal: at least 100 closed trades for any claim; net expectancy
after costs with a 95% block/cluster-aware interval above zero; statistical evidence under the pre-registered family-wise
procedure; positive results in at least two-thirds of chronological folds/periods; profit factor at least 1.2; and robustness to
removing the best period and doubling spread. Require comparison against the unchanged baseline and a matched control where the
filter changes which trades are retained. The final preregistration must specify one exact rule for each criterion before running;
no candidate becomes validated from this plan alone. A 70% win rate is neither necessary nor sufficient.

## 7. Implementation and review gates

| Gate | Deliverable | Required before proceeding |
|---|---|---|
| 0. Plan review | This file and the initial root-cause baseline | Owner reviews scope, data sources, split policy, and acceptance criteria |
| 1. Data audit | Coverage/completeness table and immutable snapshot manifest for authorized non-sealed data | Prove point-in-time inputs and non-sealed status; stop on ambiguity |
| 2. Diagnostic engine | Offline, read-only trade-level diagnostic and excursion calculations | Unit/property tests for MFE/MAE, threshold timing, target/stop touch, fills, costs, expiry, and same-candle ambiguity |
| 3. Root-cause report | `TRADE_EXCURSION_ANALYSIS.md` plus updates to the initial audit only when a new snapshot is explicitly dated | Reconcile counts to baseline; separate measured evidence, hypotheses, and unavailable fields |
| 4. Preregistration | Frozen candidates, arms, counts, seeds, splits, costs, statistical plan, and hashes | Owner approval before computing candidate outcome comparisons |
| 5. Offline experiments | A-H results and strategy comparison | Baseline reproduction; no production logic or account changes |
| 6. Confirmation | One-time, frozen, eligible non-sealed confirmation result | Adequate power and all registered criteria; no tuning after viewing |
| 7. Proposal | Surgical production/shadow-mode proposal, migration and rollback plan, tests | Explicit owner approval; keep analysis-only and preserve the original baseline |
| 8. Dashboard | Correctly labelled lifetime, rolling-window, and date-range analytics | API/UI consistency tests and clear paper-vs-broker distinction |

The eventual report set in the request is produced only when the corresponding evidence exists: trade excursion, entry, stop,
take-profit, regime/session, strategy comparison, parameter register, and final report. Do not create an “optimized performance”
report with no qualifying experiment. Dashboard work follows validated metric definitions; lifetime, last 100/50, last 30/7 days,
sample size/date range, expectancy, hit rates, stop rate, drawdown, loss streaks, and strategy/instrument/timeframe/regime
breakdowns must clearly identify the simulated forward-test population.

### Approved prospective shadow candidate — 2026-11-19

The owner approved an isolated paper-only evaluation prioritizing net expectancy. Freeze variant `tp1-cap-2r-v1` as follows: use the
same newly recorded signal, entry, stop, and configured spread as baseline; when planned TP1 reward/risk exceeds 2R, set the shadow
target to exactly 2R from planned entry, otherwise retain planned TP1. Compare paired outcomes only after both paths are terminal;
count terminal unfilled signals as 0R and exclude unresolved pairs. The candidate runs in parallel and must not modify baseline rows,
the paper account, V1/V2 strategy behavior, or live decisions. The cohort begins with signals recorded after this implementation;
the existing 20-trade sample and sealed XAUUSD final-test data are excluded. Results are exploratory and do not authorize promotion.

## 8. Non-negotiable safeguards

- Preserve the current and earlier dated baselines; never overwrite historical results or recast the last 100 as lifetime.
- Do not modify the paper account, platform permissions, real trade state, or production strategy in the diagnostic/experiment phase.
- Do not access sealed XAUUSD final-test data or any other sealed segment.
- Do not promote, disable, or suppress a losing strategy solely because of the exploratory 647-trade snapshot.
- Do not move stops retrospectively, widen stops to reduce stop counts, count TP1 as a full winner when later weighted exits lose,
  or omit spread/slippage and ambiguous executions.
- Keep all outputs reproducible and reversible. No push, merge, or deployment without separate explicit approval.

## References

- [Initial performance audit and root-cause findings](INITIAL_PERFORMANCE_AUDIT.md)
- [Earlier 646-trade snapshot](../reports/PERFORMANCE_AUDIT_2026-11-19.md)
- [Paper-trading methodology](../PAPER_TRADING.md)
- [Backtesting methodology](../BACKTESTING_METHODOLOGY.md)
- [Historical-data split and sealed-loader rules](../HISTORICAL_DATA.md)
- [V2 strategy experiment plan](../engine_v2/EXPERIMENT_PLAN.md)
- [V2 confirmation experiment plan](../engine_v2/EXPERIMENT_6_PLAN.md)
