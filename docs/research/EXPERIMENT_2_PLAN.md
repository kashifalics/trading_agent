# Experiment 2 plan: longer holds, structural limit entries, realistic bid/ask costs (XAUUSD)

_Status: **plan only, not started.** Written 2026-11-10, after experiment 1 (`docs/reports/PATTERN_STUDY_XAUUSD.md`), the
research audit (`docs/reports/XAUUSD_RESEARCH_AUDIT.md`) and the pipeline audit (`docs/reports/XAUUSD_PIPELINE_AUDIT.md`).
Analysis only. Nothing here changes production models, promotes anything, pushes, merges or deploys._

## 1. Why this experiment

- **Experiment 1 found no validated edge** in 2,000+ pattern, combination, multi-timeframe and unnamed-shape tests, nor in the models.
- **The pipeline audit shows why short timeframes cannot work:** before costs every M5–H1 result is zero within ±0.02R, and the spread
  costs 0.17R (H1) to 0.54R (M5) per trade.
- **Longer timeframes are where a modest real edge could survive costs:** on H4 the spread is 0.08R, on D1 0.05R.
- **Structural limit entries are the other lever:** they buy closer to the invalidation level, so the stop is tighter in price but the
  entry is better.
- **The question:** do structural setups traded with limit orders and held for days beat direction-matched random trades taken the
  same way, after real bid/ask costs, financing costs and realistic fills?

## 2. Data-use rules (most important)

1. **Development uses training data only:** 2003-05-05 to 2020-02-07.
2. **The existing validation period (2020-02-08 to 2023-06-24) is no longer independent for this experiment.**
   - Its results for related hypotheses (H4 and H1 models, zone patterns, the near-break-even H4 top decile) have been seen, and this
     experiment was shaped by them.
   - Using it to select or confirm experiment-2 hypotheses would be selection on seen data.
   - It will not be used for experiment 2. If it is ever shown, it is labelled "previously seen, not evidence".
3. **The sealed final test (2023-06-24 onward) stays sealed** unless you explicitly approve its use (see section 3).
4. **Any experiment designed after looking at earlier validation results needs a fresh, independent validation period.** A result
   that has not passed such a period is a hypothesis, not evidence.
5. **Trial counts accumulate across experiments.** Experiment 1 ran 1,931 discovery tests (stages 1–3). Experiment 2's deflated
   Sharpe ratio and probability-of-overfitting figures will count those trials too.

## 3. Where the fresh validation comes from: your decision

| Option | Development | Fresh validation | Strength | Cost |
|---|---|---|---|---|
| **A. Split inside training** | 2003-05-05 to 2014-12-31 | 2015-01-01 to 2020-02-07 (about 5 years) | Good screening; no sealed data used | Only *partly* fresh: experiment 1 looked at aggregates that included these years, and the pipeline audit's H4 "2013+" breakdown looked at them in aggregate. It cannot be the final proof |
| **B. Forward data** | all of training | new days after 2026-11-06 (paper trading) | Truly fresh | Slow: at H4 and D1 a few hundred trades take years |
| **C. Sealed final test** | all of training (+ A as a screen) | 2023-06-24 to 2026-11-06, once | Truly fresh, about 3.4 years | Uses up the only untouched historical period |

**My recommendation: A, then C, then B.**
1. Develop on 2003–2014 and screen on 2015–2020 (option A).
2. Freeze a short pre-registered list of what survives.
3. Only then, and only with your explicit approval, test that list once on the sealed period (option C).
4. Follow with forward paper trading (option B).

If nothing survives A, the sealed period stays sealed.

## 4. Fixes required before any run (each with a test)

