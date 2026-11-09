# XAUUSD pattern study

_Written by `python -m app.gold_research report` from the stored trade files. Analysis only; nothing here is a trade recommendation._

## Data and split

| Segment | From | To (exclusive) | M1 candles | Used for |
|---|---|---|---|---|
| Training | 2003-05-05 | 2020-02-08 | 5,603,658 | finding candidates |
| Validation | 2020-02-08 | 2023-06-24 | 1,196,473 | confirming them |
| Final test | 2023-06-24 | open | 1,196,779 at freeze | **sealed**, not read |

Split frozen 2026-11-09 (SHA-256 `c2e8d3f85d7d3879`). Dukascopy 1-minute bid/ask; see XAUUSD_DATA_QUALITY.md.

## Method (decided before any result was seen)

* **One main test per pattern, timeframe and direction:** the pattern's natural entry (next open; zones: a limit order at the zone's near edge, live for 50 candles, cancelled by a close through its far edge), its structural stop plus 0.1 ATR (at least 0.25 ATR), a 2R target and a 48-candle limit.
* **Real execution prices:** longs buy at the ask and sell at the bid, shorts the reverse. Where the order of events inside a candle matters (fill candle, stop candle) the 1-minute path decides; inside one minute the stop counts first.
* **Edge** = R minus the average R of matched random trades (same entry type and stop size or zone geometry, same New York session, volatility level, year and segment). This removes gold's uptrend and its daily rhythm.
* **Training:** Benjamini-Hochberg across every test with at least 100 trades (q < 0.1). Standard errors are clustered on blocks of max(one week, the holding period).
* **Validation:** only the frozen candidate list, Holm-corrected (alpha 0.05); market entries must keep the edge when entered one candle later; 'confirmed' also requires a positive average R after the spread.
* Other targets and holding periods are shown for description only and were never used to choose anything.

## Training result

1931 tests with enough trades. 62 candidate, 1869 no edge in training, 554 not enough trades.

### Candidates sent to validation

| TF | Pattern | Dir | Entry | Trades | Win % | Mean R | Control R | Edge | q | 1-candle-late edge |
|---|---|---|---|---|---|---|---|---|---|---|
| M5 | inverted_hammer | long | market | 22,869 | 14 | -0.61 | -0.69 | +0.08 +/- 0.01 | 0.0000 | -0.01 |
| M5 | rejection_block | long | limit | 32,071 | 16 | -0.56 | -0.59 | +0.04 +/- 0.01 | 0.0000 | - |
| M5 | order_block | long | limit | 24,299 | 21 | -0.42 | -0.46 | +0.05 +/- 0.01 | 0.0000 | - |
| M5 | range_boundary_rejection | long | market | 32,903 | 22 | -0.39 | -0.43 | +0.05 +/- 0.01 | 0.0000 | -0.02 |
| M5 | order_block_choch | long | limit | 11,895 | 22 | -0.39 | -0.45 | +0.06 +/- 0.01 | 0.0000 | - |
| M5 | breaker_block | long | limit | 26,706 | 20 | -0.42 | -0.47 | +0.04 +/- 0.01 | 0.0000 | - |
| M5 | order_block_fvg | long | limit | 9,622 | 21 | -0.41 | -0.47 | +0.06 +/- 0.01 | 0.0000 | - |
| M5 | failed_momentum_breakout | long | market | 18,155 | 28 | -0.26 | -0.31 | +0.05 +/- 0.01 | 0.0001 | +0.01 |
| M5 | supply_zone | short | limit | 8,455 | 14 | -0.59 | -0.65 | +0.06 +/- 0.01 | 0.0002 | - |
| M5 | harami_bull | long | market | 44,609 | 22 | -0.38 | -0.42 | +0.04 +/- 0.01 | 0.0008 | -0.04 |
| M5 | round10_reaction | long | market | 18,249 | 21 | -0.41 | -0.47 | +0.06 +/- 0.01 | 0.0024 | -0.00 |
| M15 | demand_zone | long | limit | 2,329 | 24 | -0.29 | -0.40 | +0.11 +/- 0.03 | 0.0030 | - |
| M5 | order_block_sweep | long | limit | 3,977 | 26 | -0.32 | -0.38 | +0.07 +/- 0.02 | 0.0178 | - |
| M5 | grab_reversal+order_block | long | limit | 4,675 | 22 | -0.39 | -0.46 | +0.06 +/- 0.02 | 0.0178 | - |
| H1 | order_block | short | limit | 2,121 | 31 | -0.08 | -0.18 | +0.11 +/- 0.03 | 0.0209 | - |
| M15 | breaker_block | long | limit | 9,065 | 27 | -0.22 | -0.27 | +0.05 +/- 0.02 | 0.0212 | - |
| M15 | tweezer_bottom | long | market | 8,881 | 25 | -0.30 | -0.36 | +0.05 +/- 0.02 | 0.0212 | -0.00 |
| M15 | failed_momentum_breakout | long | market | 5,841 | 32 | -0.13 | -0.20 | +0.06 +/- 0.02 | 0.0212 | +0.05 |
| M15 | strong_demand | long | limit | 344 | 29 | -0.14 | -0.40 | +0.27 +/- 0.08 | 0.0212 | - |
| M15 | round10_reaction | long | market | 10,168 | 25 | -0.28 | -0.34 | +0.06 +/- 0.02 | 0.0218 | +0.02 |
| H1 | order_block_choch | short | limit | 1,159 | 32 | -0.05 | -0.19 | +0.14 +/- 0.04 | 0.0218 | - |
| H1 | round50_reaction | long | market | 530 | 36 | +0.07 | -0.19 | +0.27 +/- 0.08 | 0.0218 | +0.25 |
| M30 | displacement | long | market | 1,872 | 42 | +0.06 | -0.05 | +0.11 +/- 0.03 | 0.0221 | +0.05 |
| H1 | order_block|intraday:counter | short | limit | 1,061 | 32 | -0.05 | -0.19 | +0.14 +/- 0.04 | 0.0221 | - |
| M5 | selling_climax | long | market | 5,418 | 25 | -0.29 | -0.36 | +0.07 +/- 0.02 | 0.0243 | +0.06 |
| M5 | falling_wedge_breakout | long | market | 4,844 | 33 | -0.18 | -0.24 | +0.06 +/- 0.02 | 0.0254 | +0.04 |
| M5 | rectangle_breakout | long | market | 2,271 | 39 | -0.09 | -0.17 | +0.08 +/- 0.02 | 0.0254 | +0.07 |
| M5 | elliott_impulse | long | market | 2,143 | 34 | -0.16 | -0.25 | +0.09 +/- 0.03 | 0.0290 | +0.05 |
| M30 | bos+displacement | long | market | 806 | 43 | +0.12 | -0.04 | +0.16 +/- 0.05 | 0.0322 | +0.11 |
| M15 | demand_zone|scalp:bias | long | limit | 1,266 | 24 | -0.30 | -0.41 | +0.12 +/- 0.04 | 0.0352 | - |
| M30 | breaker_block | long | limit | 4,628 | 31 | -0.12 | -0.19 | +0.07 +/- 0.02 | 0.0357 | - |
| M30 | consecutive_fvg | long | limit | 2,024 | 34 | -0.06 | -0.16 | +0.10 +/- 0.03 | 0.0357 | - |
| M5 | sweep+order_block | long | limit | 6,203 | 22 | -0.40 | -0.44 | +0.05 +/- 0.02 | 0.0362 | - |
| M15 | order_block|scalp:counter | long | limit | 3,949 | 28 | -0.21 | -0.28 | +0.07 +/- 0.02 | 0.0362 | - |
| M5 | CHoCH | long | market | 19,123 | 35 | -0.17 | -0.20 | +0.03 +/- 0.01 | 0.0384 | +0.02 |
| M5 | tweezer_bottom | long | market | 27,107 | 20 | -0.44 | -0.46 | +0.03 +/- 0.01 | 0.0391 | -0.04 |
| M15 | harami_bull | long | market | 13,658 | 26 | -0.26 | -0.30 | +0.04 +/- 0.01 | 0.0391 | +0.00 |
| M30 | range_boundary_rejection | long | market | 4,102 | 29 | -0.16 | -0.23 | +0.07 +/- 0.02 | 0.0391 | +0.04 |
| M30 | hammer | long | market | 4,335 | 28 | -0.17 | -0.24 | +0.07 +/- 0.02 | 0.0434 | +0.02 |
| M5 | fvg_with_choch | long | limit | 13,050 | 12 | -0.64 | -0.67 | +0.03 +/- 0.01 | 0.0442 | - |
| M5 | pd_low_sweep | long | market | 869 | 26 | -0.30 | -0.42 | +0.12 +/- 0.04 | 0.0481 | +0.06 |
| M30 | order_block_sweep | short | limit | 922 | 33 | -0.07 | -0.20 | +0.13 +/- 0.04 | 0.0512 | - |
| M5 | demand_zone | long | limit | 7,621 | 13 | -0.61 | -0.65 | +0.04 +/- 0.01 | 0.0542 | - |
| M5 | order_block_bos | long | limit | 12,404 | 20 | -0.44 | -0.47 | +0.03 +/- 0.01 | 0.0542 | - |
| M5 | reclaimed_order_block | long | market | 14,767 | 36 | -0.14 | -0.18 | +0.04 +/- 0.01 | 0.0546 | +0.03 |
| H1 | breaker_block | long | limit | 2,228 | 33 | -0.04 | -0.13 | +0.09 +/- 0.03 | 0.0574 | - |
| M15 | order_block_fvg | long | limit | 3,143 | 27 | -0.22 | -0.28 | +0.07 +/- 0.02 | 0.0714 | - |
| M5 | fvg_with_choch | short | limit | 15,953 | 11 | -0.69 | -0.71 | +0.02 +/- 0.01 | 0.0727 | - |
| M15 | rejection_block | long | limit | 11,452 | 22 | -0.36 | -0.39 | +0.03 +/- 0.01 | 0.0735 | - |
| M15 | order_block_sweep | short | limit | 1,699 | 30 | -0.17 | -0.25 | +0.09 +/- 0.03 | 0.0735 | - |
| M15 | range_boundary_rejection | long | market | 10,273 | 26 | -0.27 | -0.31 | +0.04 +/- 0.01 | 0.0741 | -0.00 |
| M30 | order_block | short | limit | 4,386 | 29 | -0.16 | -0.22 | +0.06 +/- 0.02 | 0.0798 | - |
| M5 | double_bottom | long | market | 1,779 | 38 | -0.09 | -0.17 | +0.07 +/- 0.03 | 0.0843 | +0.06 |
| M30 | deep_retracement | long | market | 315 | 39 | +0.08 | -0.14 | +0.22 +/- 0.08 | 0.0843 | +0.08 |
| M5 | rounding_bottom | long | market | 714 | 43 | -0.06 | -0.16 | +0.10 +/- 0.04 | 0.0847 | +0.07 |
| M5 | triple_bottom | long | market | 502 | 39 | -0.06 | -0.17 | +0.12 +/- 0.04 | 0.0847 | +0.10 |
| M5 | sweep+double_bottom | long | market | 1,114 | 39 | -0.08 | -0.16 | +0.09 +/- 0.03 | 0.0847 | +0.06 |
| M15 | fib_extension | long | market | 2,514 | 44 | -0.01 | -0.08 | +0.07 +/- 0.03 | 0.0847 | +0.05 |
| M15 | grab_reversal+order_block | short | limit | 1,611 | 28 | -0.21 | -0.30 | +0.09 +/- 0.03 | 0.0878 | - |
| H1 | harami_bear | short | market | 3,147 | 27 | -0.19 | -0.26 | +0.07 +/- 0.03 | 0.0878 | +0.03 |
| M30 | failed_bos | short | market | 3,879 | 29 | -0.17 | -0.23 | +0.06 +/- 0.02 | 0.0883 | +0.01 |
| H1 | displacement_imbalance | short | limit | 673 | 34 | -0.02 | -0.17 | +0.14 +/- 0.05 | 0.0921 | - |

### Every test (training, main setting)

Smallest detectable edge = the edge this sample would find 80% of the time; 'no edge' means no edge larger than that.

#### M5

| Pattern | Dir | Entry | Trades | Win % | Mean R | Edge | Smallest detectable | q | Status |
|---|---|---|---|---|---|---|---|---|---|
| BOS | long | market | 19,751 | 32 | -0.23 | -0.02 | 0.03 | 1.000 | no edge in training |
| BOS | short | market | 17,179 | 27 | -0.30 | -0.06 | 0.03 | 1.000 | no edge in training |
| CHoCH | long | market | 19,123 | 35 | -0.17 | +0.03 | 0.02 | 0.038 | candidate |
| CHoCH | short | market | 19,108 | 29 | -0.28 | -0.02 | 0.02 | 1.000 | no edge in training |
| abcd | long | market | 2,475 | 34 | -0.20 | +0.04 | 0.06 | 0.385 | no edge in training |
| abcd | short | market | 2,398 | 28 | -0.30 | +0.05 | 0.06 | 0.259 | no edge in training |
| asc_triangle_breakout | long | market | 3,506 | 34 | -0.20 | +0.01 | 0.05 | 0.722 | no edge in training |
| asia_high_sweep | short | market | 1,872 | 13 | -0.80 | -0.08 | 0.06 | 1.000 | no edge in training |
| asia_high_sweep+bos | short | market | 57 | - | - | - | - | - | not enough trades |
| asia_low_sweep | long | market | 1,967 | 20 | -0.45 | -0.02 | 0.06 | 1.000 | no edge in training |
| asia_low_sweep+bos | long | market | 72 | - | - | - | - | - | not enough trades |
| atr_expansion | long | market | 3,224 | 34 | -0.13 | +0.04 | 0.06 | 0.378 | no edge in training |
| atr_expansion | short | market | 3,238 | 30 | -0.19 | -0.03 | 0.06 | 1.000 | no edge in training |
| atr_expansion+bos | long | market | 679 | 38 | -0.13 | +0.00 | 0.11 | 0.887 | no edge in training |
| atr_expansion+bos | short | market | 762 | 36 | -0.15 | -0.07 | 0.10 | 1.000 | no edge in training |
| balanced_price_range | long | limit | 16,360 | 6 | -0.83 | -0.01 | 0.02 | 1.000 | no edge in training |
| balanced_price_range | short | limit | 20,703 | 4 | -0.88 | -0.03 | 0.01 | 1.000 | no edge in training |
| bat | long | market | 143 | 33 | -0.15 | +0.06 | 0.24 | 0.687 | no edge in training |
| bat | short | market | 124 | 28 | -0.22 | +0.07 | 0.28 | 0.675 | no edge in training |
| bear_flag | short | market | 267 | 26 | -0.28 | -0.02 | 0.19 | 0.875 | no edge in training |
| bear_pennant | short | market | 515 | 23 | -0.35 | -0.01 | 0.13 | 0.868 | no edge in training |
| bos+displacement | long | market | 3,684 | 33 | -0.18 | -0.00 | 0.05 | 0.940 | no edge in training |
| bos+displacement | short | market | 3,709 | 31 | -0.19 | -0.02 | 0.06 | 1.000 | no edge in training |
| breaker+fvg | long | limit | 22,222 | 13 | -0.64 | +0.00 | 0.02 | 0.729 | no edge in training |
| breaker+fvg | short | limit | 26,347 | 11 | -0.67 | -0.01 | 0.02 | 1.000 | no edge in training |
| breaker_block | long | limit | 26,706 | 20 | -0.42 | +0.04 | 0.02 | 0.000 | candidate |
| breaker_block | short | limit | 30,222 | 17 | -0.51 | -0.02 | 0.02 | 1.000 | no edge in training |
| breakout | long | market | 45,778 | 24 | -0.34 | -0.03 | 0.02 | 1.000 | no edge in training |
| breakout | short | market | 46,445 | 19 | -0.49 | -0.05 | 0.02 | 1.000 | no edge in training |
| broadening_breakout | long | market | 735 | 40 | -0.11 | +0.05 | 0.08 | 0.342 | no edge in training |
| broadening_breakout | short | market | 742 | 39 | -0.11 | +0.01 | 0.09 | 0.708 | no edge in training |
| bull_flag | long | market | 388 | 36 | -0.14 | +0.06 | 0.14 | 0.507 | no edge in training |
| bull_pennant | long | market | 569 | 29 | -0.25 | -0.01 | 0.12 | 0.863 | no edge in training |
| butterfly | long | market | 104 | 27 | -0.27 | -0.06 | 0.26 | 0.917 | no edge in training |
| butterfly | short | market | 108 | 28 | -0.33 | -0.08 | 0.25 | 0.952 | no edge in training |
| buying_climax | short | market | 4,674 | 19 | -0.55 | -0.07 | 0.05 | 1.000 | no edge in training |
| channel_breakout | long | market | 1,056 | 37 | -0.14 | +0.02 | 0.08 | 0.674 | no edge in training |
| channel_breakout | short | market | 1,051 | 34 | -0.20 | -0.06 | 0.08 | 1.000 | no edge in training |
| choch+fvg | long | limit | 20,232 | 11 | -0.67 | -0.00 | 0.02 | 1.000 | no edge in training |
| choch+fvg | short | limit | 24,213 | 10 | -0.72 | -0.02 | 0.02 | 1.000 | no edge in training |
| climax_reversal | long | market | 1,136 | 34 | -0.10 | +0.07 | 0.10 | 0.347 | no edge in training |
| climax_reversal | short | market | 961 | 34 | -0.07 | +0.04 | 0.11 | 0.640 | no edge in training |
| compression+sweep | long | market | 2,546 | 21 | -0.45 | +0.00 | 0.07 | 0.887 | no edge in training |
| compression+sweep | short | market | 2,542 | 8 | -1.16 | -0.14 | 0.08 | 1.000 | no edge in training |
| compression_breakout | long | market | 850 | 30 | -0.25 | -0.07 | 0.13 | 1.000 | no edge in training |
| compression_breakout | short | market | 678 | 20 | -0.56 | -0.17 | 0.13 | 1.000 | no edge in training |
| consecutive_expansion | long | market | 24,253 | 28 | -0.29 | -0.00 | 0.02 | 1.000 | no edge in training |
| consecutive_expansion | short | market | 24,729 | 21 | -0.48 | -0.06 | 0.02 | 1.000 | no edge in training |
| consecutive_fvg | long | limit | 15,255 | 22 | -0.39 | +0.02 | 0.03 | 0.282 | no edge in training |
| consecutive_fvg | short | limit | 17,094 | 21 | -0.43 | -0.01 | 0.03 | 1.000 | no edge in training |
| crab | long | market | 53 | - | - | - | - | - | not enough trades |
| crab | short | market | 46 | - | - | - | - | - | not enough trades |
| creek_breakout | long | market | 660 | 29 | -0.24 | -0.06 | 0.12 | 0.992 | no edge in training |
| cup_and_handle | long | market | 141 | 30 | -0.23 | -0.05 | 0.24 | 0.899 | no edge in training |
| cypher | long | market | 246 | 31 | -0.26 | -0.05 | 0.20 | 0.936 | no edge in training |
| cypher | short | market | 252 | 25 | -0.35 | -0.07 | 0.17 | 0.979 | no edge in training |
| dark_cloud_cover | short | market | 13,771 | 17 | -0.56 | +0.01 | 0.03 | 0.733 | no edge in training |
| deep_crab | long | market | 102 | 33 | -0.25 | -0.02 | 0.25 | 0.864 | no edge in training |
| deep_crab | short | market | 112 | 23 | -0.47 | -0.22 | 0.22 | 1.000 | no edge in training |
| deep_retracement | long | market | 2,267 | 28 | -0.25 | +0.02 | 0.07 | 0.687 | no edge in training |
| deep_retracement | short | market | 2,434 | 22 | -0.44 | -0.04 | 0.06 | 1.000 | no edge in training |
| demand_to_supply_flip | short | limit | 8,246 | 12 | -0.63 | -0.00 | 0.03 | 0.985 | no edge in training |
| demand_zone | long | limit | 7,621 | 13 | -0.61 | +0.04 | 0.03 | 0.054 | candidate |
| desc_triangle_breakdown | short | market | 3,346 | 28 | -0.29 | -0.04 | 0.05 | 1.000 | no edge in training |
| displacement | long | market | 9,509 | 33 | -0.16 | +0.01 | 0.04 | 0.603 | no edge in training |
| displacement | short | market | 9,405 | 30 | -0.21 | -0.02 | 0.04 | 1.000 | no edge in training |
| displacement_imbalance | long | limit | 6,535 | 21 | -0.41 | +0.03 | 0.03 | 0.249 | no edge in training |
| displacement_imbalance | short | limit | 7,102 | 21 | -0.41 | +0.02 | 0.04 | 0.540 | no edge in training |
| double_bottom | long | market | 1,779 | 38 | -0.09 | +0.07 | 0.06 | 0.084 | candidate |
| double_top | short | market | 1,769 | 35 | -0.13 | +0.02 | 0.07 | 0.687 | no edge in training |
| dragonfly_doji | long | market | 14,177 | 17 | -0.54 | -0.05 | 0.03 | 1.000 | no edge in training |
| elliott_impulse | long | market | 2,143 | 34 | -0.16 | +0.09 | 0.07 | 0.029 | candidate |
| elliott_impulse | short | market | 2,362 | 26 | -0.34 | +0.05 | 0.06 | 0.317 | no edge in training |
| elliott_wave5 | long | market | 3,888 | 34 | -0.19 | +0.00 | 0.04 | 0.761 | no edge in training |
| elliott_wave5 | short | market | 3,835 | 32 | -0.21 | -0.01 | 0.05 | 0.892 | no edge in training |
| ema_bounce | long | market | 56,970 | 15 | -0.61 | -0.07 | 0.02 | 1.000 | no edge in training |
| ema_bounce | short | market | 43,455 | 7 | -1.09 | -0.13 | 0.02 | 1.000 | no edge in training |
| engulfing_bear | short | market | 71,605 | 17 | -0.59 | -0.03 | 0.02 | 1.000 | no edge in training |
| engulfing_bull | long | market | 70,129 | 24 | -0.35 | -0.01 | 0.02 | 1.000 | no edge in training |
| equal_highs | short | market | 17,238 | 15 | -0.61 | -0.03 | 0.03 | 1.000 | no edge in training |
| equal_highs+displacement | short | market | 2,691 | 29 | -0.24 | -0.04 | 0.06 | 1.000 | no edge in training |
| equal_lows | long | market | 17,553 | 12 | -0.69 | -0.06 | 0.03 | 1.000 | no edge in training |
| equal_lows+displacement | long | market | 2,567 | 33 | -0.16 | +0.02 | 0.07 | 0.684 | no edge in training |
| evening_doji_star | short | market | 7,496 | 17 | -0.60 | -0.04 | 0.04 | 1.000 | no edge in training |
| evening_star | short | market | 19,069 | 18 | -0.54 | -0.03 | 0.03 | 1.000 | no edge in training |
| exhaustion_sequence | long | market | 1,339 | 34 | -0.14 | +0.06 | 0.09 | 0.323 | no edge in training |
| exhaustion_sequence | short | market | 1,039 | 31 | -0.17 | +0.05 | 0.10 | 0.539 | no edge in training |
| external_bos | long | market | 13,508 | 34 | -0.19 | +0.00 | 0.03 | 0.798 | no edge in training |
| external_bos | short | market | 11,609 | 29 | -0.27 | -0.05 | 0.03 | 1.000 | no edge in training |
| external_sweep | long | market | 32,601 | 19 | -0.47 | +0.00 | 0.02 | 0.890 | no edge in training |
| external_sweep | short | market | 30,144 | 9 | -0.97 | -0.10 | 0.02 | 1.000 | no edge in training |
| failed_bos | long | market | 22,517 | 27 | -0.30 | +0.02 | 0.02 | 0.126 | no edge in training |
| failed_bos | short | market | 23,904 | 18 | -0.57 | -0.02 | 0.02 | 1.000 | no edge in training |
| failed_breakout | long | market | 16,387 | 29 | -0.26 | +0.00 | 0.03 | 0.860 | no edge in training |
| failed_breakout | short | market | 14,703 | 25 | -0.34 | +0.01 | 0.03 | 0.775 | no edge in training |
| failed_breakout+reclaim | long | market | 1,944 | 37 | -0.15 | +0.03 | 0.06 | 0.592 | no edge in training |
| failed_breakout+reclaim | short | market | 1,820 | 35 | -0.13 | +0.05 | 0.06 | 0.312 | no edge in training |
| failed_momentum_breakout | long | market | 18,155 | 28 | -0.26 | +0.05 | 0.03 | 0.000 | candidate |
| failed_momentum_breakout | short | market | 20,405 | 19 | -0.54 | +0.00 | 0.02 | 0.868 | no edge in training |
| failed_sweep | long | market | 21,255 | 28 | -0.30 | -0.04 | 0.03 | 1.000 | no edge in training |
| failed_sweep | short | market | 20,332 | 22 | -0.41 | -0.07 | 0.03 | 1.000 | no edge in training |
| failed_swing | long | market | 39,496 | 33 | -0.22 | -0.00 | 0.02 | 0.985 | no edge in training |
| failed_swing | short | market | 36,394 | 27 | -0.31 | -0.05 | 0.02 | 1.000 | no edge in training |
| falling_channel_break | long | market | 5,229 | 35 | -0.17 | +0.04 | 0.04 | 0.150 | no edge in training |
| falling_three_methods | short | market | 714 | 27 | -0.31 | -0.04 | 0.11 | 1.000 | no edge in training |
| falling_wedge_breakout | long | market | 4,844 | 33 | -0.18 | +0.06 | 0.04 | 0.025 | candidate |
| fib_extension | long | market | 7,749 | 38 | -0.13 | +0.03 | 0.04 | 0.270 | no edge in training |
| fib_extension | short | market | 7,377 | 36 | -0.14 | -0.01 | 0.04 | 0.979 | no edge in training |
| fib_retracement | long | market | 5,296 | 26 | -0.30 | +0.01 | 0.04 | 0.713 | no edge in training |
| fib_retracement | short | market | 4,997 | 20 | -0.48 | -0.04 | 0.04 | 1.000 | no edge in training |
| fvg | long | limit | 61,132 | 10 | -0.71 | -0.00 | 0.01 | 1.000 | no edge in training |
| fvg | short | limit | 73,490 | 8 | -0.76 | -0.02 | 0.01 | 1.000 | no edge in training |
| fvg_after_sweep | long | limit | 7,780 | 10 | -0.71 | +0.01 | 0.03 | 0.616 | no edge in training |
| fvg_after_sweep | short | limit | 8,902 | 9 | -0.75 | -0.00 | 0.02 | 0.929 | no edge in training |
| fvg_continuation | long | limit | 41,233 | 11 | -0.69 | -0.01 | 0.01 | 1.000 | no edge in training |
| fvg_continuation | short | limit | 48,697 | 9 | -0.73 | -0.02 | 0.01 | 1.000 | no edge in training |
| fvg_formation | long | market | 82,202 | 24 | -0.34 | -0.02 | 0.02 | 1.000 | no edge in training |
| fvg_formation | short | market | 81,368 | 18 | -0.56 | -0.05 | 0.02 | 1.000 | no edge in training |
| fvg_reversal | long | limit | 19,899 | 9 | -0.74 | +0.01 | 0.02 | 0.550 | no edge in training |
| fvg_reversal | short | limit | 24,793 | 7 | -0.81 | -0.02 | 0.01 | 1.000 | no edge in training |
| fvg_with_bos | long | limit | 11,796 | 11 | -0.69 | -0.01 | 0.02 | 1.000 | no edge in training |
| fvg_with_bos | short | limit | 13,752 | 11 | -0.68 | +0.01 | 0.02 | 0.320 | no edge in training |
| fvg_with_choch | long | limit | 13,050 | 12 | -0.64 | +0.03 | 0.02 | 0.044 | candidate |
| fvg_with_choch | short | limit | 15,953 | 11 | -0.69 | +0.02 | 0.02 | 0.073 | candidate |
| gap_continuation | long | market | 20,794 | 8 | -0.84 | -0.11 | 0.02 | 1.000 | no edge in training |
| gap_continuation | short | market | 18,443 | 2 | -1.44 | -0.28 | 0.04 | 1.000 | no edge in training |
| gap_fade | long | market | 21,633 | 12 | -0.70 | -0.07 | 0.02 | 1.000 | no edge in training |
| gap_fade | short | market | 20,908 | 2 | -1.37 | -0.23 | 0.03 | 1.000 | no edge in training |
| gartley | long | market | 139 | 39 | -0.10 | +0.11 | 0.24 | 0.483 | no edge in training |
| gartley | short | market | 160 | 31 | -0.20 | +0.12 | 0.23 | 0.470 | no edge in training |
| golden_pullback | long | market | 2,325 | 26 | -0.31 | -0.03 | 0.06 | 0.992 | no edge in training |
| golden_pullback | short | market | 2,282 | 22 | -0.44 | -0.00 | 0.06 | 0.849 | no edge in training |
| grab_reversal | long | market | 19,353 | 29 | -0.28 | +0.01 | 0.03 | 0.734 | no edge in training |
| grab_reversal | short | market | 16,251 | 23 | -0.40 | -0.01 | 0.03 | 1.000 | no edge in training |
| grab_reversal+order_block | long | limit | 4,675 | 22 | -0.39 | +0.06 | 0.04 | 0.018 | candidate |
| grab_reversal+order_block | short | limit | 4,630 | 20 | -0.44 | +0.03 | 0.04 | 0.271 | no edge in training |
| gravestone_doji | short | market | 8,348 | 11 | -1.02 | -0.18 | 0.10 | 1.000 | no edge in training |
| hammer | long | market | 34,523 | 20 | -0.46 | -0.00 | 0.02 | 0.939 | no edge in training |
| hanging_man | short | market | 34,005 | 2 | -1.61 | -0.36 | 0.03 | 1.000 | no edge in training |
| harami_bear | short | market | 44,175 | 13 | -0.78 | -0.02 | 0.03 | 1.000 | no edge in training |
| harami_bull | long | market | 44,609 | 22 | -0.38 | +0.04 | 0.02 | 0.001 | candidate |
| head_and_shoulders | short | market | 370 | 41 | -0.13 | +0.05 | 0.12 | 0.516 | no edge in training |
| higher_low | long | market | 60,000 | 25 | -0.34 | -0.01 | 0.02 | 1.000 | no edge in training |
| higher_low+bos | long | market | 14,463 | 32 | -0.23 | -0.02 | 0.03 | 1.000 | no edge in training |
| ice_breakdown | short | market | 581 | 30 | -0.19 | -0.03 | 0.14 | 0.903 | no edge in training |
| inside_bar_bear | short | market | 91,195 | 12 | -0.80 | -0.04 | 0.02 | 1.000 | no edge in training |
| inside_bar_bull | long | market | 85,528 | 20 | -0.43 | +0.00 | 0.02 | 0.890 | no edge in training |
| inside_compression+nr_breakout | long | market | 4,028 | 21 | -0.41 | -0.03 | 0.05 | 1.000 | no edge in training |
| inside_compression+nr_breakout | short | market | 4,034 | 17 | -0.64 | -0.02 | 0.05 | 1.000 | no edge in training |
| internal_bos | long | market | 26,192 | 30 | -0.25 | -0.02 | 0.03 | 1.000 | no edge in training |
| internal_bos | short | market | 22,681 | 26 | -0.34 | -0.06 | 0.03 | 1.000 | no edge in training |
| internal_sweep | long | market | 79,980 | 19 | -0.49 | -0.00 | 0.02 | 1.000 | no edge in training |
| internal_sweep | short | market | 72,529 | 9 | -1.00 | -0.11 | 0.02 | 1.000 | no edge in training |
| inverse_cup_and_handle | short | market | 250 | 31 | -0.23 | -0.07 | 0.18 | 0.979 | no edge in training |
| inverse_fvg | long | limit | 52,241 | 9 | -0.73 | -0.00 | 0.01 | 1.000 | no edge in training |
| inverse_fvg | short | limit | 61,614 | 8 | -0.77 | -0.02 | 0.01 | 1.000 | no edge in training |
| inverse_head_and_shoulders | long | market | 408 | 40 | -0.10 | +0.06 | 0.10 | 0.415 | no edge in training |
| inverted_hammer | long | market | 22,869 | 14 | -0.61 | +0.08 | 0.03 | 0.000 | candidate |
| kicker | long | market | 106 | 27 | -0.36 | -0.07 | 0.24 | 1.000 | no edge in training |
| kicker | short | market | 46 | - | - | - | - | - | not enough trades |
| last_point_of_supply | short | market | 187 | 21 | -0.45 | +0.04 | 0.21 | 0.689 | no edge in training |
| last_point_of_support | long | market | 190 | 26 | -0.27 | +0.05 | 0.22 | 0.687 | no edge in training |
| liquidity_sweep | long | market | 54,684 | 19 | -0.48 | +0.00 | 0.02 | 0.851 | no edge in training |
| liquidity_sweep | short | market | 50,037 | 9 | -0.98 | -0.10 | 0.02 | 1.000 | no edge in training |
| london_high_sweep | short | market | 1,936 | 15 | -0.72 | -0.10 | 0.06 | 1.000 | no edge in training |
| london_high_sweep+choch | short | market | 950 | 33 | -0.23 | -0.04 | 0.08 | 1.000 | no edge in training |
| london_low_sweep | long | market | 2,033 | 21 | -0.41 | -0.03 | 0.07 | 1.000 | no edge in training |
| london_low_sweep+choch | long | market | 1,081 | 39 | -0.11 | +0.04 | 0.08 | 0.515 | no edge in training |
| lower_high | short | market | 57,723 | 18 | -0.58 | -0.05 | 0.02 | 1.000 | no edge in training |
| lower_high+bos | short | market | 12,523 | 27 | -0.30 | -0.05 | 0.03 | 1.000 | no edge in training |
| market_structure_shift | long | market | 7,747 | 33 | -0.21 | -0.01 | 0.03 | 1.000 | no edge in training |
| market_structure_shift | short | market | 7,292 | 27 | -0.30 | -0.06 | 0.03 | 1.000 | no edge in training |
| marubozu_bear | short | market | 17,485 | 22 | -0.39 | -0.05 | 0.03 | 1.000 | no edge in training |
| marubozu_bull | long | market | 16,600 | 28 | -0.26 | -0.02 | 0.03 | 1.000 | no edge in training |
| momentum_continuation | long | market | 17,723 | 39 | -0.10 | +0.04 | 0.04 | 0.133 | no edge in training |
| momentum_continuation | short | market | 16,714 | 35 | -0.15 | -0.05 | 0.04 | 1.000 | no edge in training |
| momentum_exhaustion | long | market | 1,907 | 36 | -0.15 | +0.02 | 0.07 | 0.672 | no edge in training |
| momentum_exhaustion | short | market | 1,988 | 29 | -0.25 | -0.03 | 0.07 | 1.000 | no edge in training |
| morning_doji_star | long | market | 7,718 | 23 | -0.38 | -0.03 | 0.04 | 1.000 | no edge in training |
| morning_star | long | market | 19,433 | 25 | -0.33 | -0.00 | 0.03 | 0.952 | no edge in training |
| multi_touch_rejection | long | market | 8,150 | 25 | -0.33 | -0.01 | 0.04 | 1.000 | no edge in training |
| multi_touch_rejection | short | market | 7,252 | 18 | -0.52 | -0.02 | 0.04 | 1.000 | no edge in training |
| multiple_sweeps | long | market | 17,955 | 18 | -0.55 | -0.03 | 0.03 | 1.000 | no edge in training |
| multiple_sweeps | short | market | 15,075 | 7 | -1.06 | -0.13 | 0.03 | 1.000 | no edge in training |
| nr_breakout | long | market | 49,071 | 23 | -0.36 | -0.01 | 0.02 | 1.000 | no edge in training |
| nr_breakout | short | market | 48,689 | 16 | -0.61 | -0.04 | 0.02 | 1.000 | no edge in training |
| order_block | long | limit | 24,299 | 21 | -0.42 | +0.05 | 0.02 | 0.000 | candidate |
| order_block | short | limit | 26,171 | 19 | -0.47 | +0.01 | 0.02 | 0.562 | no edge in training |
| order_block_bos | long | limit | 12,404 | 20 | -0.44 | +0.03 | 0.03 | 0.054 | candidate |
| order_block_bos | short | limit | 12,350 | 18 | -0.49 | -0.01 | 0.03 | 1.000 | no edge in training |
| order_block_choch | long | limit | 11,895 | 22 | -0.39 | +0.06 | 0.03 | 0.000 | candidate |
| order_block_choch | short | limit | 13,821 | 20 | -0.45 | +0.02 | 0.03 | 0.265 | no edge in training |
| order_block_fvg | long | limit | 9,622 | 21 | -0.41 | +0.06 | 0.03 | 0.000 | candidate |
| order_block_fvg | short | limit | 10,967 | 19 | -0.47 | +0.02 | 0.03 | 0.391 | no edge in training |
| order_block_sweep | long | limit | 3,977 | 26 | -0.32 | +0.07 | 0.05 | 0.018 | candidate |
| order_block_sweep | short | limit | 4,561 | 22 | -0.39 | +0.03 | 0.04 | 0.361 | no edge in training |
| outside_bar_bear | short | market | 59,842 | 13 | -0.79 | -0.08 | 0.02 | 1.000 | no edge in training |
| outside_bar_bull | long | market | 66,883 | 21 | -0.43 | -0.02 | 0.02 | 1.000 | no edge in training |
| pd_high_sweep | short | market | 929 | 13 | -0.80 | -0.05 | 0.08 | 1.000 | no edge in training |
| pd_low_sweep | long | market | 869 | 26 | -0.30 | +0.12 | 0.10 | 0.048 | candidate |
| pdh_sweep+choch | short | market | 172 | 34 | -0.22 | +0.02 | 0.20 | 0.849 | no edge in training |
| pdh_sweep+engulfing | short | market | 194 | 20 | -0.56 | -0.04 | 0.17 | 1.000 | no edge in training |
| pdh_sweep+fvg | short | limit | 373 | 9 | -0.73 | -0.02 | 0.11 | 0.994 | no edge in training |
| pdl_sweep+choch | long | market | 178 | 36 | -0.20 | -0.02 | 0.18 | 0.968 | no edge in training |
| pdl_sweep+engulfing | long | market | 187 | 37 | -0.10 | +0.23 | 0.22 | 0.126 | no edge in training |
| pdl_sweep+fvg | long | limit | 448 | 13 | -0.62 | +0.06 | 0.10 | 0.472 | no edge in training |
| piercing | long | market | 13,266 | 24 | -0.33 | +0.02 | 0.03 | 0.383 | no edge in training |
| pin_bar_bear | short | market | 53,919 | 12 | -0.88 | -0.09 | 0.04 | 1.000 | no edge in training |
| pin_bar_bull | long | market | 81,035 | 18 | -0.50 | -0.03 | 0.02 | 1.000 | no edge in training |
| pm_high_sweep | short | market | 41 | - | - | - | - | - | not enough trades |
| pm_low_sweep | long | market | 38 | - | - | - | - | - | not enough trades |
| preliminary_supply | short | market | 5,161 | 17 | -0.56 | -0.06 | 0.04 | 1.000 | no edge in training |
| preliminary_support | long | market | 5,507 | 25 | -0.30 | +0.04 | 0.04 | 0.122 | no edge in training |
| pw_high_sweep | short | market | 188 | 16 | -0.70 | -0.01 | 0.19 | 0.929 | no edge in training |
| pw_low_sweep | long | market | 161 | 19 | -0.53 | -0.14 | 0.20 | 1.000 | no edge in training |
| range_boundary_rejection | long | market | 32,903 | 22 | -0.39 | +0.05 | 0.02 | 0.000 | candidate |
| range_boundary_rejection | short | market | 35,313 | 12 | -0.83 | -0.05 | 0.02 | 1.000 | no edge in training |
| range_midpoint_cross | long | market | 52,145 | 25 | -0.37 | -0.02 | 0.02 | 1.000 | no edge in training |
| range_midpoint_cross | short | market | 52,104 | 17 | -0.63 | -0.07 | 0.02 | 1.000 | no edge in training |
| range_to_trend | long | market | 9,202 | 38 | -0.15 | +0.03 | 0.04 | 0.320 | no edge in training |
| range_to_trend | short | market | 8,445 | 33 | -0.20 | -0.03 | 0.04 | 1.000 | no edge in training |
| reclaimed_order_block | long | market | 14,767 | 36 | -0.14 | +0.04 | 0.03 | 0.055 | candidate |
| reclaimed_order_block | short | market | 13,592 | 32 | -0.20 | -0.00 | 0.03 | 0.929 | no edge in training |
| rectangle_breakout | long | market | 2,271 | 39 | -0.09 | +0.08 | 0.06 | 0.025 | candidate |
| rectangle_breakout | short | market | 1,998 | 30 | -0.24 | -0.05 | 0.06 | 1.000 | no edge in training |
| rejection_bear | short | market | 39,917 | 14 | -0.73 | -0.04 | 0.02 | 1.000 | no edge in training |
| rejection_bear+bos | short | market | 3,812 | 29 | -0.25 | -0.02 | 0.05 | 1.000 | no edge in training |
| rejection_block | long | limit | 32,071 | 16 | -0.56 | +0.04 | 0.02 | 0.000 | candidate |
| rejection_block | short | limit | 29,802 | 12 | -0.65 | -0.01 | 0.02 | 1.000 | no edge in training |
| rejection_bull | long | market | 50,386 | 21 | -0.42 | +0.00 | 0.02 | 0.862 | no edge in training |
| rejection_bull+bos | long | market | 5,319 | 33 | -0.22 | -0.01 | 0.04 | 0.985 | no edge in training |
| resistance_rejection | short | market | 10,589 | 17 | -0.54 | -0.01 | 0.03 | 1.000 | no edge in training |
| resistance_rejection+engulfing | short | market | 1,857 | 21 | -0.43 | +0.00 | 0.07 | 0.878 | no edge in training |
| retest | long | market | 19,914 | 20 | -0.43 | -0.02 | 0.03 | 1.000 | no edge in training |
| retest | short | market | 18,894 | 15 | -0.66 | -0.04 | 0.03 | 1.000 | no edge in training |
| retest+momentum | long | market | 4,847 | 37 | -0.13 | +0.01 | 0.06 | 0.783 | no edge in training |
| retest+momentum | short | market | 4,941 | 35 | -0.14 | -0.04 | 0.06 | 1.000 | no edge in training |
| rising_channel_break | short | market | 5,014 | 30 | -0.23 | +0.04 | 0.04 | 0.183 | no edge in training |
| rising_three_methods | long | market | 822 | 32 | -0.18 | +0.04 | 0.11 | 0.640 | no edge in training |
| rising_wedge_breakdown | short | market | 5,567 | 26 | -0.34 | +0.02 | 0.04 | 0.415 | no edge in training |
| round100_reaction | long | market | 2,058 | 20 | -0.46 | +0.03 | 0.08 | 0.591 | no edge in training |
| round100_reaction | short | market | 1,791 | 14 | -0.75 | +0.02 | 0.08 | 0.753 | no edge in training |
| round10_reaction | long | market | 18,249 | 21 | -0.41 | +0.06 | 0.03 | 0.002 | candidate |
| round10_reaction | short | market | 15,414 | 14 | -0.75 | -0.01 | 0.05 | 1.000 | no edge in training |
| round50_reaction | long | market | 2,124 | 21 | -0.40 | +0.08 | 0.10 | 0.226 | no edge in training |
| round50_reaction | short | market | 1,737 | 12 | -0.79 | -0.01 | 0.09 | 0.978 | no edge in training |
| round_placebo_reaction | long | market | 27,520 | 19 | -0.47 | +0.01 | 0.03 | 0.539 | no edge in training |
| round_placebo_reaction | short | market | 22,910 | 12 | -0.79 | -0.02 | 0.03 | 1.000 | no edge in training |
| rounding_bottom | long | market | 714 | 43 | -0.06 | +0.10 | 0.10 | 0.085 | candidate |
| rounding_top | short | market | 977 | 37 | -0.15 | -0.02 | 0.09 | 0.899 | no edge in training |
| secondary_test | long | market | 721 | 24 | -0.32 | +0.02 | 0.11 | 0.713 | no edge in training |
| secondary_test | short | market | 670 | 21 | -0.43 | +0.01 | 0.12 | 0.713 | no edge in training |
| selling_climax | long | market | 5,418 | 25 | -0.29 | +0.07 | 0.04 | 0.024 | candidate |
| shark | long | market | 416 | 38 | -0.10 | +0.10 | 0.14 | 0.317 | no edge in training |
| shark | short | market | 370 | 28 | -0.29 | -0.04 | 0.14 | 0.936 | no edge in training |
| shooting_star | short | market | 24,022 | 13 | -0.80 | -0.05 | 0.03 | 1.000 | no edge in training |
| sign_of_strength | long | market | 811 | 27 | -0.32 | -0.04 | 0.10 | 0.979 | no edge in training |
| sign_of_weakness | short | market | 785 | 20 | -0.47 | -0.07 | 0.10 | 1.000 | no edge in training |
| spring | long | market | 2,144 | 15 | -0.61 | -0.04 | 0.05 | 1.000 | no edge in training |
| squeeze+bos | long | market | 1,678 | 33 | -0.20 | -0.00 | 0.07 | 0.897 | no edge in training |
| squeeze+bos | short | market | 1,657 | 26 | -0.34 | -0.12 | 0.07 | 1.000 | no edge in training |
| squeeze_release | long | market | 9,357 | 33 | -0.20 | +0.01 | 0.03 | 0.661 | no edge in training |
| squeeze_release | short | market | 9,243 | 27 | -0.34 | -0.06 | 0.04 | 1.000 | no edge in training |
| strong_bear_sequence | short | market | 1,647 | 34 | -0.21 | -0.03 | 0.07 | 1.000 | no edge in training |
| strong_bull_sequence | long | market | 1,574 | 38 | -0.11 | +0.07 | 0.07 | 0.156 | no edge in training |
| strong_demand | long | limit | 1,169 | 13 | -0.62 | +0.05 | 0.07 | 0.419 | no edge in training |
| strong_supply | short | limit | 1,378 | 12 | -0.64 | +0.03 | 0.06 | 0.539 | no edge in training |
| structural_reclaim | long | market | 6,545 | 36 | -0.16 | +0.03 | 0.03 | 0.236 | no edge in training |
| structural_reclaim | short | market | 6,828 | 32 | -0.20 | +0.03 | 0.04 | 0.271 | no edge in training |
| supply_to_demand_flip | long | limit | 7,327 | 13 | -0.62 | -0.01 | 0.03 | 1.000 | no edge in training |
| supply_zone | short | limit | 8,455 | 14 | -0.59 | +0.06 | 0.03 | 0.000 | candidate |
| support_rejection | long | market | 11,551 | 24 | -0.34 | -0.01 | 0.03 | 1.000 | no edge in training |
| support_rejection+engulfing | long | market | 1,935 | 25 | -0.32 | -0.02 | 0.07 | 1.000 | no edge in training |
| sweep+bos | long | market | 3,542 | 34 | -0.19 | +0.04 | 0.05 | 0.269 | no edge in training |
| sweep+bos | short | market | 2,697 | 28 | -0.27 | -0.02 | 0.06 | 1.000 | no edge in training |
| sweep+choch | long | market | 6,391 | 35 | -0.17 | +0.03 | 0.04 | 0.277 | no edge in training |
| sweep+choch | short | market | 5,873 | 30 | -0.26 | -0.01 | 0.04 | 1.000 | no edge in training |
| sweep+double_bottom | long | market | 1,114 | 39 | -0.08 | +0.09 | 0.08 | 0.085 | candidate |
| sweep+double_top | short | market | 1,068 | 36 | -0.10 | +0.04 | 0.09 | 0.483 | no edge in training |
| sweep+mss | long | market | 2,953 | 33 | -0.22 | -0.01 | 0.05 | 1.000 | no edge in training |
| sweep+mss | short | market | 2,650 | 28 | -0.29 | -0.05 | 0.06 | 1.000 | no edge in training |
| sweep+order_block | long | limit | 6,203 | 22 | -0.40 | +0.05 | 0.04 | 0.036 | candidate |
| sweep+order_block | short | limit | 6,266 | 19 | -0.46 | +0.02 | 0.04 | 0.591 | no edge in training |
| sweep_reclaim | long | market | 12,002 | 24 | -0.37 | +0.00 | 0.03 | 0.853 | no edge in training |
| sweep_reclaim | short | market | 12,537 | 15 | -0.68 | -0.02 | 0.03 | 1.000 | no edge in training |
| sweep_to_bos | long | market | 12,688 | 34 | -0.19 | +0.02 | 0.03 | 0.320 | no edge in training |
| sweep_to_bos | short | market | 10,693 | 30 | -0.24 | +0.01 | 0.04 | 0.701 | no edge in training |
| swing_failure | long | market | 30,826 | 19 | -0.49 | +0.00 | 0.02 | 0.819 | no edge in training |
| swing_failure | short | market | 28,483 | 8 | -1.03 | -0.11 | 0.02 | 1.000 | no edge in training |
| swing_failure+choch | long | market | 4,705 | 35 | -0.18 | +0.03 | 0.04 | 0.323 | no edge in training |
| swing_failure+choch | short | market | 4,252 | 29 | -0.29 | -0.03 | 0.05 | 1.000 | no edge in training |
| sym_triangle_breakout | long | market | 5,453 | 31 | -0.21 | +0.03 | 0.04 | 0.401 | no edge in training |
| sym_triangle_breakout | short | market | 5,371 | 27 | -0.28 | +0.02 | 0.04 | 0.415 | no edge in training |
| three_bar_continuation | long | market | 15,041 | 28 | -0.28 | -0.02 | 0.03 | 1.000 | no edge in training |
| three_bar_continuation | short | market | 14,134 | 22 | -0.42 | -0.06 | 0.03 | 1.000 | no edge in training |
| three_bar_reversal | long | market | 84,503 | 27 | -0.28 | +0.00 | 0.02 | 0.842 | no edge in training |
| three_bar_reversal | short | market | 78,307 | 21 | -0.43 | -0.03 | 0.02 | 1.000 | no edge in training |
| three_black_crows | short | market | 2,565 | 27 | -0.31 | -0.07 | 0.06 | 1.000 | no edge in training |
| three_drives | long | market | 191 | 34 | -0.23 | +0.00 | 0.19 | 0.786 | no edge in training |
| three_drives | short | market | 167 | 23 | -0.39 | -0.03 | 0.19 | 0.890 | no edge in training |
| three_inside_down | short | market | 8,755 | 22 | -0.40 | -0.03 | 0.03 | 1.000 | no edge in training |
| three_inside_up | long | market | 8,927 | 28 | -0.26 | +0.00 | 0.04 | 0.835 | no edge in training |
| three_outside_down | short | market | 30,594 | 23 | -0.40 | -0.04 | 0.02 | 1.000 | no edge in training |
| three_outside_up | long | market | 30,059 | 28 | -0.27 | -0.00 | 0.02 | 0.987 | no edge in training |
| three_white_soldiers | long | market | 2,384 | 35 | -0.14 | +0.06 | 0.07 | 0.282 | no edge in training |
| triple_bottom | long | market | 502 | 39 | -0.06 | +0.12 | 0.11 | 0.085 | candidate |
| triple_top | short | market | 520 | 33 | -0.16 | +0.01 | 0.12 | 0.741 | no edge in training |
| tweezer_bottom | long | market | 27,107 | 20 | -0.44 | +0.03 | 0.02 | 0.039 | candidate |
| tweezer_top | short | market | 31,456 | 9 | -0.96 | -0.08 | 0.02 | 1.000 | no edge in training |
| upthrust | short | market | 2,110 | 2 | -1.23 | -0.18 | 0.03 | 1.000 | no edge in training |
| wide_range | long | market | 22,978 | 32 | -0.19 | +0.01 | 0.03 | 0.604 | no edge in training |
| wide_range | short | market | 21,525 | 28 | -0.26 | -0.05 | 0.03 | 1.000 | no edge in training |
| wide_range_reversal | long | market | 9,710 | 32 | -0.19 | +0.01 | 0.04 | 0.733 | no edge in training |
| wide_range_reversal | short | market | 8,413 | 28 | -0.25 | -0.03 | 0.04 | 1.000 | no edge in training |

#### M15

| Pattern | Dir | Entry | Trades | Win % | Mean R | Edge | Smallest detectable | q | Status |
|---|---|---|---|---|---|---|---|---|---|
| BOS | long | market | 6,857 | 35 | -0.11 | +0.00 | 0.05 | 0.860 | no edge in training |
| BOS | short | market | 5,735 | 31 | -0.18 | -0.03 | 0.05 | 1.000 | no edge in training |
| BOS|scalp:bias | long | market | 4,672 | 35 | -0.10 | +0.01 | 0.06 | 0.708 | no edge in training |
| BOS|scalp:bias | short | market | 3,705 | 32 | -0.15 | -0.01 | 0.06 | 1.000 | no edge in training |
| BOS|scalp:bias+context | long | market | 2,524 | 37 | -0.07 | +0.04 | 0.08 | 0.539 | no edge in training |
| BOS|scalp:bias+context | short | market | 1,540 | 34 | -0.10 | +0.03 | 0.10 | 0.660 | no edge in training |
| BOS|scalp:counter | long | market | 2,185 | 34 | -0.14 | -0.02 | 0.08 | 1.000 | no edge in training |
| BOS|scalp:counter | short | market | 2,030 | 28 | -0.24 | -0.08 | 0.07 | 1.000 | no edge in training |
| BOS|scalp:full | long | market | 2,274 | 37 | -0.07 | +0.04 | 0.08 | 0.539 | no edge in training |
| BOS|scalp:full | short | market | 1,388 | 34 | -0.10 | +0.03 | 0.11 | 0.690 | no edge in training |
| CHoCH | long | market | 6,522 | 36 | -0.13 | -0.02 | 0.04 | 1.000 | no edge in training |
| CHoCH | short | market | 6,505 | 32 | -0.18 | -0.03 | 0.04 | 1.000 | no edge in training |
| CHoCH|scalp:bias | long | market | 2,689 | 35 | -0.13 | -0.03 | 0.06 | 1.000 | no edge in training |
| CHoCH|scalp:bias | short | market | 2,411 | 34 | -0.11 | +0.03 | 0.06 | 0.569 | no edge in training |
| CHoCH|scalp:bias+context | long | market | 1,443 | 34 | -0.15 | -0.05 | 0.08 | 1.000 | no edge in training |
| CHoCH|scalp:bias+context | short | market | 988 | 35 | -0.08 | +0.03 | 0.10 | 0.640 | no edge in training |
| CHoCH|scalp:counter | long | market | 3,833 | 36 | -0.12 | -0.02 | 0.05 | 1.000 | no edge in training |
| CHoCH|scalp:counter | short | market | 4,094 | 31 | -0.22 | -0.06 | 0.05 | 1.000 | no edge in training |
| CHoCH|scalp:full | long | market | 1,260 | 35 | -0.15 | -0.04 | 0.09 | 1.000 | no edge in training |
| CHoCH|scalp:full | short | market | 869 | 35 | -0.08 | +0.04 | 0.10 | 0.603 | no edge in training |
| abcd | long | market | 718 | 36 | -0.12 | +0.01 | 0.11 | 0.730 | no edge in training |
| abcd | short | market | 743 | 32 | -0.17 | +0.03 | 0.11 | 0.687 | no edge in training |
| asc_triangle_breakout | long | market | 1,216 | 33 | -0.19 | -0.07 | 0.09 | 1.000 | no edge in training |
| asia_high_sweep | short | market | 1,851 | 19 | -0.50 | -0.01 | 0.07 | 0.985 | no edge in training |
| asia_high_sweep+bos | short | market | 92 | - | - | - | - | - | not enough trades |
| asia_low_sweep | long | market | 1,959 | 22 | -0.36 | -0.03 | 0.07 | 1.000 | no edge in training |
| asia_low_sweep+bos | long | market | 114 | 37 | -0.11 | +0.00 | 0.28 | 0.887 | no edge in training |
| atr_expansion | long | market | 1,236 | 39 | -0.04 | +0.03 | 0.09 | 0.591 | no edge in training |
| atr_expansion | short | market | 1,218 | 34 | -0.11 | +0.02 | 0.09 | 0.753 | no edge in training |
| atr_expansion+bos | long | market | 224 | 45 | -0.00 | +0.03 | 0.16 | 0.769 | no edge in training |
| atr_expansion+bos | short | market | 267 | 36 | -0.15 | -0.08 | 0.14 | 1.000 | no edge in training |
| balanced_price_range | long | limit | 5,234 | 11 | -0.66 | -0.05 | 0.04 | 1.000 | no edge in training |
| balanced_price_range | short | limit | 5,427 | 10 | -0.72 | -0.09 | 0.03 | 1.000 | no edge in training |
| bat | long | market | 42 | - | - | - | - | - | not enough trades |
| bat | short | market | 33 | - | - | - | - | - | not enough trades |
| bear_flag | short | market | 106 | 30 | -0.21 | -0.04 | 0.29 | 0.881 | no edge in training |
| bear_pennant | short | market | 189 | 24 | -0.32 | -0.09 | 0.21 | 0.979 | no edge in training |
| bos+displacement | long | market | 1,413 | 37 | -0.07 | +0.03 | 0.09 | 0.641 | no edge in training |
| bos+displacement | short | market | 1,347 | 35 | -0.05 | +0.05 | 0.09 | 0.539 | no edge in training |
| breaker+fvg | long | limit | 7,362 | 20 | -0.43 | +0.01 | 0.03 | 0.684 | no edge in training |
| breaker+fvg | short | limit | 8,059 | 19 | -0.45 | -0.01 | 0.03 | 1.000 | no edge in training |
| breaker_block | long | limit | 9,065 | 27 | -0.22 | +0.05 | 0.04 | 0.021 | candidate |
| breaker_block | short | limit | 9,992 | 24 | -0.30 | +0.01 | 0.04 | 0.766 | no edge in training |
| breaker_block|scalp:bias | long | limit | 5,512 | 28 | -0.21 | +0.05 | 0.05 | 0.132 | no edge in training |
| breaker_block|scalp:bias | short | limit | 5,754 | 25 | -0.28 | +0.01 | 0.05 | 0.744 | no edge in training |
| breaker_block|scalp:bias+context | long | limit | 2,828 | 29 | -0.19 | +0.07 | 0.07 | 0.138 | no edge in training |
| breaker_block|scalp:bias+context | short | limit | 2,247 | 25 | -0.28 | +0.00 | 0.08 | 0.887 | no edge in training |
| breaker_block|scalp:counter | long | limit | 3,553 | 26 | -0.23 | +0.06 | 0.06 | 0.120 | no edge in training |
| breaker_block|scalp:counter | short | limit | 4,238 | 23 | -0.32 | +0.00 | 0.05 | 0.870 | no edge in training |
| breaker_block|scalp:full | long | limit | 2,184 | 29 | -0.19 | +0.07 | 0.08 | 0.219 | no edge in training |
| breaker_block|scalp:full | short | limit | 1,693 | 27 | -0.23 | +0.05 | 0.10 | 0.472 | no edge in training |
| breakout | long | market | 14,282 | 29 | -0.20 | +0.01 | 0.04 | 0.805 | no edge in training |
| breakout | short | market | 14,829 | 25 | -0.30 | -0.03 | 0.03 | 1.000 | no edge in training |
| broadening_breakout | long | market | 299 | 44 | -0.01 | +0.05 | 0.11 | 0.483 | no edge in training |
| broadening_breakout | short | market | 282 | 43 | -0.02 | +0.07 | 0.14 | 0.487 | no edge in training |
| bull_flag | long | market | 152 | 37 | -0.04 | +0.11 | 0.26 | 0.516 | no edge in training |
| bull_pennant | long | market | 250 | 29 | -0.20 | -0.02 | 0.21 | 0.868 | no edge in training |
| butterfly | long | market | 42 | - | - | - | - | - | not enough trades |
| butterfly | short | market | 44 | - | - | - | - | - | not enough trades |
| buying_climax | short | market | 1,805 | 24 | -0.33 | -0.04 | 0.07 | 0.992 | no edge in training |
| channel_breakout | long | market | 359 | 45 | +0.04 | +0.12 | 0.14 | 0.188 | no edge in training |
| channel_breakout | short | market | 362 | 36 | -0.12 | -0.03 | 0.14 | 0.903 | no edge in training |
| choch+fvg | long | limit | 6,899 | 18 | -0.47 | +0.00 | 0.03 | 0.862 | no edge in training |
| choch+fvg | short | limit | 7,467 | 17 | -0.52 | -0.03 | 0.03 | 1.000 | no edge in training |
| climax_reversal | long | market | 443 | 38 | -0.03 | +0.05 | 0.15 | 0.640 | no edge in training |
| climax_reversal | short | market | 362 | 39 | -0.00 | +0.09 | 0.17 | 0.539 | no edge in training |
| compression+sweep | long | market | 1,332 | 26 | -0.26 | +0.10 | 0.10 | 0.144 | no edge in training |
| compression+sweep | short | market | 1,492 | 17 | -0.59 | -0.01 | 0.09 | 0.955 | no edge in training |
| compression_breakout | long | market | 284 | 37 | -0.00 | +0.11 | 0.21 | 0.510 | no edge in training |
| compression_breakout | short | market | 260 | 31 | -0.16 | -0.04 | 0.20 | 1.000 | no edge in training |
| consecutive_expansion | long | market | 8,040 | 31 | -0.20 | -0.02 | 0.04 | 1.000 | no edge in training |
| consecutive_expansion | short | market | 8,141 | 27 | -0.29 | -0.03 | 0.04 | 1.000 | no edge in training |
| consecutive_fvg | long | limit | 4,255 | 29 | -0.19 | +0.04 | 0.05 | 0.320 | no edge in training |
| consecutive_fvg | short | limit | 4,404 | 28 | -0.24 | +0.00 | 0.05 | 0.885 | no edge in training |
| crab | long | market | 15 | - | - | - | - | - | not enough trades |
| crab | short | market | 15 | - | - | - | - | - | not enough trades |
| creek_breakout | long | market | 237 | 32 | -0.22 | -0.10 | 0.18 | 1.000 | no edge in training |
| cup_and_handle | long | market | 55 | - | - | - | - | - | not enough trades |
| cypher | long | market | 73 | - | - | - | - | - | not enough trades |
| cypher | short | market | 64 | - | - | - | - | - | not enough trades |
| dark_cloud_cover | short | market | 4,083 | 24 | -0.31 | +0.02 | 0.05 | 0.567 | no edge in training |
| deep_crab | long | market | 25 | - | - | - | - | - | not enough trades |
| deep_crab | short | market | 34 | - | - | - | - | - | not enough trades |
| deep_retracement | long | market | 742 | 31 | -0.19 | -0.02 | 0.11 | 0.890 | no edge in training |
| deep_retracement | short | market | 745 | 31 | -0.14 | +0.07 | 0.12 | 0.401 | no edge in training |
| demand_to_supply_flip | short | limit | 2,296 | 21 | -0.38 | +0.01 | 0.07 | 0.853 | no edge in training |
| demand_zone | long | limit | 2,329 | 24 | -0.29 | +0.11 | 0.07 | 0.003 | candidate |
| demand_zone|scalp:bias | long | limit | 1,266 | 24 | -0.30 | +0.12 | 0.09 | 0.035 | candidate |
| demand_zone|scalp:bias+context | long | limit | 663 | 23 | -0.32 | +0.09 | 0.13 | 0.347 | no edge in training |
| demand_zone|scalp:counter | long | limit | 1,063 | 24 | -0.29 | +0.11 | 0.10 | 0.102 | no edge in training |
| demand_zone|scalp:full | long | limit | 548 | 23 | -0.31 | +0.11 | 0.14 | 0.300 | no edge in training |
| desc_triangle_breakdown | short | market | 1,015 | 31 | -0.16 | -0.00 | 0.10 | 0.813 | no edge in training |
| displacement | long | market | 3,330 | 37 | -0.07 | +0.03 | 0.06 | 0.539 | no edge in training |
| displacement | short | market | 3,335 | 34 | -0.10 | +0.00 | 0.06 | 0.876 | no edge in training |
| displacement_imbalance | long | limit | 2,371 | 26 | -0.27 | -0.01 | 0.06 | 0.987 | no edge in training |
| displacement_imbalance | short | limit | 2,490 | 27 | -0.25 | +0.02 | 0.06 | 0.725 | no edge in training |
| double_bottom | long | market | 531 | 38 | -0.08 | +0.01 | 0.12 | 0.730 | no edge in training |
| double_top | short | market | 500 | 35 | -0.09 | +0.01 | 0.13 | 0.761 | no edge in training |
| dragonfly_doji | long | market | 3,151 | 22 | -0.37 | -0.02 | 0.06 | 1.000 | no edge in training |
| elliott_impulse | long | market | 701 | 35 | -0.09 | +0.06 | 0.12 | 0.415 | no edge in training |
| elliott_impulse | short | market | 885 | 27 | -0.25 | +0.00 | 0.11 | 0.806 | no edge in training |
| elliott_wave5 | long | market | 1,402 | 38 | -0.08 | +0.02 | 0.08 | 0.605 | no edge in training |
| elliott_wave5 | short | market | 1,245 | 34 | -0.12 | +0.02 | 0.08 | 0.687 | no edge in training |
| ema_bounce | long | market | 16,720 | 20 | -0.44 | -0.03 | 0.04 | 1.000 | no edge in training |
| ema_bounce | short | market | 13,072 | 13 | -0.69 | -0.08 | 0.03 | 1.000 | no edge in training |
| engulfing_bear | short | market | 24,278 | 22 | -0.37 | -0.03 | 0.02 | 1.000 | no edge in training |
| engulfing_bear|scalp:bias | short | market | 11,476 | 23 | -0.35 | -0.02 | 0.03 | 1.000 | no edge in training |
| engulfing_bear|scalp:bias+context | short | market | 4,853 | 24 | -0.31 | +0.01 | 0.05 | 0.828 | no edge in training |
| engulfing_bear|scalp:counter | short | market | 12,802 | 22 | -0.39 | -0.03 | 0.03 | 1.000 | no edge in training |
| engulfing_bear|scalp:full | short | market | 1,397 | 26 | -0.27 | -0.03 | 0.09 | 1.000 | no edge in training |
| engulfing_bull | long | market | 24,151 | 27 | -0.24 | -0.01 | 0.03 | 1.000 | no edge in training |
| engulfing_bull|scalp:bias | long | market | 12,510 | 26 | -0.26 | -0.02 | 0.04 | 1.000 | no edge in training |
| engulfing_bull|scalp:bias+context | long | market | 6,606 | 26 | -0.27 | -0.03 | 0.05 | 1.000 | no edge in training |
| engulfing_bull|scalp:counter | long | market | 11,641 | 28 | -0.22 | +0.01 | 0.04 | 0.640 | no edge in training |
| engulfing_bull|scalp:full | long | market | 1,955 | 27 | -0.24 | -0.05 | 0.09 | 1.000 | no edge in training |
| equal_highs | short | market | 5,037 | 21 | -0.40 | -0.01 | 0.05 | 1.000 | no edge in training |
| equal_highs+displacement | short | market | 941 | 34 | -0.08 | +0.03 | 0.11 | 0.708 | no edge in training |
| equal_lows | long | market | 4,909 | 20 | -0.44 | -0.05 | 0.05 | 1.000 | no edge in training |
| equal_lows+displacement | long | market | 1,024 | 38 | -0.04 | +0.05 | 0.10 | 0.550 | no edge in training |
| evening_doji_star | short | market | 2,247 | 23 | -0.38 | -0.04 | 0.06 | 1.000 | no edge in training |
| evening_star | short | market | 5,809 | 24 | -0.33 | -0.01 | 0.04 | 1.000 | no edge in training |
| exhaustion_sequence | long | market | 434 | 36 | -0.05 | +0.05 | 0.15 | 0.640 | no edge in training |
| exhaustion_sequence | short | market | 335 | 34 | -0.05 | +0.06 | 0.19 | 0.649 | no edge in training |
| external_bos | long | market | 4,613 | 38 | -0.07 | +0.04 | 0.05 | 0.361 | no edge in training |
| external_bos | short | market | 3,871 | 35 | -0.12 | +0.01 | 0.05 | 0.769 | no edge in training |
| external_sweep | long | market | 10,591 | 24 | -0.33 | +0.01 | 0.04 | 0.708 | no edge in training |
| external_sweep | short | market | 9,997 | 17 | -0.58 | -0.05 | 0.03 | 1.000 | no edge in training |
| failed_bos | long | market | 7,361 | 30 | -0.19 | +0.02 | 0.04 | 0.590 | no edge in training |
| failed_bos | short | market | 7,937 | 25 | -0.30 | +0.03 | 0.04 | 0.214 | no edge in training |
| failed_breakout | long | market | 4,805 | 32 | -0.16 | -0.00 | 0.05 | 0.934 | no edge in training |
| failed_breakout | short | market | 4,220 | 30 | -0.17 | +0.05 | 0.06 | 0.205 | no edge in training |
| failed_breakout+reclaim | long | market | 666 | 38 | -0.12 | -0.04 | 0.10 | 1.000 | no edge in training |
| failed_breakout+reclaim | short | market | 619 | 38 | -0.04 | +0.08 | 0.12 | 0.368 | no edge in training |
| failed_breakout|scalp:bias | long | market | 2,093 | 30 | -0.21 | -0.05 | 0.08 | 1.000 | no edge in training |
| failed_breakout|scalp:bias | short | market | 1,948 | 30 | -0.17 | +0.06 | 0.08 | 0.347 | no edge in training |
| failed_breakout|scalp:bias+context | long | market | 1,020 | 30 | -0.23 | -0.07 | 0.12 | 1.000 | no edge in training |
| failed_breakout|scalp:bias+context | short | market | 767 | 31 | -0.14 | +0.07 | 0.13 | 0.506 | no edge in training |
| failed_breakout|scalp:counter | long | market | 2,712 | 34 | -0.12 | +0.03 | 0.07 | 0.562 | no edge in training |
| failed_breakout|scalp:counter | short | market | 2,272 | 30 | -0.18 | +0.04 | 0.08 | 0.474 | no edge in training |
| failed_breakout|scalp:full | long | market | 183 | 36 | -0.08 | +0.02 | 0.24 | 0.845 | no edge in training |
| failed_breakout|scalp:full | short | market | 136 | 30 | -0.22 | -0.04 | 0.26 | 0.985 | no edge in training |
| failed_momentum_breakout | long | market | 5,841 | 32 | -0.13 | +0.06 | 0.04 | 0.021 | candidate |
| failed_momentum_breakout | short | market | 6,654 | 25 | -0.30 | +0.03 | 0.04 | 0.277 | no edge in training |
| failed_sweep | long | market | 7,289 | 33 | -0.16 | -0.01 | 0.05 | 0.985 | no edge in training |
| failed_sweep | short | market | 7,213 | 27 | -0.26 | -0.07 | 0.05 | 1.000 | no edge in training |
| failed_swing | long | market | 13,312 | 35 | -0.13 | -0.01 | 0.04 | 1.000 | no edge in training |
| failed_swing | short | market | 11,816 | 31 | -0.19 | -0.04 | 0.04 | 1.000 | no edge in training |
| falling_channel_break | long | market | 1,727 | 35 | -0.14 | -0.02 | 0.07 | 0.937 | no edge in training |
| falling_three_methods | short | market | 273 | 27 | -0.31 | -0.12 | 0.18 | 1.000 | no edge in training |
| falling_wedge_breakout | long | market | 1,712 | 34 | -0.12 | +0.03 | 0.07 | 0.570 | no edge in training |
| fib_extension | long | market | 2,514 | 44 | -0.01 | +0.07 | 0.06 | 0.085 | candidate |
| fib_extension | short | market | 2,316 | 39 | -0.04 | +0.04 | 0.07 | 0.415 | no edge in training |
| fib_retracement | long | market | 1,680 | 31 | -0.16 | +0.05 | 0.07 | 0.368 | no edge in training |
| fib_retracement | short | market | 1,642 | 26 | -0.29 | +0.01 | 0.08 | 0.713 | no edge in training |
| fvg | long | limit | 20,808 | 16 | -0.52 | -0.02 | 0.02 | 1.000 | no edge in training |
| fvg | short | limit | 21,793 | 15 | -0.56 | -0.04 | 0.02 | 1.000 | no edge in training |
| fvg_after_sweep | long | limit | 2,759 | 16 | -0.53 | -0.01 | 0.05 | 1.000 | no edge in training |
| fvg_after_sweep | short | limit | 2,854 | 17 | -0.52 | +0.00 | 0.05 | 0.862 | no edge in training |
| fvg_continuation | long | limit | 14,375 | 17 | -0.49 | -0.01 | 0.02 | 1.000 | no edge in training |
| fvg_continuation | short | limit | 14,788 | 16 | -0.53 | -0.04 | 0.02 | 1.000 | no edge in training |
| fvg_formation | long | market | 24,962 | 27 | -0.23 | -0.02 | 0.03 | 1.000 | no edge in training |
| fvg_formation | short | market | 24,210 | 24 | -0.34 | -0.05 | 0.03 | 1.000 | no edge in training |
| fvg_reversal | long | limit | 6,433 | 14 | -0.57 | -0.04 | 0.04 | 1.000 | no edge in training |
| fvg_reversal | short | limit | 7,005 | 13 | -0.61 | -0.04 | 0.03 | 1.000 | no edge in training |
| fvg_with_bos | long | limit | 4,375 | 18 | -0.48 | +0.01 | 0.04 | 0.767 | no edge in training |
| fvg_with_bos | short | limit | 4,334 | 18 | -0.48 | +0.00 | 0.04 | 0.887 | no edge in training |
| fvg_with_choch | long | limit | 4,572 | 19 | -0.44 | +0.03 | 0.04 | 0.360 | no edge in training |
| fvg_with_choch | short | limit | 5,100 | 19 | -0.46 | +0.04 | 0.04 | 0.119 | no edge in training |
| fvg|scalp:bias | long | limit | 11,129 | 16 | -0.52 | -0.03 | 0.03 | 1.000 | no edge in training |
| fvg|scalp:bias | short | limit | 11,405 | 16 | -0.54 | -0.04 | 0.03 | 1.000 | no edge in training |
| fvg|scalp:bias+context | long | limit | 5,767 | 17 | -0.51 | -0.02 | 0.04 | 1.000 | no edge in training |
| fvg|scalp:bias+context | short | limit | 4,834 | 16 | -0.53 | -0.04 | 0.04 | 1.000 | no edge in training |
| fvg|scalp:counter | long | limit | 9,679 | 17 | -0.51 | -0.00 | 0.03 | 0.939 | no edge in training |
| fvg|scalp:counter | short | limit | 10,388 | 15 | -0.58 | -0.03 | 0.03 | 1.000 | no edge in training |
| fvg|scalp:full | long | limit | 3,851 | 17 | -0.50 | -0.02 | 0.05 | 1.000 | no edge in training |
| fvg|scalp:full | short | limit | 3,247 | 16 | -0.54 | -0.05 | 0.05 | 1.000 | no edge in training |
| gap_continuation | long | market | 2,870 | 12 | -0.71 | -0.09 | 0.05 | 1.000 | no edge in training |
| gap_continuation | short | market | 2,593 | 4 | -1.20 | -0.25 | 0.04 | 1.000 | no edge in training |
| gap_fade | long | market | 3,047 | 15 | -0.59 | -0.05 | 0.06 | 1.000 | no edge in training |
| gap_fade | short | market | 2,941 | 5 | -1.05 | -0.19 | 0.04 | 1.000 | no edge in training |
| gartley | long | market | 43 | - | - | - | - | - | not enough trades |
| gartley | short | market | 45 | - | - | - | - | - | not enough trades |
| golden_pullback | long | market | 698 | 31 | -0.16 | +0.02 | 0.12 | 0.708 | no edge in training |
| golden_pullback | short | market | 696 | 28 | -0.24 | +0.03 | 0.12 | 0.675 | no edge in training |
| grab_reversal | long | market | 6,126 | 33 | -0.15 | +0.01 | 0.05 | 0.805 | no edge in training |
| grab_reversal | short | market | 5,433 | 29 | -0.21 | +0.02 | 0.05 | 0.558 | no edge in training |
| grab_reversal+order_block | long | limit | 1,748 | 27 | -0.25 | +0.02 | 0.08 | 0.711 | no edge in training |
| grab_reversal+order_block | short | limit | 1,611 | 28 | -0.21 | +0.09 | 0.08 | 0.088 | candidate |
| grab_reversal|scalp:bias | long | market | 3,255 | 33 | -0.16 | +0.01 | 0.07 | 0.853 | no edge in training |
| grab_reversal|scalp:bias | short | market | 2,623 | 30 | -0.18 | +0.04 | 0.07 | 0.529 | no edge in training |
| grab_reversal|scalp:bias+context | long | market | 1,754 | 33 | -0.12 | +0.04 | 0.09 | 0.592 | no edge in training |
| grab_reversal|scalp:bias+context | short | market | 1,137 | 31 | -0.16 | +0.05 | 0.10 | 0.539 | no edge in training |
| grab_reversal|scalp:counter | long | market | 2,871 | 32 | -0.15 | +0.01 | 0.07 | 0.805 | no edge in training |
| grab_reversal|scalp:counter | short | market | 2,810 | 28 | -0.23 | +0.01 | 0.07 | 0.815 | no edge in training |
| grab_reversal|scalp:full | long | market | 639 | 33 | -0.16 | -0.04 | 0.15 | 1.000 | no edge in training |
| grab_reversal|scalp:full | short | market | 403 | 33 | -0.13 | +0.06 | 0.17 | 0.660 | no edge in training |
| gravestone_doji | short | market | 1,983 | 21 | -0.45 | -0.05 | 0.09 | 1.000 | no edge in training |
| hammer | long | market | 9,795 | 25 | -0.29 | +0.03 | 0.04 | 0.165 | no edge in training |
| hanging_man | short | market | 9,963 | 7 | -0.95 | -0.21 | 0.03 | 1.000 | no edge in training |
| harami_bear | short | market | 13,650 | 20 | -0.44 | +0.00 | 0.03 | 0.862 | no edge in training |
| harami_bull | long | market | 13,658 | 26 | -0.26 | +0.04 | 0.03 | 0.039 | candidate |
| head_and_shoulders | short | market | 104 | 35 | -0.20 | -0.10 | 0.24 | 0.979 | no edge in training |
| higher_low | long | market | 19,942 | 29 | -0.23 | -0.01 | 0.03 | 1.000 | no edge in training |
| higher_low+bos | long | market | 4,945 | 35 | -0.11 | +0.01 | 0.05 | 0.769 | no edge in training |
| ice_breakdown | short | market | 247 | 33 | -0.14 | -0.00 | 0.20 | 0.815 | no edge in training |
| inside_bar_bear | short | market | 31,400 | 19 | -0.48 | -0.01 | 0.02 | 1.000 | no edge in training |
| inside_bar_bull | long | market | 30,249 | 25 | -0.30 | +0.01 | 0.02 | 0.603 | no edge in training |
| inside_compression+nr_breakout | long | market | 1,681 | 27 | -0.24 | +0.03 | 0.08 | 0.639 | no edge in training |
| inside_compression+nr_breakout | short | market | 1,650 | 21 | -0.41 | -0.04 | 0.08 | 1.000 | no edge in training |
| internal_bos | long | market | 8,926 | 33 | -0.15 | -0.03 | 0.04 | 1.000 | no edge in training |
| internal_bos | short | market | 7,612 | 30 | -0.20 | -0.04 | 0.05 | 1.000 | no edge in training |
| internal_sweep | long | market | 25,883 | 23 | -0.36 | +0.00 | 0.03 | 0.805 | no edge in training |
| internal_sweep | short | market | 24,176 | 16 | -0.60 | -0.05 | 0.02 | 1.000 | no edge in training |
| inverse_cup_and_handle | short | market | 93 | - | - | - | - | - | not enough trades |
| inverse_fvg | long | limit | 17,155 | 15 | -0.55 | -0.04 | 0.02 | 1.000 | no edge in training |
| inverse_fvg | short | limit | 18,384 | 14 | -0.58 | -0.05 | 0.02 | 1.000 | no edge in training |
| inverse_head_and_shoulders | long | market | 105 | 44 | -0.04 | +0.06 | 0.22 | 0.675 | no edge in training |
| inverted_hammer | long | market | 6,610 | 17 | -0.50 | +0.03 | 0.04 | 0.290 | no edge in training |
| kicker | long | market | 42 | - | - | - | - | - | not enough trades |
| kicker | short | market | 9 | - | - | - | - | - | not enough trades |
| last_point_of_supply | short | market | 89 | - | - | - | - | - | not enough trades |
| last_point_of_support | long | market | 90 | - | - | - | - | - | not enough trades |
| liquidity_sweep | long | market | 17,764 | 23 | -0.35 | +0.01 | 0.03 | 0.771 | no edge in training |
| liquidity_sweep | short | market | 16,780 | 16 | -0.59 | -0.05 | 0.03 | 1.000 | no edge in training |
| liquidity_sweep|scalp:bias | long | market | 9,793 | 23 | -0.36 | -0.00 | 0.04 | 0.968 | no edge in training |
| liquidity_sweep|scalp:bias | short | market | 7,964 | 17 | -0.56 | -0.04 | 0.04 | 1.000 | no edge in training |
| liquidity_sweep|scalp:bias+context | long | market | 5,250 | 23 | -0.34 | +0.02 | 0.05 | 0.643 | no edge in training |
| liquidity_sweep|scalp:bias+context | short | market | 3,328 | 18 | -0.52 | -0.03 | 0.06 | 1.000 | no edge in training |
| liquidity_sweep|scalp:counter | long | market | 7,971 | 24 | -0.33 | +0.02 | 0.04 | 0.562 | no edge in training |
| liquidity_sweep|scalp:counter | short | market | 8,816 | 16 | -0.62 | -0.06 | 0.04 | 1.000 | no edge in training |
| liquidity_sweep|scalp:full | long | market | 186 | 27 | -0.21 | +0.02 | 0.30 | 0.862 | no edge in training |
| liquidity_sweep|scalp:full | short | market | 91 | - | - | - | - | - | not enough trades |
| london_high_sweep | short | market | 1,952 | 20 | -0.47 | -0.03 | 0.07 | 1.000 | no edge in training |
| london_high_sweep+choch | short | market | 902 | 35 | -0.17 | -0.00 | 0.09 | 0.929 | no edge in training |
| london_low_sweep | long | market | 2,060 | 26 | -0.27 | +0.01 | 0.07 | 0.769 | no edge in training |
| london_low_sweep+choch | long | market | 1,068 | 39 | -0.09 | -0.01 | 0.08 | 0.963 | no edge in training |
| lower_high | short | market | 18,980 | 23 | -0.38 | -0.03 | 0.03 | 1.000 | no edge in training |
| lower_high+bos | short | market | 4,175 | 30 | -0.20 | -0.05 | 0.06 | 1.000 | no edge in training |
| market_structure_shift | long | market | 2,655 | 36 | -0.09 | +0.02 | 0.06 | 0.639 | no edge in training |
| market_structure_shift | short | market | 2,460 | 30 | -0.19 | -0.05 | 0.06 | 1.000 | no edge in training |
| market_structure_shift|scalp:bias | long | market | 1,468 | 37 | -0.06 | +0.05 | 0.08 | 0.363 | no edge in training |
| market_structure_shift|scalp:bias | short | market | 1,253 | 32 | -0.13 | -0.00 | 0.09 | 0.929 | no edge in training |
| market_structure_shift|scalp:bias+context | long | market | 773 | 38 | -0.03 | +0.08 | 0.11 | 0.335 | no edge in training |
| market_structure_shift|scalp:bias+context | short | market | 500 | 33 | -0.08 | +0.03 | 0.14 | 0.747 | no edge in training |
| market_structure_shift|scalp:counter | long | market | 1,187 | 35 | -0.13 | -0.02 | 0.09 | 1.000 | no edge in training |
| market_structure_shift|scalp:counter | short | market | 1,207 | 28 | -0.25 | -0.10 | 0.09 | 1.000 | no edge in training |
| market_structure_shift|scalp:full | long | market | 701 | 39 | -0.03 | +0.08 | 0.12 | 0.343 | no edge in training |
| market_structure_shift|scalp:full | short | market | 457 | 34 | -0.08 | +0.03 | 0.15 | 0.747 | no edge in training |
| marubozu_bear | short | market | 3,637 | 27 | -0.24 | -0.06 | 0.06 | 1.000 | no edge in training |
| marubozu_bull | long | market | 3,642 | 31 | -0.15 | -0.01 | 0.06 | 1.000 | no edge in training |
| momentum_continuation | long | market | 5,658 | 43 | -0.05 | -0.00 | 0.05 | 0.929 | no edge in training |
| momentum_continuation | short | market | 5,199 | 37 | -0.14 | -0.04 | 0.05 | 1.000 | no edge in training |
| momentum_exhaustion | long | market | 753 | 38 | -0.11 | +0.01 | 0.11 | 0.862 | no edge in training |
| momentum_exhaustion | short | market | 798 | 29 | -0.28 | -0.14 | 0.11 | 1.000 | no edge in training |
| morning_doji_star | long | market | 2,273 | 29 | -0.20 | +0.03 | 0.07 | 0.550 | no edge in training |
| morning_star | long | market | 5,728 | 29 | -0.20 | +0.01 | 0.05 | 0.708 | no edge in training |
| multi_touch_rejection | long | market | 2,772 | 28 | -0.23 | -0.01 | 0.06 | 0.982 | no edge in training |
| multi_touch_rejection | short | market | 2,333 | 24 | -0.32 | +0.00 | 0.07 | 0.888 | no edge in training |
| multiple_sweeps | long | market | 5,000 | 22 | -0.39 | -0.01 | 0.05 | 1.000 | no edge in training |
| multiple_sweeps | short | market | 4,454 | 13 | -0.72 | -0.11 | 0.05 | 1.000 | no edge in training |
| nr_breakout | long | market | 16,388 | 26 | -0.27 | -0.02 | 0.03 | 1.000 | no edge in training |
| nr_breakout | short | market | 15,862 | 21 | -0.40 | -0.06 | 0.03 | 1.000 | no edge in training |
| order_block | long | limit | 8,690 | 26 | -0.25 | +0.03 | 0.03 | 0.230 | no edge in training |
| order_block | short | limit | 8,767 | 25 | -0.28 | +0.02 | 0.03 | 0.452 | no edge in training |
| order_block_bos | long | limit | 4,446 | 26 | -0.24 | +0.05 | 0.05 | 0.114 | no edge in training |
| order_block_bos | short | limit | 4,034 | 24 | -0.30 | +0.00 | 0.05 | 0.853 | no edge in training |
| order_block_choch | long | limit | 4,244 | 27 | -0.26 | +0.01 | 0.05 | 0.808 | no edge in training |
| order_block_choch | short | limit | 4,733 | 26 | -0.27 | +0.03 | 0.05 | 0.320 | no edge in training |
| order_block_fvg | long | limit | 3,143 | 27 | -0.22 | +0.07 | 0.06 | 0.071 | candidate |
| order_block_fvg | short | limit | 3,287 | 26 | -0.26 | +0.03 | 0.06 | 0.539 | no edge in training |
| order_block_sweep | long | limit | 1,489 | 29 | -0.21 | +0.01 | 0.08 | 0.862 | no edge in training |
| order_block_sweep | short | limit | 1,699 | 30 | -0.17 | +0.09 | 0.08 | 0.073 | candidate |
| order_block|scalp:bias | long | limit | 4,741 | 25 | -0.29 | -0.00 | 0.05 | 0.923 | no edge in training |
| order_block|scalp:bias | short | limit | 4,274 | 25 | -0.27 | +0.03 | 0.05 | 0.468 | no edge in training |
| order_block|scalp:bias+context | long | limit | 2,580 | 25 | -0.29 | -0.02 | 0.06 | 1.000 | no edge in training |
| order_block|scalp:bias+context | short | limit | 1,764 | 24 | -0.29 | -0.00 | 0.08 | 0.926 | no edge in training |
| order_block|scalp:counter | long | limit | 3,949 | 28 | -0.21 | +0.07 | 0.05 | 0.036 | candidate |
| order_block|scalp:counter | short | limit | 4,493 | 25 | -0.29 | +0.01 | 0.05 | 0.713 | no edge in training |
| order_block|scalp:full | long | limit | 2,296 | 25 | -0.29 | -0.01 | 0.07 | 1.000 | no edge in training |
| order_block|scalp:full | short | limit | 1,568 | 24 | -0.29 | -0.00 | 0.08 | 0.929 | no edge in training |
| outside_bar_bear | short | market | 19,095 | 19 | -0.50 | -0.06 | 0.03 | 1.000 | no edge in training |
| outside_bar_bull | long | market | 21,124 | 25 | -0.31 | -0.02 | 0.03 | 1.000 | no edge in training |
| pd_high_sweep | short | market | 919 | 18 | -0.51 | -0.01 | 0.09 | 0.951 | no edge in training |
| pd_high_sweep|scalp:bias | short | market | 172 | 20 | -0.46 | -0.08 | 0.22 | 1.000 | no edge in training |
| pd_high_sweep|scalp:bias+context | short | market | 58 | - | - | - | - | - | not enough trades |
| pd_high_sweep|scalp:counter | short | market | 747 | 18 | -0.52 | +0.01 | 0.10 | 0.860 | no edge in training |
| pd_high_sweep|scalp:full | short | market | 2 | - | - | - | - | - | not enough trades |
| pd_low_sweep | long | market | 886 | 27 | -0.26 | +0.05 | 0.10 | 0.529 | no edge in training |
| pd_low_sweep|scalp:bias | long | market | 182 | 30 | -0.24 | +0.06 | 0.22 | 0.708 | no edge in training |
| pd_low_sweep|scalp:bias+context | long | market | 84 | - | - | - | - | - | not enough trades |
| pd_low_sweep|scalp:counter | long | market | 704 | 26 | -0.27 | +0.05 | 0.12 | 0.558 | no edge in training |
| pd_low_sweep|scalp:full | long | market | 2 | - | - | - | - | - | not enough trades |
| pdh_sweep+choch | short | market | 191 | 34 | -0.17 | +0.00 | 0.20 | 0.887 | no edge in training |
| pdh_sweep+engulfing | short | market | 205 | 21 | -0.38 | -0.08 | 0.20 | 1.000 | no edge in training |
| pdh_sweep+fvg | short | limit | 396 | 17 | -0.51 | +0.03 | 0.14 | 0.771 | no edge in training |
| pdl_sweep+choch | long | market | 210 | 42 | -0.09 | +0.02 | 0.17 | 0.845 | no edge in training |
| pdl_sweep+engulfing | long | market | 205 | 33 | -0.08 | +0.10 | 0.24 | 0.562 | no edge in training |
| pdl_sweep+fvg | long | limit | 429 | 17 | -0.52 | -0.06 | 0.13 | 1.000 | no edge in training |
| piercing | long | market | 4,062 | 27 | -0.24 | +0.00 | 0.05 | 0.860 | no edge in training |
| pin_bar_bear | short | market | 15,838 | 20 | -0.45 | -0.03 | 0.03 | 1.000 | no edge in training |
| pin_bar_bear|scalp:bias | short | market | 7,527 | 20 | -0.43 | -0.01 | 0.04 | 1.000 | no edge in training |
| pin_bar_bear|scalp:bias+context | short | market | 3,181 | 22 | -0.38 | +0.02 | 0.06 | 0.666 | no edge in training |
| pin_bar_bear|scalp:counter | short | market | 8,311 | 20 | -0.47 | -0.04 | 0.05 | 1.000 | no edge in training |
| pin_bar_bear|scalp:full | short | market | 421 | 23 | -0.33 | +0.08 | 0.15 | 0.539 | no edge in training |
| pin_bar_bull | long | market | 22,540 | 23 | -0.34 | +0.00 | 0.03 | 0.885 | no edge in training |
| pin_bar_bull|scalp:bias | long | market | 12,070 | 22 | -0.36 | -0.02 | 0.03 | 1.000 | no edge in training |
| pin_bar_bull|scalp:bias+context | long | market | 6,475 | 23 | -0.35 | -0.00 | 0.05 | 0.935 | no edge in training |
| pin_bar_bull|scalp:counter | long | market | 10,470 | 24 | -0.31 | +0.02 | 0.04 | 0.515 | no edge in training |
| pin_bar_bull|scalp:full | long | market | 903 | 21 | -0.40 | -0.07 | 0.10 | 1.000 | no edge in training |
| pm_high_sweep | short | market | 44 | - | - | - | - | - | not enough trades |
| pm_low_sweep | long | market | 35 | - | - | - | - | - | not enough trades |
| preliminary_supply | short | market | 1,843 | 25 | -0.28 | +0.02 | 0.07 | 0.570 | no edge in training |
| preliminary_support | long | market | 1,871 | 29 | -0.20 | +0.03 | 0.07 | 0.507 | no edge in training |
| pw_high_sweep | short | market | 184 | 21 | -0.49 | +0.01 | 0.20 | 0.862 | no edge in training |
| pw_low_sweep | long | market | 161 | 22 | -0.37 | -0.08 | 0.23 | 1.000 | no edge in training |
| range_boundary_rejection | long | market | 10,273 | 26 | -0.27 | +0.04 | 0.04 | 0.074 | candidate |
| range_boundary_rejection | short | market | 11,389 | 19 | -0.48 | -0.01 | 0.03 | 1.000 | no edge in training |
| range_midpoint_cross | long | market | 14,161 | 30 | -0.20 | +0.00 | 0.04 | 0.845 | no edge in training |
| range_midpoint_cross | short | market | 14,121 | 25 | -0.33 | -0.01 | 0.03 | 1.000 | no edge in training |
| range_to_trend | long | market | 3,741 | 40 | -0.07 | +0.03 | 0.06 | 0.546 | no edge in training |
| range_to_trend | short | market | 3,166 | 35 | -0.13 | -0.01 | 0.06 | 1.000 | no edge in training |
| reclaimed_order_block | long | market | 4,833 | 38 | -0.10 | -0.01 | 0.05 | 1.000 | no edge in training |
| reclaimed_order_block | short | market | 4,311 | 37 | -0.08 | +0.05 | 0.05 | 0.205 | no edge in training |
| rectangle_breakout | long | market | 749 | 38 | -0.04 | +0.05 | 0.11 | 0.507 | no edge in training |
| rectangle_breakout | short | market | 672 | 35 | -0.11 | +0.00 | 0.11 | 0.770 | no edge in training |
| rejection_bear | short | market | 12,962 | 22 | -0.40 | +0.01 | 0.03 | 0.660 | no edge in training |
| rejection_bear+bos | short | market | 1,262 | 34 | -0.13 | -0.00 | 0.09 | 0.917 | no edge in training |
| rejection_block | long | limit | 11,452 | 22 | -0.36 | +0.03 | 0.03 | 0.073 | candidate |
| rejection_block | short | limit | 10,450 | 20 | -0.42 | +0.02 | 0.03 | 0.539 | no edge in training |
| rejection_bull | long | market | 15,908 | 25 | -0.28 | +0.02 | 0.03 | 0.347 | no edge in training |
| rejection_bull+bos | long | market | 1,832 | 37 | -0.06 | +0.06 | 0.08 | 0.323 | no edge in training |
| resistance_rejection | short | market | 3,407 | 24 | -0.32 | +0.02 | 0.06 | 0.689 | no edge in training |
| resistance_rejection+engulfing | short | market | 624 | 26 | -0.28 | +0.01 | 0.12 | 0.867 | no edge in training |
| resistance_rejection|scalp:bias | short | market | 1,330 | 24 | -0.31 | +0.00 | 0.09 | 0.866 | no edge in training |
| resistance_rejection|scalp:bias+context | short | market | 502 | 26 | -0.26 | +0.03 | 0.14 | 0.779 | no edge in training |
| resistance_rejection|scalp:counter | short | market | 2,077 | 24 | -0.33 | +0.02 | 0.07 | 0.640 | no edge in training |
| resistance_rejection|scalp:full | short | market | 51 | - | - | - | - | - | not enough trades |
| retest | long | market | 6,143 | 25 | -0.28 | +0.01 | 0.05 | 0.807 | no edge in training |
| retest | short | market | 6,210 | 22 | -0.38 | -0.01 | 0.04 | 0.985 | no edge in training |
| retest+momentum | long | market | 1,448 | 44 | -0.05 | -0.00 | 0.09 | 0.903 | no edge in training |
| retest+momentum | short | market | 1,421 | 36 | -0.15 | -0.04 | 0.09 | 1.000 | no edge in training |
| retest|scalp:bias | long | market | 3,646 | 25 | -0.30 | -0.01 | 0.06 | 0.955 | no edge in training |
| retest|scalp:bias | short | market | 3,686 | 22 | -0.38 | -0.01 | 0.06 | 1.000 | no edge in training |
| retest|scalp:bias+context | long | market | 1,732 | 25 | -0.29 | +0.00 | 0.08 | 0.876 | no edge in training |
| retest|scalp:bias+context | short | market | 1,332 | 24 | -0.32 | +0.03 | 0.09 | 0.684 | no edge in training |
| retest|scalp:counter | long | market | 2,497 | 26 | -0.26 | +0.02 | 0.07 | 0.639 | no edge in training |
| retest|scalp:counter | short | market | 2,524 | 22 | -0.39 | +0.00 | 0.07 | 0.862 | no edge in training |
| retest|scalp:full | long | market | 557 | 24 | -0.33 | -0.03 | 0.14 | 1.000 | no edge in training |
| retest|scalp:full | short | market | 414 | 24 | -0.30 | +0.03 | 0.16 | 0.783 | no edge in training |
| rising_channel_break | short | market | 1,715 | 32 | -0.14 | +0.04 | 0.08 | 0.415 | no edge in training |
| rising_three_methods | long | market | 315 | 34 | -0.13 | -0.01 | 0.17 | 0.926 | no edge in training |
| rising_wedge_breakdown | short | market | 1,890 | 28 | -0.24 | +0.01 | 0.07 | 0.713 | no edge in training |
| round100_reaction | long | market | 1,119 | 23 | -0.33 | +0.02 | 0.11 | 0.807 | no edge in training |
| round100_reaction | short | market | 1,020 | 21 | -0.42 | +0.05 | 0.11 | 0.550 | no edge in training |
| round10_reaction | long | market | 10,168 | 25 | -0.28 | +0.06 | 0.04 | 0.022 | candidate |
| round10_reaction | short | market | 8,929 | 21 | -0.42 | +0.01 | 0.05 | 0.809 | no edge in training |
| round50_reaction | long | market | 1,178 | 25 | -0.29 | +0.06 | 0.13 | 0.562 | no edge in training |
| round50_reaction | short | market | 970 | 18 | -0.50 | -0.02 | 0.11 | 1.000 | no edge in training |
| round_placebo_reaction | long | market | 15,053 | 23 | -0.33 | +0.02 | 0.04 | 0.452 | no edge in training |
| round_placebo_reaction | short | market | 12,958 | 19 | -0.46 | +0.00 | 0.03 | 0.876 | no edge in training |
| rounding_bottom | long | market | 265 | 42 | -0.00 | +0.06 | 0.17 | 0.544 | no edge in training |
| rounding_top | short | market | 404 | 38 | -0.09 | +0.00 | 0.13 | 0.770 | no edge in training |
| secondary_test | long | market | 272 | 27 | -0.26 | -0.02 | 0.19 | 0.880 | no edge in training |
| secondary_test | short | market | 284 | 30 | -0.16 | +0.15 | 0.20 | 0.317 | no edge in training |
| selling_climax | long | market | 2,078 | 26 | -0.25 | -0.02 | 0.07 | 0.956 | no edge in training |
| shark | long | market | 135 | 33 | -0.16 | -0.04 | 0.23 | 0.892 | no edge in training |
| shark | short | market | 127 | 35 | -0.14 | +0.02 | 0.26 | 0.735 | no edge in training |
| shooting_star | short | market | 7,358 | 22 | -0.40 | +0.00 | 0.04 | 0.887 | no edge in training |
| sign_of_strength | long | market | 341 | 34 | -0.12 | +0.04 | 0.18 | 0.689 | no edge in training |
| sign_of_weakness | short | market | 337 | 29 | -0.16 | +0.08 | 0.18 | 0.507 | no edge in training |
| spring | long | market | 664 | 19 | -0.45 | +0.02 | 0.11 | 0.689 | no edge in training |
| squeeze+bos | long | market | 688 | 36 | -0.09 | +0.03 | 0.12 | 0.684 | no edge in training |
| squeeze+bos | short | market | 622 | 29 | -0.20 | -0.07 | 0.12 | 1.000 | no edge in training |
| squeeze_release | long | market | 3,746 | 35 | -0.14 | -0.01 | 0.05 | 1.000 | no edge in training |
| squeeze_release | short | market | 3,546 | 31 | -0.18 | -0.02 | 0.05 | 1.000 | no edge in training |
| strong_bear_sequence | short | market | 377 | 41 | +0.02 | +0.11 | 0.16 | 0.347 | no edge in training |
| strong_bull_sequence | long | market | 399 | 41 | -0.05 | +0.03 | 0.14 | 0.747 | no edge in training |
| strong_demand | long | limit | 344 | 29 | -0.14 | +0.27 | 0.19 | 0.021 | candidate |
| strong_supply | short | limit | 392 | 25 | -0.24 | +0.16 | 0.17 | 0.169 | no edge in training |
| structural_reclaim | long | market | 2,200 | 39 | -0.08 | +0.02 | 0.06 | 0.697 | no edge in training |
| structural_reclaim | short | market | 2,372 | 35 | -0.12 | +0.02 | 0.06 | 0.609 | no edge in training |
| supply_to_demand_flip | long | limit | 2,143 | 23 | -0.32 | +0.05 | 0.07 | 0.368 | no edge in training |
| supply_zone | short | limit | 2,406 | 21 | -0.37 | +0.03 | 0.06 | 0.506 | no edge in training |
| supply_zone|scalp:bias | short | limit | 1,236 | 21 | -0.39 | +0.01 | 0.09 | 0.788 | no edge in training |
| supply_zone|scalp:bias+context | short | limit | 523 | 20 | -0.42 | -0.03 | 0.13 | 1.000 | no edge in training |
| supply_zone|scalp:counter | short | limit | 1,170 | 22 | -0.36 | +0.05 | 0.09 | 0.448 | no edge in training |
| supply_zone|scalp:full | short | limit | 430 | 18 | -0.46 | -0.06 | 0.14 | 1.000 | no edge in training |
| support_rejection | long | market | 3,954 | 27 | -0.26 | -0.03 | 0.05 | 1.000 | no edge in training |
| support_rejection+engulfing | long | market | 712 | 29 | -0.22 | -0.02 | 0.11 | 0.985 | no edge in training |
| support_rejection|scalp:bias | long | market | 1,673 | 25 | -0.31 | -0.07 | 0.08 | 1.000 | no edge in training |
| support_rejection|scalp:bias+context | long | market | 849 | 26 | -0.28 | -0.05 | 0.12 | 1.000 | no edge in training |
| support_rejection|scalp:counter | long | market | 2,281 | 28 | -0.22 | +0.00 | 0.07 | 0.862 | no edge in training |
| support_rejection|scalp:full | long | market | 85 | - | - | - | - | - | not enough trades |
| sweep+bos | long | market | 1,290 | 37 | -0.08 | +0.04 | 0.09 | 0.546 | no edge in training |
| sweep+bos | short | market | 973 | 33 | -0.15 | -0.01 | 0.10 | 0.941 | no edge in training |
| sweep+choch | long | market | 2,345 | 38 | -0.11 | -0.01 | 0.06 | 1.000 | no edge in training |
| sweep+choch | short | market | 2,200 | 34 | -0.15 | -0.00 | 0.06 | 0.891 | no edge in training |
| sweep+double_bottom | long | market | 340 | 37 | -0.11 | -0.01 | 0.15 | 0.864 | no edge in training |
| sweep+double_top | short | market | 310 | 36 | -0.04 | +0.05 | 0.17 | 0.675 | no edge in training |
| sweep+mss | long | market | 1,086 | 36 | -0.10 | +0.01 | 0.09 | 0.805 | no edge in training |
| sweep+mss | short | market | 1,003 | 31 | -0.17 | -0.04 | 0.09 | 1.000 | no edge in training |
| sweep+order_block | long | limit | 2,406 | 27 | -0.24 | +0.03 | 0.06 | 0.539 | no edge in training |
| sweep+order_block | short | limit | 2,319 | 27 | -0.23 | +0.07 | 0.07 | 0.154 | no edge in training |
| sweep_reclaim | long | market | 3,775 | 29 | -0.21 | +0.04 | 0.05 | 0.320 | no edge in training |
| sweep_reclaim | short | market | 4,079 | 22 | -0.39 | +0.02 | 0.05 | 0.656 | no edge in training |
| sweep_to_bos | long | market | 4,651 | 38 | -0.10 | +0.01 | 0.06 | 0.779 | no edge in training |
| sweep_to_bos | short | market | 3,999 | 34 | -0.14 | +0.01 | 0.06 | 0.744 | no edge in training |
| sweep_to_bos|scalp:bias | long | market | 2,484 | 37 | -0.11 | +0.00 | 0.08 | 0.870 | no edge in training |
| sweep_to_bos|scalp:bias | short | market | 1,877 | 35 | -0.11 | +0.03 | 0.09 | 0.660 | no edge in training |
| sweep_to_bos|scalp:bias+context | long | market | 1,319 | 37 | -0.11 | -0.00 | 0.11 | 0.926 | no edge in training |
| sweep_to_bos|scalp:bias+context | short | market | 793 | 37 | -0.06 | +0.07 | 0.14 | 0.539 | no edge in training |
| sweep_to_bos|scalp:counter | long | market | 2,167 | 38 | -0.09 | +0.02 | 0.08 | 0.730 | no edge in training |
| sweep_to_bos|scalp:counter | short | market | 2,122 | 34 | -0.16 | +0.00 | 0.08 | 0.889 | no edge in training |
| sweep_to_bos|scalp:full | long | market | 1,181 | 36 | -0.12 | -0.02 | 0.11 | 0.993 | no edge in training |
| sweep_to_bos|scalp:full | short | market | 701 | 36 | -0.08 | +0.05 | 0.14 | 0.640 | no edge in training |
| swing_failure | long | market | 9,864 | 22 | -0.37 | -0.00 | 0.03 | 0.903 | no edge in training |
| swing_failure | short | market | 9,581 | 15 | -0.62 | -0.05 | 0.03 | 1.000 | no edge in training |
| swing_failure+choch | long | market | 1,743 | 36 | -0.13 | -0.02 | 0.07 | 1.000 | no edge in training |
| swing_failure+choch | short | market | 1,599 | 33 | -0.17 | -0.02 | 0.07 | 1.000 | no edge in training |
| swing_failure|scalp:bias | long | market | 5,357 | 21 | -0.40 | -0.02 | 0.04 | 1.000 | no edge in training |
| swing_failure|scalp:bias | short | market | 4,465 | 16 | -0.58 | -0.03 | 0.04 | 1.000 | no edge in training |
| swing_failure|scalp:bias+context | long | market | 2,911 | 21 | -0.39 | -0.01 | 0.06 | 0.968 | no edge in training |
| swing_failure|scalp:bias+context | short | market | 1,874 | 17 | -0.54 | -0.01 | 0.07 | 1.000 | no edge in training |
| swing_failure|scalp:counter | long | market | 4,507 | 23 | -0.34 | +0.03 | 0.05 | 0.490 | no edge in training |
| swing_failure|scalp:counter | short | market | 5,116 | 15 | -0.65 | -0.06 | 0.04 | 1.000 | no edge in training |
| swing_failure|scalp:full | long | market | 134 | 27 | -0.23 | +0.01 | 0.28 | 0.862 | no edge in training |
| swing_failure|scalp:full | short | market | 63 | - | - | - | - | - | not enough trades |
| sym_triangle_breakout | long | market | 1,784 | 32 | -0.19 | -0.05 | 0.08 | 1.000 | no edge in training |
| sym_triangle_breakout | short | market | 1,761 | 30 | -0.18 | +0.04 | 0.08 | 0.505 | no edge in training |
| three_bar_continuation | long | market | 5,001 | 31 | -0.16 | +0.00 | 0.05 | 0.887 | no edge in training |
| three_bar_continuation | short | market | 4,567 | 27 | -0.26 | -0.05 | 0.05 | 1.000 | no edge in training |
| three_bar_reversal | long | market | 27,438 | 30 | -0.19 | -0.01 | 0.03 | 1.000 | no edge in training |
| three_bar_reversal | short | market | 25,297 | 27 | -0.24 | +0.00 | 0.03 | 0.845 | no edge in training |
| three_black_crows | short | market | 566 | 35 | -0.12 | +0.02 | 0.14 | 0.807 | no edge in training |
| three_drives | long | market | 51 | - | - | - | - | - | not enough trades |
| three_drives | short | market | 57 | - | - | - | - | - | not enough trades |
| three_inside_down | short | market | 2,469 | 27 | -0.26 | -0.02 | 0.07 | 1.000 | no edge in training |
| three_inside_up | long | market | 2,572 | 31 | -0.15 | +0.02 | 0.07 | 0.746 | no edge in training |
| three_outside_down | short | market | 10,648 | 26 | -0.27 | -0.04 | 0.04 | 1.000 | no edge in training |
| three_outside_up | long | market | 10,663 | 30 | -0.19 | -0.02 | 0.04 | 1.000 | no edge in training |
| three_white_soldiers | long | market | 660 | 35 | -0.13 | -0.02 | 0.13 | 1.000 | no edge in training |
| triple_bottom | long | market | 153 | 42 | -0.07 | +0.04 | 0.21 | 0.708 | no edge in training |
| triple_top | short | market | 146 | 38 | -0.04 | +0.05 | 0.23 | 0.692 | no edge in training |
| tweezer_bottom | long | market | 8,881 | 25 | -0.30 | +0.05 | 0.04 | 0.021 | candidate |
| tweezer_top | short | market | 10,272 | 15 | -0.61 | -0.04 | 0.03 | 1.000 | no edge in training |
| upthrust | short | market | 629 | 7 | -0.89 | -0.12 | 0.07 | 1.000 | no edge in training |
| wide_range | long | market | 8,491 | 35 | -0.09 | +0.01 | 0.04 | 0.672 | no edge in training |
| wide_range | short | market | 8,135 | 32 | -0.12 | +0.00 | 0.04 | 0.878 | no edge in training |
| wide_range_reversal | long | market | 3,654 | 34 | -0.12 | -0.02 | 0.06 | 1.000 | no edge in training |
| wide_range_reversal | short | market | 3,148 | 32 | -0.13 | -0.01 | 0.06 | 1.000 | no edge in training |

#### M30

| Pattern | Dir | Entry | Trades | Win % | Mean R | Edge | Smallest detectable | q | Status |
|---|---|---|---|---|---|---|---|---|---|
| BOS | long | market | 3,475 | 37 | -0.02 | +0.03 | 0.07 | 0.562 | no edge in training |
| BOS | short | market | 2,882 | 35 | -0.07 | +0.02 | 0.07 | 0.708 | no edge in training |
| CHoCH | long | market | 3,253 | 39 | -0.06 | +0.00 | 0.05 | 0.862 | no edge in training |
| CHoCH | short | market | 3,252 | 33 | -0.14 | -0.04 | 0.06 | 1.000 | no edge in training |
| abcd | long | market | 308 | 34 | -0.13 | -0.05 | 0.18 | 0.932 | no edge in training |
| abcd | short | market | 332 | 31 | -0.18 | -0.07 | 0.18 | 0.979 | no edge in training |
| asc_triangle_breakout | long | market | 570 | 38 | -0.01 | +0.05 | 0.14 | 0.544 | no edge in training |
| asia_high_sweep | short | market | 1,850 | 22 | -0.36 | +0.01 | 0.07 | 0.799 | no edge in training |
| asia_high_sweep+bos | short | market | 160 | 48 | +0.15 | +0.21 | 0.26 | 0.277 | no edge in training |
| asia_low_sweep | long | market | 1,879 | 24 | -0.30 | -0.02 | 0.08 | 1.000 | no edge in training |
| asia_low_sweep+bos | long | market | 180 | 44 | +0.03 | +0.06 | 0.23 | 0.705 | no edge in training |
| atr_expansion | long | market | 542 | 39 | -0.02 | +0.03 | 0.13 | 0.748 | no edge in training |
| atr_expansion | short | market | 592 | 35 | -0.09 | -0.01 | 0.13 | 0.964 | no edge in training |
| atr_expansion+bos | long | market | 84 | - | - | - | - | - | not enough trades |
| atr_expansion+bos | short | market | 125 | 50 | +0.07 | +0.13 | 0.22 | 0.448 | no edge in training |
| balanced_price_range | long | limit | 2,385 | 16 | -0.53 | -0.10 | 0.06 | 1.000 | no edge in training |
| balanced_price_range | short | limit | 2,541 | 16 | -0.53 | -0.07 | 0.06 | 1.000 | no edge in training |
| bat | long | market | 19 | - | - | - | - | - | not enough trades |
| bat | short | market | 21 | - | - | - | - | - | not enough trades |
| bear_flag | short | market | 49 | - | - | - | - | - | not enough trades |
| bear_pennant | short | market | 104 | 29 | -0.20 | -0.05 | 0.33 | 0.890 | no edge in training |
| bos+displacement | long | market | 806 | 43 | +0.12 | +0.16 | 0.12 | 0.032 | candidate |
| bos+displacement | short | market | 763 | 35 | -0.09 | -0.04 | 0.13 | 1.000 | no edge in training |
| breaker+fvg | long | limit | 3,817 | 23 | -0.33 | -0.02 | 0.05 | 1.000 | no edge in training |
| breaker+fvg | short | limit | 3,895 | 23 | -0.33 | -0.02 | 0.05 | 1.000 | no edge in training |
| breaker_block | long | limit | 4,628 | 31 | -0.12 | +0.07 | 0.06 | 0.036 | candidate |
| breaker_block | short | limit | 4,869 | 27 | -0.22 | -0.00 | 0.05 | 0.915 | no edge in training |
| breakout | long | market | 7,193 | 31 | -0.12 | +0.03 | 0.05 | 0.468 | no edge in training |
| breakout | short | market | 7,464 | 27 | -0.23 | -0.04 | 0.05 | 1.000 | no edge in training |
| broadening_breakout | long | market | 161 | 53 | +0.08 | +0.10 | 0.17 | 0.415 | no edge in training |
| broadening_breakout | short | market | 154 | 49 | +0.02 | +0.07 | 0.18 | 0.544 | no edge in training |
| bull_flag | long | market | 85 | - | - | - | - | - | not enough trades |
| bull_pennant | long | market | 127 | 28 | -0.22 | -0.10 | 0.27 | 0.979 | no edge in training |
| butterfly | long | market | 23 | - | - | - | - | - | not enough trades |
| butterfly | short | market | 18 | - | - | - | - | - | not enough trades |
| buying_climax | short | market | 1,083 | 24 | -0.32 | -0.11 | 0.09 | 1.000 | no edge in training |
| channel_breakout | long | market | 197 | 43 | -0.06 | -0.05 | 0.19 | 0.932 | no edge in training |
| channel_breakout | short | market | 166 | 40 | -0.04 | +0.01 | 0.20 | 0.761 | no edge in training |
| choch+fvg | long | limit | 3,478 | 22 | -0.36 | -0.02 | 0.05 | 1.000 | no edge in training |
| choch+fvg | short | limit | 3,549 | 22 | -0.37 | -0.01 | 0.05 | 1.000 | no edge in training |
| climax_reversal | long | market | 267 | 42 | +0.08 | +0.15 | 0.21 | 0.323 | no edge in training |
| climax_reversal | short | market | 247 | 36 | -0.06 | +0.01 | 0.20 | 0.862 | no edge in training |
| compression+sweep | long | market | 903 | 28 | -0.18 | +0.09 | 0.12 | 0.298 | no edge in training |
| compression+sweep | short | market | 932 | 20 | -0.44 | -0.04 | 0.11 | 1.000 | no edge in training |
| compression_breakout | long | market | 156 | 37 | +0.04 | +0.13 | 0.27 | 0.539 | no edge in training |
| compression_breakout | short | market | 155 | 39 | +0.14 | +0.18 | 0.30 | 0.472 | no edge in training |
| consecutive_expansion | long | market | 3,978 | 33 | -0.12 | -0.00 | 0.06 | 0.938 | no edge in training |
| consecutive_expansion | short | market | 3,978 | 28 | -0.23 | -0.05 | 0.06 | 1.000 | no edge in training |
| consecutive_fvg | long | limit | 2,024 | 34 | -0.06 | +0.10 | 0.08 | 0.036 | candidate |
| consecutive_fvg | short | limit | 1,937 | 31 | -0.15 | +0.01 | 0.08 | 0.805 | no edge in training |
| crab | long | market | 5 | - | - | - | - | - | not enough trades |
| crab | short | market | 8 | - | - | - | - | - | not enough trades |
| creek_breakout | long | market | 138 | 36 | -0.03 | +0.05 | 0.28 | 0.692 | no edge in training |
| cup_and_handle | long | market | 27 | - | - | - | - | - | not enough trades |
| cypher | long | market | 29 | - | - | - | - | - | not enough trades |
| cypher | short | market | 35 | - | - | - | - | - | not enough trades |
| dark_cloud_cover | short | market | 1,941 | 27 | -0.21 | +0.03 | 0.07 | 0.640 | no edge in training |
| deep_crab | long | market | 19 | - | - | - | - | - | not enough trades |
| deep_crab | short | market | 15 | - | - | - | - | - | not enough trades |
| deep_retracement | long | market | 315 | 39 | +0.08 | +0.22 | 0.19 | 0.084 | candidate |
| deep_retracement | short | market | 388 | 29 | -0.17 | +0.01 | 0.17 | 0.755 | no edge in training |
| demand_to_supply_flip | short | limit | 1,024 | 27 | -0.18 | +0.09 | 0.11 | 0.254 | no edge in training |
| demand_zone | long | limit | 1,060 | 26 | -0.22 | +0.06 | 0.10 | 0.448 | no edge in training |
| desc_triangle_breakdown | short | market | 450 | 33 | -0.17 | -0.09 | 0.16 | 1.000 | no edge in training |
| displacement | long | market | 1,872 | 42 | +0.06 | +0.11 | 0.08 | 0.022 | candidate |
| displacement | short | market | 1,834 | 35 | -0.08 | -0.02 | 0.08 | 1.000 | no edge in training |
| displacement_imbalance | long | limit | 1,278 | 30 | -0.17 | +0.02 | 0.09 | 0.753 | no edge in training |
| displacement_imbalance | short | limit | 1,330 | 28 | -0.18 | +0.01 | 0.09 | 0.809 | no edge in training |
| double_bottom | long | market | 242 | 44 | -0.06 | -0.04 | 0.17 | 0.907 | no edge in training |
| double_top | short | market | 238 | 36 | -0.06 | -0.02 | 0.20 | 0.868 | no edge in training |
| dragonfly_doji | long | market | 1,216 | 25 | -0.28 | -0.03 | 0.10 | 1.000 | no edge in training |
| elliott_impulse | long | market | 390 | 36 | -0.05 | +0.05 | 0.15 | 0.590 | no edge in training |
| elliott_impulse | short | market | 482 | 33 | -0.08 | +0.07 | 0.15 | 0.483 | no edge in training |
| elliott_wave5 | long | market | 686 | 36 | -0.14 | -0.08 | 0.11 | 1.000 | no edge in training |
| elliott_wave5 | short | market | 619 | 39 | -0.01 | +0.07 | 0.11 | 0.401 | no edge in training |
| ema_bounce | long | market | 7,583 | 22 | -0.35 | -0.01 | 0.06 | 1.000 | no edge in training |
| ema_bounce | short | market | 5,670 | 19 | -0.47 | -0.03 | 0.04 | 1.000 | no edge in training |
| engulfing_bear | short | market | 11,718 | 26 | -0.26 | -0.01 | 0.04 | 1.000 | no edge in training |
| engulfing_bull | long | market | 12,441 | 29 | -0.17 | +0.00 | 0.04 | 0.834 | no edge in training |
| equal_highs | short | market | 2,125 | 25 | -0.25 | +0.02 | 0.07 | 0.696 | no edge in training |
| equal_highs+displacement | short | market | 503 | 35 | -0.07 | +0.01 | 0.15 | 0.862 | no edge in training |
| equal_lows | long | market | 2,076 | 25 | -0.27 | -0.02 | 0.07 | 1.000 | no edge in training |
| equal_lows+displacement | long | market | 526 | 41 | +0.03 | +0.08 | 0.14 | 0.506 | no edge in training |
| evening_doji_star | short | market | 1,094 | 27 | -0.22 | +0.03 | 0.10 | 0.684 | no edge in training |
| evening_star | short | market | 2,827 | 28 | -0.21 | +0.01 | 0.06 | 0.766 | no edge in training |
| exhaustion_sequence | long | market | 240 | 40 | +0.07 | +0.12 | 0.23 | 0.539 | no edge in training |
| exhaustion_sequence | short | market | 196 | 37 | +0.00 | +0.09 | 0.23 | 0.612 | no edge in training |
| external_bos | long | market | 2,354 | 40 | -0.00 | +0.03 | 0.07 | 0.539 | no edge in training |
| external_bos | short | market | 1,878 | 37 | -0.04 | +0.03 | 0.08 | 0.660 | no edge in training |
| external_sweep | long | market | 4,985 | 27 | -0.22 | +0.04 | 0.05 | 0.298 | no edge in training |
| external_sweep | short | market | 4,853 | 21 | -0.41 | -0.03 | 0.05 | 1.000 | no edge in training |
| failed_bos | long | market | 3,632 | 31 | -0.14 | +0.00 | 0.06 | 0.862 | no edge in training |
| failed_bos | short | market | 3,879 | 29 | -0.17 | +0.06 | 0.05 | 0.088 | candidate |
| failed_breakout | long | market | 2,398 | 35 | -0.07 | +0.03 | 0.08 | 0.592 | no edge in training |
| failed_breakout | short | market | 2,039 | 32 | -0.11 | +0.04 | 0.08 | 0.500 | no edge in training |
| failed_breakout+reclaim | long | market | 313 | 42 | -0.02 | +0.03 | 0.16 | 0.797 | no edge in training |
| failed_breakout+reclaim | short | market | 256 | 32 | -0.12 | -0.05 | 0.19 | 1.000 | no edge in training |
| failed_momentum_breakout | long | market | 2,856 | 34 | -0.08 | +0.05 | 0.06 | 0.265 | no edge in training |
| failed_momentum_breakout | short | market | 3,397 | 28 | -0.20 | +0.02 | 0.05 | 0.604 | no edge in training |
| failed_sweep | long | market | 3,728 | 35 | -0.09 | -0.01 | 0.07 | 0.940 | no edge in training |
| failed_sweep | short | market | 3,502 | 30 | -0.19 | -0.06 | 0.07 | 1.000 | no edge in training |
| failed_swing | long | market | 6,677 | 39 | -0.04 | +0.02 | 0.05 | 0.609 | no edge in training |
| failed_swing | short | market | 5,874 | 34 | -0.12 | -0.02 | 0.06 | 1.000 | no edge in training |
| falling_channel_break | long | market | 859 | 38 | -0.05 | +0.02 | 0.11 | 0.687 | no edge in training |
| falling_three_methods | short | market | 134 | 36 | -0.08 | -0.01 | 0.28 | 0.929 | no edge in training |
| falling_wedge_breakout | long | market | 831 | 34 | -0.09 | +0.02 | 0.11 | 0.713 | no edge in training |
| fib_extension | long | market | 1,343 | 47 | +0.05 | +0.06 | 0.09 | 0.317 | no edge in training |
| fib_extension | short | market | 1,156 | 42 | -0.02 | +0.03 | 0.10 | 0.675 | no edge in training |
| fib_retracement | long | market | 840 | 32 | -0.11 | +0.05 | 0.12 | 0.507 | no edge in training |
| fib_retracement | short | market | 814 | 27 | -0.23 | -0.00 | 0.12 | 0.815 | no edge in training |
| fvg | long | limit | 10,484 | 21 | -0.40 | -0.03 | 0.03 | 1.000 | no edge in training |
| fvg | short | limit | 10,386 | 20 | -0.42 | -0.04 | 0.03 | 1.000 | no edge in training |
| fvg_after_sweep | long | limit | 1,462 | 21 | -0.39 | -0.02 | 0.08 | 1.000 | no edge in training |
| fvg_after_sweep | short | limit | 1,393 | 22 | -0.37 | +0.01 | 0.08 | 0.849 | no edge in training |
| fvg_continuation | long | limit | 7,292 | 21 | -0.39 | -0.03 | 0.04 | 1.000 | no edge in training |
| fvg_continuation | short | limit | 7,162 | 21 | -0.38 | -0.02 | 0.04 | 1.000 | no edge in training |
| fvg_formation | long | market | 12,344 | 30 | -0.16 | -0.00 | 0.04 | 0.939 | no edge in training |
| fvg_formation | short | market | 11,529 | 26 | -0.25 | -0.05 | 0.04 | 1.000 | no edge in training |
| fvg_reversal | long | limit | 3,192 | 19 | -0.43 | -0.04 | 0.05 | 1.000 | no edge in training |
| fvg_reversal | short | limit | 3,224 | 17 | -0.50 | -0.07 | 0.05 | 1.000 | no edge in training |
| fvg_with_bos | long | limit | 2,241 | 23 | -0.34 | +0.03 | 0.06 | 0.539 | no edge in training |
| fvg_with_bos | short | limit | 2,134 | 25 | -0.27 | +0.07 | 0.07 | 0.124 | no edge in training |
| fvg_with_choch | long | limit | 2,241 | 23 | -0.33 | +0.02 | 0.06 | 0.640 | no edge in training |
| fvg_with_choch | short | limit | 2,415 | 22 | -0.34 | +0.03 | 0.06 | 0.539 | no edge in training |
| gap_continuation | long | market | 697 | 16 | -0.57 | -0.12 | 0.10 | 1.000 | no edge in training |
| gap_continuation | short | market | 578 | 7 | -0.97 | -0.22 | 0.08 | 1.000 | no edge in training |
| gap_fade | long | market | 695 | 22 | -0.39 | +0.05 | 0.12 | 0.597 | no edge in training |
| gap_fade | short | market | 718 | 10 | -0.81 | -0.12 | 0.09 | 1.000 | no edge in training |
| gartley | long | market | 17 | - | - | - | - | - | not enough trades |
| gartley | short | market | 25 | - | - | - | - | - | not enough trades |
| golden_pullback | long | market | 354 | 30 | -0.15 | -0.02 | 0.18 | 0.868 | no edge in training |
| golden_pullback | short | market | 313 | 33 | -0.07 | +0.12 | 0.19 | 0.401 | no edge in training |
| grab_reversal | long | market | 3,076 | 34 | -0.09 | +0.00 | 0.07 | 0.862 | no edge in training |
| grab_reversal | short | market | 2,563 | 31 | -0.13 | +0.01 | 0.07 | 0.769 | no edge in training |
| grab_reversal+order_block | long | limit | 899 | 31 | -0.10 | +0.08 | 0.12 | 0.335 | no edge in training |
| grab_reversal+order_block | short | limit | 858 | 30 | -0.13 | +0.09 | 0.11 | 0.277 | no edge in training |
| gravestone_doji | short | market | 868 | 24 | -0.32 | -0.03 | 0.12 | 1.000 | no edge in training |
| hammer | long | market | 4,335 | 28 | -0.17 | +0.07 | 0.05 | 0.043 | candidate |
| hanging_man | short | market | 4,384 | 13 | -0.65 | -0.11 | 0.04 | 1.000 | no edge in training |
| harami_bear | short | market | 6,622 | 24 | -0.31 | +0.02 | 0.04 | 0.616 | no edge in training |
| harami_bull | long | market | 6,392 | 27 | -0.20 | +0.03 | 0.05 | 0.413 | no edge in training |
| head_and_shoulders | short | market | 54 | - | - | - | - | - | not enough trades |
| higher_low | long | market | 9,758 | 30 | -0.16 | -0.00 | 0.04 | 0.937 | no edge in training |
| higher_low+bos | long | market | 2,475 | 37 | -0.02 | +0.04 | 0.08 | 0.529 | no edge in training |
| ice_breakdown | short | market | 138 | 33 | -0.09 | -0.01 | 0.28 | 0.847 | no edge in training |
| inside_bar_bear | short | market | 16,218 | 22 | -0.35 | -0.00 | 0.03 | 1.000 | no edge in training |
| inside_bar_bull | long | market | 15,816 | 27 | -0.23 | +0.01 | 0.03 | 0.728 | no edge in training |
| inside_compression+nr_breakout | long | market | 1,055 | 26 | -0.25 | -0.06 | 0.11 | 1.000 | no edge in training |
| inside_compression+nr_breakout | short | market | 971 | 22 | -0.40 | -0.08 | 0.10 | 1.000 | no edge in training |
| internal_bos | long | market | 4,583 | 36 | -0.05 | +0.02 | 0.06 | 0.705 | no edge in training |
| internal_bos | short | market | 3,791 | 33 | -0.10 | +0.00 | 0.06 | 0.862 | no edge in training |
| internal_sweep | long | market | 12,400 | 26 | -0.25 | +0.04 | 0.04 | 0.192 | no edge in training |
| internal_sweep | short | market | 11,822 | 20 | -0.43 | -0.03 | 0.03 | 1.000 | no edge in training |
| inverse_cup_and_handle | short | market | 58 | - | - | - | - | - | not enough trades |
| inverse_fvg | long | limit | 8,257 | 20 | -0.42 | -0.04 | 0.03 | 1.000 | no edge in training |
| inverse_fvg | short | limit | 9,029 | 18 | -0.46 | -0.08 | 0.03 | 1.000 | no edge in training |
| inverse_head_and_shoulders | long | market | 70 | - | - | - | - | - | not enough trades |
| inverted_hammer | long | market | 3,037 | 21 | -0.39 | +0.02 | 0.06 | 0.585 | no edge in training |
| kicker | long | market | 28 | - | - | - | - | - | not enough trades |
| kicker | short | market | 6 | - | - | - | - | - | not enough trades |
| last_point_of_supply | short | market | 62 | - | - | - | - | - | not enough trades |
| last_point_of_support | long | market | 92 | - | - | - | - | - | not enough trades |
| liquidity_sweep | long | market | 8,509 | 27 | -0.23 | +0.05 | 0.04 | 0.119 | no edge in training |
| liquidity_sweep | short | market | 8,112 | 20 | -0.42 | -0.03 | 0.04 | 1.000 | no edge in training |
| london_high_sweep | short | market | 1,919 | 24 | -0.32 | +0.00 | 0.07 | 0.862 | no edge in training |
| london_high_sweep+choch | short | market | 832 | 34 | -0.14 | -0.04 | 0.10 | 1.000 | no edge in training |
| london_low_sweep | long | market | 1,911 | 29 | -0.18 | +0.06 | 0.08 | 0.324 | no edge in training |
| london_low_sweep+choch | long | market | 871 | 42 | -0.03 | +0.02 | 0.09 | 0.783 | no edge in training |
| lower_high | short | market | 9,141 | 27 | -0.25 | +0.01 | 0.04 | 0.727 | no edge in training |
| lower_high+bos | short | market | 2,033 | 34 | -0.10 | -0.02 | 0.08 | 1.000 | no edge in training |
| market_structure_shift | long | market | 1,340 | 38 | -0.04 | +0.02 | 0.09 | 0.729 | no edge in training |
| market_structure_shift | short | market | 1,219 | 37 | -0.04 | +0.05 | 0.09 | 0.539 | no edge in training |
| marubozu_bear | short | market | 1,477 | 30 | -0.16 | -0.05 | 0.09 | 1.000 | no edge in training |
| marubozu_bull | long | market | 1,409 | 32 | -0.10 | -0.02 | 0.09 | 1.000 | no edge in training |
| momentum_continuation | long | market | 2,775 | 45 | -0.03 | -0.01 | 0.07 | 1.000 | no edge in training |
| momentum_continuation | short | market | 2,543 | 41 | -0.04 | +0.02 | 0.08 | 0.674 | no edge in training |
| momentum_exhaustion | long | market | 410 | 34 | -0.19 | -0.13 | 0.16 | 1.000 | no edge in training |
| momentum_exhaustion | short | market | 447 | 28 | -0.29 | -0.14 | 0.15 | 1.000 | no edge in training |
| morning_doji_star | long | market | 1,060 | 29 | -0.19 | -0.03 | 0.10 | 1.000 | no edge in training |
| morning_star | long | market | 2,818 | 29 | -0.17 | -0.02 | 0.07 | 1.000 | no edge in training |
| multi_touch_rejection | long | market | 1,399 | 30 | -0.12 | +0.05 | 0.09 | 0.539 | no edge in training |
| multi_touch_rejection | short | market | 1,084 | 24 | -0.30 | -0.07 | 0.10 | 1.000 | no edge in training |
| multiple_sweeps | long | market | 2,090 | 26 | -0.24 | +0.04 | 0.09 | 0.539 | no edge in training |
| multiple_sweeps | short | market | 1,869 | 19 | -0.48 | -0.05 | 0.07 | 1.000 | no edge in training |
| nr_breakout | long | market | 8,491 | 27 | -0.21 | -0.03 | 0.04 | 1.000 | no edge in training |
| nr_breakout | short | market | 7,999 | 23 | -0.35 | -0.07 | 0.04 | 1.000 | no edge in training |
| order_block | long | limit | 4,375 | 29 | -0.17 | +0.03 | 0.05 | 0.546 | no edge in training |
| order_block | short | limit | 4,386 | 29 | -0.16 | +0.06 | 0.05 | 0.080 | candidate |
| order_block_bos | long | limit | 2,275 | 28 | -0.19 | +0.02 | 0.07 | 0.729 | no edge in training |
| order_block_bos | short | limit | 2,012 | 28 | -0.17 | +0.04 | 0.08 | 0.506 | no edge in training |
| order_block_choch | long | limit | 2,100 | 29 | -0.15 | +0.03 | 0.08 | 0.550 | no edge in training |
| order_block_choch | short | limit | 2,374 | 29 | -0.15 | +0.07 | 0.07 | 0.119 | no edge in training |
| order_block_fvg | long | limit | 1,498 | 27 | -0.20 | +0.00 | 0.09 | 0.887 | no edge in training |
| order_block_fvg | short | limit | 1,549 | 30 | -0.11 | +0.09 | 0.09 | 0.114 | no edge in training |
| order_block_sweep | long | limit | 776 | 35 | -0.03 | +0.10 | 0.13 | 0.271 | no edge in training |
| order_block_sweep | short | limit | 922 | 33 | -0.07 | +0.13 | 0.11 | 0.051 | candidate |
| outside_bar_bear | short | market | 9,246 | 23 | -0.34 | -0.02 | 0.04 | 1.000 | no edge in training |
| outside_bar_bull | long | market | 10,118 | 27 | -0.22 | -0.01 | 0.04 | 1.000 | no edge in training |
| pd_high_sweep | short | market | 925 | 22 | -0.37 | +0.03 | 0.10 | 0.660 | no edge in training |
| pd_low_sweep | long | market | 860 | 27 | -0.21 | +0.05 | 0.11 | 0.592 | no edge in training |
| pdh_sweep+choch | short | market | 219 | 32 | -0.17 | -0.08 | 0.19 | 1.000 | no edge in training |
| pdh_sweep+engulfing | short | market | 189 | 31 | -0.22 | -0.01 | 0.23 | 0.923 | no edge in training |
| pdh_sweep+fvg | short | limit | 398 | 22 | -0.39 | -0.00 | 0.17 | 0.891 | no edge in training |
| pdl_sweep+choch | long | market | 214 | 47 | +0.09 | +0.14 | 0.19 | 0.312 | no edge in training |
| pdl_sweep+engulfing | long | market | 245 | 36 | -0.07 | +0.09 | 0.21 | 0.591 | no edge in training |
| pdl_sweep+fvg | long | limit | 425 | 23 | -0.35 | +0.00 | 0.15 | 0.885 | no edge in training |
| piercing | long | market | 1,990 | 29 | -0.16 | +0.02 | 0.08 | 0.753 | no edge in training |
| pin_bar_bear | short | market | 7,307 | 23 | -0.33 | -0.03 | 0.04 | 1.000 | no edge in training |
| pin_bar_bull | long | market | 9,934 | 26 | -0.24 | +0.01 | 0.04 | 0.707 | no edge in training |
| pm_high_sweep | short | market | 43 | - | - | - | - | - | not enough trades |
| pm_low_sweep | long | market | 33 | - | - | - | - | - | not enough trades |
| preliminary_supply | short | market | 888 | 29 | -0.15 | +0.09 | 0.11 | 0.270 | no edge in training |
| preliminary_support | long | market | 831 | 29 | -0.16 | +0.01 | 0.11 | 0.722 | no edge in training |
| pw_high_sweep | short | market | 185 | 22 | -0.40 | -0.03 | 0.21 | 0.985 | no edge in training |
| pw_low_sweep | long | market | 159 | 24 | -0.32 | -0.10 | 0.24 | 1.000 | no edge in training |
| range_boundary_rejection | long | market | 4,102 | 29 | -0.16 | +0.07 | 0.06 | 0.039 | candidate |
| range_boundary_rejection | short | market | 5,079 | 22 | -0.36 | +0.00 | 0.04 | 0.885 | no edge in training |
| range_midpoint_cross | long | market | 6,064 | 32 | -0.13 | -0.00 | 0.05 | 0.893 | no edge in training |
| range_midpoint_cross | short | market | 6,004 | 28 | -0.23 | -0.01 | 0.05 | 1.000 | no edge in training |
| range_to_trend | long | market | 2,188 | 44 | +0.00 | +0.05 | 0.08 | 0.443 | no edge in training |
| range_to_trend | short | market | 1,721 | 39 | -0.04 | +0.04 | 0.09 | 0.567 | no edge in training |
| reclaimed_order_block | long | market | 2,213 | 41 | -0.01 | +0.03 | 0.07 | 0.550 | no edge in training |
| reclaimed_order_block | short | market | 1,935 | 36 | -0.11 | -0.03 | 0.07 | 1.000 | no edge in training |
| rectangle_breakout | long | market | 331 | 37 | -0.15 | -0.13 | 0.15 | 1.000 | no edge in training |
| rectangle_breakout | short | market | 292 | 37 | -0.07 | +0.01 | 0.18 | 0.761 | no edge in training |
| rejection_bear | short | market | 6,375 | 25 | -0.28 | +0.02 | 0.04 | 0.638 | no edge in training |
| rejection_bear+bos | short | market | 706 | 40 | +0.02 | +0.09 | 0.12 | 0.298 | no edge in training |
| rejection_block | long | limit | 5,702 | 25 | -0.25 | +0.02 | 0.04 | 0.546 | no edge in training |
| rejection_block | short | limit | 5,135 | 24 | -0.30 | +0.02 | 0.05 | 0.639 | no edge in training |
| rejection_bull | long | market | 7,513 | 28 | -0.19 | +0.03 | 0.04 | 0.324 | no edge in training |
| rejection_bull+bos | long | market | 933 | 40 | +0.00 | +0.05 | 0.11 | 0.539 | no edge in training |
| resistance_rejection | short | market | 1,645 | 24 | -0.29 | -0.05 | 0.08 | 1.000 | no edge in training |
| resistance_rejection+engulfing | short | market | 279 | 29 | -0.18 | -0.01 | 0.19 | 0.929 | no edge in training |
| retest | long | market | 3,017 | 28 | -0.20 | +0.03 | 0.07 | 0.539 | no edge in training |
| retest | short | market | 3,030 | 24 | -0.30 | -0.00 | 0.06 | 0.938 | no edge in training |
| retest+momentum | long | market | 656 | 48 | +0.03 | +0.03 | 0.13 | 0.713 | no edge in training |
| retest+momentum | short | market | 650 | 41 | -0.05 | +0.02 | 0.13 | 0.805 | no edge in training |
| rising_channel_break | short | market | 859 | 36 | -0.02 | +0.11 | 0.11 | 0.150 | no edge in training |
| rising_three_methods | long | market | 174 | 41 | +0.05 | +0.14 | 0.25 | 0.472 | no edge in training |
| rising_wedge_breakdown | short | market | 1,086 | 30 | -0.14 | +0.04 | 0.10 | 0.523 | no edge in training |
| round100_reaction | long | market | 743 | 24 | -0.30 | -0.04 | 0.14 | 1.000 | no edge in training |
| round100_reaction | short | market | 703 | 25 | -0.25 | +0.07 | 0.14 | 0.539 | no edge in training |
| round10_reaction | long | market | 6,943 | 27 | -0.22 | +0.05 | 0.05 | 0.154 | no edge in training |
| round10_reaction | short | market | 6,305 | 25 | -0.27 | +0.04 | 0.05 | 0.265 | no edge in training |
| round50_reaction | long | market | 785 | 30 | -0.12 | +0.16 | 0.15 | 0.124 | no edge in training |
| round50_reaction | short | market | 674 | 24 | -0.31 | +0.04 | 0.13 | 0.708 | no edge in training |
| round_placebo_reaction | long | market | 10,080 | 26 | -0.24 | +0.04 | 0.04 | 0.249 | no edge in training |
| round_placebo_reaction | short | market | 9,075 | 23 | -0.33 | +0.01 | 0.04 | 0.708 | no edge in training |
| rounding_bottom | long | market | 133 | 44 | -0.03 | -0.01 | 0.21 | 0.851 | no edge in training |
| rounding_top | short | market | 224 | 45 | -0.01 | +0.05 | 0.16 | 0.596 | no edge in training |
| secondary_test | long | market | 156 | 33 | -0.04 | +0.16 | 0.27 | 0.415 | no edge in training |
| secondary_test | short | market | 181 | 30 | -0.12 | +0.18 | 0.25 | 0.321 | no edge in training |
| selling_climax | long | market | 1,116 | 28 | -0.19 | +0.01 | 0.10 | 0.735 | no edge in training |
| shark | long | market | 79 | - | - | - | - | - | not enough trades |
| shark | short | market | 52 | - | - | - | - | - | not enough trades |
| shooting_star | short | market | 3,460 | 23 | -0.32 | -0.02 | 0.05 | 1.000 | no edge in training |
| sign_of_strength | long | market | 268 | 40 | +0.06 | +0.13 | 0.20 | 0.401 | no edge in training |
| sign_of_weakness | short | market | 258 | 29 | -0.21 | -0.01 | 0.19 | 0.851 | no edge in training |
| spring | long | market | 328 | 20 | -0.43 | -0.07 | 0.16 | 0.979 | no edge in training |
| squeeze+bos | long | market | 403 | 36 | -0.08 | -0.04 | 0.15 | 1.000 | no edge in training |
| squeeze+bos | short | market | 372 | 42 | +0.07 | +0.14 | 0.17 | 0.249 | no edge in training |
| squeeze_release | long | market | 2,003 | 40 | -0.01 | +0.05 | 0.07 | 0.320 | no edge in training |
| squeeze_release | short | market | 1,852 | 36 | -0.07 | +0.04 | 0.07 | 0.506 | no edge in training |
| strong_bear_sequence | short | market | 148 | 41 | -0.01 | +0.03 | 0.23 | 0.819 | no edge in training |
| strong_bull_sequence | long | market | 208 | 45 | +0.04 | +0.07 | 0.17 | 0.591 | no edge in training |
| strong_demand | long | limit | 169 | 25 | -0.24 | +0.03 | 0.25 | 0.834 | no edge in training |
| strong_supply | short | limit | 197 | 24 | -0.29 | -0.01 | 0.24 | 0.929 | no edge in training |
| structural_reclaim | long | market | 1,113 | 38 | -0.07 | -0.02 | 0.09 | 1.000 | no edge in training |
| structural_reclaim | short | market | 1,183 | 35 | -0.09 | +0.01 | 0.09 | 0.844 | no edge in training |
| supply_to_demand_flip | long | limit | 1,023 | 25 | -0.24 | +0.01 | 0.10 | 0.862 | no edge in training |
| supply_zone | short | limit | 1,136 | 26 | -0.24 | +0.02 | 0.10 | 0.786 | no edge in training |
| support_rejection | long | market | 2,034 | 29 | -0.16 | +0.02 | 0.07 | 0.684 | no edge in training |
| support_rejection+engulfing | long | market | 365 | 36 | +0.02 | +0.17 | 0.18 | 0.169 | no edge in training |
| sweep+bos | long | market | 653 | 43 | +0.05 | +0.10 | 0.13 | 0.290 | no edge in training |
| sweep+bos | short | market | 492 | 41 | +0.04 | +0.13 | 0.15 | 0.230 | no edge in training |
| sweep+choch | long | market | 1,184 | 40 | -0.04 | -0.00 | 0.08 | 0.924 | no edge in training |
| sweep+choch | short | market | 1,159 | 34 | -0.14 | -0.06 | 0.09 | 1.000 | no edge in training |
| sweep+double_bottom | long | market | 159 | 48 | +0.02 | +0.05 | 0.21 | 0.687 | no edge in training |
| sweep+double_top | short | market | 158 | 37 | -0.06 | -0.03 | 0.24 | 0.880 | no edge in training |
| sweep+mss | long | market | 537 | 40 | +0.01 | +0.06 | 0.13 | 0.558 | no edge in training |
| sweep+mss | short | market | 494 | 43 | +0.08 | +0.15 | 0.14 | 0.119 | no edge in training |
| sweep+order_block | long | limit | 1,217 | 31 | -0.11 | +0.07 | 0.10 | 0.320 | no edge in training |
| sweep+order_block | short | limit | 1,206 | 30 | -0.14 | +0.08 | 0.09 | 0.208 | no edge in training |
| sweep_reclaim | long | market | 1,862 | 30 | -0.15 | +0.02 | 0.08 | 0.690 | no edge in training |
| sweep_reclaim | short | market | 1,975 | 26 | -0.24 | +0.03 | 0.07 | 0.562 | no edge in training |
| sweep_to_bos | long | market | 2,332 | 42 | -0.01 | +0.04 | 0.08 | 0.539 | no edge in training |
| sweep_to_bos | short | market | 2,036 | 36 | -0.09 | -0.00 | 0.08 | 0.929 | no edge in training |
| swing_failure | long | market | 4,841 | 26 | -0.25 | +0.04 | 0.05 | 0.312 | no edge in training |
| swing_failure | short | market | 4,749 | 20 | -0.44 | -0.03 | 0.04 | 1.000 | no edge in training |
| swing_failure+choch | long | market | 876 | 39 | -0.06 | -0.02 | 0.10 | 1.000 | no edge in training |
| swing_failure+choch | short | market | 866 | 34 | -0.15 | -0.07 | 0.10 | 1.000 | no edge in training |
| sym_triangle_breakout | long | market | 881 | 34 | -0.06 | +0.05 | 0.12 | 0.516 | no edge in training |
| sym_triangle_breakout | short | market | 827 | 31 | -0.12 | +0.02 | 0.12 | 0.713 | no edge in training |
| three_bar_continuation | long | market | 2,575 | 32 | -0.12 | -0.02 | 0.07 | 1.000 | no edge in training |
| three_bar_continuation | short | market | 2,271 | 28 | -0.23 | -0.08 | 0.07 | 1.000 | no edge in training |
| three_bar_reversal | long | market | 13,474 | 31 | -0.13 | -0.01 | 0.04 | 1.000 | no edge in training |
| three_bar_reversal | short | market | 12,351 | 29 | -0.19 | -0.02 | 0.04 | 1.000 | no edge in training |
| three_black_crows | short | market | 224 | 35 | -0.10 | -0.03 | 0.23 | 0.987 | no edge in training |
| three_drives | long | market | 13 | - | - | - | - | - | not enough trades |
| three_drives | short | market | 23 | - | - | - | - | - | not enough trades |
| three_inside_down | short | market | 1,221 | 29 | -0.15 | -0.01 | 0.09 | 0.929 | no edge in training |
| three_inside_up | long | market | 1,191 | 31 | -0.12 | -0.01 | 0.10 | 0.949 | no edge in training |
| three_outside_down | short | market | 5,162 | 30 | -0.15 | -0.00 | 0.05 | 0.938 | no edge in training |
| three_outside_up | long | market | 5,577 | 32 | -0.11 | +0.00 | 0.05 | 0.888 | no edge in training |
| three_white_soldiers | long | market | 308 | 36 | -0.14 | -0.09 | 0.17 | 1.000 | no edge in training |
| triple_bottom | long | market | 47 | - | - | - | - | - | not enough trades |
| triple_top | short | market | 63 | - | - | - | - | - | not enough trades |
| tweezer_bottom | long | market | 4,351 | 26 | -0.25 | +0.03 | 0.05 | 0.539 | no edge in training |
| tweezer_top | short | market | 5,055 | 18 | -0.48 | -0.03 | 0.04 | 1.000 | no edge in training |
| upthrust | short | market | 304 | 10 | -0.75 | -0.14 | 0.12 | 1.000 | no edge in training |
| wide_range | long | market | 4,759 | 38 | +0.00 | +0.06 | 0.06 | 0.126 | no edge in training |
| wide_range | short | market | 4,623 | 35 | -0.06 | +0.01 | 0.06 | 0.744 | no edge in training |
| wide_range_reversal | long | market | 2,097 | 37 | -0.01 | +0.05 | 0.08 | 0.378 | no edge in training |
| wide_range_reversal | short | market | 1,937 | 34 | -0.07 | +0.02 | 0.08 | 0.757 | no edge in training |

#### H1

| Pattern | Dir | Entry | Trades | Win % | Mean R | Edge | Smallest detectable | q | Status |
|---|---|---|---|---|---|---|---|---|---|
| BOS | long | market | 1,740 | 39 | +0.00 | +0.01 | 0.09 | 0.853 | no edge in training |
| BOS | short | market | 1,372 | 35 | -0.11 | -0.05 | 0.10 | 1.000 | no edge in training |
| BOS|intraday:bias | long | market | 1,259 | 40 | +0.01 | +0.01 | 0.11 | 0.849 | no edge in training |
| BOS|intraday:bias | short | market | 910 | 35 | -0.11 | -0.05 | 0.12 | 1.000 | no edge in training |
| BOS|intraday:bias+context | long | market | 684 | 37 | -0.04 | -0.05 | 0.14 | 1.000 | no edge in training |
| BOS|intraday:bias+context | short | market | 325 | 33 | -0.16 | -0.16 | 0.19 | 1.000 | no edge in training |
| BOS|intraday:counter | long | market | 481 | 37 | -0.02 | +0.00 | 0.17 | 0.887 | no edge in training |
| BOS|intraday:counter | short | market | 462 | 34 | -0.10 | -0.03 | 0.16 | 1.000 | no edge in training |
| BOS|intraday:full | long | market | 569 | 36 | -0.05 | -0.08 | 0.15 | 1.000 | no edge in training |
| BOS|intraday:full | short | market | 285 | 33 | -0.15 | -0.15 | 0.20 | 1.000 | no edge in training |
| CHoCH | long | market | 1,588 | 43 | +0.03 | +0.04 | 0.08 | 0.474 | no edge in training |
| CHoCH | short | market | 1,581 | 35 | -0.10 | -0.02 | 0.08 | 1.000 | no edge in training |
| CHoCH|intraday:bias | long | market | 654 | 42 | +0.03 | +0.02 | 0.12 | 0.798 | no edge in training |
| CHoCH|intraday:bias | short | market | 594 | 38 | -0.04 | +0.02 | 0.13 | 0.788 | no edge in training |
| CHoCH|intraday:bias+context | long | market | 338 | 46 | +0.11 | +0.08 | 0.16 | 0.539 | no edge in training |
| CHoCH|intraday:bias+context | short | market | 190 | 37 | -0.04 | -0.03 | 0.23 | 0.987 | no edge in training |
| CHoCH|intraday:counter | long | market | 934 | 43 | +0.04 | +0.06 | 0.10 | 0.448 | no edge in training |
| CHoCH|intraday:counter | short | market | 987 | 34 | -0.13 | -0.05 | 0.10 | 1.000 | no edge in training |
| CHoCH|intraday:full | long | market | 285 | 46 | +0.10 | +0.07 | 0.18 | 0.625 | no edge in training |
| CHoCH|intraday:full | short | market | 157 | 36 | -0.08 | -0.08 | 0.24 | 1.000 | no edge in training |
| abcd | long | market | 124 | 40 | +0.05 | +0.10 | 0.30 | 0.585 | no edge in training |
| abcd | short | market | 146 | 34 | -0.08 | +0.04 | 0.25 | 0.713 | no edge in training |
| asc_triangle_breakout | long | market | 271 | 44 | +0.10 | +0.11 | 0.20 | 0.424 | no edge in training |
| asia_high_sweep | short | market | 1,767 | 26 | -0.24 | +0.03 | 0.08 | 0.616 | no edge in training |
| asia_high_sweep+bos | short | market | 214 | 43 | +0.03 | +0.09 | 0.22 | 0.600 | no edge in training |
| asia_low_sweep | long | market | 1,735 | 28 | -0.17 | +0.05 | 0.08 | 0.474 | no edge in training |
| asia_low_sweep+bos | long | market | 286 | 41 | +0.03 | +0.01 | 0.19 | 0.862 | no edge in training |
| atr_expansion | long | market | 224 | 48 | +0.14 | +0.16 | 0.22 | 0.333 | no edge in training |
| atr_expansion | short | market | 235 | 36 | -0.08 | +0.02 | 0.20 | 0.834 | no edge in training |
| atr_expansion+bos | long | market | 37 | - | - | - | - | - | not enough trades |
| atr_expansion+bos | short | market | 44 | - | - | - | - | - | not enough trades |
| balanced_price_range | long | limit | 1,131 | 21 | -0.36 | -0.05 | 0.09 | 1.000 | no edge in training |
| balanced_price_range | short | limit | 1,144 | 22 | -0.35 | -0.02 | 0.09 | 1.000 | no edge in training |
| bat | long | market | 8 | - | - | - | - | - | not enough trades |
| bat | short | market | 11 | - | - | - | - | - | not enough trades |
| bear_flag | short | market | 21 | - | - | - | - | - | not enough trades |
| bear_pennant | short | market | 46 | - | - | - | - | - | not enough trades |
| bos+displacement | long | market | 417 | 41 | +0.03 | +0.03 | 0.18 | 0.805 | no edge in training |
| bos+displacement | short | market | 380 | 40 | +0.03 | +0.07 | 0.19 | 0.603 | no edge in training |
| breaker+fvg | long | limit | 1,997 | 28 | -0.18 | +0.05 | 0.08 | 0.452 | no edge in training |
| breaker+fvg | short | limit | 1,936 | 25 | -0.27 | -0.03 | 0.07 | 1.000 | no edge in training |
| breaker_block | long | limit | 2,228 | 33 | -0.04 | +0.09 | 0.08 | 0.057 | candidate |
| breaker_block | short | limit | 2,369 | 30 | -0.14 | +0.04 | 0.08 | 0.539 | no edge in training |
| breaker_block|intraday:bias | long | limit | 1,405 | 34 | -0.03 | +0.09 | 0.10 | 0.164 | no edge in training |
| breaker_block|intraday:bias | short | limit | 1,423 | 31 | -0.09 | +0.07 | 0.11 | 0.354 | no edge in training |
| breaker_block|intraday:bias+context | long | limit | 680 | 33 | -0.05 | +0.06 | 0.14 | 0.591 | no edge in training |
| breaker_block|intraday:bias+context | short | limit | 425 | 31 | -0.11 | +0.03 | 0.21 | 0.809 | no edge in training |
| breaker_block|intraday:counter | long | limit | 823 | 32 | -0.06 | +0.09 | 0.13 | 0.320 | no edge in training |
| breaker_block|intraday:counter | short | limit | 946 | 27 | -0.20 | -0.02 | 0.11 | 0.985 | no edge in training |
| breaker_block|intraday:full | long | limit | 513 | 34 | -0.02 | +0.08 | 0.17 | 0.539 | no edge in training |
| breaker_block|intraday:full | short | limit | 314 | 30 | -0.13 | +0.00 | 0.23 | 0.887 | no edge in training |
| breakout | long | market | 3,623 | 34 | -0.05 | +0.05 | 0.07 | 0.335 | no edge in training |
| breakout | short | market | 3,590 | 29 | -0.17 | -0.02 | 0.07 | 1.000 | no edge in training |
| broadening_breakout | long | market | 76 | - | - | - | - | - | not enough trades |
| broadening_breakout | short | market | 65 | - | - | - | - | - | not enough trades |
| bull_flag | long | market | 31 | - | - | - | - | - | not enough trades |
| bull_pennant | long | market | 55 | - | - | - | - | - | not enough trades |
| butterfly | long | market | 3 | - | - | - | - | - | not enough trades |
| butterfly | short | market | 12 | - | - | - | - | - | not enough trades |
| buying_climax | short | market | 587 | 29 | -0.16 | +0.02 | 0.13 | 0.713 | no edge in training |
| channel_breakout | long | market | 108 | 45 | +0.07 | +0.04 | 0.27 | 0.713 | no edge in training |
| channel_breakout | short | market | 67 | - | - | - | - | - | not enough trades |
| choch+fvg | long | limit | 1,738 | 26 | -0.24 | -0.00 | 0.08 | 0.919 | no edge in training |
| choch+fvg | short | limit | 1,760 | 24 | -0.28 | -0.02 | 0.08 | 1.000 | no edge in training |
| climax_reversal | long | market | 151 | 37 | +0.02 | +0.05 | 0.28 | 0.789 | no edge in training |
| climax_reversal | short | market | 165 | 39 | +0.08 | +0.16 | 0.27 | 0.474 | no edge in training |
| compression+sweep | long | market | 477 | 30 | -0.14 | +0.05 | 0.17 | 0.656 | no edge in training |
| compression+sweep | short | market | 528 | 29 | -0.16 | +0.06 | 0.18 | 0.639 | no edge in training |
| compression_breakout | long | market | 119 | 42 | +0.12 | +0.12 | 0.33 | 0.626 | no edge in training |
| compression_breakout | short | market | 103 | 38 | +0.02 | +0.06 | 0.33 | 0.784 | no edge in training |
| consecutive_expansion | long | market | 1,988 | 35 | -0.04 | +0.02 | 0.09 | 0.727 | no edge in training |
| consecutive_expansion | short | market | 1,937 | 30 | -0.16 | -0.05 | 0.09 | 1.000 | no edge in training |
| consecutive_fvg | long | limit | 961 | 32 | -0.08 | +0.03 | 0.11 | 0.694 | no edge in training |
| consecutive_fvg | short | limit | 907 | 33 | -0.10 | +0.03 | 0.12 | 0.744 | no edge in training |
| crab | long | market | 3 | - | - | - | - | - | not enough trades |
| crab | short | market | 5 | - | - | - | - | - | not enough trades |
| creek_breakout | long | market | 80 | - | - | - | - | - | not enough trades |
| cup_and_handle | long | market | 22 | - | - | - | - | - | not enough trades |
| cypher | long | market | 18 | - | - | - | - | - | not enough trades |
| cypher | short | market | 21 | - | - | - | - | - | not enough trades |
| dark_cloud_cover | short | market | 865 | 28 | -0.17 | +0.00 | 0.11 | 0.888 | no edge in training |
| deep_crab | long | market | 6 | - | - | - | - | - | not enough trades |
| deep_crab | short | market | 9 | - | - | - | - | - | not enough trades |
| deep_retracement | long | market | 179 | 33 | -0.06 | +0.03 | 0.26 | 0.713 | no edge in training |
| deep_retracement | short | market | 188 | 25 | -0.29 | -0.10 | 0.21 | 0.992 | no edge in training |
| demand_to_supply_flip | short | limit | 505 | 28 | -0.17 | +0.01 | 0.15 | 0.860 | no edge in training |
| demand_zone | long | limit | 518 | 29 | -0.13 | +0.08 | 0.15 | 0.515 | no edge in training |
| demand_zone|intraday:bias | long | limit | 314 | 30 | -0.12 | +0.09 | 0.19 | 0.545 | no edge in training |
| demand_zone|intraday:bias+context | long | limit | 171 | 33 | -0.02 | +0.17 | 0.28 | 0.448 | no edge in training |
| demand_zone|intraday:counter | long | limit | 204 | 28 | -0.15 | +0.06 | 0.23 | 0.713 | no edge in training |
| demand_zone|intraday:full | long | limit | 149 | 30 | -0.12 | +0.06 | 0.29 | 0.748 | no edge in training |
| desc_triangle_breakdown | short | market | 226 | 37 | -0.04 | +0.05 | 0.22 | 0.689 | no edge in training |
| displacement | long | market | 990 | 42 | +0.06 | +0.06 | 0.11 | 0.474 | no edge in training |
| displacement | short | market | 954 | 40 | +0.03 | +0.09 | 0.12 | 0.325 | no edge in training |
| displacement_imbalance | long | limit | 662 | 32 | -0.10 | +0.01 | 0.13 | 0.853 | no edge in training |
| displacement_imbalance | short | limit | 673 | 34 | -0.02 | +0.14 | 0.13 | 0.092 | candidate |
| double_bottom | long | market | 128 | 46 | +0.09 | +0.06 | 0.26 | 0.687 | no edge in training |
| double_top | short | market | 125 | 36 | -0.16 | -0.11 | 0.27 | 0.979 | no edge in training |
| dragonfly_doji | long | market | 453 | 31 | -0.09 | +0.08 | 0.17 | 0.539 | no edge in training |
| elliott_impulse | long | market | 205 | 42 | +0.15 | +0.23 | 0.24 | 0.150 | no edge in training |
| elliott_impulse | short | market | 282 | 31 | -0.15 | +0.01 | 0.19 | 0.761 | no edge in training |
| elliott_wave5 | long | market | 392 | 41 | +0.02 | +0.01 | 0.15 | 0.735 | no edge in training |
| elliott_wave5 | short | market | 370 | 36 | -0.15 | -0.08 | 0.15 | 1.000 | no edge in training |
| ema_bounce | long | market | 3,086 | 25 | -0.28 | -0.04 | 0.08 | 1.000 | no edge in training |
| ema_bounce | short | market | 2,580 | 21 | -0.37 | -0.07 | 0.07 | 1.000 | no edge in training |
| engulfing_bear | short | market | 5,720 | 28 | -0.17 | -0.01 | 0.05 | 0.982 | no edge in training |
| engulfing_bear|intraday:bias | short | market | 2,666 | 29 | -0.17 | -0.02 | 0.07 | 1.000 | no edge in training |
| engulfing_bear|intraday:bias+context | short | market | 947 | 29 | -0.15 | -0.06 | 0.13 | 1.000 | no edge in training |
| engulfing_bear|intraday:counter | short | market | 3,054 | 28 | -0.18 | +0.00 | 0.07 | 0.862 | no edge in training |
| engulfing_bear|intraday:full | short | market | 345 | 30 | -0.13 | -0.09 | 0.20 | 1.000 | no edge in training |
| engulfing_bull | long | market | 6,023 | 30 | -0.12 | -0.00 | 0.05 | 0.929 | no edge in training |
| engulfing_bull|intraday:bias | long | market | 3,291 | 31 | -0.10 | +0.01 | 0.07 | 0.805 | no edge in training |
| engulfing_bull|intraday:bias+context | long | market | 1,762 | 31 | -0.08 | +0.01 | 0.09 | 0.820 | no edge in training |
| engulfing_bull|intraday:counter | long | market | 2,732 | 29 | -0.15 | -0.02 | 0.08 | 1.000 | no edge in training |
| engulfing_bull|intraday:full | long | market | 649 | 33 | -0.04 | +0.01 | 0.14 | 0.862 | no edge in training |
| equal_highs | short | market | 872 | 29 | -0.15 | +0.03 | 0.11 | 0.713 | no edge in training |
| equal_highs+displacement | short | market | 232 | 43 | +0.10 | +0.18 | 0.22 | 0.277 | no edge in training |
| equal_lows | long | market | 856 | 27 | -0.19 | -0.03 | 0.12 | 1.000 | no edge in training |
| equal_lows+displacement | long | market | 245 | 42 | +0.07 | +0.07 | 0.22 | 0.660 | no edge in training |
| evening_doji_star | short | market | 504 | 30 | -0.15 | +0.01 | 0.14 | 0.853 | no edge in training |
| evening_star | short | market | 1,299 | 28 | -0.21 | -0.05 | 0.10 | 1.000 | no edge in training |
| exhaustion_sequence | long | market | 124 | 39 | +0.03 | +0.05 | 0.30 | 0.805 | no edge in training |
| exhaustion_sequence | short | market | 107 | 42 | +0.23 | +0.33 | 0.35 | 0.165 | no edge in training |
| external_bos | long | market | 1,178 | 41 | -0.01 | -0.02 | 0.10 | 1.000 | no edge in training |
| external_bos | short | market | 921 | 35 | -0.13 | -0.08 | 0.11 | 1.000 | no edge in training |
| external_sweep | long | market | 2,224 | 30 | -0.14 | +0.04 | 0.08 | 0.529 | no edge in training |
| external_sweep | short | market | 2,148 | 26 | -0.25 | +0.02 | 0.08 | 0.766 | no edge in training |
| failed_bos | long | market | 1,718 | 36 | +0.01 | +0.08 | 0.08 | 0.138 | no edge in training |
| failed_bos | short | market | 1,851 | 29 | -0.16 | -0.00 | 0.08 | 0.929 | no edge in training |
| failed_breakout | long | market | 1,110 | 37 | +0.02 | +0.07 | 0.11 | 0.431 | no edge in training |
| failed_breakout | short | market | 942 | 32 | -0.11 | +0.01 | 0.12 | 0.845 | no edge in training |
| failed_breakout+reclaim | long | market | 148 | 45 | +0.02 | +0.01 | 0.25 | 0.862 | no edge in training |
| failed_breakout+reclaim | short | market | 131 | 45 | +0.09 | +0.16 | 0.28 | 0.474 | no edge in training |
| failed_breakout|intraday:bias | long | market | 477 | 39 | +0.09 | +0.14 | 0.18 | 0.282 | no edge in training |
| failed_breakout|intraday:bias | short | market | 439 | 33 | -0.06 | +0.05 | 0.18 | 0.684 | no edge in training |
| failed_breakout|intraday:bias+context | long | market | 237 | 45 | +0.27 | +0.29 | 0.28 | 0.126 | no edge in training |
| failed_breakout|intraday:bias+context | short | market | 141 | 34 | -0.08 | -0.02 | 0.33 | 0.929 | no edge in training |
| failed_breakout|intraday:counter | long | market | 633 | 36 | -0.03 | +0.02 | 0.15 | 0.845 | no edge in training |
| failed_breakout|intraday:counter | short | market | 503 | 30 | -0.15 | -0.02 | 0.16 | 0.987 | no edge in training |
| failed_breakout|intraday:full | long | market | 56 | - | - | - | - | - | not enough trades |
| failed_breakout|intraday:full | short | market | 44 | - | - | - | - | - | not enough trades |
| failed_momentum_breakout | long | market | 1,252 | 36 | +0.00 | +0.07 | 0.09 | 0.286 | no edge in training |
| failed_momentum_breakout | short | market | 1,556 | 32 | -0.10 | +0.07 | 0.08 | 0.237 | no edge in training |
| failed_sweep | long | market | 1,697 | 40 | +0.02 | +0.04 | 0.09 | 0.604 | no edge in training |
| failed_sweep | short | market | 1,620 | 36 | -0.05 | +0.05 | 0.10 | 0.529 | no edge in training |
| failed_swing | long | market | 3,242 | 42 | +0.04 | +0.04 | 0.08 | 0.526 | no edge in training |
| failed_swing | short | market | 2,828 | 36 | -0.09 | -0.02 | 0.08 | 1.000 | no edge in training |
| falling_channel_break | long | market | 388 | 40 | +0.05 | +0.08 | 0.16 | 0.470 | no edge in training |
| falling_three_methods | short | market | 77 | - | - | - | - | - | not enough trades |
| falling_wedge_breakout | long | market | 434 | 34 | -0.09 | -0.03 | 0.16 | 0.890 | no edge in training |
| fib_extension | long | market | 737 | 47 | +0.05 | +0.02 | 0.12 | 0.708 | no edge in training |
| fib_extension | short | market | 576 | 40 | -0.06 | -0.02 | 0.12 | 0.881 | no edge in training |
| fib_retracement | long | market | 456 | 31 | -0.11 | -0.00 | 0.16 | 0.815 | no edge in training |
| fib_retracement | short | market | 385 | 30 | -0.14 | +0.02 | 0.17 | 0.735 | no edge in training |
| fvg | long | limit | 5,194 | 25 | -0.27 | -0.01 | 0.05 | 1.000 | no edge in training |
| fvg | short | limit | 4,966 | 24 | -0.30 | -0.02 | 0.05 | 1.000 | no edge in training |
| fvg_after_sweep | long | limit | 694 | 28 | -0.18 | +0.08 | 0.12 | 0.387 | no edge in training |
| fvg_after_sweep | short | limit | 667 | 22 | -0.35 | -0.05 | 0.12 | 1.000 | no edge in training |
| fvg_continuation | long | limit | 3,690 | 25 | -0.27 | -0.01 | 0.05 | 1.000 | no edge in training |
| fvg_continuation | short | limit | 3,461 | 24 | -0.29 | -0.02 | 0.05 | 1.000 | no edge in training |
| fvg_formation | long | market | 6,035 | 31 | -0.11 | -0.00 | 0.05 | 0.938 | no edge in training |
| fvg_formation | short | market | 5,521 | 29 | -0.19 | -0.04 | 0.05 | 1.000 | no edge in training |
| fvg_reversal | long | limit | 1,504 | 24 | -0.29 | -0.01 | 0.08 | 0.965 | no edge in training |
| fvg_reversal | short | limit | 1,505 | 23 | -0.32 | -0.00 | 0.09 | 0.902 | no edge in training |
| fvg_with_bos | long | limit | 1,078 | 26 | -0.23 | +0.03 | 0.10 | 0.702 | no edge in training |
| fvg_with_bos | short | limit | 1,016 | 27 | -0.22 | +0.02 | 0.10 | 0.708 | no edge in training |
| fvg_with_choch | long | limit | 1,100 | 28 | -0.17 | +0.07 | 0.10 | 0.311 | no edge in training |
| fvg_with_choch | short | limit | 1,153 | 26 | -0.24 | +0.03 | 0.09 | 0.660 | no edge in training |
| fvg|intraday:bias | long | limit | 2,930 | 26 | -0.24 | +0.01 | 0.06 | 0.745 | no edge in training |
| fvg|intraday:bias | short | limit | 2,594 | 25 | -0.26 | +0.01 | 0.06 | 0.855 | no edge in training |
| fvg|intraday:bias+context | long | limit | 1,570 | 25 | -0.25 | +0.01 | 0.08 | 0.853 | no edge in training |
| fvg|intraday:bias+context | short | limit | 905 | 24 | -0.30 | -0.08 | 0.12 | 1.000 | no edge in training |
| fvg|intraday:counter | long | limit | 2,264 | 23 | -0.31 | -0.05 | 0.07 | 1.000 | no edge in training |
| fvg|intraday:counter | short | limit | 2,372 | 22 | -0.34 | -0.04 | 0.06 | 1.000 | no edge in training |
| fvg|intraday:full | long | limit | 774 | 25 | -0.25 | +0.02 | 0.11 | 0.805 | no edge in training |
| fvg|intraday:full | short | limit | 464 | 24 | -0.28 | -0.05 | 0.15 | 1.000 | no edge in training |
| gap_continuation | long | market | 172 | 25 | -0.27 | -0.08 | 0.23 | 1.000 | no edge in training |
| gap_continuation | short | market | 96 | - | - | - | - | - | not enough trades |
| gap_fade | long | market | 119 | 31 | -0.09 | +0.15 | 0.31 | 0.539 | no edge in training |
| gap_fade | short | market | 180 | 23 | -0.35 | -0.02 | 0.24 | 0.941 | no edge in training |
| gartley | long | market | 8 | - | - | - | - | - | not enough trades |
| gartley | short | market | 17 | - | - | - | - | - | not enough trades |
| golden_pullback | long | market | 155 | 28 | -0.25 | -0.16 | 0.25 | 1.000 | no edge in training |
| golden_pullback | short | market | 163 | 36 | +0.03 | +0.17 | 0.26 | 0.385 | no edge in training |
| grab_reversal | long | market | 1,319 | 36 | -0.02 | +0.03 | 0.11 | 0.729 | no edge in training |
| grab_reversal | short | market | 1,187 | 34 | -0.08 | +0.02 | 0.11 | 0.769 | no edge in training |
| grab_reversal+order_block | long | limit | 443 | 34 | -0.02 | +0.10 | 0.17 | 0.468 | no edge in training |
| grab_reversal+order_block | short | limit | 403 | 32 | -0.05 | +0.12 | 0.16 | 0.305 | no edge in training |
| grab_reversal|intraday:bias | long | market | 686 | 38 | +0.02 | +0.06 | 0.15 | 0.614 | no edge in training |
| grab_reversal|intraday:bias | short | market | 509 | 31 | -0.12 | -0.05 | 0.17 | 1.000 | no edge in training |
| grab_reversal|intraday:bias+context | long | market | 384 | 38 | -0.01 | +0.01 | 0.20 | 0.876 | no edge in training |
| grab_reversal|intraday:bias+context | short | market | 172 | 30 | -0.15 | -0.16 | 0.27 | 1.000 | no edge in training |
| grab_reversal|intraday:counter | long | market | 633 | 35 | -0.05 | -0.01 | 0.15 | 0.929 | no edge in training |
| grab_reversal|intraday:counter | short | market | 678 | 35 | -0.04 | +0.07 | 0.15 | 0.539 | no edge in training |
| grab_reversal|intraday:full | long | market | 214 | 40 | +0.01 | +0.01 | 0.26 | 0.876 | no edge in training |
| grab_reversal|intraday:full | short | market | 92 | - | - | - | - | - | not enough trades |
| gravestone_doji | short | market | 398 | 22 | -0.36 | -0.16 | 0.16 | 1.000 | no edge in training |
| hammer | long | market | 1,782 | 30 | -0.12 | +0.05 | 0.09 | 0.506 | no edge in training |
| hanging_man | short | market | 1,876 | 19 | -0.44 | -0.04 | 0.07 | 1.000 | no edge in training |
| harami_bear | short | market | 3,147 | 27 | -0.19 | +0.07 | 0.06 | 0.088 | candidate |
| harami_bull | long | market | 2,891 | 29 | -0.16 | +0.01 | 0.07 | 0.854 | no edge in training |
| head_and_shoulders | short | market | 31 | - | - | - | - | - | not enough trades |
| higher_low | long | market | 4,685 | 33 | -0.08 | +0.03 | 0.06 | 0.568 | no edge in training |
| higher_low+bos | long | market | 1,247 | 38 | -0.02 | -0.02 | 0.11 | 1.000 | no edge in training |
| ice_breakdown | short | market | 72 | - | - | - | - | - | not enough trades |
| inside_bar_bear | short | market | 8,162 | 25 | -0.25 | +0.01 | 0.04 | 0.640 | no edge in training |
| inside_bar_bull | long | market | 8,094 | 29 | -0.16 | +0.02 | 0.04 | 0.612 | no edge in training |
| inside_compression+nr_breakout | long | market | 574 | 24 | -0.29 | -0.13 | 0.14 | 1.000 | no edge in training |
| inside_compression+nr_breakout | short | market | 567 | 23 | -0.34 | -0.11 | 0.14 | 1.000 | no edge in training |
| internal_bos | long | market | 2,313 | 38 | +0.00 | +0.02 | 0.08 | 0.717 | no edge in training |
| internal_bos | short | market | 1,847 | 34 | -0.09 | -0.03 | 0.09 | 1.000 | no edge in training |
| internal_sweep | long | market | 5,652 | 29 | -0.16 | +0.05 | 0.05 | 0.261 | no edge in training |
| internal_sweep | short | market | 5,402 | 24 | -0.29 | -0.01 | 0.05 | 1.000 | no edge in training |
| inverse_cup_and_handle | short | market | 42 | - | - | - | - | - | not enough trades |
| inverse_fvg | long | limit | 3,958 | 24 | -0.29 | -0.02 | 0.05 | 1.000 | no edge in training |
| inverse_fvg | short | limit | 4,373 | 23 | -0.32 | -0.04 | 0.05 | 1.000 | no edge in training |
| inverse_head_and_shoulders | long | market | 52 | - | - | - | - | - | not enough trades |
| inverted_hammer | long | market | 1,460 | 23 | -0.31 | +0.01 | 0.08 | 0.799 | no edge in training |
| kicker | long | market | 26 | - | - | - | - | - | not enough trades |
| kicker | short | market | 8 | - | - | - | - | - | not enough trades |
| kmeans_c00 | long | market | 2,897 | 30 | -0.12 | +0.00 | 0.07 | 1.000 | no edge in training |
| kmeans_c00 | short | market | 2,897 | 28 | -0.15 | +0.00 | 0.06 | 1.000 | no edge in training |
| kmeans_c01 | long | market | 6,526 | 28 | -0.17 | -0.01 | 0.06 | 1.000 | no edge in training |
| kmeans_c01 | short | market | 6,526 | 28 | -0.18 | -0.01 | 0.05 | 1.000 | no edge in training |
| kmeans_c02 | long | market | 2,837 | 27 | -0.19 | -0.07 | 0.07 | 1.000 | no edge in training |
| kmeans_c02 | short | market | 2,837 | 29 | -0.14 | +0.02 | 0.07 | 1.000 | no edge in training |
| kmeans_c03 | long | market | 2,911 | 29 | -0.14 | -0.02 | 0.07 | 1.000 | no edge in training |
| kmeans_c03 | short | market | 2,911 | 28 | -0.16 | +0.01 | 0.07 | 1.000 | no edge in training |
| kmeans_c04 | long | market | 2,513 | 31 | -0.09 | +0.04 | 0.07 | 0.981 | no edge in training |
| kmeans_c04 | short | market | 2,513 | 28 | -0.18 | -0.03 | 0.07 | 1.000 | no edge in training |
| kmeans_c05 | long | market | 5,250 | 29 | -0.15 | +0.01 | 0.05 | 1.000 | no edge in training |
| kmeans_c05 | short | market | 5,250 | 28 | -0.15 | -0.00 | 0.06 | 1.000 | no edge in training |
| kmeans_c06 | long | market | 2,984 | 30 | -0.09 | +0.04 | 0.06 | 0.981 | no edge in training |
| kmeans_c06 | short | market | 2,984 | 27 | -0.19 | -0.05 | 0.06 | 1.000 | no edge in training |
| kmeans_c07 | long | market | 7,130 | 27 | -0.20 | -0.04 | 0.05 | 1.000 | no edge in training |
| kmeans_c07 | short | market | 7,130 | 28 | -0.16 | +0.01 | 0.05 | 1.000 | no edge in training |
| kmeans_c08 | long | market | 2,781 | 31 | -0.07 | +0.06 | 0.07 | 0.981 | no edge in training |
| kmeans_c08 | short | market | 2,781 | 27 | -0.20 | -0.07 | 0.07 | 1.000 | no edge in training |
| kmeans_c09 | long | market | 2,114 | 30 | -0.10 | +0.02 | 0.07 | 1.000 | no edge in training |
| kmeans_c09 | short | market | 2,114 | 26 | -0.22 | -0.07 | 0.07 | 1.000 | no edge in training |
| kmeans_c10 | long | market | 6,457 | 28 | -0.18 | -0.01 | 0.05 | 1.000 | no edge in training |
| kmeans_c10 | short | market | 6,457 | 27 | -0.19 | -0.02 | 0.05 | 1.000 | no edge in training |
| kmeans_c11 | long | market | 2,229 | 30 | -0.11 | +0.02 | 0.07 | 1.000 | no edge in training |
| kmeans_c11 | short | market | 2,229 | 27 | -0.20 | -0.07 | 0.07 | 1.000 | no edge in training |
| kmeans_c12 | long | market | 4,786 | 28 | -0.17 | -0.02 | 0.06 | 1.000 | no edge in training |
| kmeans_c12 | short | market | 4,786 | 29 | -0.12 | +0.02 | 0.06 | 1.000 | no edge in training |
| kmeans_c13 | long | market | 1,526 | 29 | -0.15 | -0.02 | 0.09 | 1.000 | no edge in training |
| kmeans_c13 | short | market | 1,526 | 26 | -0.24 | -0.07 | 0.08 | 1.000 | no edge in training |
| kmeans_c14 | long | market | 6,162 | 27 | -0.19 | -0.02 | 0.05 | 1.000 | no edge in training |
| kmeans_c14 | short | market | 6,162 | 29 | -0.15 | +0.01 | 0.05 | 1.000 | no edge in training |
| kmeans_c15 | long | market | 6,064 | 28 | -0.16 | -0.01 | 0.06 | 1.000 | no edge in training |
| kmeans_c15 | short | market | 6,064 | 28 | -0.18 | -0.01 | 0.05 | 1.000 | no edge in training |
| kmeans_c16 | long | market | 2,579 | 29 | -0.13 | -0.01 | 0.07 | 1.000 | no edge in training |
| kmeans_c16 | short | market | 2,579 | 30 | -0.11 | +0.03 | 0.07 | 1.000 | no edge in training |
| kmeans_c17 | long | market | 4,548 | 28 | -0.17 | -0.01 | 0.06 | 1.000 | no edge in training |
| kmeans_c17 | short | market | 4,548 | 27 | -0.19 | -0.05 | 0.06 | 1.000 | no edge in training |
| kmeans_c18 | long | market | 3,044 | 28 | -0.16 | -0.02 | 0.07 | 1.000 | no edge in training |
| kmeans_c18 | short | market | 3,044 | 27 | -0.18 | -0.02 | 0.07 | 1.000 | no edge in training |
| kmeans_c19 | long | market | 1,806 | 28 | -0.17 | -0.04 | 0.08 | 1.000 | no edge in training |
| kmeans_c19 | short | market | 1,806 | 30 | -0.10 | +0.01 | 0.08 | 1.000 | no edge in training |
| kmeans_c20 | long | market | 2,147 | 29 | -0.12 | +0.00 | 0.08 | 1.000 | no edge in training |
| kmeans_c20 | short | market | 2,147 | 26 | -0.22 | -0.05 | 0.07 | 1.000 | no edge in training |
| kmeans_c21 | long | market | 1,706 | 29 | -0.15 | -0.03 | 0.08 | 1.000 | no edge in training |
| kmeans_c21 | short | market | 1,706 | 29 | -0.13 | -0.00 | 0.09 | 1.000 | no edge in training |
| kmeans_c22 | long | market | 2,810 | 28 | -0.18 | -0.05 | 0.07 | 1.000 | no edge in training |
| kmeans_c22 | short | market | 2,810 | 30 | -0.12 | +0.03 | 0.07 | 1.000 | no edge in training |
| kmeans_c23 | long | market | 2,883 | 31 | -0.09 | +0.03 | 0.07 | 1.000 | no edge in training |
| kmeans_c23 | short | market | 2,883 | 26 | -0.23 | -0.06 | 0.06 | 1.000 | no edge in training |
| last_point_of_supply | short | market | 19 | - | - | - | - | - | not enough trades |
| last_point_of_support | long | market | 25 | - | - | - | - | - | not enough trades |
| liquidity_sweep | long | market | 3,823 | 29 | -0.16 | +0.03 | 0.06 | 0.488 | no edge in training |
| liquidity_sweep | short | market | 3,715 | 24 | -0.30 | -0.03 | 0.06 | 1.000 | no edge in training |
| liquidity_sweep|intraday:bias | long | market | 2,064 | 28 | -0.18 | +0.01 | 0.08 | 0.823 | no edge in training |
| liquidity_sweep|intraday:bias | short | market | 1,664 | 24 | -0.29 | -0.04 | 0.09 | 1.000 | no edge in training |
| liquidity_sweep|intraday:bias+context | long | market | 1,130 | 30 | -0.13 | +0.05 | 0.12 | 0.539 | no edge in training |
| liquidity_sweep|intraday:bias+context | short | market | 588 | 26 | -0.23 | -0.06 | 0.15 | 1.000 | no edge in training |
| liquidity_sweep|intraday:counter | long | market | 1,759 | 29 | -0.14 | +0.06 | 0.09 | 0.358 | no edge in training |
| liquidity_sweep|intraday:counter | short | market | 2,051 | 24 | -0.30 | -0.01 | 0.08 | 0.985 | no edge in training |
| liquidity_sweep|intraday:full | long | market | 40 | - | - | - | - | - | not enough trades |
| liquidity_sweep|intraday:full | short | market | 24 | - | - | - | - | - | not enough trades |
| london_high_sweep | short | market | 1,852 | 26 | -0.23 | +0.01 | 0.08 | 0.849 | no edge in training |
| london_high_sweep+choch | short | market | 777 | 36 | -0.07 | +0.00 | 0.11 | 0.871 | no edge in training |
| london_low_sweep | long | market | 1,844 | 29 | -0.16 | +0.00 | 0.08 | 0.888 | no edge in training |
| london_low_sweep+choch | long | market | 772 | 44 | +0.06 | +0.08 | 0.11 | 0.335 | no edge in training |
| lower_high | short | market | 4,420 | 30 | -0.13 | +0.04 | 0.06 | 0.335 | no edge in training |
| lower_high+bos | short | market | 1,018 | 34 | -0.11 | -0.04 | 0.11 | 1.000 | no edge in training |
| market_structure_shift | long | market | 685 | 40 | +0.03 | +0.04 | 0.12 | 0.639 | no edge in training |
| market_structure_shift | short | market | 583 | 34 | -0.13 | -0.07 | 0.13 | 1.000 | no edge in training |
| market_structure_shift|intraday:bias | long | market | 385 | 43 | +0.08 | +0.09 | 0.16 | 0.526 | no edge in training |
| market_structure_shift|intraday:bias | short | market | 312 | 35 | -0.11 | -0.06 | 0.18 | 1.000 | no edge in training |
| market_structure_shift|intraday:bias+context | long | market | 208 | 42 | +0.09 | +0.07 | 0.23 | 0.658 | no edge in training |
| market_structure_shift|intraday:bias+context | short | market | 108 | 29 | -0.25 | -0.25 | 0.32 | 1.000 | no edge in training |
| market_structure_shift|intraday:counter | long | market | 300 | 36 | -0.04 | -0.01 | 0.19 | 0.929 | no edge in training |
| market_structure_shift|intraday:counter | short | market | 271 | 33 | -0.16 | -0.09 | 0.18 | 1.000 | no edge in training |
| market_structure_shift|intraday:full | long | market | 175 | 41 | +0.09 | +0.06 | 0.25 | 0.708 | no edge in training |
| market_structure_shift|intraday:full | short | market | 99 | - | - | - | - | - | not enough trades |
| marubozu_bear | short | market | 557 | 33 | -0.07 | +0.01 | 0.14 | 0.860 | no edge in training |
| marubozu_bull | long | market | 595 | 37 | +0.02 | +0.05 | 0.14 | 0.624 | no edge in training |
| momentum_continuation | long | market | 1,386 | 48 | +0.03 | +0.02 | 0.11 | 0.766 | no edge in training |
| momentum_continuation | short | market | 1,318 | 42 | -0.06 | +0.02 | 0.11 | 0.805 | no edge in training |
| momentum_exhaustion | long | market | 211 | 31 | -0.24 | -0.18 | 0.22 | 1.000 | no edge in training |
| momentum_exhaustion | short | market | 224 | 33 | -0.07 | +0.01 | 0.24 | 0.868 | no edge in training |
| morning_doji_star | long | market | 523 | 32 | -0.09 | +0.00 | 0.15 | 0.882 | no edge in training |
| morning_star | long | market | 1,321 | 32 | -0.09 | +0.01 | 0.10 | 0.860 | no edge in training |
| multi_touch_rejection | long | market | 640 | 31 | -0.09 | +0.03 | 0.14 | 0.775 | no edge in training |
| multi_touch_rejection | short | market | 577 | 26 | -0.24 | -0.09 | 0.14 | 1.000 | no edge in training |
| multiple_sweeps | long | market | 712 | 28 | -0.19 | +0.00 | 0.14 | 0.876 | no edge in training |
| multiple_sweeps | short | market | 769 | 23 | -0.34 | -0.06 | 0.13 | 1.000 | no edge in training |
| nr_breakout | long | market | 3,696 | 28 | -0.18 | -0.05 | 0.06 | 1.000 | no edge in training |
| nr_breakout | short | market | 3,567 | 24 | -0.29 | -0.08 | 0.06 | 1.000 | no edge in training |
| order_block | long | limit | 2,161 | 30 | -0.12 | +0.03 | 0.08 | 0.649 | no edge in training |
| order_block | short | limit | 2,121 | 31 | -0.08 | +0.11 | 0.07 | 0.021 | candidate |
| order_block_bos | long | limit | 1,117 | 29 | -0.14 | +0.01 | 0.10 | 0.805 | no edge in training |
| order_block_bos | short | limit | 962 | 30 | -0.11 | +0.07 | 0.11 | 0.448 | no edge in training |
| order_block_choch | long | limit | 1,044 | 31 | -0.10 | +0.04 | 0.10 | 0.640 | no edge in training |
| order_block_choch | short | limit | 1,159 | 32 | -0.05 | +0.14 | 0.10 | 0.022 | candidate |
| order_block_fvg | long | limit | 722 | 30 | -0.13 | +0.03 | 0.13 | 0.767 | no edge in training |
| order_block_fvg | short | limit | 742 | 32 | -0.06 | +0.11 | 0.13 | 0.246 | no edge in training |
| order_block_sweep | long | limit | 383 | 36 | +0.00 | +0.10 | 0.18 | 0.474 | no edge in training |
| order_block_sweep | short | limit | 414 | 33 | -0.04 | +0.14 | 0.17 | 0.249 | no edge in training |
| order_block|intraday:bias | long | limit | 1,238 | 30 | -0.14 | +0.01 | 0.10 | 0.852 | no edge in training |
| order_block|intraday:bias | short | limit | 1,060 | 30 | -0.11 | +0.07 | 0.10 | 0.398 | no edge in training |
| order_block|intraday:bias+context | long | limit | 667 | 30 | -0.13 | -0.00 | 0.14 | 0.894 | no edge in training |
| order_block|intraday:bias+context | short | limit | 379 | 32 | -0.04 | +0.09 | 0.18 | 0.539 | no edge in training |
| order_block|intraday:counter | long | limit | 923 | 31 | -0.10 | +0.05 | 0.11 | 0.567 | no edge in training |
| order_block|intraday:counter | short | limit | 1,061 | 32 | -0.05 | +0.14 | 0.11 | 0.022 | candidate |
| order_block|intraday:full | long | limit | 558 | 29 | -0.15 | -0.02 | 0.15 | 0.963 | no edge in training |
| order_block|intraday:full | short | limit | 328 | 33 | -0.03 | +0.11 | 0.19 | 0.495 | no edge in training |
| outside_bar_bear | short | market | 4,681 | 26 | -0.23 | -0.02 | 0.06 | 1.000 | no edge in training |
| outside_bar_bull | long | market | 5,133 | 30 | -0.15 | -0.01 | 0.06 | 0.963 | no edge in training |
| pd_high_sweep | short | market | 882 | 25 | -0.25 | +0.05 | 0.10 | 0.539 | no edge in training |
| pd_high_sweep|intraday:bias | short | market | 336 | 26 | -0.25 | +0.03 | 0.16 | 0.784 | no edge in training |
| pd_high_sweep|intraday:bias+context | short | market | 106 | 30 | -0.09 | +0.09 | 0.32 | 0.684 | no edge in training |
| pd_high_sweep|intraday:counter | short | market | 546 | 25 | -0.26 | +0.06 | 0.14 | 0.551 | no edge in training |
| pd_high_sweep|intraday:full | short | market | 3 | - | - | - | - | - | not enough trades |
| pd_low_sweep | long | market | 812 | 29 | -0.15 | +0.05 | 0.12 | 0.550 | no edge in training |
| pd_low_sweep|intraday:bias | long | market | 383 | 30 | -0.14 | +0.05 | 0.17 | 0.684 | no edge in training |
| pd_low_sweep|intraday:bias+context | long | market | 206 | 32 | -0.07 | +0.11 | 0.25 | 0.562 | no edge in training |
| pd_low_sweep|intraday:counter | long | market | 429 | 29 | -0.15 | +0.06 | 0.16 | 0.639 | no edge in training |
| pd_low_sweep|intraday:full | long | market | 10 | - | - | - | - | - | not enough trades |
| pdh_sweep+choch | short | market | 220 | 36 | -0.11 | -0.02 | 0.20 | 0.947 | no edge in training |
| pdh_sweep+engulfing | short | market | 203 | 29 | -0.18 | -0.03 | 0.24 | 0.985 | no edge in training |
| pdh_sweep+fvg | short | limit | 406 | 25 | -0.26 | +0.04 | 0.16 | 0.708 | no edge in training |
| pdl_sweep+choch | long | market | 233 | 46 | +0.06 | +0.06 | 0.18 | 0.640 | no edge in training |
| pdl_sweep+engulfing | long | market | 221 | 38 | +0.04 | +0.14 | 0.23 | 0.443 | no edge in training |
| pdl_sweep+fvg | long | limit | 416 | 28 | -0.17 | +0.08 | 0.16 | 0.526 | no edge in training |
| piercing | long | market | 878 | 30 | -0.12 | +0.00 | 0.12 | 0.876 | no edge in training |
| pin_bar_bear | short | market | 3,457 | 26 | -0.25 | -0.03 | 0.06 | 1.000 | no edge in training |
| pin_bar_bear|intraday:bias | short | market | 1,652 | 27 | -0.23 | -0.02 | 0.08 | 1.000 | no edge in training |
| pin_bar_bear|intraday:bias+context | short | market | 611 | 25 | -0.27 | -0.11 | 0.13 | 1.000 | no edge in training |
| pin_bar_bear|intraday:counter | short | market | 1,805 | 25 | -0.27 | -0.04 | 0.08 | 1.000 | no edge in training |
| pin_bar_bear|intraday:full | short | market | 62 | - | - | - | - | - | not enough trades |
| pin_bar_bull | long | market | 4,104 | 28 | -0.17 | +0.01 | 0.06 | 0.805 | no edge in training |
| pin_bar_bull|intraday:bias | long | market | 2,224 | 28 | -0.16 | +0.01 | 0.08 | 0.844 | no edge in training |
| pin_bar_bull|intraday:bias+context | long | market | 1,172 | 28 | -0.17 | -0.01 | 0.11 | 0.947 | no edge in training |
| pin_bar_bull|intraday:counter | long | market | 1,880 | 28 | -0.18 | +0.01 | 0.09 | 0.845 | no edge in training |
| pin_bar_bull|intraday:full | long | market | 122 | 27 | -0.20 | -0.06 | 0.30 | 1.000 | no edge in training |
| pm_high_sweep | short | market | 41 | - | - | - | - | - | not enough trades |
| pm_low_sweep | long | market | 31 | - | - | - | - | - | not enough trades |
| preliminary_supply | short | market | 462 | 28 | -0.16 | +0.02 | 0.16 | 0.713 | no edge in training |
| preliminary_support | long | market | 371 | 34 | -0.03 | +0.08 | 0.17 | 0.483 | no edge in training |
| pw_high_sweep | short | market | 170 | 27 | -0.20 | +0.08 | 0.24 | 0.640 | no edge in training |
| pw_low_sweep | long | market | 152 | 25 | -0.28 | -0.09 | 0.26 | 1.000 | no edge in training |
| range_boundary_rejection | long | market | 1,805 | 31 | -0.10 | +0.07 | 0.08 | 0.214 | no edge in training |
| range_boundary_rejection | short | market | 2,487 | 25 | -0.26 | +0.00 | 0.06 | 0.862 | no edge in training |
| range_midpoint_cross | long | market | 2,742 | 36 | -0.02 | +0.05 | 0.08 | 0.472 | no edge in training |
| range_midpoint_cross | short | market | 2,731 | 31 | -0.12 | +0.02 | 0.08 | 0.682 | no edge in training |
| range_to_trend | long | market | 1,231 | 44 | +0.04 | +0.05 | 0.10 | 0.539 | no edge in training |
| range_to_trend | short | market | 938 | 40 | -0.07 | -0.01 | 0.10 | 0.963 | no edge in training |
| reclaimed_order_block | long | market | 1,024 | 45 | +0.09 | +0.09 | 0.11 | 0.269 | no edge in training |
| reclaimed_order_block | short | market | 857 | 38 | -0.05 | +0.03 | 0.12 | 0.753 | no edge in training |
| rectangle_breakout | long | market | 120 | 39 | +0.01 | -0.01 | 0.27 | 0.847 | no edge in training |
| rectangle_breakout | short | market | 121 | 35 | -0.07 | -0.03 | 0.28 | 0.868 | no edge in training |
| rejection_bear | short | market | 3,068 | 27 | -0.21 | -0.01 | 0.06 | 1.000 | no edge in training |
| rejection_bear+bos | short | market | 304 | 43 | +0.11 | +0.16 | 0.19 | 0.265 | no edge in training |
| rejection_block | long | limit | 2,641 | 28 | -0.17 | +0.02 | 0.07 | 0.723 | no edge in training |
| rejection_block | short | limit | 2,430 | 26 | -0.23 | -0.00 | 0.07 | 0.903 | no edge in training |
| rejection_bull | long | market | 3,400 | 30 | -0.12 | +0.03 | 0.06 | 0.529 | no edge in training |
| rejection_bull+bos | long | market | 454 | 41 | +0.02 | +0.01 | 0.15 | 0.862 | no edge in training |
| resistance_rejection | short | market | 869 | 26 | -0.22 | -0.05 | 0.11 | 1.000 | no edge in training |
| resistance_rejection+engulfing | short | market | 157 | 27 | -0.20 | -0.07 | 0.26 | 1.000 | no edge in training |
| resistance_rejection|intraday:bias | short | market | 324 | 28 | -0.15 | +0.00 | 0.20 | 0.883 | no edge in training |
| resistance_rejection|intraday:bias+context | short | market | 110 | 24 | -0.29 | -0.20 | 0.27 | 1.000 | no edge in training |
| resistance_rejection|intraday:counter | short | market | 545 | 25 | -0.27 | -0.08 | 0.14 | 1.000 | no edge in training |
| resistance_rejection|intraday:full | short | market | 10 | - | - | - | - | - | not enough trades |
| retest | long | market | 1,517 | 30 | -0.13 | +0.04 | 0.09 | 0.546 | no edge in training |
| retest | short | market | 1,430 | 27 | -0.21 | +0.02 | 0.09 | 0.767 | no edge in training |
| retest+momentum | long | market | 278 | 56 | +0.18 | +0.17 | 0.21 | 0.277 | no edge in training |
| retest+momentum | short | market | 269 | 39 | -0.19 | -0.11 | 0.18 | 1.000 | no edge in training |
| retest|intraday:bias | long | market | 903 | 32 | -0.08 | +0.09 | 0.12 | 0.320 | no edge in training |
| retest|intraday:bias | short | market | 863 | 26 | -0.23 | -0.01 | 0.11 | 0.929 | no edge in training |
| retest|intraday:bias+context | long | market | 416 | 32 | -0.10 | +0.06 | 0.16 | 0.639 | no edge in training |
| retest|intraday:bias+context | short | market | 268 | 28 | -0.18 | -0.01 | 0.21 | 0.929 | no edge in training |
| retest|intraday:counter | long | market | 614 | 27 | -0.20 | -0.02 | 0.15 | 0.993 | no edge in training |
| retest|intraday:counter | short | market | 567 | 27 | -0.19 | +0.06 | 0.14 | 0.603 | no edge in training |
| retest|intraday:full | long | market | 98 | - | - | - | - | - | not enough trades |
| retest|intraday:full | short | market | 67 | - | - | - | - | - | not enough trades |
| rising_channel_break | short | market | 438 | 37 | -0.02 | +0.08 | 0.16 | 0.431 | no edge in training |
| rising_three_methods | long | market | 116 | 47 | +0.26 | +0.29 | 0.32 | 0.208 | no edge in training |
| rising_wedge_breakdown | short | market | 589 | 32 | -0.10 | +0.01 | 0.14 | 0.730 | no edge in training |
| round100_reaction | long | market | 480 | 26 | -0.23 | -0.06 | 0.18 | 1.000 | no edge in training |
| round100_reaction | short | market | 466 | 27 | -0.20 | +0.05 | 0.15 | 0.639 | no edge in training |
| round10_reaction | long | market | 4,642 | 29 | -0.15 | +0.04 | 0.06 | 0.391 | no edge in training |
| round10_reaction | short | market | 4,303 | 28 | -0.18 | +0.05 | 0.06 | 0.216 | no edge in training |
| round50_reaction | long | market | 530 | 36 | +0.07 | +0.27 | 0.19 | 0.022 | candidate |
| round50_reaction | short | market | 471 | 29 | -0.16 | +0.10 | 0.17 | 0.503 | no edge in training |
| round_placebo_reaction | long | market | 6,600 | 28 | -0.19 | +0.01 | 0.05 | 0.733 | no edge in training |
| round_placebo_reaction | short | market | 6,166 | 26 | -0.23 | +0.01 | 0.05 | 0.761 | no edge in training |
| rounding_bottom | long | market | 54 | - | - | - | - | - | not enough trades |
| rounding_top | short | market | 115 | 42 | -0.13 | -0.05 | 0.18 | 0.937 | no edge in training |
| secondary_test | long | market | 101 | 24 | -0.29 | -0.11 | 0.32 | 0.964 | no edge in training |
| secondary_test | short | market | 93 | - | - | - | - | - | not enough trades |
| selling_climax | long | market | 552 | 27 | -0.20 | -0.06 | 0.14 | 0.990 | no edge in training |
| seq2_dl1-um3 | long | market | 951 | 29 | -0.13 | -0.00 | 0.11 | 1.000 | no edge in training |
| seq2_dl1-um3 | short | market | 951 | 31 | -0.06 | +0.08 | 0.12 | 0.981 | no edge in training |
| seq2_dm1-dl1 | long | market | 694 | 32 | -0.05 | +0.08 | 0.14 | 0.981 | no edge in training |
| seq2_dm1-dl1 | short | market | 694 | 27 | -0.20 | -0.08 | 0.13 | 1.000 | no edge in training |
| seq2_dm1-dm1 | long | market | 1,454 | 29 | -0.12 | +0.01 | 0.09 | 1.000 | no edge in training |
| seq2_dm1-dm1 | short | market | 1,454 | 25 | -0.24 | -0.10 | 0.09 | 1.000 | no edge in training |
| seq2_dm1-dm2 | long | market | 680 | 29 | -0.13 | +0.02 | 0.13 | 1.000 | no edge in training |
| seq2_dm1-dm2 | short | market | 680 | 28 | -0.16 | -0.02 | 0.13 | 1.000 | no edge in training |
| seq2_dm1-ds1 | long | market | 766 | 30 | -0.10 | +0.05 | 0.13 | 1.000 | no edge in training |
| seq2_dm1-ds1 | short | market | 766 | 26 | -0.22 | -0.08 | 0.13 | 1.000 | no edge in training |
| seq2_dm1-ds2 | long | market | 900 | 28 | -0.17 | -0.01 | 0.12 | 1.000 | no edge in training |
| seq2_dm1-ds2 | short | market | 900 | 27 | -0.19 | -0.03 | 0.11 | 1.000 | no edge in training |
| seq2_dm1-fs2 | long | market | 711 | 28 | -0.18 | -0.02 | 0.13 | 1.000 | no edge in training |
| seq2_dm1-fs2 | short | market | 711 | 23 | -0.32 | -0.14 | 0.12 | 1.000 | no edge in training |
| seq2_dm1-ul3 | long | market | 668 | 33 | -0.03 | +0.09 | 0.14 | 0.981 | no edge in training |
| seq2_dm1-ul3 | short | market | 668 | 27 | -0.19 | -0.07 | 0.13 | 1.000 | no edge in training |
| seq2_dm1-um2 | long | market | 614 | 29 | -0.15 | -0.01 | 0.14 | 1.000 | no edge in training |
| seq2_dm1-um2 | short | market | 614 | 30 | -0.11 | +0.04 | 0.14 | 1.000 | no edge in training |
| seq2_dm1-um3 | long | market | 2,258 | 28 | -0.15 | -0.01 | 0.08 | 1.000 | no edge in training |
| seq2_dm1-um3 | short | market | 2,258 | 29 | -0.13 | +0.00 | 0.08 | 1.000 | no edge in training |
| seq2_dm1-us2 | long | market | 1,083 | 30 | -0.09 | +0.05 | 0.11 | 1.000 | no edge in training |
| seq2_dm1-us2 | short | market | 1,083 | 27 | -0.19 | -0.05 | 0.10 | 1.000 | no edge in training |
| seq2_dm1-us3 | long | market | 1,026 | 27 | -0.20 | -0.05 | 0.12 | 1.000 | no edge in training |
| seq2_dm1-us3 | short | market | 1,026 | 31 | -0.07 | +0.08 | 0.11 | 0.981 | no edge in training |
| seq2_dm2-dm1 | long | market | 603 | 30 | -0.12 | +0.03 | 0.15 | 1.000 | no edge in training |
| seq2_dm2-dm1 | short | market | 603 | 28 | -0.17 | -0.02 | 0.14 | 1.000 | no edge in training |
| seq2_dm2-um3 | long | market | 844 | 26 | -0.23 | -0.08 | 0.12 | 1.000 | no edge in training |
| seq2_dm2-um3 | short | market | 844 | 29 | -0.14 | +0.03 | 0.12 | 1.000 | no edge in training |
| seq2_ds1-dm1 | long | market | 864 | 29 | -0.13 | +0.03 | 0.12 | 1.000 | no edge in training |
| seq2_ds1-dm1 | short | market | 864 | 26 | -0.22 | -0.10 | 0.11 | 1.000 | no edge in training |
| seq2_ds1-ds1 | long | market | 605 | 30 | -0.09 | +0.06 | 0.16 | 1.000 | no edge in training |
| seq2_ds1-ds1 | short | market | 605 | 24 | -0.29 | -0.15 | 0.14 | 1.000 | no edge in training |
| seq2_ds1-ds2 | long | market | 544 | 29 | -0.15 | -0.00 | 0.14 | 1.000 | no edge in training |
| seq2_ds1-ds2 | short | market | 544 | 30 | -0.10 | +0.04 | 0.15 | 1.000 | no edge in training |
| seq2_ds1-um3 | long | market | 1,032 | 30 | -0.11 | +0.04 | 0.11 | 1.000 | no edge in training |
| seq2_ds1-um3 | short | market | 1,032 | 29 | -0.14 | -0.01 | 0.11 | 1.000 | no edge in training |
| seq2_ds1-us2 | long | market | 664 | 31 | -0.08 | +0.07 | 0.14 | 1.000 | no edge in training |
| seq2_ds1-us2 | short | market | 664 | 25 | -0.27 | -0.12 | 0.13 | 1.000 | no edge in training |
| seq2_ds1-us3 | long | market | 667 | 25 | -0.24 | -0.10 | 0.13 | 1.000 | no edge in training |
| seq2_ds1-us3 | short | market | 667 | 30 | -0.10 | +0.04 | 0.14 | 1.000 | no edge in training |
| seq2_ds2-dm1 | long | market | 941 | 28 | -0.17 | -0.01 | 0.11 | 1.000 | no edge in training |
| seq2_ds2-dm1 | short | market | 941 | 25 | -0.26 | -0.09 | 0.11 | 1.000 | no edge in training |
| seq2_ds2-ds1 | long | market | 657 | 27 | -0.21 | -0.04 | 0.13 | 1.000 | no edge in training |
| seq2_ds2-ds1 | short | market | 657 | 27 | -0.20 | -0.05 | 0.13 | 1.000 | no edge in training |
| seq2_ds2-ds2 | long | market | 687 | 26 | -0.23 | -0.06 | 0.15 | 1.000 | no edge in training |
| seq2_ds2-ds2 | short | market | 687 | 29 | -0.15 | +0.04 | 0.14 | 1.000 | no edge in training |
| seq2_ds2-fs2 | long | market | 532 | 26 | -0.22 | -0.04 | 0.14 | 1.000 | no edge in training |
| seq2_ds2-fs2 | short | market | 532 | 28 | -0.18 | +0.05 | 0.15 | 1.000 | no edge in training |
| seq2_ds2-um3 | long | market | 1,191 | 28 | -0.17 | -0.02 | 0.11 | 1.000 | no edge in training |
| seq2_ds2-um3 | short | market | 1,191 | 28 | -0.16 | +0.02 | 0.10 | 1.000 | no edge in training |
| seq2_ds2-us2 | long | market | 671 | 26 | -0.24 | -0.08 | 0.13 | 1.000 | no edge in training |
| seq2_ds2-us2 | short | market | 671 | 27 | -0.18 | +0.01 | 0.13 | 1.000 | no edge in training |
| seq2_ds2-us3 | long | market | 727 | 28 | -0.18 | -0.02 | 0.13 | 1.000 | no edge in training |
| seq2_ds2-us3 | short | market | 727 | 27 | -0.20 | +0.00 | 0.13 | 1.000 | no edge in training |
| seq2_fs2-dm1 | long | market | 709 | 30 | -0.11 | +0.05 | 0.13 | 1.000 | no edge in training |
| seq2_fs2-dm1 | short | market | 709 | 26 | -0.23 | -0.07 | 0.12 | 1.000 | no edge in training |
| seq2_fs2-ds2 | long | market | 525 | 26 | -0.22 | -0.05 | 0.14 | 1.000 | no edge in training |
| seq2_fs2-ds2 | short | market | 525 | 26 | -0.24 | -0.00 | 0.15 | 1.000 | no edge in training |
| seq2_fs2-um3 | long | market | 847 | 27 | -0.19 | -0.03 | 0.12 | 1.000 | no edge in training |
| seq2_fs2-um3 | short | market | 847 | 29 | -0.13 | +0.06 | 0.12 | 1.000 | no edge in training |
| seq2_fs2-us2 | long | market | 501 | 29 | -0.13 | +0.05 | 0.16 | 1.000 | no edge in training |
| seq2_fs2-us2 | short | market | 501 | 23 | -0.33 | -0.11 | 0.14 | 1.000 | no edge in training |
| seq2_fs2-us3 | long | market | 521 | 30 | -0.09 | +0.07 | 0.16 | 1.000 | no edge in training |
| seq2_fs2-us3 | short | market | 521 | 24 | -0.28 | -0.05 | 0.14 | 1.000 | no edge in training |
| seq2_ul3-dm1 | long | market | 875 | 28 | -0.15 | -0.04 | 0.12 | 1.000 | no edge in training |
| seq2_ul3-dm1 | short | market | 875 | 31 | -0.08 | +0.07 | 0.12 | 0.981 | no edge in training |
| seq2_ul3-um3 | long | market | 625 | 28 | -0.18 | -0.06 | 0.13 | 1.000 | no edge in training |
| seq2_ul3-um3 | short | market | 625 | 27 | -0.19 | -0.03 | 0.13 | 1.000 | no edge in training |
| seq2_um2-dm1 | long | market | 676 | 30 | -0.09 | +0.05 | 0.14 | 1.000 | no edge in training |
| seq2_um2-dm1 | short | market | 676 | 26 | -0.21 | -0.08 | 0.14 | 1.000 | no edge in training |
| seq2_um2-um3 | long | market | 671 | 28 | -0.16 | -0.03 | 0.13 | 1.000 | no edge in training |
| seq2_um2-um3 | short | market | 671 | 28 | -0.16 | +0.01 | 0.13 | 1.000 | no edge in training |
| seq2_um3-dl1 | long | market | 692 | 28 | -0.15 | -0.02 | 0.13 | 1.000 | no edge in training |
| seq2_um3-dl1 | short | market | 692 | 29 | -0.13 | -0.01 | 0.13 | 1.000 | no edge in training |
| seq2_um3-dm1 | long | market | 2,253 | 29 | -0.15 | -0.00 | 0.08 | 1.000 | no edge in training |
| seq2_um3-dm1 | short | market | 2,253 | 29 | -0.15 | -0.00 | 0.08 | 1.000 | no edge in training |
| seq2_um3-dm2 | long | market | 766 | 27 | -0.21 | -0.05 | 0.13 | 1.000 | no edge in training |
| seq2_um3-dm2 | short | market | 766 | 28 | -0.18 | +0.00 | 0.12 | 1.000 | no edge in training |
| seq2_um3-ds1 | long | market | 1,078 | 29 | -0.14 | +0.00 | 0.11 | 1.000 | no edge in training |
| seq2_um3-ds1 | short | market | 1,078 | 27 | -0.19 | -0.04 | 0.10 | 1.000 | no edge in training |
| seq2_um3-ds2 | long | market | 1,304 | 25 | -0.25 | -0.10 | 0.10 | 1.000 | no edge in training |
| seq2_um3-ds2 | short | market | 1,304 | 27 | -0.18 | +0.00 | 0.09 | 1.000 | no edge in training |
| seq2_um3-fs2 | long | market | 869 | 28 | -0.17 | -0.01 | 0.12 | 1.000 | no edge in training |
| seq2_um3-fs2 | short | market | 869 | 26 | -0.23 | -0.03 | 0.11 | 1.000 | no edge in training |
| seq2_um3-ul3 | long | market | 758 | 29 | -0.14 | -0.01 | 0.12 | 1.000 | no edge in training |
| seq2_um3-ul3 | short | market | 758 | 28 | -0.16 | -0.02 | 0.12 | 1.000 | no edge in training |
| seq2_um3-um2 | long | market | 693 | 29 | -0.14 | +0.01 | 0.13 | 1.000 | no edge in training |
| seq2_um3-um2 | short | market | 693 | 31 | -0.07 | +0.08 | 0.13 | 0.981 | no edge in training |
| seq2_um3-um3 | long | market | 1,857 | 25 | -0.25 | -0.10 | 0.08 | 1.000 | no edge in training |
| seq2_um3-um3 | short | market | 1,857 | 30 | -0.10 | +0.07 | 0.08 | 0.981 | no edge in training |
| seq2_um3-us2 | long | market | 1,040 | 31 | -0.09 | +0.06 | 0.11 | 0.981 | no edge in training |
| seq2_um3-us2 | short | market | 1,040 | 27 | -0.20 | -0.03 | 0.11 | 1.000 | no edge in training |
| seq2_um3-us3 | long | market | 1,101 | 28 | -0.18 | -0.04 | 0.10 | 1.000 | no edge in training |
| seq2_um3-us3 | short | market | 1,101 | 29 | -0.15 | +0.02 | 0.11 | 1.000 | no edge in training |
| seq2_us2-dm1 | long | market | 960 | 29 | -0.14 | +0.01 | 0.11 | 1.000 | no edge in training |
| seq2_us2-dm1 | short | market | 960 | 29 | -0.14 | +0.00 | 0.11 | 1.000 | no edge in training |
| seq2_us2-ds1 | long | market | 627 | 27 | -0.21 | -0.07 | 0.14 | 1.000 | no edge in training |
| seq2_us2-ds1 | short | market | 627 | 26 | -0.21 | -0.05 | 0.13 | 1.000 | no edge in training |
| seq2_us2-ds2 | long | market | 693 | 28 | -0.17 | -0.01 | 0.13 | 1.000 | no edge in training |
| seq2_us2-ds2 | short | market | 693 | 27 | -0.19 | -0.00 | 0.12 | 1.000 | no edge in training |
| seq2_us2-fs2 | long | market | 459 | 32 | -0.06 | +0.11 | 0.17 | 0.981 | no edge in training |
| seq2_us2-fs2 | short | market | 459 | 24 | -0.30 | -0.10 | 0.15 | 1.000 | no edge in training |
| seq2_us2-um3 | long | market | 1,066 | 25 | -0.26 | -0.10 | 0.11 | 1.000 | no edge in training |
| seq2_us2-um3 | short | market | 1,066 | 28 | -0.17 | -0.01 | 0.11 | 1.000 | no edge in training |
| seq2_us2-us2 | long | market | 614 | 29 | -0.12 | +0.04 | 0.16 | 1.000 | no edge in training |
| seq2_us2-us2 | short | market | 614 | 27 | -0.20 | -0.02 | 0.15 | 1.000 | no edge in training |
| seq2_us2-us3 | long | market | 737 | 27 | -0.20 | -0.05 | 0.13 | 1.000 | no edge in training |
| seq2_us2-us3 | short | market | 737 | 28 | -0.17 | +0.02 | 0.12 | 1.000 | no edge in training |
| seq2_us3-dm1 | long | market | 1,093 | 31 | -0.08 | +0.07 | 0.11 | 0.981 | no edge in training |
| seq2_us3-dm1 | short | market | 1,093 | 28 | -0.16 | -0.00 | 0.10 | 1.000 | no edge in training |
| seq2_us3-ds1 | long | market | 688 | 29 | -0.13 | +0.02 | 0.14 | 1.000 | no edge in training |
| seq2_us3-ds1 | short | market | 688 | 28 | -0.17 | -0.02 | 0.13 | 1.000 | no edge in training |
| seq2_us3-ds2 | long | market | 784 | 27 | -0.21 | -0.06 | 0.12 | 1.000 | no edge in training |
| seq2_us3-ds2 | short | market | 784 | 26 | -0.23 | -0.03 | 0.12 | 1.000 | no edge in training |
| seq2_us3-um3 | long | market | 1,036 | 26 | -0.22 | -0.08 | 0.11 | 1.000 | no edge in training |
| seq2_us3-um3 | short | market | 1,036 | 29 | -0.13 | +0.04 | 0.11 | 1.000 | no edge in training |
| seq2_us3-us2 | long | market | 648 | 29 | -0.15 | +0.01 | 0.14 | 1.000 | no edge in training |
| seq2_us3-us2 | short | market | 648 | 29 | -0.15 | +0.04 | 0.14 | 1.000 | no edge in training |
| seq2_us3-us3 | long | market | 758 | 30 | -0.11 | +0.04 | 0.14 | 1.000 | no edge in training |
| seq2_us3-us3 | short | market | 758 | 28 | -0.17 | +0.03 | 0.15 | 1.000 | no edge in training |
| seq3_dm1-dm1-um3 | long | market | 284 | 27 | -0.20 | -0.06 | 0.20 | 1.000 | no edge in training |
| seq3_dm1-dm1-um3 | short | market | 284 | 36 | +0.08 | +0.20 | 0.22 | 0.981 | no edge in training |
| seq3_dm1-um3-dm1 | long | market | 368 | 30 | -0.09 | +0.05 | 0.19 | 1.000 | no edge in training |
| seq3_dm1-um3-dm1 | short | market | 368 | 24 | -0.29 | -0.17 | 0.17 | 1.000 | no edge in training |
| seq3_dm1-um3-um3 | long | market | 306 | 25 | -0.24 | -0.10 | 0.19 | 1.000 | no edge in training |
| seq3_dm1-um3-um3 | short | market | 306 | 29 | -0.13 | -0.00 | 0.19 | 1.000 | no edge in training |
| seq3_um3-dm1-dm1 | long | market | 307 | 26 | -0.22 | -0.07 | 0.19 | 1.000 | no edge in training |
| seq3_um3-dm1-dm1 | short | market | 307 | 28 | -0.17 | -0.05 | 0.20 | 1.000 | no edge in training |
| seq3_um3-dm1-um3 | long | market | 373 | 27 | -0.19 | -0.05 | 0.17 | 1.000 | no edge in training |
| seq3_um3-dm1-um3 | short | market | 373 | 27 | -0.21 | -0.07 | 0.17 | 1.000 | no edge in training |
| seq3_um3-um3-dm1 | long | market | 329 | 27 | -0.18 | -0.04 | 0.18 | 1.000 | no edge in training |
| seq3_um3-um3-dm1 | short | market | 329 | 33 | -0.02 | +0.14 | 0.19 | 0.981 | no edge in training |
| shark | long | market | 24 | - | - | - | - | - | not enough trades |
| shark | short | market | 31 | - | - | - | - | - | not enough trades |
| shooting_star | short | market | 1,590 | 26 | -0.24 | -0.04 | 0.09 | 1.000 | no edge in training |
| sign_of_strength | long | market | 51 | - | - | - | - | - | not enough trades |
| sign_of_weakness | short | market | 47 | - | - | - | - | - | not enough trades |
| spring | long | market | 65 | - | - | - | - | - | not enough trades |
| squeeze+bos | long | market | 189 | 47 | +0.19 | +0.20 | 0.23 | 0.208 | no edge in training |
| squeeze+bos | short | market | 149 | 29 | -0.30 | -0.24 | 0.23 | 1.000 | no edge in training |
| squeeze_release | long | market | 1,002 | 42 | +0.03 | +0.04 | 0.10 | 0.558 | no edge in training |
| squeeze_release | short | market | 881 | 34 | -0.10 | -0.01 | 0.10 | 0.956 | no edge in training |
| strong_bear_sequence | short | market | 58 | - | - | - | - | - | not enough trades |
| strong_bull_sequence | long | market | 100 | 43 | -0.11 | -0.14 | 0.24 | 1.000 | no edge in training |
| strong_demand | long | limit | 105 | 30 | -0.12 | +0.11 | 0.34 | 0.656 | no edge in training |
| strong_supply | short | limit | 104 | 31 | -0.08 | +0.14 | 0.35 | 0.592 | no edge in training |
| structural_reclaim | long | market | 474 | 43 | +0.04 | +0.05 | 0.14 | 0.640 | no edge in training |
| structural_reclaim | short | market | 552 | 39 | +0.01 | +0.10 | 0.13 | 0.335 | no edge in training |
| supply_to_demand_flip | long | limit | 527 | 30 | -0.09 | +0.06 | 0.15 | 0.612 | no edge in training |
| supply_zone | short | limit | 586 | 28 | -0.16 | +0.03 | 0.13 | 0.729 | no edge in training |
| supply_zone|intraday:bias | short | limit | 310 | 29 | -0.13 | +0.05 | 0.19 | 0.708 | no edge in training |
| supply_zone|intraday:bias+context | short | limit | 122 | 25 | -0.24 | -0.06 | 0.27 | 1.000 | no edge in training |
| supply_zone|intraday:counter | short | limit | 276 | 27 | -0.19 | +0.01 | 0.19 | 0.862 | no edge in training |
| supply_zone|intraday:full | short | limit | 113 | 27 | -0.21 | -0.03 | 0.28 | 0.968 | no edge in training |
| support_rejection | long | market | 920 | 31 | -0.09 | +0.04 | 0.12 | 0.639 | no edge in training |
| support_rejection+engulfing | long | market | 156 | 33 | -0.05 | +0.04 | 0.28 | 0.805 | no edge in training |
| support_rejection|intraday:bias | long | market | 349 | 31 | -0.07 | +0.03 | 0.20 | 0.805 | no edge in training |
| support_rejection|intraday:bias+context | long | market | 191 | 29 | -0.13 | -0.04 | 0.26 | 0.985 | no edge in training |
| support_rejection|intraday:counter | long | market | 571 | 31 | -0.09 | +0.05 | 0.15 | 0.640 | no edge in training |
| support_rejection|intraday:full | long | market | 18 | - | - | - | - | - | not enough trades |
| sweep+bos | long | market | 308 | 40 | -0.02 | -0.02 | 0.18 | 0.985 | no edge in training |
| sweep+bos | short | market | 223 | 35 | -0.09 | -0.03 | 0.22 | 0.987 | no edge in training |
| sweep+choch | long | market | 569 | 42 | -0.00 | -0.01 | 0.12 | 0.929 | no edge in training |
| sweep+choch | short | market | 575 | 37 | -0.09 | -0.01 | 0.12 | 0.937 | no edge in training |
| sweep+double_bottom | long | market | 74 | - | - | - | - | - | not enough trades |
| sweep+double_top | short | market | 71 | - | - | - | - | - | not enough trades |
| sweep+mss | long | market | 291 | 44 | +0.09 | +0.10 | 0.19 | 0.529 | no edge in training |
| sweep+mss | short | market | 235 | 33 | -0.16 | -0.11 | 0.20 | 1.000 | no edge in training |
| sweep+order_block | long | limit | 605 | 33 | -0.04 | +0.07 | 0.15 | 0.539 | no edge in training |
| sweep+order_block | short | limit | 586 | 29 | -0.15 | +0.04 | 0.13 | 0.660 | no edge in training |
| sweep_reclaim | long | market | 859 | 33 | -0.04 | +0.06 | 0.12 | 0.500 | no edge in training |
| sweep_reclaim | short | market | 955 | 28 | -0.16 | +0.02 | 0.11 | 0.761 | no edge in training |
| sweep_to_bos | long | market | 1,068 | 41 | -0.03 | -0.03 | 0.11 | 1.000 | no edge in training |
| sweep_to_bos | short | market | 958 | 35 | -0.10 | -0.01 | 0.13 | 0.947 | no edge in training |
| sweep_to_bos|intraday:bias | long | market | 567 | 43 | -0.01 | -0.03 | 0.15 | 1.000 | no edge in training |
| sweep_to_bos|intraday:bias | short | market | 433 | 34 | -0.14 | -0.08 | 0.19 | 1.000 | no edge in training |
| sweep_to_bos|intraday:bias+context | long | market | 306 | 43 | -0.01 | -0.04 | 0.21 | 1.000 | no edge in training |
| sweep_to_bos|intraday:bias+context | short | market | 138 | 30 | -0.29 | -0.28 | 0.29 | 1.000 | no edge in training |
| sweep_to_bos|intraday:counter | long | market | 501 | 39 | -0.04 | -0.03 | 0.16 | 1.000 | no edge in training |
| sweep_to_bos|intraday:counter | short | market | 525 | 37 | -0.06 | +0.04 | 0.17 | 0.708 | no edge in training |
| sweep_to_bos|intraday:full | long | market | 258 | 40 | -0.07 | -0.12 | 0.22 | 1.000 | no edge in training |
| sweep_to_bos|intraday:full | short | market | 106 | 25 | -0.42 | -0.40 | 0.27 | 1.000 | no edge in training |
| swing_failure | long | market | 2,209 | 29 | -0.16 | +0.06 | 0.07 | 0.306 | no edge in training |
| swing_failure | short | market | 2,218 | 23 | -0.33 | -0.05 | 0.07 | 1.000 | no edge in training |
| swing_failure+choch | long | market | 440 | 41 | -0.01 | -0.01 | 0.14 | 0.963 | no edge in training |
| swing_failure+choch | short | market | 457 | 37 | -0.08 | +0.01 | 0.14 | 0.862 | no edge in training |
| swing_failure|intraday:bias | long | market | 1,224 | 27 | -0.20 | +0.01 | 0.10 | 0.805 | no edge in training |
| swing_failure|intraday:bias | short | market | 974 | 22 | -0.34 | -0.08 | 0.10 | 1.000 | no edge in training |
| swing_failure|intraday:bias+context | long | market | 666 | 30 | -0.14 | +0.08 | 0.13 | 0.420 | no edge in training |
| swing_failure|intraday:bias+context | short | market | 322 | 24 | -0.29 | -0.11 | 0.17 | 1.000 | no edge in training |
| swing_failure|intraday:counter | long | market | 985 | 30 | -0.12 | +0.11 | 0.11 | 0.154 | no edge in training |
| swing_failure|intraday:counter | short | market | 1,244 | 23 | -0.33 | -0.02 | 0.09 | 1.000 | no edge in training |
| swing_failure|intraday:full | long | market | 31 | - | - | - | - | - | not enough trades |
| swing_failure|intraday:full | short | market | 19 | - | - | - | - | - | not enough trades |
| sym_triangle_breakout | long | market | 399 | 36 | +0.02 | +0.07 | 0.17 | 0.516 | no edge in training |
| sym_triangle_breakout | short | market | 401 | 35 | -0.00 | +0.07 | 0.18 | 0.507 | no edge in training |
| three_bar_continuation | long | market | 1,343 | 33 | -0.08 | -0.02 | 0.10 | 1.000 | no edge in training |
| three_bar_continuation | short | market | 1,136 | 30 | -0.15 | -0.05 | 0.10 | 1.000 | no edge in training |
| three_bar_reversal | long | market | 6,544 | 33 | -0.08 | -0.01 | 0.05 | 1.000 | no edge in training |
| three_bar_reversal | short | market | 6,102 | 30 | -0.15 | -0.04 | 0.05 | 1.000 | no edge in training |
| three_black_crows | short | market | 99 | - | - | - | - | - | not enough trades |
| three_drives | long | market | 10 | - | - | - | - | - | not enough trades |
| three_drives | short | market | 8 | - | - | - | - | - | not enough trades |
| three_inside_down | short | market | 580 | 31 | -0.12 | -0.03 | 0.14 | 1.000 | no edge in training |
| three_inside_up | long | market | 520 | 28 | -0.21 | -0.13 | 0.15 | 1.000 | no edge in training |
| three_outside_down | short | market | 2,570 | 31 | -0.12 | -0.02 | 0.07 | 1.000 | no edge in training |
| three_outside_up | long | market | 2,735 | 34 | -0.04 | +0.02 | 0.07 | 0.696 | no edge in training |
| three_white_soldiers | long | market | 127 | 40 | -0.02 | -0.02 | 0.28 | 0.935 | no edge in training |
| triple_bottom | long | market | 33 | - | - | - | - | - | not enough trades |
| triple_top | short | market | 32 | - | - | - | - | - | not enough trades |
| tweezer_bottom | long | market | 2,138 | 28 | -0.17 | +0.04 | 0.08 | 0.495 | no edge in training |
| tweezer_top | short | market | 2,451 | 23 | -0.32 | +0.02 | 0.06 | 0.647 | no edge in training |
| upthrust | short | market | 58 | - | - | - | - | - | not enough trades |
| wide_range | long | market | 2,580 | 40 | +0.05 | +0.06 | 0.08 | 0.277 | no edge in training |
| wide_range | short | market | 2,510 | 36 | -0.03 | +0.04 | 0.08 | 0.550 | no edge in training |
| wide_range_reversal | long | market | 1,180 | 40 | +0.06 | +0.07 | 0.10 | 0.388 | no edge in training |
| wide_range_reversal | short | market | 1,048 | 35 | -0.05 | +0.02 | 0.11 | 0.767 | no edge in training |

#### H4

| Pattern | Dir | Entry | Trades | Win % | Mean R | Edge | Smallest detectable | q | Status |
|---|---|---|---|---|---|---|---|---|---|
| BOS | long | market | 442 | 42 | +0.12 | -0.05 | 0.19 | 1.000 | no edge in training |
| BOS | short | market | 324 | 38 | -0.02 | +0.07 | 0.21 | 0.649 | no edge in training |
| BOS|swing:bias | long | market | 299 | 43 | +0.11 | -0.07 | 0.23 | 1.000 | no edge in training |
| BOS|swing:bias | short | market | 184 | 41 | +0.12 | +0.19 | 0.29 | 0.391 | no edge in training |
| BOS|swing:bias+context | long | market | 251 | 43 | +0.12 | -0.10 | 0.26 | 1.000 | no edge in training |
| BOS|swing:bias+context | short | market | 48 | - | - | - | - | - | not enough trades |
| BOS|swing:counter | long | market | 143 | 41 | +0.13 | -0.02 | 0.33 | 0.929 | no edge in training |
| BOS|swing:counter | short | market | 140 | 33 | -0.20 | -0.09 | 0.27 | 1.000 | no edge in training |
| BOS|swing:full | long | market | 215 | 44 | +0.13 | -0.08 | 0.27 | 1.000 | no edge in training |
| BOS|swing:full | short | market | 38 | - | - | - | - | - | not enough trades |
| CHoCH | long | market | 318 | 45 | +0.16 | +0.03 | 0.17 | 0.783 | no edge in training |
| CHoCH | short | market | 326 | 35 | -0.10 | +0.02 | 0.17 | 0.845 | no edge in training |
| CHoCH|swing:bias | long | market | 152 | 45 | +0.17 | +0.01 | 0.25 | 0.862 | no edge in training |
| CHoCH|swing:bias | short | market | 109 | 28 | -0.20 | -0.13 | 0.29 | 1.000 | no edge in training |
| CHoCH|swing:bias+context | long | market | 118 | 49 | +0.25 | +0.05 | 0.29 | 0.769 | no edge in training |
| CHoCH|swing:bias+context | short | market | 27 | - | - | - | - | - | not enough trades |
| CHoCH|swing:counter | long | market | 166 | 44 | +0.15 | +0.05 | 0.23 | 0.769 | no edge in training |
| CHoCH|swing:counter | short | market | 217 | 38 | -0.05 | +0.09 | 0.20 | 0.562 | no edge in training |
| CHoCH|swing:full | long | market | 97 | - | - | - | - | - | not enough trades |
| CHoCH|swing:full | short | market | 21 | - | - | - | - | - | not enough trades |
| abcd | long | market | 30 | - | - | - | - | - | not enough trades |
| abcd | short | market | 41 | - | - | - | - | - | not enough trades |
| asc_triangle_breakout | long | market | 96 | - | - | - | - | - | not enough trades |
| atr_expansion | long | market | 45 | - | - | - | - | - | not enough trades |
| atr_expansion | short | market | 50 | - | - | - | - | - | not enough trades |
| atr_expansion+bos | long | market | 7 | - | - | - | - | - | not enough trades |
| atr_expansion+bos | short | market | 9 | - | - | - | - | - | not enough trades |
| balanced_price_range | long | limit | 262 | 32 | -0.06 | +0.14 | 0.21 | 0.383 | no edge in training |
| balanced_price_range | short | limit | 257 | 25 | -0.27 | -0.05 | 0.20 | 1.000 | no edge in training |
| bat | long | market | 2 | - | - | - | - | - | not enough trades |
| bat | short | market | 8 | - | - | - | - | - | not enough trades |
| bear_flag | short | market | 4 | - | - | - | - | - | not enough trades |
| bear_pennant | short | market | 5 | - | - | - | - | - | not enough trades |
| bos+displacement | long | market | 108 | 38 | +0.06 | -0.12 | 0.31 | 1.000 | no edge in training |
| bos+displacement | short | market | 97 | - | - | - | - | - | not enough trades |
| breaker+fvg | long | limit | 504 | 31 | -0.11 | -0.00 | 0.15 | 0.919 | no edge in training |
| breaker+fvg | short | limit | 479 | 32 | -0.06 | +0.10 | 0.15 | 0.347 | no edge in training |
| breaker_block | long | limit | 485 | 36 | +0.06 | +0.05 | 0.17 | 0.708 | no edge in training |
| breaker_block | short | limit | 532 | 27 | -0.19 | -0.03 | 0.15 | 1.000 | no edge in training |
| breaker_block|swing:bias | long | limit | 287 | 39 | +0.14 | +0.12 | 0.23 | 0.529 | no edge in training |
| breaker_block|swing:bias | short | limit | 271 | 28 | -0.19 | -0.06 | 0.23 | 1.000 | no edge in training |
| breaker_block|swing:bias+context | long | limit | 205 | 40 | +0.18 | +0.12 | 0.27 | 0.551 | no edge in training |
| breaker_block|swing:bias+context | short | limit | 58 | - | - | - | - | - | not enough trades |
| breaker_block|swing:counter | long | limit | 198 | 32 | -0.06 | -0.06 | 0.27 | 1.000 | no edge in training |
| breaker_block|swing:counter | short | limit | 261 | 27 | -0.20 | +0.00 | 0.21 | 0.887 | no edge in training |
| breaker_block|swing:full | long | limit | 153 | 42 | +0.23 | +0.15 | 0.32 | 0.539 | no edge in training |
| breaker_block|swing:full | short | limit | 41 | - | - | - | - | - | not enough trades |
| breakout | long | market | 791 | 34 | -0.00 | -0.01 | 0.17 | 0.935 | no edge in training |
| breakout | short | market | 793 | 34 | -0.02 | +0.10 | 0.15 | 0.360 | no edge in training |
| broadening_breakout | long | market | 20 | - | - | - | - | - | not enough trades |
| broadening_breakout | short | market | 9 | - | - | - | - | - | not enough trades |
| bull_flag | long | market | 9 | - | - | - | - | - | not enough trades |
| bull_pennant | long | market | 4 | - | - | - | - | - | not enough trades |
| butterfly | long | market | 3 | - | - | - | - | - | not enough trades |
| butterfly | short | market | 4 | - | - | - | - | - | not enough trades |
| buying_climax | short | market | 132 | 27 | -0.20 | -0.01 | 0.28 | 0.847 | no edge in training |
| channel_breakout | long | market | 20 | - | - | - | - | - | not enough trades |
| channel_breakout | short | market | 16 | - | - | - | - | - | not enough trades |
| choch+fvg | long | limit | 427 | 33 | -0.02 | +0.09 | 0.18 | 0.515 | no edge in training |
| choch+fvg | short | limit | 414 | 30 | -0.12 | +0.05 | 0.16 | 0.649 | no edge in training |
| climax_reversal | long | market | 49 | - | - | - | - | - | not enough trades |
| climax_reversal | short | market | 42 | - | - | - | - | - | not enough trades |
| compression+sweep | long | market | 36 | - | - | - | - | - | not enough trades |
| compression+sweep | short | market | 40 | - | - | - | - | - | not enough trades |
| compression_breakout | long | market | 14 | - | - | - | - | - | not enough trades |
| compression_breakout | short | market | 17 | - | - | - | - | - | not enough trades |
| consecutive_expansion | long | market | 515 | 39 | +0.11 | +0.01 | 0.18 | 0.862 | no edge in training |
| consecutive_expansion | short | market | 476 | 31 | -0.14 | -0.04 | 0.17 | 1.000 | no edge in training |
| consecutive_fvg | long | limit | 256 | 36 | +0.02 | -0.02 | 0.21 | 0.969 | no edge in training |
| consecutive_fvg | short | limit | 208 | 33 | -0.10 | +0.02 | 0.24 | 0.862 | no edge in training |
| crab | long | market | 3 | - | - | - | - | - | not enough trades |
| crab | short | market | 1 | - | - | - | - | - | not enough trades |
| creek_breakout | long | market | 22 | - | - | - | - | - | not enough trades |
| cup_and_handle | long | market | 3 | - | - | - | - | - | not enough trades |
| cypher | long | market | 1 | - | - | - | - | - | not enough trades |
| cypher | short | market | 2 | - | - | - | - | - | not enough trades |
| dark_cloud_cover | short | market | 157 | 35 | +0.04 | +0.15 | 0.27 | 0.500 | no edge in training |
| deep_crab | long | market | 5 | - | - | - | - | - | not enough trades |
| deep_crab | short | market | 3 | - | - | - | - | - | not enough trades |
| deep_retracement | long | market | 49 | - | - | - | - | - | not enough trades |
| deep_retracement | short | market | 59 | - | - | - | - | - | not enough trades |
| demand_to_supply_flip | short | limit | 161 | 33 | -0.02 | +0.15 | 0.28 | 0.500 | no edge in training |
| demand_zone | long | limit | 175 | 35 | +0.04 | +0.11 | 0.27 | 0.570 | no edge in training |
| demand_zone|swing:bias | long | limit | 108 | 28 | -0.17 | -0.10 | 0.31 | 1.000 | no edge in training |
| demand_zone|swing:bias+context | long | limit | 82 | - | - | - | - | - | not enough trades |
| demand_zone|swing:counter | long | limit | 67 | - | - | - | - | - | not enough trades |
| demand_zone|swing:full | long | limit | 72 | - | - | - | - | - | not enough trades |
| desc_triangle_breakdown | short | market | 38 | - | - | - | - | - | not enough trades |
| displacement | long | market | 240 | 38 | +0.07 | -0.06 | 0.21 | 1.000 | no edge in training |
| displacement | short | market | 252 | 38 | -0.00 | +0.12 | 0.20 | 0.450 | no edge in training |
| displacement_imbalance | long | limit | 192 | 36 | +0.02 | +0.01 | 0.25 | 0.864 | no edge in training |
| displacement_imbalance | short | limit | 202 | 34 | -0.02 | +0.15 | 0.24 | 0.443 | no edge in training |
| double_bottom | long | market | 41 | - | - | - | - | - | not enough trades |
| double_top | short | market | 40 | - | - | - | - | - | not enough trades |
| dragonfly_doji | long | market | 85 | - | - | - | - | - | not enough trades |
| elliott_impulse | long | market | 59 | - | - | - | - | - | not enough trades |
| elliott_impulse | short | market | 90 | - | - | - | - | - | not enough trades |
| elliott_wave5 | long | market | 121 | 44 | +0.02 | -0.13 | 0.27 | 0.992 | no edge in training |
| elliott_wave5 | short | market | 81 | - | - | - | - | - | not enough trades |
| ema_bounce | long | market | 501 | 34 | +0.01 | +0.06 | 0.19 | 0.656 | no edge in training |
| ema_bounce | short | market | 455 | 32 | -0.06 | +0.08 | 0.19 | 0.580 | no edge in training |
| engulfing_bear | short | market | 1,190 | 32 | -0.08 | +0.03 | 0.11 | 0.659 | no edge in training |
| engulfing_bear|swing:bias | short | market | 553 | 31 | -0.08 | +0.01 | 0.17 | 0.862 | no edge in training |
| engulfing_bear|swing:bias+context | short | market | 152 | 38 | +0.08 | +0.01 | 0.33 | 0.873 | no edge in training |
| engulfing_bear|swing:counter | short | market | 637 | 32 | -0.08 | +0.06 | 0.14 | 0.596 | no edge in training |
| engulfing_bear|swing:full | short | market | 55 | - | - | - | - | - | not enough trades |
| engulfing_bull | long | market | 1,267 | 36 | +0.05 | +0.05 | 0.11 | 0.539 | no edge in training |
| engulfing_bull|swing:bias | long | market | 702 | 35 | +0.02 | -0.00 | 0.14 | 0.903 | no edge in training |
| engulfing_bull|swing:bias+context | long | market | 546 | 36 | +0.05 | -0.01 | 0.16 | 0.929 | no edge in training |
| engulfing_bull|swing:counter | long | market | 565 | 37 | +0.08 | +0.13 | 0.17 | 0.320 | no edge in training |
| engulfing_bull|swing:full | long | market | 236 | 37 | +0.07 | -0.02 | 0.23 | 0.955 | no edge in training |
| equal_highs | short | market | 158 | 36 | +0.08 | +0.18 | 0.29 | 0.435 | no edge in training |
| equal_highs+displacement | short | market | 47 | - | - | - | - | - | not enough trades |
| equal_lows | long | market | 160 | 36 | +0.06 | +0.07 | 0.29 | 0.734 | no edge in training |
| equal_lows+displacement | long | market | 60 | - | - | - | - | - | not enough trades |
| evening_doji_star | short | market | 129 | 30 | -0.12 | -0.01 | 0.29 | 0.929 | no edge in training |
| evening_star | short | market | 287 | 30 | -0.13 | -0.03 | 0.21 | 0.973 | no edge in training |
| exhaustion_sequence | long | market | 26 | - | - | - | - | - | not enough trades |
| exhaustion_sequence | short | market | 35 | - | - | - | - | - | not enough trades |
| external_bos | long | market | 294 | 44 | +0.13 | -0.06 | 0.21 | 1.000 | no edge in training |
| external_bos | short | market | 211 | 43 | +0.03 | +0.09 | 0.24 | 0.616 | no edge in training |
| external_sweep | long | market | 438 | 37 | +0.12 | +0.18 | 0.19 | 0.156 | no edge in training |
| external_sweep | short | market | 419 | 30 | -0.12 | +0.03 | 0.19 | 0.797 | no edge in training |
| failed_bos | long | market | 311 | 38 | +0.10 | +0.07 | 0.20 | 0.639 | no edge in training |
| failed_bos | short | market | 336 | 33 | -0.05 | +0.08 | 0.18 | 0.551 | no edge in training |
| failed_breakout | long | market | 218 | 39 | +0.11 | +0.07 | 0.25 | 0.689 | no edge in training |
| failed_breakout | short | market | 179 | 28 | -0.21 | -0.09 | 0.24 | 1.000 | no edge in training |
| failed_breakout+reclaim | long | market | 40 | - | - | - | - | - | not enough trades |
| failed_breakout+reclaim | short | market | 42 | - | - | - | - | - | not enough trades |
| failed_breakout|swing:bias | long | market | 100 | 42 | +0.26 | +0.20 | 0.39 | 0.539 | no edge in training |
| failed_breakout|swing:bias | short | market | 98 | - | - | - | - | - | not enough trades |
| failed_breakout|swing:bias+context | long | market | 83 | - | - | - | - | - | not enough trades |
| failed_breakout|swing:bias+context | short | market | 21 | - | - | - | - | - | not enough trades |
| failed_breakout|swing:counter | long | market | 118 | 36 | -0.01 | -0.03 | 0.32 | 0.963 | no edge in training |
| failed_breakout|swing:counter | short | market | 81 | - | - | - | - | - | not enough trades |
| failed_breakout|swing:full | long | market | 25 | - | - | - | - | - | not enough trades |
| failed_breakout|swing:full | short | market | 5 | - | - | - | - | - | not enough trades |
| failed_momentum_breakout | long | market | 235 | 34 | -0.01 | -0.03 | 0.22 | 0.993 | no edge in training |
| failed_momentum_breakout | short | market | 329 | 31 | -0.07 | +0.08 | 0.19 | 0.554 | no edge in training |
| failed_sweep | long | market | 343 | 37 | +0.03 | -0.10 | 0.21 | 1.000 | no edge in training |
| failed_sweep | short | market | 288 | 36 | -0.05 | +0.05 | 0.21 | 0.734 | no edge in training |
| failed_swing | long | market | 812 | 45 | +0.14 | -0.02 | 0.15 | 0.987 | no edge in training |
| failed_swing | short | market | 630 | 38 | -0.04 | +0.06 | 0.16 | 0.639 | no edge in training |
| falling_channel_break | long | market | 95 | - | - | - | - | - | not enough trades |
| falling_three_methods | short | market | 46 | - | - | - | - | - | not enough trades |
| falling_wedge_breakout | long | market | 106 | 46 | +0.23 | +0.19 | 0.34 | 0.415 | no edge in training |
| fib_extension | long | market | 238 | 51 | +0.15 | -0.05 | 0.20 | 0.922 | no edge in training |
| fib_extension | short | market | 151 | 44 | -0.01 | +0.09 | 0.25 | 0.544 | no edge in training |
| fib_retracement | long | market | 118 | 42 | +0.19 | +0.15 | 0.34 | 0.507 | no edge in training |
| fib_retracement | short | market | 89 | - | - | - | - | - | not enough trades |
| fvg | long | limit | 1,350 | 32 | -0.05 | +0.07 | 0.10 | 0.320 | no edge in training |
| fvg | short | limit | 1,119 | 29 | -0.12 | +0.05 | 0.10 | 0.515 | no edge in training |
| fvg_after_sweep | long | limit | 167 | 40 | +0.16 | +0.29 | 0.28 | 0.133 | no edge in training |
| fvg_after_sweep | short | limit | 123 | 32 | -0.05 | +0.15 | 0.33 | 0.539 | no edge in training |
| fvg_continuation | long | limit | 986 | 32 | -0.04 | +0.08 | 0.11 | 0.378 | no edge in training |
| fvg_continuation | short | limit | 795 | 30 | -0.13 | +0.04 | 0.12 | 0.640 | no edge in training |
| fvg_formation | long | market | 1,545 | 34 | -0.00 | -0.02 | 0.10 | 1.000 | no edge in training |
| fvg_formation | short | market | 1,271 | 31 | -0.10 | -0.00 | 0.11 | 0.895 | no edge in training |
| fvg_reversal | long | limit | 364 | 31 | -0.08 | +0.06 | 0.17 | 0.656 | no edge in training |
| fvg_reversal | short | limit | 324 | 29 | -0.12 | +0.08 | 0.19 | 0.564 | no edge in training |
| fvg_with_bos | long | limit | 351 | 32 | -0.05 | +0.08 | 0.20 | 0.603 | no edge in training |
| fvg_with_bos | short | limit | 273 | 30 | -0.11 | +0.05 | 0.22 | 0.761 | no edge in training |
| fvg_with_choch | long | limit | 259 | 36 | +0.04 | +0.15 | 0.23 | 0.388 | no edge in training |
| fvg_with_choch | short | limit | 280 | 35 | +0.03 | +0.20 | 0.21 | 0.192 | no edge in training |
| fvg|swing:bias | long | limit | 784 | 31 | -0.08 | +0.04 | 0.12 | 0.639 | no edge in training |
| fvg|swing:bias | short | limit | 515 | 30 | -0.10 | +0.04 | 0.15 | 0.684 | no edge in training |
| fvg|swing:bias+context | long | limit | 626 | 31 | -0.09 | +0.03 | 0.13 | 0.770 | no edge in training |
| fvg|swing:bias+context | short | limit | 142 | 27 | -0.19 | -0.13 | 0.31 | 1.000 | no edge in training |
| fvg|swing:counter | long | limit | 566 | 33 | -0.02 | +0.11 | 0.14 | 0.320 | no edge in training |
| fvg|swing:counter | short | limit | 604 | 29 | -0.14 | +0.06 | 0.13 | 0.550 | no edge in training |
| fvg|swing:full | long | limit | 329 | 34 | +0.00 | +0.12 | 0.20 | 0.450 | no edge in training |
| fvg|swing:full | short | limit | 80 | - | - | - | - | - | not enough trades |
| gap_continuation | long | market | 18 | - | - | - | - | - | not enough trades |
| gap_continuation | short | market | 11 | - | - | - | - | - | not enough trades |
| gap_fade | long | market | 13 | - | - | - | - | - | not enough trades |
| gap_fade | short | market | 20 | - | - | - | - | - | not enough trades |
| gartley | long | market | 4 | - | - | - | - | - | not enough trades |
| gartley | short | market | 3 | - | - | - | - | - | not enough trades |
| golden_pullback | long | market | 61 | - | - | - | - | - | not enough trades |
| golden_pullback | short | market | 32 | - | - | - | - | - | not enough trades |
| grab_reversal | long | market | 222 | 37 | +0.09 | +0.02 | 0.26 | 0.862 | no edge in training |
| grab_reversal | short | market | 216 | 31 | -0.12 | +0.01 | 0.25 | 0.862 | no edge in training |
| grab_reversal+order_block | long | limit | 61 | - | - | - | - | - | not enough trades |
| grab_reversal+order_block | short | limit | 60 | - | - | - | - | - | not enough trades |
| grab_reversal|swing:bias | long | market | 122 | 39 | +0.19 | +0.09 | 0.35 | 0.708 | no edge in training |
| grab_reversal|swing:bias | short | market | 96 | - | - | - | - | - | not enough trades |
| grab_reversal|swing:bias+context | long | market | 99 | - | - | - | - | - | not enough trades |
| grab_reversal|swing:bias+context | short | market | 20 | - | - | - | - | - | not enough trades |
| grab_reversal|swing:counter | long | market | 100 | 35 | -0.02 | -0.07 | 0.38 | 1.000 | no edge in training |
| grab_reversal|swing:counter | short | market | 120 | 30 | -0.17 | -0.02 | 0.32 | 0.929 | no edge in training |
| grab_reversal|swing:full | long | market | 59 | - | - | - | - | - | not enough trades |
| grab_reversal|swing:full | short | market | 15 | - | - | - | - | - | not enough trades |
| gravestone_doji | short | market | 46 | - | - | - | - | - | not enough trades |
| hammer | long | market | 368 | 30 | -0.12 | -0.06 | 0.19 | 1.000 | no edge in training |
| hanging_man | short | market | 406 | 25 | -0.26 | -0.01 | 0.17 | 0.938 | no edge in training |
| harami_bear | short | market | 601 | 29 | -0.12 | +0.02 | 0.14 | 0.834 | no edge in training |
| harami_bull | long | market | 602 | 30 | -0.12 | -0.05 | 0.14 | 1.000 | no edge in training |
| head_and_shoulders | short | market | 6 | - | - | - | - | - | not enough trades |
| higher_low | long | market | 1,086 | 38 | +0.07 | +0.02 | 0.12 | 0.766 | no edge in training |
| higher_low+bos | long | market | 342 | 42 | +0.12 | -0.05 | 0.21 | 1.000 | no edge in training |
| ice_breakdown | short | market | 14 | - | - | - | - | - | not enough trades |
| inside_bar_bear | short | market | 1,883 | 29 | -0.13 | +0.01 | 0.09 | 0.805 | no edge in training |
| inside_bar_bull | long | market | 1,887 | 33 | -0.03 | +0.00 | 0.09 | 0.887 | no edge in training |
| inside_compression+nr_breakout | long | market | 220 | 35 | +0.05 | +0.11 | 0.26 | 0.583 | no edge in training |
| inside_compression+nr_breakout | short | market | 163 | 29 | -0.12 | -0.01 | 0.28 | 0.924 | no edge in training |
| internal_bos | long | market | 569 | 42 | +0.11 | -0.04 | 0.17 | 1.000 | no edge in training |
| internal_bos | short | market | 421 | 35 | -0.10 | -0.00 | 0.18 | 0.891 | no edge in training |
| internal_sweep | long | market | 1,072 | 33 | -0.01 | +0.06 | 0.13 | 0.539 | no edge in training |
| internal_sweep | short | market | 1,036 | 27 | -0.20 | -0.04 | 0.12 | 1.000 | no edge in training |
| inverse_cup_and_handle | short | market | 6 | - | - | - | - | - | not enough trades |
| inverse_fvg | long | limit | 929 | 31 | -0.10 | +0.02 | 0.11 | 0.808 | no edge in training |
| inverse_fvg | short | limit | 1,071 | 27 | -0.21 | -0.02 | 0.10 | 0.993 | no edge in training |
| inverse_head_and_shoulders | long | market | 10 | - | - | - | - | - | not enough trades |
| inverted_hammer | long | market | 225 | 28 | -0.15 | +0.02 | 0.24 | 0.853 | no edge in training |
| kicker | long | market | 4 | - | - | - | - | - | not enough trades |
| kmeans_c00 | long | market | 545 | 36 | +0.08 | +0.09 | 0.16 | 0.981 | no edge in training |
| kmeans_c00 | short | market | 545 | 28 | -0.18 | -0.09 | 0.15 | 1.000 | no edge in training |
| kmeans_c01 | long | market | 1,111 | 33 | -0.02 | -0.00 | 0.12 | 1.000 | no edge in training |
| kmeans_c01 | short | market | 1,111 | 30 | -0.09 | +0.02 | 0.11 | 1.000 | no edge in training |
| kmeans_c02 | long | market | 724 | 31 | -0.06 | -0.04 | 0.14 | 1.000 | no edge in training |
| kmeans_c02 | short | market | 724 | 26 | -0.22 | -0.11 | 0.12 | 1.000 | no edge in training |
| kmeans_c03 | long | market | 689 | 31 | -0.08 | -0.07 | 0.14 | 1.000 | no edge in training |
| kmeans_c03 | short | market | 689 | 32 | -0.05 | +0.04 | 0.14 | 1.000 | no edge in training |
| kmeans_c04 | long | market | 704 | 34 | +0.01 | +0.01 | 0.14 | 1.000 | no edge in training |
| kmeans_c04 | short | market | 704 | 30 | -0.09 | +0.02 | 0.13 | 1.000 | no edge in training |
| kmeans_c05 | long | market | 1,046 | 35 | +0.05 | +0.07 | 0.12 | 0.981 | no edge in training |
| kmeans_c05 | short | market | 1,046 | 31 | -0.06 | +0.05 | 0.12 | 1.000 | no edge in training |
| kmeans_c06 | long | market | 686 | 29 | -0.12 | -0.12 | 0.13 | 1.000 | no edge in training |
| kmeans_c06 | short | market | 686 | 30 | -0.12 | +0.01 | 0.14 | 1.000 | no edge in training |
| kmeans_c07 | long | market | 731 | 32 | -0.03 | -0.01 | 0.14 | 1.000 | no edge in training |
| kmeans_c07 | short | market | 731 | 27 | -0.20 | -0.08 | 0.12 | 1.000 | no edge in training |
| kmeans_c08 | long | market | 592 | 33 | -0.01 | +0.00 | 0.15 | 1.000 | no edge in training |
| kmeans_c08 | short | market | 592 | 27 | -0.18 | -0.06 | 0.15 | 1.000 | no edge in training |
| kmeans_c09 | long | market | 592 | 32 | -0.03 | -0.04 | 0.15 | 1.000 | no edge in training |
| kmeans_c09 | short | market | 592 | 28 | -0.15 | -0.03 | 0.15 | 1.000 | no edge in training |
| kmeans_c10 | long | market | 1,064 | 35 | +0.06 | +0.08 | 0.13 | 0.981 | no edge in training |
| kmeans_c10 | short | market | 1,064 | 29 | -0.12 | -0.03 | 0.12 | 1.000 | no edge in training |
| kmeans_c11 | long | market | 747 | 32 | -0.04 | -0.03 | 0.13 | 1.000 | no edge in training |
| kmeans_c11 | short | market | 747 | 29 | -0.13 | -0.02 | 0.13 | 1.000 | no edge in training |
| kmeans_c12 | long | market | 759 | 36 | +0.06 | +0.06 | 0.13 | 1.000 | no edge in training |
| kmeans_c12 | short | market | 759 | 26 | -0.22 | -0.09 | 0.12 | 1.000 | no edge in training |
| kmeans_c13 | long | market | 1,042 | 35 | +0.05 | +0.06 | 0.13 | 1.000 | no edge in training |
| kmeans_c13 | short | market | 1,042 | 32 | -0.05 | +0.07 | 0.12 | 0.981 | no edge in training |
| kmeans_c14 | long | market | 883 | 36 | +0.09 | +0.09 | 0.13 | 0.981 | no edge in training |
| kmeans_c14 | short | market | 883 | 29 | -0.14 | -0.03 | 0.13 | 1.000 | no edge in training |
| kmeans_c15 | long | market | 925 | 34 | +0.03 | +0.05 | 0.14 | 1.000 | no edge in training |
| kmeans_c15 | short | market | 925 | 28 | -0.15 | -0.03 | 0.13 | 1.000 | no edge in training |
| kmeans_c16 | long | market | 524 | 31 | -0.06 | -0.05 | 0.15 | 1.000 | no edge in training |
| kmeans_c16 | short | market | 524 | 31 | -0.08 | +0.02 | 0.15 | 1.000 | no edge in training |
| kmeans_c17 | long | market | 686 | 31 | -0.08 | -0.06 | 0.14 | 1.000 | no edge in training |
| kmeans_c17 | short | market | 686 | 32 | -0.05 | +0.03 | 0.13 | 1.000 | no edge in training |
| kmeans_c18 | long | market | 576 | 34 | +0.01 | +0.01 | 0.15 | 1.000 | no edge in training |
| kmeans_c18 | short | market | 576 | 23 | -0.30 | -0.16 | 0.14 | 1.000 | no edge in training |
| kmeans_c19 | long | market | 724 | 27 | -0.21 | -0.22 | 0.13 | 1.000 | no edge in training |
| kmeans_c19 | short | market | 724 | 34 | +0.01 | +0.12 | 0.13 | 0.981 | no edge in training |
| kmeans_c20 | long | market | 1,157 | 33 | -0.01 | +0.00 | 0.12 | 1.000 | no edge in training |
| kmeans_c20 | short | market | 1,157 | 32 | -0.04 | +0.05 | 0.12 | 1.000 | no edge in training |
| kmeans_c21 | long | market | 422 | 30 | -0.12 | -0.11 | 0.17 | 1.000 | no edge in training |
| kmeans_c21 | short | market | 422 | 31 | -0.07 | +0.06 | 0.17 | 1.000 | no edge in training |
| kmeans_c22 | long | market | 567 | 29 | -0.14 | -0.11 | 0.14 | 1.000 | no edge in training |
| kmeans_c22 | short | market | 567 | 32 | -0.03 | +0.06 | 0.15 | 1.000 | no edge in training |
| kmeans_c23 | long | market | 621 | 33 | -0.03 | -0.01 | 0.14 | 1.000 | no edge in training |
| kmeans_c23 | short | market | 621 | 29 | -0.12 | -0.05 | 0.14 | 1.000 | no edge in training |
| last_point_of_supply | short | market | 1 | - | - | - | - | - | not enough trades |
| last_point_of_support | long | market | 1 | - | - | - | - | - | not enough trades |
| liquidity_sweep | long | market | 759 | 34 | +0.02 | +0.08 | 0.15 | 0.474 | no edge in training |
| liquidity_sweep | short | market | 735 | 28 | -0.18 | -0.02 | 0.14 | 0.970 | no edge in training |
| liquidity_sweep|swing:bias | long | market | 438 | 33 | -0.01 | +0.04 | 0.19 | 0.759 | no edge in training |
| liquidity_sweep|swing:bias | short | market | 340 | 27 | -0.21 | -0.07 | 0.20 | 1.000 | no edge in training |
| liquidity_sweep|swing:bias+context | long | market | 326 | 33 | -0.02 | +0.00 | 0.22 | 0.885 | no edge in training |
| liquidity_sweep|swing:bias+context | short | market | 69 | - | - | - | - | - | not enough trades |
| liquidity_sweep|swing:counter | long | market | 321 | 35 | +0.06 | +0.14 | 0.23 | 0.413 | no edge in training |
| liquidity_sweep|swing:counter | short | market | 395 | 29 | -0.15 | +0.03 | 0.20 | 0.809 | no edge in training |
| liquidity_sweep|swing:full | long | market | 18 | - | - | - | - | - | not enough trades |
| liquidity_sweep|swing:full | short | market | 6 | - | - | - | - | - | not enough trades |
| lower_high | short | market | 964 | 32 | -0.08 | +0.04 | 0.12 | 0.640 | no edge in training |
| lower_high+bos | short | market | 240 | 39 | +0.02 | +0.11 | 0.23 | 0.549 | no edge in training |
| market_structure_shift | long | market | 161 | 47 | +0.17 | +0.04 | 0.25 | 0.805 | no edge in training |
| market_structure_shift | short | market | 139 | 37 | -0.12 | -0.02 | 0.24 | 0.935 | no edge in training |
| market_structure_shift|swing:bias | long | market | 92 | - | - | - | - | - | not enough trades |
| market_structure_shift|swing:bias | short | market | 58 | - | - | - | - | - | not enough trades |
| market_structure_shift|swing:bias+context | long | market | 75 | - | - | - | - | - | not enough trades |
| market_structure_shift|swing:bias+context | short | market | 12 | - | - | - | - | - | not enough trades |
| market_structure_shift|swing:counter | long | market | 69 | - | - | - | - | - | not enough trades |
| market_structure_shift|swing:counter | short | market | 81 | - | - | - | - | - | not enough trades |
| market_structure_shift|swing:full | long | market | 69 | - | - | - | - | - | not enough trades |
| market_structure_shift|swing:full | short | market | 9 | - | - | - | - | - | not enough trades |
| marubozu_bear | short | market | 100 | 36 | +0.01 | +0.14 | 0.34 | 0.603 | no edge in training |
| marubozu_bull | long | market | 133 | 35 | +0.02 | -0.03 | 0.29 | 0.947 | no edge in training |
| momentum_continuation | long | market | 282 | 47 | +0.15 | +0.03 | 0.28 | 0.832 | no edge in training |
| momentum_continuation | short | market | 247 | 36 | -0.20 | -0.08 | 0.23 | 1.000 | no edge in training |
| momentum_exhaustion | long | market | 40 | - | - | - | - | - | not enough trades |
| momentum_exhaustion | short | market | 45 | - | - | - | - | - | not enough trades |
| morning_doji_star | long | market | 102 | 39 | +0.16 | +0.11 | 0.35 | 0.660 | no edge in training |
| morning_star | long | market | 280 | 38 | +0.12 | +0.09 | 0.21 | 0.591 | no edge in training |
| multi_touch_rejection | long | market | 128 | 31 | -0.07 | -0.04 | 0.32 | 0.985 | no edge in training |
| multi_touch_rejection | short | market | 124 | 35 | +0.06 | +0.20 | 0.36 | 0.474 | no edge in training |
| multiple_sweeps | long | market | 116 | 41 | +0.25 | +0.33 | 0.36 | 0.204 | no edge in training |
| multiple_sweeps | short | market | 117 | 24 | -0.31 | -0.14 | 0.31 | 1.000 | no edge in training |
| nr_breakout | long | market | 834 | 35 | +0.03 | +0.06 | 0.12 | 0.539 | no edge in training |
| nr_breakout | short | market | 681 | 29 | -0.13 | -0.03 | 0.13 | 1.000 | no edge in training |
| order_block | long | limit | 493 | 35 | +0.04 | +0.07 | 0.17 | 0.591 | no edge in training |
| order_block | short | limit | 432 | 30 | -0.14 | +0.05 | 0.17 | 0.699 | no edge in training |
| order_block_bos | long | limit | 285 | 33 | -0.00 | +0.03 | 0.22 | 0.806 | no edge in training |
| order_block_bos | short | limit | 197 | 28 | -0.19 | -0.02 | 0.24 | 0.935 | no edge in training |
| order_block_choch | long | limit | 208 | 38 | +0.10 | +0.12 | 0.25 | 0.539 | no edge in training |
| order_block_choch | short | limit | 235 | 31 | -0.09 | +0.10 | 0.22 | 0.562 | no edge in training |
| order_block_fvg | long | limit | 195 | 35 | +0.02 | +0.07 | 0.26 | 0.707 | no edge in training |
| order_block_fvg | short | limit | 169 | 34 | -0.04 | +0.13 | 0.28 | 0.550 | no edge in training |
| order_block_sweep | long | limit | 53 | - | - | - | - | - | not enough trades |
| order_block_sweep | short | limit | 73 | - | - | - | - | - | not enough trades |
| order_block|swing:bias | long | limit | 297 | 34 | -0.00 | +0.02 | 0.20 | 0.859 | no edge in training |
| order_block|swing:bias | short | limit | 190 | 30 | -0.12 | +0.03 | 0.26 | 0.845 | no edge in training |
| order_block|swing:bias+context | long | limit | 245 | 35 | +0.02 | +0.02 | 0.22 | 0.849 | no edge in training |
| order_block|swing:bias+context | short | limit | 50 | - | - | - | - | - | not enough trades |
| order_block|swing:counter | long | limit | 196 | 38 | +0.11 | +0.15 | 0.28 | 0.515 | no edge in training |
| order_block|swing:counter | short | limit | 242 | 29 | -0.15 | +0.06 | 0.22 | 0.701 | no edge in training |
| order_block|swing:full | long | limit | 197 | 34 | +0.01 | +0.01 | 0.25 | 0.876 | no edge in training |
| order_block|swing:full | short | limit | 40 | - | - | - | - | - | not enough trades |
| outside_bar_bear | short | market | 1,295 | 29 | -0.16 | -0.04 | 0.10 | 1.000 | no edge in training |
| outside_bar_bull | long | market | 1,394 | 34 | -0.01 | +0.00 | 0.10 | 0.888 | no edge in training |
| pd_high_sweep | short | market | 812 | 28 | -0.16 | +0.00 | 0.12 | 0.878 | no edge in training |
| pd_high_sweep|swing:bias | short | market | 358 | 27 | -0.19 | -0.05 | 0.18 | 1.000 | no edge in training |
| pd_high_sweep|swing:bias+context | short | market | 78 | - | - | - | - | - | not enough trades |
| pd_high_sweep|swing:counter | short | market | 454 | 29 | -0.13 | +0.05 | 0.16 | 0.698 | no edge in training |
| pd_high_sweep|swing:full | short | market | 8 | - | - | - | - | - | not enough trades |
| pd_low_sweep | long | market | 839 | 30 | -0.09 | -0.01 | 0.12 | 0.939 | no edge in training |
| pd_low_sweep|swing:bias | long | market | 450 | 31 | -0.06 | +0.00 | 0.17 | 0.888 | no edge in training |
| pd_low_sweep|swing:bias+context | long | market | 351 | 32 | -0.04 | -0.00 | 0.19 | 0.897 | no edge in training |
| pd_low_sweep|swing:counter | long | market | 389 | 29 | -0.13 | -0.02 | 0.18 | 0.970 | no edge in training |
| pd_low_sweep|swing:full | long | market | 31 | - | - | - | - | - | not enough trades |
| pdh_sweep+choch | short | market | 156 | 33 | -0.09 | +0.02 | 0.23 | 0.851 | no edge in training |
| pdh_sweep+engulfing | short | market | 249 | 26 | -0.26 | -0.11 | 0.20 | 1.000 | no edge in training |
| pdh_sweep+fvg | short | limit | 408 | 27 | -0.18 | -0.01 | 0.16 | 0.939 | no edge in training |
| pdl_sweep+choch | long | market | 163 | 45 | +0.20 | +0.08 | 0.23 | 0.649 | no edge in training |
| pdl_sweep+engulfing | long | market | 240 | 37 | +0.08 | +0.08 | 0.23 | 0.638 | no edge in training |
| pdl_sweep+fvg | long | limit | 539 | 33 | -0.02 | +0.10 | 0.16 | 0.368 | no edge in training |
| piercing | long | market | 168 | 33 | +0.01 | +0.06 | 0.28 | 0.734 | no edge in training |
| pin_bar_bear | short | market | 592 | 30 | -0.09 | +0.02 | 0.15 | 0.805 | no edge in training |
| pin_bar_bear|swing:bias | short | market | 264 | 31 | -0.08 | +0.00 | 0.23 | 0.888 | no edge in training |
| pin_bar_bear|swing:bias+context | short | market | 77 | - | - | - | - | - | not enough trades |
| pin_bar_bear|swing:counter | short | market | 328 | 30 | -0.10 | +0.04 | 0.19 | 0.767 | no edge in training |
| pin_bar_bear|swing:full | short | market | 7 | - | - | - | - | - | not enough trades |
| pin_bar_bull | long | market | 848 | 31 | -0.07 | -0.02 | 0.13 | 0.982 | no edge in training |
| pin_bar_bull|swing:bias | long | market | 492 | 32 | -0.04 | +0.01 | 0.18 | 0.862 | no edge in training |
| pin_bar_bull|swing:bias+context | long | market | 392 | 35 | +0.04 | +0.07 | 0.21 | 0.637 | no edge in training |
| pin_bar_bull|swing:counter | long | market | 356 | 29 | -0.12 | -0.06 | 0.19 | 1.000 | no edge in training |
| pin_bar_bull|swing:full | long | market | 50 | - | - | - | - | - | not enough trades |
| pm_high_sweep | short | market | 34 | - | - | - | - | - | not enough trades |
| pm_low_sweep | long | market | 20 | - | - | - | - | - | not enough trades |
| preliminary_supply | short | market | 105 | 36 | +0.07 | +0.20 | 0.35 | 0.415 | no edge in training |
| preliminary_support | long | market | 74 | - | - | - | - | - | not enough trades |
| pw_high_sweep | short | market | 127 | 31 | -0.06 | +0.10 | 0.31 | 0.647 | no edge in training |
| pw_low_sweep | long | market | 113 | 35 | +0.02 | +0.11 | 0.33 | 0.640 | no edge in training |
| range_boundary_rejection | long | market | 375 | 32 | -0.06 | +0.02 | 0.17 | 0.845 | no edge in training |
| range_boundary_rejection | short | market | 587 | 30 | -0.09 | +0.07 | 0.14 | 0.538 | no edge in training |
| range_midpoint_cross | long | market | 492 | 38 | +0.09 | +0.03 | 0.18 | 0.769 | no edge in training |
| range_midpoint_cross | short | market | 505 | 31 | -0.16 | -0.06 | 0.16 | 1.000 | no edge in training |
| range_to_trend | long | market | 327 | 43 | +0.08 | -0.11 | 0.23 | 1.000 | no edge in training |
| range_to_trend | short | market | 216 | 38 | -0.07 | +0.03 | 0.21 | 0.808 | no edge in training |
| reclaimed_order_block | long | market | 247 | 44 | +0.14 | +0.03 | 0.21 | 0.797 | no edge in training |
| reclaimed_order_block | short | market | 183 | 37 | -0.12 | -0.02 | 0.24 | 0.940 | no edge in training |
| rectangle_breakout | long | market | 45 | - | - | - | - | - | not enough trades |
| rectangle_breakout | short | market | 37 | - | - | - | - | - | not enough trades |
| rejection_bear | short | market | 595 | 29 | -0.13 | -0.01 | 0.14 | 0.938 | no edge in training |
| rejection_bear+bos | short | market | 58 | - | - | - | - | - | not enough trades |
| rejection_block | long | limit | 526 | 30 | -0.11 | -0.03 | 0.15 | 1.000 | no edge in training |
| rejection_block | short | limit | 500 | 30 | -0.12 | +0.05 | 0.15 | 0.660 | no edge in training |
| rejection_bull | long | market | 643 | 34 | +0.02 | +0.04 | 0.14 | 0.708 | no edge in training |
| rejection_bull+bos | long | market | 97 | - | - | - | - | - | not enough trades |
| resistance_rejection | short | market | 175 | 37 | +0.11 | +0.26 | 0.28 | 0.204 | no edge in training |
| resistance_rejection+engulfing | short | market | 29 | - | - | - | - | - | not enough trades |
| resistance_rejection|swing:bias | short | market | 69 | - | - | - | - | - | not enough trades |
| resistance_rejection|swing:bias+context | short | market | 15 | - | - | - | - | - | not enough trades |
| resistance_rejection|swing:counter | short | market | 106 | 37 | +0.10 | +0.24 | 0.36 | 0.368 | no edge in training |
| resistance_rejection|swing:full | short | market | 3 | - | - | - | - | - | not enough trades |
| retest | long | market | 342 | 31 | -0.08 | -0.03 | 0.22 | 0.985 | no edge in training |
| retest | short | market | 309 | 35 | +0.04 | +0.20 | 0.20 | 0.132 | no edge in training |
| retest+momentum | long | market | 26 | - | - | - | - | - | not enough trades |
| retest+momentum | short | market | 43 | - | - | - | - | - | not enough trades |
| retest|swing:bias | long | market | 174 | 32 | -0.05 | +0.00 | 0.32 | 0.889 | no edge in training |
| retest|swing:bias | short | market | 164 | 36 | +0.05 | +0.18 | 0.26 | 0.335 | no edge in training |
| retest|swing:bias+context | long | market | 140 | 34 | -0.01 | +0.02 | 0.37 | 0.862 | no edge in training |
| retest|swing:bias+context | short | market | 29 | - | - | - | - | - | not enough trades |
| retest|swing:counter | long | market | 168 | 30 | -0.11 | -0.06 | 0.30 | 1.000 | no edge in training |
| retest|swing:counter | short | market | 145 | 34 | +0.02 | +0.21 | 0.30 | 0.335 | no edge in training |
| retest|swing:full | long | market | 32 | - | - | - | - | - | not enough trades |
| retest|swing:full | short | market | 7 | - | - | - | - | - | not enough trades |
| rising_channel_break | short | market | 99 | - | - | - | - | - | not enough trades |
| rising_three_methods | long | market | 48 | - | - | - | - | - | not enough trades |
| rising_wedge_breakdown | short | market | 148 | 35 | +0.02 | +0.16 | 0.29 | 0.415 | no edge in training |
| round100_reaction | long | market | 183 | 33 | -0.00 | +0.03 | 0.29 | 0.853 | no edge in training |
| round100_reaction | short | market | 172 | 30 | -0.13 | -0.00 | 0.28 | 0.893 | no edge in training |
| round10_reaction | long | market | 1,844 | 32 | -0.06 | +0.01 | 0.10 | 0.844 | no edge in training |
| round10_reaction | short | market | 1,660 | 30 | -0.11 | +0.02 | 0.09 | 0.782 | no edge in training |
| round50_reaction | long | market | 209 | 40 | +0.18 | +0.24 | 0.27 | 0.225 | no edge in training |
| round50_reaction | short | market | 208 | 35 | +0.02 | +0.18 | 0.27 | 0.368 | no edge in training |
| round_placebo_reaction | long | market | 2,459 | 31 | -0.09 | -0.03 | 0.08 | 1.000 | no edge in training |
| round_placebo_reaction | short | market | 2,299 | 29 | -0.13 | +0.01 | 0.08 | 0.805 | no edge in training |
| rounding_bottom | long | market | 8 | - | - | - | - | - | not enough trades |
| rounding_top | short | market | 22 | - | - | - | - | - | not enough trades |
| secondary_test | long | market | 17 | - | - | - | - | - | not enough trades |
| secondary_test | short | market | 26 | - | - | - | - | - | not enough trades |
| selling_climax | long | market | 121 | 31 | -0.11 | -0.05 | 0.30 | 0.890 | no edge in training |
| seq2_dm1-dm1 | long | market | 299 | 34 | +0.01 | +0.05 | 0.21 | 1.000 | no edge in training |
| seq2_dm1-dm1 | short | market | 299 | 29 | -0.12 | -0.04 | 0.22 | 1.000 | no edge in training |
| seq2_dm1-um3 | long | market | 423 | 38 | +0.15 | +0.15 | 0.19 | 0.981 | no edge in training |
| seq2_dm1-um3 | short | market | 423 | 29 | -0.14 | -0.04 | 0.17 | 1.000 | no edge in training |
| seq2_dm1-us2 | long | market | 225 | 31 | -0.08 | -0.06 | 0.23 | 1.000 | no edge in training |
| seq2_dm1-us2 | short | market | 225 | 32 | -0.03 | +0.06 | 0.23 | 1.000 | no edge in training |
| seq2_dm1-us3 | long | market | 221 | 32 | -0.05 | -0.04 | 0.24 | 1.000 | no edge in training |
| seq2_dm1-us3 | short | market | 221 | 26 | -0.23 | -0.13 | 0.22 | 1.000 | no edge in training |
| seq2_ds1-um3 | long | market | 229 | 35 | +0.05 | +0.06 | 0.25 | 1.000 | no edge in training |
| seq2_ds1-um3 | short | market | 229 | 27 | -0.19 | -0.11 | 0.22 | 1.000 | no edge in training |
| seq2_ds2-dm1 | long | market | 221 | 33 | -0.01 | +0.01 | 0.23 | 1.000 | no edge in training |
| seq2_ds2-dm1 | short | market | 221 | 31 | -0.06 | +0.04 | 0.24 | 1.000 | no edge in training |
| seq2_ds2-um3 | long | market | 247 | 31 | -0.07 | -0.06 | 0.21 | 1.000 | no edge in training |
| seq2_ds2-um3 | short | market | 247 | 30 | -0.11 | +0.00 | 0.23 | 1.000 | no edge in training |
| seq2_um3-dm1 | long | market | 417 | 30 | -0.11 | -0.11 | 0.17 | 1.000 | no edge in training |
| seq2_um3-dm1 | short | market | 417 | 32 | -0.04 | +0.06 | 0.18 | 1.000 | no edge in training |
| seq2_um3-ds1 | long | market | 251 | 33 | -0.02 | +0.00 | 0.24 | 1.000 | no edge in training |
| seq2_um3-ds1 | short | market | 251 | 30 | -0.10 | -0.02 | 0.23 | 1.000 | no edge in training |
| seq2_um3-ds2 | long | market | 258 | 32 | -0.05 | -0.04 | 0.22 | 1.000 | no edge in training |
| seq2_um3-ds2 | short | market | 258 | 26 | -0.22 | -0.10 | 0.21 | 1.000 | no edge in training |
| seq2_um3-um3 | long | market | 431 | 32 | -0.04 | -0.04 | 0.19 | 1.000 | no edge in training |
| seq2_um3-um3 | short | market | 431 | 28 | -0.15 | -0.04 | 0.17 | 1.000 | no edge in training |
| seq2_um3-us2 | long | market | 224 | 40 | +0.20 | +0.21 | 0.25 | 0.981 | no edge in training |
| seq2_um3-us2 | short | market | 224 | 30 | -0.10 | -0.01 | 0.23 | 1.000 | no edge in training |
| seq2_um3-us3 | long | market | 244 | 31 | -0.07 | -0.07 | 0.22 | 1.000 | no edge in training |
| seq2_um3-us3 | short | market | 244 | 30 | -0.12 | +0.01 | 0.22 | 1.000 | no edge in training |
| seq2_us2-um3 | long | market | 263 | 38 | +0.14 | +0.14 | 0.23 | 0.981 | no edge in training |
| seq2_us2-um3 | short | market | 263 | 30 | -0.09 | +0.03 | 0.22 | 1.000 | no edge in training |
| seq2_us3-dm1 | long | market | 222 | 32 | -0.06 | -0.05 | 0.24 | 1.000 | no edge in training |
| seq2_us3-dm1 | short | market | 222 | 30 | -0.09 | +0.01 | 0.24 | 1.000 | no edge in training |
| seq2_us3-um3 | long | market | 268 | 32 | -0.04 | -0.04 | 0.22 | 1.000 | no edge in training |
| seq2_us3-um3 | short | market | 268 | 32 | -0.04 | +0.08 | 0.22 | 1.000 | no edge in training |
| shark | long | market | 6 | - | - | - | - | - | not enough trades |
| shark | short | market | 6 | - | - | - | - | - | not enough trades |
| shooting_star | short | market | 281 | 30 | -0.11 | -0.01 | 0.20 | 0.927 | no edge in training |
| sign_of_strength | long | market | 6 | - | - | - | - | - | not enough trades |
| sign_of_weakness | short | market | 3 | - | - | - | - | - | not enough trades |
| squeeze+bos | long | market | 55 | - | - | - | - | - | not enough trades |
| squeeze+bos | short | market | 43 | - | - | - | - | - | not enough trades |
| squeeze_release | long | market | 174 | 40 | +0.05 | -0.13 | 0.24 | 1.000 | no edge in training |
| squeeze_release | short | market | 130 | 46 | +0.08 | +0.17 | 0.27 | 0.435 | no edge in training |
| strong_bear_sequence | short | market | 16 | - | - | - | - | - | not enough trades |
| strong_bull_sequence | long | market | 22 | - | - | - | - | - | not enough trades |
| strong_demand | long | limit | 37 | - | - | - | - | - | not enough trades |
| strong_supply | short | limit | 44 | - | - | - | - | - | not enough trades |
| structural_reclaim | long | market | 162 | 41 | +0.07 | -0.03 | 0.23 | 0.968 | no edge in training |
| structural_reclaim | short | market | 189 | 35 | -0.15 | -0.01 | 0.20 | 0.922 | no edge in training |
| supply_to_demand_flip | long | limit | 194 | 34 | +0.00 | +0.03 | 0.27 | 0.834 | no edge in training |
| supply_zone | short | limit | 193 | 33 | -0.00 | +0.20 | 0.24 | 0.265 | no edge in training |
| supply_zone|swing:bias | short | limit | 89 | - | - | - | - | - | not enough trades |
| supply_zone|swing:bias+context | short | limit | 18 | - | - | - | - | - | not enough trades |
| supply_zone|swing:counter | short | limit | 104 | 30 | -0.11 | +0.12 | 0.33 | 0.639 | no edge in training |
| supply_zone|swing:full | short | limit | 15 | - | - | - | - | - | not enough trades |
| support_rejection | long | market | 203 | 34 | +0.01 | +0.02 | 0.25 | 0.853 | no edge in training |
| support_rejection+engulfing | long | market | 32 | - | - | - | - | - | not enough trades |
| support_rejection|swing:bias | long | market | 78 | - | - | - | - | - | not enough trades |
| support_rejection|swing:bias+context | long | market | 59 | - | - | - | - | - | not enough trades |
| support_rejection|swing:counter | long | market | 125 | 33 | -0.02 | -0.00 | 0.30 | 0.903 | no edge in training |
| support_rejection|swing:full | long | market | 9 | - | - | - | - | - | not enough trades |
| sweep+bos | long | market | 67 | - | - | - | - | - | not enough trades |
| sweep+bos | short | market | 35 | - | - | - | - | - | not enough trades |
| sweep+choch | long | market | 108 | 45 | +0.20 | +0.07 | 0.28 | 0.708 | no edge in training |
| sweep+choch | short | market | 108 | 41 | +0.04 | +0.13 | 0.30 | 0.562 | no edge in training |
| sweep+double_bottom | long | market | 26 | - | - | - | - | - | not enough trades |
| sweep+double_top | short | market | 30 | - | - | - | - | - | not enough trades |
| sweep+mss | long | market | 73 | - | - | - | - | - | not enough trades |
| sweep+mss | short | market | 73 | - | - | - | - | - | not enough trades |
| sweep+order_block | long | limit | 100 | 33 | -0.03 | -0.03 | 0.35 | 0.955 | no edge in training |
| sweep+order_block | short | limit | 95 | - | - | - | - | - | not enough trades |
| sweep_reclaim | long | market | 148 | 36 | +0.05 | +0.02 | 0.29 | 0.853 | no edge in training |
| sweep_reclaim | short | market | 166 | 33 | -0.04 | +0.09 | 0.26 | 0.639 | no edge in training |
| sweep_to_bos | long | market | 198 | 46 | +0.16 | +0.00 | 0.26 | 0.885 | no edge in training |
| sweep_to_bos | short | market | 169 | 42 | +0.04 | +0.13 | 0.29 | 0.562 | no edge in training |
| sweep_to_bos|swing:bias | long | market | 111 | 44 | +0.12 | -0.05 | 0.33 | 1.000 | no edge in training |
| sweep_to_bos|swing:bias | short | market | 54 | - | - | - | - | - | not enough trades |
| sweep_to_bos|swing:bias+context | long | market | 92 | - | - | - | - | - | not enough trades |
| sweep_to_bos|swing:bias+context | short | market | 17 | - | - | - | - | - | not enough trades |
| sweep_to_bos|swing:counter | long | market | 87 | - | - | - | - | - | not enough trades |
| sweep_to_bos|swing:counter | short | market | 115 | 41 | -0.01 | +0.12 | 0.35 | 0.640 | no edge in training |
| sweep_to_bos|swing:full | long | market | 73 | - | - | - | - | - | not enough trades |
| sweep_to_bos|swing:full | short | market | 14 | - | - | - | - | - | not enough trades |
| swing_failure | long | market | 431 | 34 | +0.01 | +0.07 | 0.17 | 0.567 | no edge in training |
| swing_failure | short | market | 438 | 29 | -0.15 | +0.01 | 0.17 | 0.868 | no edge in training |
| swing_failure+choch | long | market | 79 | - | - | - | - | - | not enough trades |
| swing_failure+choch | short | market | 77 | - | - | - | - | - | not enough trades |
| swing_failure|swing:bias | long | market | 229 | 33 | -0.00 | +0.04 | 0.24 | 0.805 | no edge in training |
| swing_failure|swing:bias | short | market | 195 | 29 | -0.15 | -0.02 | 0.25 | 0.955 | no edge in training |
| swing_failure|swing:bias+context | long | market | 167 | 34 | +0.01 | +0.01 | 0.28 | 0.862 | no edge in training |
| swing_failure|swing:bias+context | short | market | 38 | - | - | - | - | - | not enough trades |
| swing_failure|swing:counter | long | market | 202 | 34 | +0.02 | +0.11 | 0.23 | 0.539 | no edge in training |
| swing_failure|swing:counter | short | market | 243 | 29 | -0.14 | +0.03 | 0.22 | 0.805 | no edge in training |
| swing_failure|swing:full | long | market | 14 | - | - | - | - | - | not enough trades |
| swing_failure|swing:full | short | market | 3 | - | - | - | - | - | not enough trades |
| sym_triangle_breakout | long | market | 101 | 50 | +0.37 | +0.26 | 0.37 | 0.342 | no edge in training |
| sym_triangle_breakout | short | market | 72 | - | - | - | - | - | not enough trades |
| three_bar_continuation | long | market | 303 | 38 | +0.11 | +0.05 | 0.20 | 0.713 | no edge in training |
| three_bar_continuation | short | market | 208 | 30 | -0.13 | -0.07 | 0.24 | 1.000 | no edge in training |
| three_bar_reversal | long | market | 1,416 | 36 | +0.03 | -0.03 | 0.11 | 1.000 | no edge in training |
| three_bar_reversal | short | market | 1,277 | 29 | -0.16 | -0.06 | 0.11 | 1.000 | no edge in training |
| three_black_crows | short | market | 19 | - | - | - | - | - | not enough trades |
| three_drives | long | market | 2 | - | - | - | - | - | not enough trades |
| three_drives | short | market | 2 | - | - | - | - | - | not enough trades |
| three_inside_down | short | market | 90 | - | - | - | - | - | not enough trades |
| three_inside_up | long | market | 106 | 37 | +0.06 | -0.00 | 0.34 | 0.891 | no edge in training |
| three_outside_down | short | market | 572 | 32 | -0.09 | +0.01 | 0.16 | 0.862 | no edge in training |
| three_outside_up | long | market | 628 | 38 | +0.07 | +0.01 | 0.15 | 0.862 | no edge in training |
| three_white_soldiers | long | market | 28 | - | - | - | - | - | not enough trades |
| triple_bottom | long | market | 8 | - | - | - | - | - | not enough trades |
| triple_top | short | market | 11 | - | - | - | - | - | not enough trades |
| tweezer_bottom | long | market | 378 | 33 | -0.04 | +0.06 | 0.19 | 0.680 | no edge in training |
| tweezer_top | short | market | 533 | 28 | -0.17 | +0.01 | 0.14 | 0.862 | no edge in training |
| upthrust | short | market | 2 | - | - | - | - | - | not enough trades |
| wide_range | long | market | 634 | 39 | +0.11 | -0.02 | 0.15 | 0.987 | no edge in training |
| wide_range | short | market | 618 | 35 | -0.07 | +0.04 | 0.14 | 0.708 | no edge in training |
| wide_range_reversal | long | market | 281 | 41 | +0.16 | +0.06 | 0.21 | 0.705 | no edge in training |
| wide_range_reversal | short | market | 270 | 36 | -0.01 | +0.10 | 0.22 | 0.539 | no edge in training |

#### D1

| Pattern | Dir | Entry | Trades | Win % | Mean R | Edge | Smallest detectable | q | Status |
|---|---|---|---|---|---|---|---|---|---|
| BOS | long | market | 54 | - | - | - | - | - | not enough trades |
| BOS | short | market | 23 | - | - | - | - | - | not enough trades |
| CHoCH | long | market | 33 | - | - | - | - | - | not enough trades |
| CHoCH | short | market | 32 | - | - | - | - | - | not enough trades |
| abcd | long | market | 3 | - | - | - | - | - | not enough trades |
| abcd | short | market | 2 | - | - | - | - | - | not enough trades |
| asc_triangle_breakout | long | market | 7 | - | - | - | - | - | not enough trades |
| atr_expansion | long | market | 7 | - | - | - | - | - | not enough trades |
| atr_expansion | short | market | 8 | - | - | - | - | - | not enough trades |
| atr_expansion+bos | long | market | 2 | - | - | - | - | - | not enough trades |
| balanced_price_range | long | limit | 44 | - | - | - | - | - | not enough trades |
| balanced_price_range | short | limit | 58 | - | - | - | - | - | not enough trades |
| bear_pennant | short | market | 1 | - | - | - | - | - | not enough trades |
| bos+displacement | long | market | 9 | - | - | - | - | - | not enough trades |
| bos+displacement | short | market | 8 | - | - | - | - | - | not enough trades |
| breaker+fvg | long | limit | 52 | - | - | - | - | - | not enough trades |
| breaker+fvg | short | limit | 49 | - | - | - | - | - | not enough trades |
| breaker_block | long | limit | 45 | - | - | - | - | - | not enough trades |
| breaker_block | short | limit | 47 | - | - | - | - | - | not enough trades |
| breakout | long | market | 54 | - | - | - | - | - | not enough trades |
| breakout | short | market | 51 | - | - | - | - | - | not enough trades |
| broadening_breakout | long | market | 5 | - | - | - | - | - | not enough trades |
| broadening_breakout | short | market | 2 | - | - | - | - | - | not enough trades |
| butterfly | short | market | 1 | - | - | - | - | - | not enough trades |
| buying_climax | short | market | 29 | - | - | - | - | - | not enough trades |
| channel_breakout | long | market | 6 | - | - | - | - | - | not enough trades |
| channel_breakout | short | market | 1 | - | - | - | - | - | not enough trades |
| choch+fvg | long | limit | 47 | - | - | - | - | - | not enough trades |
| choch+fvg | short | limit | 49 | - | - | - | - | - | not enough trades |
| climax_reversal | short | market | 19 | - | - | - | - | - | not enough trades |
| compression+sweep | short | market | 1 | - | - | - | - | - | not enough trades |
| compression_breakout | short | market | 1 | - | - | - | - | - | not enough trades |
| consecutive_expansion | long | market | 55 | - | - | - | - | - | not enough trades |
| consecutive_expansion | short | market | 34 | - | - | - | - | - | not enough trades |
| consecutive_fvg | long | limit | 32 | - | - | - | - | - | not enough trades |
| consecutive_fvg | short | limit | 23 | - | - | - | - | - | not enough trades |
| cypher | long | market | 1 | - | - | - | - | - | not enough trades |
| dark_cloud_cover | short | market | 22 | - | - | - | - | - | not enough trades |
| deep_crab | short | market | 1 | - | - | - | - | - | not enough trades |
| deep_retracement | long | market | 4 | - | - | - | - | - | not enough trades |
| deep_retracement | short | market | 4 | - | - | - | - | - | not enough trades |
| demand_to_supply_flip | short | limit | 16 | - | - | - | - | - | not enough trades |
| demand_zone | long | limit | 22 | - | - | - | - | - | not enough trades |
| desc_triangle_breakdown | short | market | 6 | - | - | - | - | - | not enough trades |
| displacement | long | market | 22 | - | - | - | - | - | not enough trades |
| displacement | short | market | 30 | - | - | - | - | - | not enough trades |
| displacement_imbalance | long | limit | 16 | - | - | - | - | - | not enough trades |
| displacement_imbalance | short | limit | 26 | - | - | - | - | - | not enough trades |
| double_bottom | long | market | 4 | - | - | - | - | - | not enough trades |
| double_top | short | market | 4 | - | - | - | - | - | not enough trades |
| dragonfly_doji | long | market | 5 | - | - | - | - | - | not enough trades |
| elliott_impulse | long | market | 3 | - | - | - | - | - | not enough trades |
| elliott_impulse | short | market | 9 | - | - | - | - | - | not enough trades |
| elliott_wave5 | long | market | 13 | - | - | - | - | - | not enough trades |
| elliott_wave5 | short | market | 4 | - | - | - | - | - | not enough trades |
| ema_bounce | long | market | 60 | - | - | - | - | - | not enough trades |
| ema_bounce | short | market | 41 | - | - | - | - | - | not enough trades |
| engulfing_bear | short | market | 139 | 23 | -0.33 | -0.06 | 0.27 | 1.000 | no edge in training |
| engulfing_bull | long | market | 115 | 38 | +0.15 | -0.13 | 0.34 | 1.000 | no edge in training |
| equal_highs | short | market | 7 | - | - | - | - | - | not enough trades |
| equal_highs+displacement | short | market | 4 | - | - | - | - | - | not enough trades |
| equal_lows | long | market | 14 | - | - | - | - | - | not enough trades |
| equal_lows+displacement | long | market | 5 | - | - | - | - | - | not enough trades |
| evening_doji_star | short | market | 11 | - | - | - | - | - | not enough trades |
| evening_star | short | market | 27 | - | - | - | - | - | not enough trades |
| exhaustion_sequence | short | market | 9 | - | - | - | - | - | not enough trades |
| external_bos | long | market | 29 | - | - | - | - | - | not enough trades |
| external_bos | short | market | 14 | - | - | - | - | - | not enough trades |
| external_sweep | long | market | 30 | - | - | - | - | - | not enough trades |
| external_sweep | short | market | 28 | - | - | - | - | - | not enough trades |
| failed_bos | long | market | 36 | - | - | - | - | - | not enough trades |
| failed_bos | short | market | 37 | - | - | - | - | - | not enough trades |
| failed_breakout | long | market | 17 | - | - | - | - | - | not enough trades |
| failed_breakout | short | market | 14 | - | - | - | - | - | not enough trades |
| failed_breakout+reclaim | long | market | 6 | - | - | - | - | - | not enough trades |
| failed_breakout+reclaim | short | market | 5 | - | - | - | - | - | not enough trades |
| failed_momentum_breakout | long | market | 30 | - | - | - | - | - | not enough trades |
| failed_momentum_breakout | short | market | 56 | - | - | - | - | - | not enough trades |
| failed_sweep | long | market | 28 | - | - | - | - | - | not enough trades |
| failed_sweep | short | market | 18 | - | - | - | - | - | not enough trades |
| failed_swing | long | market | 90 | - | - | - | - | - | not enough trades |
| failed_swing | short | market | 42 | - | - | - | - | - | not enough trades |
| falling_channel_break | long | market | 12 | - | - | - | - | - | not enough trades |
| falling_three_methods | short | market | 2 | - | - | - | - | - | not enough trades |
| falling_wedge_breakout | long | market | 14 | - | - | - | - | - | not enough trades |
| fib_extension | long | market | 24 | - | - | - | - | - | not enough trades |
| fib_extension | short | market | 6 | - | - | - | - | - | not enough trades |
| fib_retracement | long | market | 9 | - | - | - | - | - | not enough trades |
| fib_retracement | short | market | 6 | - | - | - | - | - | not enough trades |
| fvg | long | limit | 194 | 35 | +0.05 | +0.01 | 0.27 | 0.885 | no edge in training |
| fvg | short | limit | 155 | 30 | -0.09 | +0.13 | 0.26 | 0.539 | no edge in training |
| fvg_after_sweep | long | limit | 19 | - | - | - | - | - | not enough trades |
| fvg_after_sweep | short | limit | 17 | - | - | - | - | - | not enough trades |
| fvg_continuation | long | limit | 154 | 34 | +0.01 | -0.05 | 0.31 | 0.985 | no edge in training |
| fvg_continuation | short | limit | 78 | - | - | - | - | - | not enough trades |
| fvg_formation | long | market | 235 | 43 | +0.30 | +0.03 | 0.29 | 0.844 | no edge in training |
| fvg_formation | short | market | 157 | 25 | -0.28 | -0.00 | 0.24 | 0.907 | no edge in training |
| fvg_reversal | long | limit | 40 | - | - | - | - | - | not enough trades |
| fvg_reversal | short | limit | 77 | - | - | - | - | - | not enough trades |
| fvg_with_bos | long | limit | 45 | - | - | - | - | - | not enough trades |
| fvg_with_bos | short | limit | 23 | - | - | - | - | - | not enough trades |
| fvg_with_choch | long | limit | 27 | - | - | - | - | - | not enough trades |
| fvg_with_choch | short | limit | 38 | - | - | - | - | - | not enough trades |
| gartley | long | market | 1 | - | - | - | - | - | not enough trades |
| golden_pullback | long | market | 6 | - | - | - | - | - | not enough trades |
| golden_pullback | short | market | 5 | - | - | - | - | - | not enough trades |
| grab_reversal | long | market | 25 | - | - | - | - | - | not enough trades |
| grab_reversal | short | market | 20 | - | - | - | - | - | not enough trades |
| grab_reversal+order_block | long | limit | 5 | - | - | - | - | - | not enough trades |
| grab_reversal+order_block | short | limit | 11 | - | - | - | - | - | not enough trades |
| gravestone_doji | short | market | 5 | - | - | - | - | - | not enough trades |
| hammer | long | market | 27 | - | - | - | - | - | not enough trades |
| hanging_man | short | market | 36 | - | - | - | - | - | not enough trades |
| harami_bear | short | market | 73 | - | - | - | - | - | not enough trades |
| harami_bull | long | market | 59 | - | - | - | - | - | not enough trades |
| higher_low | long | market | 105 | 42 | +0.17 | -0.19 | 0.31 | 1.000 | no edge in training |
| higher_low+bos | long | market | 36 | - | - | - | - | - | not enough trades |
| ice_breakdown | short | market | 2 | - | - | - | - | - | not enough trades |
| inside_bar_bear | short | market | 172 | 26 | -0.22 | +0.00 | 0.23 | 0.885 | no edge in training |
| inside_bar_bull | long | market | 256 | 43 | +0.30 | +0.12 | 0.23 | 0.539 | no edge in training |
| inside_compression+nr_breakout | long | market | 10 | - | - | - | - | - | not enough trades |
| inside_compression+nr_breakout | short | market | 8 | - | - | - | - | - | not enough trades |
| internal_bos | long | market | 78 | - | - | - | - | - | not enough trades |
| internal_bos | short | market | 31 | - | - | - | - | - | not enough trades |
| internal_sweep | long | market | 72 | - | - | - | - | - | not enough trades |
| internal_sweep | short | market | 82 | - | - | - | - | - | not enough trades |
| inverse_fvg | long | limit | 132 | 40 | +0.21 | +0.18 | 0.29 | 0.452 | no edge in training |
| inverse_fvg | short | limit | 145 | 23 | -0.32 | -0.09 | 0.27 | 1.000 | no edge in training |
| inverse_head_and_shoulders | long | market | 2 | - | - | - | - | - | not enough trades |
| inverted_hammer | long | market | 18 | - | - | - | - | - | not enough trades |
| liquidity_sweep | long | market | 55 | - | - | - | - | - | not enough trades |
| liquidity_sweep | short | market | 52 | - | - | - | - | - | not enough trades |
| lower_high | short | market | 75 | - | - | - | - | - | not enough trades |
| lower_high+bos | short | market | 18 | - | - | - | - | - | not enough trades |
| market_structure_shift | long | market | 13 | - | - | - | - | - | not enough trades |
| market_structure_shift | short | market | 14 | - | - | - | - | - | not enough trades |
| marubozu_bear | short | market | 6 | - | - | - | - | - | not enough trades |
| marubozu_bull | long | market | 24 | - | - | - | - | - | not enough trades |
| momentum_continuation | long | market | 86 | - | - | - | - | - | not enough trades |
| momentum_continuation | short | market | 28 | - | - | - | - | - | not enough trades |
| momentum_exhaustion | long | market | 2 | - | - | - | - | - | not enough trades |
| momentum_exhaustion | short | market | 9 | - | - | - | - | - | not enough trades |
| morning_doji_star | long | market | 5 | - | - | - | - | - | not enough trades |
| morning_star | long | market | 24 | - | - | - | - | - | not enough trades |
| multi_touch_rejection | long | market | 8 | - | - | - | - | - | not enough trades |
| multi_touch_rejection | short | market | 4 | - | - | - | - | - | not enough trades |
| multiple_sweeps | long | market | 10 | - | - | - | - | - | not enough trades |
| multiple_sweeps | short | market | 8 | - | - | - | - | - | not enough trades |
| nr_breakout | long | market | 73 | - | - | - | - | - | not enough trades |
| nr_breakout | short | market | 58 | - | - | - | - | - | not enough trades |
| order_block | long | limit | 52 | - | - | - | - | - | not enough trades |
| order_block | short | limit | 49 | - | - | - | - | - | not enough trades |
| order_block_bos | long | limit | 38 | - | - | - | - | - | not enough trades |
| order_block_bos | short | limit | 22 | - | - | - | - | - | not enough trades |
| order_block_choch | long | limit | 14 | - | - | - | - | - | not enough trades |
| order_block_choch | short | limit | 27 | - | - | - | - | - | not enough trades |
| order_block_fvg | long | limit | 15 | - | - | - | - | - | not enough trades |
| order_block_fvg | short | limit | 27 | - | - | - | - | - | not enough trades |
| order_block_sweep | long | limit | 3 | - | - | - | - | - | not enough trades |
| order_block_sweep | short | limit | 7 | - | - | - | - | - | not enough trades |
| outside_bar_bear | short | market | 184 | 27 | -0.22 | +0.04 | 0.23 | 0.799 | no edge in training |
| outside_bar_bull | long | market | 160 | 43 | +0.29 | +0.03 | 0.32 | 0.853 | no edge in training |
| piercing | long | market | 18 | - | - | - | - | - | not enough trades |
| pin_bar_bear | short | market | 53 | - | - | - | - | - | not enough trades |
| pin_bar_bull | long | market | 83 | - | - | - | - | - | not enough trades |
| pm_high_sweep | short | market | 22 | - | - | - | - | - | not enough trades |
| pm_low_sweep | long | market | 9 | - | - | - | - | - | not enough trades |
| preliminary_supply | short | market | 21 | - | - | - | - | - | not enough trades |
| preliminary_support | long | market | 4 | - | - | - | - | - | not enough trades |
| pw_high_sweep | short | market | 80 | - | - | - | - | - | not enough trades |
| pw_low_sweep | long | market | 55 | - | - | - | - | - | not enough trades |
| range_boundary_rejection | long | market | 14 | - | - | - | - | - | not enough trades |
| range_boundary_rejection | short | market | 94 | - | - | - | - | - | not enough trades |
| range_midpoint_cross | long | market | 73 | - | - | - | - | - | not enough trades |
| range_midpoint_cross | short | market | 67 | - | - | - | - | - | not enough trades |
| range_to_trend | long | market | 48 | - | - | - | - | - | not enough trades |
| range_to_trend | short | market | 8 | - | - | - | - | - | not enough trades |
| reclaimed_order_block | long | market | 28 | - | - | - | - | - | not enough trades |
| reclaimed_order_block | short | market | 20 | - | - | - | - | - | not enough trades |
| rectangle_breakout | long | market | 2 | - | - | - | - | - | not enough trades |
| rectangle_breakout | short | market | 2 | - | - | - | - | - | not enough trades |
| rejection_bear | short | market | 66 | - | - | - | - | - | not enough trades |
| rejection_bear+bos | short | market | 6 | - | - | - | - | - | not enough trades |
| rejection_block | long | limit | 51 | - | - | - | - | - | not enough trades |
| rejection_block | short | limit | 46 | - | - | - | - | - | not enough trades |
| rejection_bull | long | market | 66 | - | - | - | - | - | not enough trades |
| rejection_bull+bos | long | market | 13 | - | - | - | - | - | not enough trades |
| resistance_rejection | short | market | 11 | - | - | - | - | - | not enough trades |
| resistance_rejection+engulfing | short | market | 2 | - | - | - | - | - | not enough trades |
| retest | long | market | 23 | - | - | - | - | - | not enough trades |
| retest | short | market | 21 | - | - | - | - | - | not enough trades |
| retest+momentum | long | market | 3 | - | - | - | - | - | not enough trades |
| retest+momentum | short | market | 4 | - | - | - | - | - | not enough trades |
| rising_channel_break | short | market | 11 | - | - | - | - | - | not enough trades |
| rising_three_methods | long | market | 4 | - | - | - | - | - | not enough trades |
| rising_wedge_breakdown | short | market | 13 | - | - | - | - | - | not enough trades |
| round100_reaction | long | market | 28 | - | - | - | - | - | not enough trades |
| round100_reaction | short | market | 13 | - | - | - | - | - | not enough trades |
| round10_reaction | long | market | 332 | 45 | +0.36 | +0.20 | 0.22 | 0.226 | no edge in training |
| round10_reaction | short | market | 303 | 33 | -0.01 | +0.19 | 0.23 | 0.277 | no edge in training |
| round50_reaction | long | market | 43 | - | - | - | - | - | not enough trades |
| round50_reaction | short | market | 40 | - | - | - | - | - | not enough trades |
| round_placebo_reaction | long | market | 377 | 45 | +0.35 | +0.19 | 0.20 | 0.169 | no edge in training |
| round_placebo_reaction | short | market | 393 | 29 | -0.15 | +0.08 | 0.18 | 0.558 | no edge in training |
| secondary_test | short | market | 4 | - | - | - | - | - | not enough trades |
| selling_climax | long | market | 3 | - | - | - | - | - | not enough trades |
| shooting_star | short | market | 25 | - | - | - | - | - | not enough trades |
| squeeze+bos | long | market | 1 | - | - | - | - | - | not enough trades |
| squeeze+bos | short | market | 2 | - | - | - | - | - | not enough trades |
| squeeze_release | long | market | 10 | - | - | - | - | - | not enough trades |
| squeeze_release | short | market | 7 | - | - | - | - | - | not enough trades |
| strong_bull_sequence | long | market | 3 | - | - | - | - | - | not enough trades |
| strong_demand | long | limit | 2 | - | - | - | - | - | not enough trades |
| strong_supply | short | limit | 8 | - | - | - | - | - | not enough trades |
| structural_reclaim | long | market | 10 | - | - | - | - | - | not enough trades |
| structural_reclaim | short | market | 20 | - | - | - | - | - | not enough trades |
| supply_to_demand_flip | long | limit | 26 | - | - | - | - | - | not enough trades |
| supply_zone | short | limit | 30 | - | - | - | - | - | not enough trades |
| support_rejection | long | market | 13 | - | - | - | - | - | not enough trades |
| sweep+bos | long | market | 2 | - | - | - | - | - | not enough trades |
| sweep+bos | short | market | 7 | - | - | - | - | - | not enough trades |
| sweep+choch | long | market | 8 | - | - | - | - | - | not enough trades |
| sweep+choch | short | market | 9 | - | - | - | - | - | not enough trades |
| sweep+double_bottom | long | market | 4 | - | - | - | - | - | not enough trades |
| sweep+double_top | short | market | 3 | - | - | - | - | - | not enough trades |
| sweep+mss | long | market | 1 | - | - | - | - | - | not enough trades |
| sweep+mss | short | market | 4 | - | - | - | - | - | not enough trades |
| sweep+order_block | long | limit | 6 | - | - | - | - | - | not enough trades |
| sweep+order_block | short | limit | 14 | - | - | - | - | - | not enough trades |
| sweep_reclaim | long | market | 16 | - | - | - | - | - | not enough trades |
| sweep_reclaim | short | market | 8 | - | - | - | - | - | not enough trades |
| sweep_to_bos | long | market | 13 | - | - | - | - | - | not enough trades |
| sweep_to_bos | short | market | 14 | - | - | - | - | - | not enough trades |
| swing_failure | long | market | 30 | - | - | - | - | - | not enough trades |
| swing_failure | short | market | 34 | - | - | - | - | - | not enough trades |
| swing_failure+choch | long | market | 6 | - | - | - | - | - | not enough trades |
| swing_failure+choch | short | market | 5 | - | - | - | - | - | not enough trades |
| sym_triangle_breakout | long | market | 15 | - | - | - | - | - | not enough trades |
| sym_triangle_breakout | short | market | 8 | - | - | - | - | - | not enough trades |
| three_bar_continuation | long | market | 67 | - | - | - | - | - | not enough trades |
| three_bar_continuation | short | market | 33 | - | - | - | - | - | not enough trades |
| three_bar_reversal | long | market | 146 | 49 | +0.47 | +0.10 | 0.33 | 0.672 | no edge in training |
| three_bar_reversal | short | market | 129 | 23 | -0.34 | +0.00 | 0.26 | 0.888 | no edge in training |
| three_black_crows | short | market | 1 | - | - | - | - | - | not enough trades |
| three_inside_down | short | market | 9 | - | - | - | - | - | not enough trades |
| three_inside_up | long | market | 10 | - | - | - | - | - | not enough trades |
| three_outside_down | short | market | 48 | - | - | - | - | - | not enough trades |
| three_outside_up | long | market | 53 | - | - | - | - | - | not enough trades |
| three_white_soldiers | long | market | 3 | - | - | - | - | - | not enough trades |
| triple_bottom | long | market | 1 | - | - | - | - | - | not enough trades |
| triple_top | short | market | 1 | - | - | - | - | - | not enough trades |
| tweezer_bottom | long | market | 29 | - | - | - | - | - | not enough trades |
| tweezer_top | short | market | 53 | - | - | - | - | - | not enough trades |
| wide_range | long | market | 54 | - | - | - | - | - | not enough trades |
| wide_range | short | market | 76 | - | - | - | - | - | not enough trades |
| wide_range_reversal | long | market | 18 | - | - | - | - | - | not enough trades |
| wide_range_reversal | short | market | 47 | - | - | - | - | - | not enough trades |

Intrabar assumption: if the favourable extreme of the stop minute had come first, 0.02% of main-test results (average over tests) would change.

## Validation result

Candidate list SHA-256 `cf89a31311ba4894` (frozen before validation was read).

| TF | Pattern | Dir | Trades | Win % | Mean R | Edge | Holm p | Late edge | R with $0.30 spread | R with $0.10 slippage/side | Max DD (R) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M5 | failed_momentum_breakout | long | 4,569 | 30 | -0.17 | +0.06 | 0.1152 | +0.02 | -0.13 | -0.29 | 801.8 | failed validation |
| M5 | range_boundary_rejection | long | 6,607 | 26 | -0.25 | +0.03 | 1.0000 | -0.02 | -0.20 | -0.40 | 1715.0 | failed validation |
| M5 | harami_bull | long | 11,099 | 23 | -0.32 | +0.02 | 1.0000 | -0.03 | -0.26 | -0.49 | 3585.3 | failed validation |
| M5 | CHoCH | long | 4,205 | 36 | -0.13 | +0.02 | 1.0000 | +0.01 | -0.10 | -0.19 | 547.5 | failed validation |
| M5 | rejection_block | long | 5,989 | 19 | -0.44 | +0.01 | 1.0000 | - | -0.33 | -0.68 | 2655.5 | failed validation |
| M5 | inverted_hammer | long | 5,172 | 17 | -0.50 | +0.10 | 0.0001 | +0.04 | -0.37 | -0.81 | 2573.2 | failed one-candle-delay check |
| M5 | tweezer_bottom | long | 5,577 | 23 | -0.33 | +0.02 | 1.0000 | -0.04 | -0.26 | -0.50 | 1854.5 | failed validation |
| M5 | reclaimed_order_block | long | 3,547 | 37 | -0.11 | +0.02 | 1.0000 | +0.02 | -0.08 | -0.16 | 388.3 | failed validation |
| M5 | demand_zone | long | 1,730 | 18 | -0.48 | +0.03 | 1.0000 | - | -0.36 | -0.73 | 828.4 | failed validation |
| M5 | order_block | long | 5,604 | 24 | -0.32 | +0.03 | 1.0000 | - | -0.23 | -0.50 | 1794.7 | failed validation |
| M5 | order_block_bos | long | 2,830 | 23 | -0.34 | +0.02 | 1.0000 | - | -0.24 | -0.52 | 954.6 | failed validation |
| M5 | order_block_choch | long | 2,774 | 24 | -0.30 | +0.04 | 1.0000 | - | -0.22 | -0.47 | 840.5 | failed validation |
| M5 | breaker_block | long | 6,334 | 23 | -0.34 | +0.02 | 1.0000 | - | -0.26 | -0.51 | 2133.6 | failed validation |
| M5 | fvg_with_choch | short | 4,061 | 15 | -0.57 | +0.04 | 0.7795 | - | -0.36 | -0.97 | 2314.1 | failed validation |
| M5 | pd_low_sweep | long | 192 | 30 | -0.12 | +0.13 | 1.0000 | +0.03 | -0.06 | -0.25 | 35.9 | failed validation |
| M5 | order_block_sweep | long | 993 | 27 | -0.24 | +0.05 | 1.0000 | - | -0.16 | -0.39 | 239.2 | failed validation |
| M5 | supply_zone | short | 1,793 | 19 | -0.45 | +0.06 | 1.0000 | - | -0.31 | -0.68 | 798.9 | failed validation |
| M5 | round10_reaction | long | 5,194 | 25 | -0.27 | +0.06 | 0.3760 | -0.03 | -0.20 | -0.42 | 1448.2 | failed validation |
| M5 | fvg_with_choch | long | 3,503 | 14 | -0.58 | +0.01 | 1.0000 | - | -0.42 | -0.95 | 2033.5 | failed validation |
| M5 | order_block_fvg | long | 2,635 | 25 | -0.28 | +0.07 | 0.2319 | - | -0.19 | -0.46 | 745.3 | failed validation |
| M5 | sweep+order_block | long | 1,323 | 24 | -0.32 | +0.02 | 1.0000 | - | -0.22 | -0.49 | 425.7 | failed validation |
| M5 | grab_reversal+order_block | long | 1,030 | 24 | -0.32 | +0.02 | 1.0000 | - | -0.22 | -0.49 | 334.1 | failed validation |
| M15 | range_boundary_rejection | long | 2,141 | 30 | -0.15 | +0.03 | 1.0000 | +0.02 | -0.12 | -0.24 | 347.8 | failed validation |
| M15 | breaker_block | long | 2,048 | 28 | -0.20 | +0.01 | 1.0000 | - | -0.16 | -0.29 | 402.4 | failed validation |
| M15 | tweezer_bottom | long | 1,820 | 28 | -0.19 | +0.06 | 1.0000 | +0.01 | -0.14 | -0.31 | 365.7 | failed validation |
| M15 | harami_bull | long | 3,421 | 28 | -0.19 | +0.04 | 1.0000 | -0.00 | -0.15 | -0.30 | 677.6 | failed validation |
| M15 | rejection_block | long | 2,214 | 25 | -0.26 | +0.01 | 1.0000 | - | -0.18 | -0.39 | 566.8 | failed validation |
| M15 | failed_momentum_breakout | long | 1,414 | 32 | -0.11 | +0.03 | 1.0000 | +0.02 | -0.09 | -0.18 | 194.8 | failed validation |
| M15 | round10_reaction | long | 3,145 | 28 | -0.20 | +0.03 | 1.0000 | +0.01 | -0.14 | -0.29 | 634.1 | failed validation |
| M15 | order_block_sweep | short | 375 | 31 | -0.12 | +0.05 | 1.0000 | - | -0.08 | -0.20 | 56.3 | failed validation |
| M15 | demand_zone | long | 471 | 24 | -0.27 | +0.03 | 1.0000 | - | -0.21 | -0.40 | 126.6 | failed validation |
| M15 | order_block_fvg | long | 774 | 28 | -0.19 | -0.00 | 1.0000 | - | -0.15 | -0.29 | 156.9 | failed validation |
| M15 | strong_demand | long | 66 | 15 | -0.55 | -0.26 | - | - | -0.48 | -0.67 | 41.0 | too few validation trades |
| M15 | grab_reversal+order_block | short | 380 | 29 | -0.15 | +0.06 | 1.0000 | - | -0.11 | -0.24 | 67.6 | failed validation |
| M15 | order_block|scalp:counter | long | 811 | 26 | -0.25 | -0.05 | 1.0000 | - | -0.21 | -0.35 | 204.3 | failed validation |
| M15 | demand_zone|scalp:bias | long | 263 | 23 | -0.32 | -0.02 | 1.0000 | - | -0.25 | -0.45 | 83.0 | failed validation |
| M30 | order_block | short | 879 | 30 | -0.14 | +0.01 | 1.0000 | - | -0.11 | -0.21 | 140.3 | failed validation |
| M30 | range_boundary_rejection | long | 943 | 30 | -0.11 | +0.03 | 1.0000 | +0.07 | -0.08 | -0.17 | 123.6 | failed validation |
| M30 | hammer | long | 886 | 28 | -0.17 | -0.01 | 1.0000 | -0.02 | -0.13 | -0.24 | 167.6 | failed validation |
| M30 | breaker_block | long | 974 | 31 | -0.08 | +0.05 | 1.0000 | - | -0.05 | -0.14 | 121.5 | failed validation |
| M30 | failed_bos | short | 786 | 31 | -0.12 | +0.01 | 1.0000 | +0.04 | -0.09 | -0.18 | 105.5 | failed validation |
| M30 | order_block_sweep | short | 180 | 31 | -0.15 | -0.02 | 1.0000 | - | -0.12 | -0.20 | 30.0 | failed validation |
| M30 | displacement | long | 383 | 39 | -0.04 | -0.02 | 1.0000 | -0.05 | -0.04 | -0.07 | 48.1 | failed validation |
| M30 | consecutive_fvg | long | 512 | 33 | -0.09 | +0.00 | 1.0000 | - | -0.07 | -0.15 | 74.2 | failed validation |
| M30 | bos+displacement | long | 149 | 38 | -0.13 | -0.10 | 1.0000 | -0.13 | -0.12 | -0.16 | 32.3 | failed validation |
| H1 | order_block | short | 406 | 30 | -0.13 | -0.04 | 1.0000 | - | -0.11 | -0.17 | 69.0 | failed validation |
| H1 | order_block_choch | short | 208 | 35 | +0.03 | +0.11 | 1.0000 | - | +0.05 | -0.02 | 22.4 | failed validation |
| H1 | harami_bear | short | 782 | 28 | -0.16 | +0.00 | 1.0000 | +0.10 | -0.10 | -0.23 | 134.5 | failed validation |
| H1 | breaker_block | long | 462 | 32 | -0.04 | +0.03 | 1.0000 | - | -0.02 | -0.08 | 61.2 | failed validation |
| H1 | displacement_imbalance | short | 137 | 30 | -0.16 | -0.03 | 1.0000 | - | -0.14 | -0.20 | 24.2 | failed validation |
| H1 | round50_reaction | long | 159 | 30 | -0.12 | -0.01 | 1.0000 | -0.14 | -0.08 | -0.18 | 22.0 | failed validation |
| H1 | order_block|intraday:counter | short | 196 | 34 | +0.03 | +0.11 | 1.0000 | - | +0.04 | -0.02 | 23.7 | failed validation |
| M5 | falling_wedge_breakout | long | 1,176 | 33 | -0.14 | +0.05 | 1.0000 | +0.04 | -0.10 | -0.23 | 185.0 | failed validation |
| M5 | rounding_bottom | long | 158 | 44 | -0.10 | +0.01 | 1.0000 | +0.04 | -0.09 | -0.13 | 20.4 | failed validation |
| M5 | rectangle_breakout | long | 474 | 36 | -0.10 | +0.02 | 1.0000 | -0.01 | -0.08 | -0.16 | 87.8 | failed validation |
| M5 | triple_bottom | long | 128 | 45 | -0.03 | +0.10 | 1.0000 | +0.12 | -0.01 | -0.07 | 13.4 | failed validation |
| M5 | selling_climax | long | 1,365 | 27 | -0.22 | +0.05 | 1.0000 | +0.03 | -0.17 | -0.36 | 303.3 | failed validation |
| M5 | elliott_impulse | long | 492 | 29 | -0.26 | -0.06 | 1.0000 | -0.08 | -0.23 | -0.36 | 130.7 | failed validation |
| M5 | double_bottom | long | 419 | 42 | -0.05 | +0.07 | 1.0000 | +0.09 | -0.03 | -0.10 | 48.2 | failed validation |
| M5 | sweep+double_bottom | long | 263 | 41 | -0.08 | +0.05 | 1.0000 | +0.09 | -0.06 | -0.13 | 27.8 | failed validation |
| M15 | fib_extension | long | 573 | 41 | -0.12 | -0.06 | 1.0000 | -0.04 | -0.11 | -0.14 | 77.3 | failed validation |
| M30 | deep_retracement | long | 93 | 33 | -0.06 | +0.02 | - | -0.08 | -0.04 | -0.11 | 21.3 | too few validation trades |

## Limitations

* One data source (Dukascopy); a broker's prices and spreads differ slightly.
* Patterns are the platform's current detectors (Phase 1). The full pattern library, regimes, combinations and multi-timeframe studies follow in later phases and join the same validation family.
* No news calendar; overnight swap is not charged (scenarios come with the swing-profile study).
* Training and validation numbers are not the final test. The final test is run once, at the end, and reported separately.
