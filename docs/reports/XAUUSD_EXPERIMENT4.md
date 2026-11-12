# XAUUSD experiment 4: the flexible double top / double bottom

_Written by `python -m app.gold_research.exp4 report`. Analysis only; nothing here is a trade recommendation._

## Question

Does the double-top detector pasted on 2026-11-12 (`detect_flexible_double_top`: lookback 20, peaks within 0.05%, sell on a close below the neckline), and its mirror image for double bottoms, earn money on gold after real costs, beyond what random entries of the same shape earn?

## Method (pre-registered before any outcome was computed)

* Data: Dukascopy 1-minute bid/ask, **training period only** (train (2003-05-05 to 2020-02-08), already examined by experiments 1-3). The sealed final test was not read.
* Main setting: market, next candle's open (ask to buy, bid to sell); stop structural extreme + 0.1 ATR(14); target 2R; time stop 48 candles; Dukascopy bid/ask; 1-minute path decides stop/target order, stop first inside a minute.
* Controls: study control pools (random market entries, same stop-size bucket, direction, NY session, volatility, year).
* The pasted levels (stop 1.5 ATR beyond the peak, targets 2 and 4 ATR) were not tested: on 2019 M15 their first target was below 1:1 reward:risk on every signal (median 1:0.47) and the second never reached 1:2.
* Pre-registration: `docs/research/XAUUSD_exp4_preregistration.json` (SHA-256 `86e139ce862fe019`), written on top of commit `e29d9e3` and committed together with the experiment code before any outcome was computed (see the git history of that file).

Pass criteria (all must hold): >= 100 trades; Benjamini-Hochberg q < 0.10 over the tests run, edge > 0; mean R > 0 with p < 0.05 at the Dukascopy spread; mean R > 0 at the user's $0.30 round-trip spread; edge > 0 when entered one candle later; deflated Sharpe > 0.95 counting every trial of experiments 1-4; mean R > 0 in both halves (2003-2011, 2012-2020).

_Training data has been examined before (experiments 1-3), so passing every criterion makes a TRAINING CANDIDATE only. Confirmation needs unused data: the sealed final test (separate approval) or forward paper trading. Failing means no evidence of an edge in 17 years of training data._

## Signal counts (counts only, fixed the test list)

| TF | Pattern | Signals in training | Test |
|---|---|---|---|
| M5 | double top (short) | 6,867 | run |
| M5 | double bottom (long) | 7,013 | run |
| M15 | double top (short) | 1,375 | run |
| M15 | double bottom (long) | 1,421 | run |
| M30 | double top (short) | 445 | run |
| M30 | double bottom (long) | 456 | run |
| H1 | double top (short) | 136 | run |
| H1 | double bottom (long) | 122 | run |
| H4 | double top (short) | 12 | not testable (fewer than 100 signals) |
| H4 | double bottom (long) | 16 | not testable (fewer than 100 signals) |
| D1 | double top (short) | 1 | not testable (fewer than 100 signals) |
| D1 | double bottom (long) | 2 | not testable (fewer than 100 signals) |

## Result

**0 of 8 tests passed.** Deflated Sharpe counts 1,981 trials (experiments 1-4).

| TF | Pattern | Trades | Win % | Mean R (bid/ask) | Mean R ($0.30 spread) | Control R | Edge | q | 1 candle late edge | Deflated Sharpe | 2003-11 / 2012-20 | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M5 | double top (short) | 6,743 | 29 | -0.257 | -0.219 | -0.230 | -0.027 | 0.999 | -0.050 | 0.00 | -0.40 / -0.19 | no edge |
| M5 | double bottom (long) | 6,881 | 35 | -0.174 | -0.149 | -0.200 | +0.026 | 0.354 | +0.012 | 0.00 | -0.20 / -0.16 | no edge |
| M15 | double top (short) | 1,304 | 29 | -0.237 | -0.206 | -0.131 | -0.106 | 0.999 | -0.115 | 0.00 | -0.41 / -0.13 | no edge |
| M15 | double bottom (long) | 1,354 | 35 | -0.125 | -0.106 | -0.117 | -0.008 | 0.999 | -0.047 | 0.00 | -0.13 / -0.12 | no edge |
| M30 | double top (short) | 414 | 31 | -0.120 | -0.100 | -0.086 | -0.034 | 0.999 | -0.062 | 0.00 | -0.36 / +0.05 | no edge |
| M30 | double bottom (long) | 424 | 38 | -0.030 | -0.014 | -0.060 | +0.030 | 0.999 | +0.013 | 0.00 | +0.02 / -0.07 | no edge |
| H1 | double top (short) | 121 | 31 | -0.120 | -0.106 | -0.085 | -0.035 | 0.999 | -0.129 | 0.00 | +0.00 / -0.20 | no edge |
| H1 | double bottom (long) | 109 | 37 | -0.116 | -0.108 | +0.032 | -0.148 | 0.999 | -0.185 | 0.00 | -0.12 / -0.11 | no edge |

Failed criteria per test:

