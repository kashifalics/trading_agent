# Experiment 3 plan: well-powered structural setups on H1 and H4 (XAUUSD)

_Plan only. Nothing in this file has been run. Analysis only._

## 1. Why this experiment

Experiment 2 found no candidate, but the signal-scarcity diagnostic (`docs/reports/XAUUSD_EXP2_SIGNAL_SCARCITY.md`) showed it
could hardly have found one:
* only 7 of its 36 tests reached 150 development trades;
* at 150 trades only an edge of about 0.29 R (0.44 R at the family level) was detectable;
* most of the scarcity came from design choices: D1/H8 timeframes, testing long and short separately, very strict filters, and a
  weekly-only liquidity setup.

Experiment 3 keeps the realistic execution of experiment 2 (limit entries, conservative fills, bid/ask, financing, the fixed gap
rule) and changes the design so that **every test that runs has enough trades to detect a 0.15 R edge**. That minimum is checked
from event counts before any outcome is seen.

## 2. Data-use rules

1. **The experiment-1 validation period (2020-02-08 to 2023-06-24) is not used at all.** Its results were seen.
2. **The sealed final test (2023-06-24 to 2026-11-06) stays sealed** until you approve its use, separately, for a frozen and
   committed candidate list (only if the route in section 3 includes it).
3. **Trial counts accumulate:** experiment 1 (1,931 tests) + experiment 2 (36) + experiment 3 (at most 9) are all counted in the
   deflated Sharpe ratio.
4. **Experiment 3 was designed after experiments 1 and 2 and the diagnostic.** Its development results are hypotheses; only
   untouched data can confirm them.
5. **Nothing from experiments 1–2 is changed.** Fixes are made in the experiment-3 code path; experiment-2 results stay reproducible.

## 3. Where the confirmation comes from: your decision

| Route | Development | Confirmation | Strength | Cost |
|---|---|---|---|---|
| **1. Full training, then sealed test** (recommended) | 2003-05-05 to 2020-02-07 (16.8 years) | Sealed period 2023-06-24 to 2026-11-06, run once, then forward paper trading | Most development trades (power was the problem); truly fresh confirmation | Uses up the only untouched historical period. If no candidate survives development, the seal stays closed |
| **2. Full training, then forward only** | same | New days only (paper trading) | Keeps the sealed period for later | Slow: a few hundred trades per setup and year, so a fair verdict takes years |
| **3. Inner split, then sealed test** | 2003-05-05 to 2014-12-31 | Screen 2015-01 to 2020-02, then the sealed period | An extra screen before the seal | About 30% fewer development trades, the exact weakness the diagnostic found. The screen years were seen in aggregate in experiment 1 |

**Recommendation: route 1.** Robustness is still checked inside development (section 6: both halves of the period and most
individual years must be positive). The sealed test is touched only if something survives, and only after you approve it.

## 4. Fixes before any run (each with a test)

| # | Fix | Why (diagnostic defect) |
|---|---|---|
| F1 | Gaps that start at the daily rollover break (21:00/22:00 UTC, up to 2 hours) are scheduled closures, not missing data | D1: 35 development trades were wrongly excluded |
| F2 | Support/resistance levels are refreshed every 5 trading days on every timeframe, from swings confirmed before the refresh | D2: a 200-candle refresh left levels months old on slower timeframes |
| F3 | When one candle breaks several bands, the band nearest the breakout close is used | D3: the kept band was arbitrary |
| F4 | Gap metadata is limited to the period being studied at load time | D6: the gap list covered the whole dataset |
| F5 | New detectors: order blocks after BOS **or** CHoCH; displacement at 1.5 ATR; previous-day sweep with a reclaim by any candle of the day | Wider definitions, pre-registered here (section 5) |

The minute-level simulator reference and the Brownian null are re-run on the experiment-3 path before any real result.

## 5. Hypotheses, fixed before any experiment-3 result is seen

**Common mechanics (unchanged from experiment 2):**
* limit order at the zone edge, live 20 candles, conservative fill (price must trade through by the spread);
* stop at the far edge + 0.1 ATR; main target 2 R (1.5 R and 3 R descriptive only);
* time stop: H1 48 candles, H4 60 candles (other holds descriptive only);
* real Dukascopy bid/ask, financing $0.10 per ounce per night (main), no-financing and FRED scenarios as in experiment 2.

**Long and short pooled in one test per setup and timeframe.** Each trade is still compared with random controls of the **same
direction**, distance, width, session and volatility, so gold's upward drift cannot pass as an edge.

| Test | Setup | Timeframes |
|---|---|---|
| E1 | Order block after a structure break (BOS or CHoCH), displacement ≥ 1.5 ATR | H1, H4 |
| E2 | Fair-value gap whose middle candle is ≥ 1.5 ATR with a body ≥ 70% | H1, H4 |
| E3 | Retest of a broken support/resistance band (F2, F3) | H1, H4 |
| E4 | Supply/demand zone pullback in the direction of the D1 structure trend | H1, H4 |
| E5 | Previous-day high/low sweep reclaimed by any candle of the same day | H1 |

At most **9 tests**. Dropped from experiment 2: the range-edge fade (S6, too rare by construction), weekly-only sweeps and the
H8/D1 entry timeframes.

## 6. Power gate, statistics and pass criteria

**Power gate (counts only, before outcomes):**
* The diagnostic's counting code runs on the development data and counts the orders each test would place and fill.
* Only tests with **at least 1,000 filled development trades** run. At 1,000 trades an edge of about 0.15 R is detectable with
  80% power at the family significance level.
* The final test list and its counts are written to a pre-registration file, hashed and committed **before** any outcome is computed.
* Tests below the minimum are reported as "not testable", never run.

**Development statistics:** edge = R − matched control mean, with standard errors clustered on max(week, holding period).

**A candidate must pass every criterion:**
* Benjamini–Hochberg q < 0.10 over the tests run, with a positive edge;
* mean R > 0 at p < 0.05 under the main costs, and still > 0 with $0.10 slippage per side and with 1.5× spread;
* deflated Sharpe ratio > 0.95, counting all trials of experiments 1–3;
* positive in at least 60% of development years **and** in both halves (2003–2011 and 2012–2020);
* at least 1,000 trades.

**Honest expectation:** the accumulated trial count (about 1,976) means the deflated Sharpe ratio needs a per-trade Sharpe above
about 0.17, roughly 0.24 R per trade, even with unlimited trades. Experiments 1–2 found nothing near that, so the most likely
outcome is again no candidate. In that case the seal stays closed, and the result still says something useful: no large structural
edge exists at well-powered sample sizes.

**Confirmation (route 1 or 3, only with your separate approval):** the frozen candidates are pre-registered, committed and run
once on the sealed period, with Holm correction. Each must beat its controls and be profitable after costs. Every result is reported.

## 7. Steps once you approve

1. Implement F1–F5 with tests, and re-run the simulator reference and the Brownian null on the experiment-3 path.
2. Freeze the experiment-3 split file and this hypothesis list (hashed).
3. Run the power gate on counts only; commit the pre-registration with the final test list.
4. Run development (H1 and H4: expected a few hours on this laptop) and write the development report, failures included.
5. Freeze candidates (if any), then **stop and ask you** before any use of the sealed period.

## 8. What I need from you

1. **The confirmation route:** 1 (recommended), 2 or 3.
2. Approval of this plan, or changes to setups, timeframes, the 1,000-trade minimum or the criteria, before anything runs.