| # | Fix | Why (audit finding) |
|---|---|---|
| F1 | US metals holiday calendar (full closures and early closes, rule-based: New Year, MLK, Presidents', Good Friday, Memorial, Juneteenth from 2022, Independence, Labor, Thanksgiving, Christmas) treated as scheduled closures | Holidays were counted as "missing data" |
| F2 | Store each trade's exit candle and reason (stop, target, time); drop a trade only if an *unscheduled* gap falls between its entry and its exit; the same rule for controls | The old rule dropped 31% of H4 and 63% of D1 signals and never filtered controls |
| F3 | Longer holding periods: H4 up to 120 candles (20 trading days), D1 up to 40 | Day-scale trades |
| F4 | Financing (swap) cost for every night held past 17:00 New York, as pre-registered scenarios: none; ±(USD rate + 2.5%)/365 per night (needs the free FRED daily fed-funds series, a public download, **your OK before fetching**); a fixed $0.10/oz/night for longs and shorts | Long holds were cost-free in experiment 1 |
| F5 | Limit fills, two variants: *touch* (as before) and *conservative*, where price must trade beyond the limit by the spread. The conservative one is primary. Unfilled orders expire after N candles; an order is cancelled if structure breaks first | Touch fills ignore queue position |
| F6 | Exits: fixed R targets (2R primary; 1.5R, 3R descriptive) plus a structural target (nearest opposing confirmed swing or previous week high/low, at least 1.5R), time stop at the holding limit | Structural exits were not tested |
| F7 | Controls with identical mechanics: random limit orders at the same distance and width, same expiry, holds, swap and gap rule, matched by direction, session, volatility and year | Comparability |
| F8 | Model feature fix (real structure trend into the regime features), only if a model is later used as a filter | Wasted feature |

## 5. Hypotheses, fixed before any experiment-2 result is seen

**Setups:** structural, limit-entry. Each entry is placed at a level known at the signal close.

| Id | Setup | Entry (limit) | Stop |
|---|---|---|---|
| S1 | Trend pullback to a demand or supply zone, with the higher-timeframe structure in the trade's direction | near edge of the zone | far edge + 0.1 ATR |
| S2 | Order-block retest after a break of structure (continuation) | near edge of the block | far edge + 0.1 ATR |
| S3 | Fair-value-gap retest after a displacement candle | near edge of the gap | far edge + 0.1 ATR |
| S4 | Retest of a broken support/resistance band | broken band edge | far side of the band + 0.1 ATR |
| S5 | Sweep of the previous week's low (high) followed by a close back inside | the swept level | sweep extreme + 0.1 ATR |
| S6 | Range-boundary fade: price reaches the edge of a 50-candle range during a no-trend regime | range edge | 0.5 ATR beyond the edge |

**Grid:**
- Timeframes: H4, H8, D1.
- Directions: long and short, reported separately; a setup only counts if it beats direction-matched controls.
- **Main setting per test:** conservative limit fill, 2R target, time stop of 60 candles on H4, 30 on H8, 20 on D1, real spread plus
  the fixed $0.10/night swap scenario.

That gives 6 × 3 × 2 = **36 primary tests**. Everything else (other targets, holds, fill variant, swap scenarios, structural exits,
sessions, regimes) is description only.

## 6. Statistics and pass criteria

- **Development (2003–2014):** edge = R minus the matched control mean; standard errors clustered on max(week, holding period).
  Benjamini-Hochberg q < 0.10 over the 36 tests, with at least 150 trades.
- **Candidates must also pass, in development:**
  - mean R > 0 after costs, under both the $0.10/side slippage scenario and the 1.5× spread scenario;
  - a deflated Sharpe ratio above 95%, using all trials so far (experiment 1 plus experiment 2);
  - positive in at least 60% of development years.
- **Option-A screen (2015–2020):** only the frozen candidates, Holm-corrected. They must beat controls and be profitable after costs.
- **Optional option-C confirmation (sealed period):** only the screen survivors, pre-registered and committed first, run once, with
  your explicit approval.
- **Power** (estimated from experiment-1 training counts):
  - H4 zone setups should have about 1,000–2,500 development trades each, enough to detect an edge of about 0.15R.
  - D1 setups will have a few hundred trades, detecting only edges of about 0.3R.
  - "No edge found" at D1 therefore means "no large edge".

## 7. Steps once you approve this plan

1. Implement fixes F1–F7, each with tests, including the minute-level simulator reference and the Brownian and sign-flip nulls rerun
   with the new rules.
2. Freeze the experiment-2 split file (development 2003–2014, screen 2015–2020-02) and this hypothesis list (hash-checked).
3. Run development (H4, H8, D1: minutes of computing, not hours) and write the development report.
4. Freeze the candidates, run the screen, report every result, failures included.
5. Stop and ask you before any use of the sealed period.

## 8. What I need from you

1. **Choose the fresh validation route:** A then C then B (recommended); A only; A then B; or another.
2. Allow or refuse the free FRED fed-funds download for the financing-cost scenario F4. If refused, only the fixed $0.10/night and
   no-swap scenarios are used.
3. Approve this plan (or change setups, timeframes or criteria) before anything runs.
