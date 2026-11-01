# Evidence score — methodology

> **Evidence Score — Not Win Probability.** The score measures how much *independent, consistent evidence* supports a setup and how
> trustworthy the inputs are. It has **not** been calibrated against outcomes and must never be read as a chance of winning. No 90%/95% figure is produced anywhere.

## Formula
```
raw      = 100 × Σ weightᵢ × componentᵢ            (componentᵢ ∈ [0, 1])
adjusted = clamp(raw − Σ penalties, 0, 100)
score    = min(adjusted, cap[strategy validation status])
```
Weights, penalties and caps live in `app/opportunities/config.py` (`WEIGHTS`, `PENALTIES`, `VALIDATION_CAPS`) and are returned by `GET /opportunities/config`.
The weights were set a priori and were not fitted to outcomes.

## Components
| Component | Weight | How it is computed |
|---|---|---|
| Higher-timeframe alignment | 0.16 | `(direction × weighted HTF structure score + 1) / 2`; 0.35 when no HTF data exists (never assumed aligned) |
| Market-structure quality | 0.14 | +0.40 setup-timeframe trend agrees; +0.20 same-direction BOS/CHoCH within 20 bars; +0.20 zone in discount (buy) / premium (sell) half (+0.08 near equilibrium); +0.20 order block / breaker / supply-demand, +0.15 FVG, or S/R band (+0.20 with ≥ 3 touches, +0.12 with 2) |
| Price-action confirmation | 0.14 | rejection candle 0.40, BOS/CHoCH 0.30, liquidity sweep 0.20, retest 0.15 (capped at 1); 0 while waiting for confirmation |
| Historical analogues | 0.14 | `clamp(0.5 + edge/0.30) × min(1, n/100)` where edge = analogue TP-first frequency − base rate; 0 if unavailable |
| Momentum | 0.08 | 0.7 × (0.5 + 0.25·tanh(10-bar move/2)·dir + 0.25·tanh(slope/2)·dir) + 0.3 × RSI closeness to a healthy 58 (buy) / 42 (sell) |
| Volatility suitability | 0.06 | 1 when ATR is between its 15th and 85th percentile of its own history, falling to 0.3 at the extremes; halved if short/long ATR ratio > 2 |
| Risk / reward | 0.10 | 0 below the style minimum; 0.5 at the minimum; 1.0 at twice the minimum |
| Data quality | 0.08 | The existing data-quality score (bar count, staleness, gaps, provider mapping status) |
| Strategy validation | 0.10 | validated 1.0 · untested 0.25 · no_edge 0.10 · negative 0 |

## Penalties (points subtracted)
Conflicting higher timeframes −15 · stale data −10 (−25 for scalping) · missing candles −2 each, max −10 · analogue sample < 30: −8, < 100: −4 ·
excessive volatility (ATR top 5% or ATR ratio > 2) −8 · R/R within 25% of the minimum −3.

## Validation caps
| Strategy status | Maximum score |
|---|---|
| validated (genuine out-of-sample evidence) | 100 |
| untested (no out-of-sample test) | 65 |
| no_edge (tested, nothing distinguishable from zero) | 58 |
| negative (tested, loses money after costs) | 49 |
A setup needs ≥ 55 (the style's `min_evidence`) to be published as BUY/SELL, so **a strategy with a negative out-of-sample result can never be published**
and an unvalidated one can only reach the narrow band below its cap. The breakdown shows the uncapped score and the reason when a cap applies.

## Ranking
Tier (actionable > watchlist > WAIT), then **validation status** (validated > untested > no_edge > negative), then evidence score, then R/R. A validated
setup therefore outranks an unvalidated one however high the latter's technical score. Same-instrument, same-direction setups are flagged `≈#n` as one exposure.

## What the score is not
* not calibrated (`calibrated: false` in every payload) and not comparable across methodology versions (`method_version`);
* not a forecast of profit; a high score on an untested rule set means "the technical picture is consistent", nothing more;
* sensitive to its inputs: stale or gappy data lowers it, and missing analogue data scores zero rather than being assumed neutral.