* M5 double top (short): bh_q_lt_0.10_and_edge_gt_0, mean_r_gt_0_p_lt_0.05, broker_spread_mean_r_gt_0, late_entry_edge_gt_0, deflated_sharpe_gt_0.95, positive_both_halves
* M5 double bottom (long): bh_q_lt_0.10_and_edge_gt_0, mean_r_gt_0_p_lt_0.05, broker_spread_mean_r_gt_0, deflated_sharpe_gt_0.95, positive_both_halves
* M15 double top (short): bh_q_lt_0.10_and_edge_gt_0, mean_r_gt_0_p_lt_0.05, broker_spread_mean_r_gt_0, late_entry_edge_gt_0, deflated_sharpe_gt_0.95, positive_both_halves
* M15 double bottom (long): bh_q_lt_0.10_and_edge_gt_0, mean_r_gt_0_p_lt_0.05, broker_spread_mean_r_gt_0, late_entry_edge_gt_0, deflated_sharpe_gt_0.95, positive_both_halves
* M30 double top (short): bh_q_lt_0.10_and_edge_gt_0, mean_r_gt_0_p_lt_0.05, broker_spread_mean_r_gt_0, late_entry_edge_gt_0, deflated_sharpe_gt_0.95, positive_both_halves
* M30 double bottom (long): bh_q_lt_0.10_and_edge_gt_0, mean_r_gt_0_p_lt_0.05, broker_spread_mean_r_gt_0, deflated_sharpe_gt_0.95, positive_both_halves
* H1 double top (short): bh_q_lt_0.10_and_edge_gt_0, mean_r_gt_0_p_lt_0.05, broker_spread_mean_r_gt_0, late_entry_edge_gt_0, deflated_sharpe_gt_0.95, positive_both_halves
* H1 double bottom (long): bh_q_lt_0.10_and_edge_gt_0, mean_r_gt_0_p_lt_0.05, broker_spread_mean_r_gt_0, late_entry_edge_gt_0, deflated_sharpe_gt_0.95, positive_both_halves

### Other targets and holding periods (description only; never used to decide)

| TF | Pattern | 1R/24 | 1R/48 | 1R/96 | 1.5R/24 | 1.5R/48 | 1.5R/96 | 2R/24 | 2R/48 | 2R/96 | 3R/24 | 3R/48 | 3R/96 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M5 | double top (short) | -0.26 | -0.26 | -0.26 | -0.25 | -0.25 | -0.26 | -0.26 | -0.26 | -0.25 | -0.25 | -0.25 | -0.24 |
| M5 | double bottom (long) | -0.17 | -0.17 | -0.17 | -0.17 | -0.17 | -0.17 | -0.17 | -0.17 | -0.17 | -0.16 | -0.16 | -0.16 |
| M15 | double top (short) | -0.20 | -0.21 | -0.21 | -0.21 | -0.22 | -0.21 | -0.23 | -0.24 | -0.24 | -0.23 | -0.25 | -0.26 |
| M15 | double bottom (long) | -0.13 | -0.13 | -0.12 | -0.14 | -0.14 | -0.13 | -0.12 | -0.13 | -0.11 | -0.12 | -0.12 | -0.09 |
| M30 | double top (short) | -0.08 | -0.08 | -0.09 | -0.10 | -0.10 | -0.12 | -0.13 | -0.12 | -0.15 | -0.17 | -0.18 | -0.22 |
| M30 | double bottom (long) | -0.11 | -0.09 | -0.10 | -0.10 | -0.06 | -0.08 | -0.09 | -0.03 | -0.06 | -0.04 | +0.03 | -0.01 |
| H1 | double top (short) | -0.10 | -0.15 | -0.16 | -0.08 | -0.11 | -0.12 | -0.03 | -0.12 | -0.15 | -0.07 | -0.12 | -0.09 |
| H1 | double bottom (long) | -0.08 | -0.13 | -0.10 | -0.01 | -0.07 | -0.05 | -0.02 | -0.12 | -0.12 | +0.00 | -0.11 | -0.16 |

Cells: mean R per trade after the Dukascopy spread (target R / holding candles).

## Cost context

| TF | Pattern | Median stop (USD) | Median spread as share of the risk |
|---|---|---|---|
| M5 | double top (short) | 1.71 | 19.3% |
| M5 | double bottom (long) | 2.10 | 16.0% |
| M15 | double top (short) | 2.98 | 11.3% |
| M15 | double bottom (long) | 3.30 | 10.1% |
| M30 | double top (short) | 4.28 | 7.9% |
| M30 | double bottom (long) | 4.61 | 7.1% |
| H1 | double top (short) | 6.54 | 4.6% |
| H1 | double bottom (long) | 7.36 | 5.0% |

## Limitations

* Training data only, and it was already examined by experiments 1-3: a pass would be a candidate, not a validated edge.
* M1 was not tested (the study's control pools start at M5).
* The study's gap rule drops trades whose 96-candle window touches a material data gap, including some US-holiday closures (documented in XAUUSD_PIPELINE_AUDIT.md); kept for comparability with the library's double top.
* The $0.30 scenario replaces the entry spread only (one round trip per trade); no slippage or swap.
