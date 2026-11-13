# Confirmation layer: VSA and indicators (design spec)

Status: draft for the owner's review, 2026-11-13. Branch `feature/confirmation-engine`. The test of this design is
[EXPERIMENT_6_PLAN.md](EXPERIMENT_6_PLAN.md).

## 1. Decisions

The owner made these choices on 2026-11-13:

1. **Confirmations judge a setup, they never create one.** A strategy finds the setup first. The confirmation layer scores it, the
   plan and risk checks validate it, and the selector decides BUY, SELL, WAIT, EXIT or NO TRADE.
2. **Show now, gate after proof.** The four new evidence categories (VSA, trend, momentum, volatility) are shown on every
   signal from the first release. A category changes a decision only after it passes Experiment 6 for that strategy and
   instrument. The checks that decide today keep deciding, unchanged.
3. **Research instruments: XAUUSD and BTCUSDT.**
   - **Gold** reuses the Experiment 5 trades. Its history carries Dukascopy venue volume, while live gold carries MT5 tick counts.
     The only overlap of the two is inside the sealed period, so the transfer cannot be checked. **Gold VSA can therefore never be
     promoted to a live gate.**
   - **BTCUSDT** history comes from Binance's public archive. It is the same volume source the live engine uses.

## 2. Flow

```
candles (completed only) -> indicators + volume quality + VSA bar labels      (once per timeframe)
strategy.evaluate -> Candidate (+ component-tagged checks, + key candles)
confirm.score(Candidate) -> ten components, each PASS | FAIL | NEUTRAL | UNAVAILABLE with reason + evidence
plan.build -> risk.check -> selector (mandatory components + promoted gates only) -> action
```

## 3. Volume data quality (`strategy_engine/volume.py`)

**Volume type,** from each candle's stored `volume_type` and its provider:

| Source | Type shown to the customer | Meaning |
|---|---|---|
| Binance (`base`) | Exchange volume (Binance only) | Coins traded on one exchange; not the whole market |
| BiQuote / OANDA / Twelve Data (`tick`) | Tick volume (broker) | Number of price updates at one broker; not traded volume |
| Dukascopy history (`bid_volume + ask_volume`) | Venue volume (Dukascopy) | Liquidity quoted at one venue; research only |
| none / zero | No volume | VSA unavailable |

Spot FX, gold, US30 and oil are never described as having market-wide traded volume.

**Reliable**, checked per instrument and timeframe over the baseline window, only when all three hold:
- at least 95% of the candles have a non-zero volume;
- no run of 10 or more identical values;
- at least 4 baseline samples (below).

Otherwise VSA, VWAP, relative volume, OBV and MFI are UNAVAILABLE, with the reason.

**Relative volume (RVOL)** = the candle's volume / its baseline:
- **Timeframes up to 4H:** the median volume of candles at the same hour of the week over the last 20 weeks, so a London open is
  compared with London opens.
- **Fallback:** fewer than 4 such samples → the same hour of the day over the last 20 weekdays.
- **8H and above:** the median of the last 20 candles.

The baseline uses only candles before the one being measured.

## 4. Indicators (`feature_engineering/indicators.py`)

Every indicator is causal: its value at candle *i* uses candles up to *i* only. Before its warm-up it is NaN, and the category
that needs it reports UNAVAILABLE.

| Indicator | Parameters | Valid from candle | Use |
|---|---|---|---|
| EMA 20 / 50 (existing) | 20, 50 | 50 | regime, strategies |
| EMA 200 | 200 | 200 | trend category |
| +DI / −DI, ADX (existing) | 14 | 28 | regime; DI spread in trend category |
| Session VWAP | anchored at the session start: 17:00 New York (DST-aware) for FX, metals, indices, oil; 00:00 UTC for BTCUSDT | first candle of the session; needs reliable volume; timeframes ≤ 1H | trend category |
| RSI (existing) | 14 | 15 | strategies; momentum evidence |
| MACD | 12 / 26 / 9, histogram | 35 | momentum category |
| Stochastic RSI | RSI 14, stochastic 14, %K 3, %D 3 | 34 | momentum category |
| ROC | 10 | 11 | momentum category |
| ATR (existing) | 14; percentile over 200 | 50 (percentile) | volatility category; VSA spread |
| Bollinger Bands and width (existing width) | 20, 2.0 | 20 | evidence |
| Keltner Channels | EMA 20 ± 2.0 × ATR 10 | 20 | volatility category (volatility expansion) |
| Historical volatility | stdev of log returns, 20; percentile over 200 | 70 | evidence |
| Volume SMA | 20 | 20 | evidence |
| OBV | cumulative; 20-candle slope vs price slope | 20 | evidence only |
| MFI | 14 | 15 | evidence only, labelled with the volume type |

## 5. VSA (`strategy_engine/vsa.py`)

**Bar measures** (all thresholds in `config.py`, fixed for Experiment 6):

| Measure | Definition |
|---|---|
| Spread | (high − low) / ATR 14. Wide ≥ 1.2, narrow ≤ 0.6 |
| Close position | (close − low) / (high − low); 0.5 when high = low. Top third ≥ 0.67, bottom third ≤ 0.33 |
| RVOL tier | low ≤ 0.7, high ≥ 1.5, ultra ≥ 2.5 |
| Prior move | net close change over the previous 8 candles, in ATR |

**Events.** Each event records the candles, the measures and its confirmation state. High volume alone never produces an event.

| Event | Required price context | Volume and bar | Confirmation (completed later candles) |
|---|---|---|---|
| Climactic volume | prior move ≥ 2 ATR in the bar's direction | ultra RVOL, wide spread | none; reported as a possible exhaustion |
| Stopping volume (bullish; bearish mirrors) | prior move ≤ −2 ATR | down bar, high or ultra RVOL, close not in the bottom third | no close below the bar's low within 3 candles |
| No demand (no supply mirrors) | close above the close 5 candles ago | up bar, narrow spread, RVOL ≤ 1.0 and below each of the 2 previous candles | none |
| Upthrust (spring mirrors) | trades above a meaningful level: a swing high of the last 50 candles, a range high or the previous day's high | closes back below the level, in the bottom third, RVOL ≥ 1.0 | no close above the bar's high within 3 candles |
| Test bar | within 10 candles after a spring or bullish stopping volume | trades within 0.3 ATR of that event's low, low RVOL, close in the top half | none |
| Effort without result | any | high RVOL, narrow spread | none |
| Result without effort | any | low RVOL, wide spread | none |
| Potential absorption | effort without result at a meaningful level, against the prior move | as above | price moves ≥ 1 ATR away from the level within 5 candles |
| Potential accumulation (distribution mirrors) | an established range from the range-reversion detector | at least one spring or bullish stopping volume plus one test bar inside the range | the events' own confirmations |

**Unconfirmed events.** An event whose confirmation window has not finished is shown as "unconfirmed". It cannot make a
category PASS.

**Buying and selling pressure:**
- **BTCUSDT:** the share of taker-buy volume in each candle, from Binance; ≥ 0.55 is buying, ≤ 0.45 is selling. The live Binance
  adapter is extended to keep this field (the archive already has it).
- **Other instruments:** inferred from the close position only, and labelled "inferred from price".

Pressure is shown as evidence and is not part of any verdict, so the rules are the same on every instrument.

## 6. Confirmation matrix (`strategy_engine/confirm.py`)

Ten components. Each returns PASS, FAIL, NEUTRAL or UNAVAILABLE, the reason in words, and the raw evidence (indicator values,
VSA events). UNAVAILABLE never counts as a pass.

| # | Component | Kind | Source |
|---|---|---|---|
| 1 | Market regime | mandatory | the regime classifier: compatible → PASS; incompatible or high volatility → FAIL; insufficient data → UNAVAILABLE |
| 2 | Higher-timeframe context | mandatory | the strategy's existing context rule; no context timeframe → NEUTRAL |
| 3 | Strategy entry | mandatory | trigger met → PASS; waiting for its trigger → NEUTRAL with the exact condition; rejected → FAIL |
| 4 | Market structure | mandatory | the strategy's structural condition (break of structure, zone, range, sweep, market-structure shift, box) |
| 5 | VSA | evidence | section 7 |
| 6 | Momentum | evidence | section 7 |
| 7 | Trend | evidence | section 7 |
| 8 | Volatility | evidence | section 7 |
| 9 | Execution | mandatory | spread limit, session block, stale data (existing rules) |
| 10 | Risk/reward | mandatory | TP1 ≥ 1.5R and the plan's own validation (existing rules) |

**Mandatory components decide exactly as today.** This layer only labels them. To make that possible, each strategy tags every
condition it checks with a component (1-4) and returns its key candles (`anchors`):
- the pullback candles and the trigger candle;
- the breakout candle and the retest candles;
- the displacement candle and its pullback;
- the boundary touches;
- the sweep candle and the candles after it;
- the expansion candle.

**One verdict per category.** Indicators that measure the same thing never add up. Momentum is decided by one primary
indicator per strategy, and the others are shown as evidence. Trend uses only signals the regime classifier does not already
use.

## 7. Category rules per strategy

Common rules (Trend, and Volatility for five strategies):

- **Trend.** Up to three sub-signals, each scored for, against or flat:
  - close vs EMA 200;
  - +DI minus −DI in the trade's direction: ≥ 5 is for, ≤ −5 against, anything between is flat;
  - close vs session VWAP, on timeframes ≤ 1H with reliable volume.

  | Verdict | When |
  |---|---|
  | PASS | at least two sub-signals for, none against |
  | FAIL | at least two against |
  | NEUTRAL | anything else |
  | UNAVAILABLE | fewer than two sub-signals available |

- **Volatility** (all except volatility expansion), from the ATR 14 percentile over 200 candles:

  | Verdict | ATR percentile |
  |---|---|
  | PASS | 20 to 90 |
  | FAIL | above 95, or below 10 (too quiet: costs are large next to the move) |
  | NEUTRAL | otherwise |

Strategy-specific rules ("for" = in the trade's direction):

| Strategy | Momentum (primary indicator) | VSA (needs reliable volume) | Volatility |
|---|---|---|---|
| Trend-following pullback | MACD histogram rising 2 candles in a row for the trade → PASS; falling 2 in a row → FAIL (RSI is already in the entry rule) | PASS: pullback candles average RVOL ≤ 0.8 and none is a wide-spread, high-RVOL candle closing in the pullback's direction. FAIL: pullback average ≥ 1.3, or such a candle exists | common |
| Breakout and retest | ROC 10 for the trade → PASS, against → FAIL; NEUTRAL when the 10-candle price change is within ±0.25 ATR | PASS: breakout candle RVOL ≥ 1.5 and retest candles average ≤ 1.0. FAIL: breakout candle RVOL < 1.0 | common |
| Momentum continuation | MACD histogram for the trade and at least as large as 3 candles ago → PASS; histogram against → FAIL (ADX and RSI are already in the entry rule) | PASS: displacement candle RVOL ≥ 1.5 and its pullback averages below 0.6 × that. FAIL: displacement RVOL < 1.0, or a climactic candle in the trade's direction in the last 3 candles (exhaustion) | common |
| Range mean reversion | Stochastic RSI %K crosses %D for the trade within the last 2 candles, from beyond 20 (BUY) or 80 (SELL) → PASS; %K beyond the opposite extreme → FAIL | PASS: in the last 3 candles at the boundary, a spring/upthrust, a no-supply/no-demand candle, or effort without result. FAIL: a wide-spread, high-RVOL candle closing against the trade in the last 3 candles | common |
| Liquidity-sweep reversal | MACD histogram rising 2 candles for the trade → PASS; falling 2 → FAIL | PASS: the sweep candle has RVOL ≥ 1.2 and closes back inside (stopping-volume type), or a test candle follows the sweep. FAIL: after the sweep, a wide-spread, high-RVOL candle closes in the sweep's direction | common |
| Volatility expansion | ROC 10, as breakout and retest | PASS: expansion candle RVOL ≥ 1.5. FAIL: below 1.0 | close beyond the Keltner band for the trade → PASS; close on the far side of its middle line → FAIL |

Any case not listed is NEUTRAL. A missing input makes the category UNAVAILABLE.

**Required combination per strategy** (from the owner's brief), tested as one arm:

| Strategy | Required categories |
|---|---|
| Trend-following pullback | trend + momentum + VSA |
| Breakout and retest | VSA + trend |
| Momentum continuation | trend + momentum + volatility |
| Range mean reversion | momentum + VSA |
| Liquidity-sweep reversal | momentum + VSA |
| Volatility expansion | volatility + VSA |

## 8. Gates

- **Gate table.** `config.GATES` maps instrument → strategy → promoted categories. It is empty at release, and only a commit
  that cites the Experiment 6 report may fill it.
- **Effect of a promoted category.** If its verdict is anything other than PASS, a BUY or SELL becomes a WAIT: "missing
  confirmation: momentum (MACD histogram falling)". This is the same rule the experiment tests: keep a trade only on PASS.
- **Scope.** A gate applies only to the instrument it passed on. Instruments without research data (EURUSD, GBPUSD, US30, USOIL)
  get no gates until they are tested.
- **Gold VSA.** It is never a gate (section 1). This covers every gold combination that includes VSA, which is five of the six;
  on gold, only momentum continuation's combination (trend + momentum + volatility) can be promoted.

## 9. API and interface

**API.** Each timeframe result gains three fields:
- `confirmations`: the ten components, each with verdict, reason, evidence, `mandatory`, `gating` and `promoted_by`;
- `volume`: type, customer label, reliable, reason;
- `vsa`: recent events with their confirmation state.

The instrument summary carries the primary plan's matrix.

**Signal card:**
- **Summary:** a row of chips (Trend, Structure, VSA, Momentum, Volatility, Spread, R:R), each showing its verdict. An "evidence
  only — not tested" mark stays until the category is promoted, then becomes "gate: Experiment 6".
- **Expanded view:** each indicator's value, the VSA events with the volume type named, and the reason for every verdict.
  Negative evidence is never hidden.
- **VSA states:** confirming (PASS), neutral, contradictory (FAIL), unavailable (with the reason, for example "no reliable volume").
- **WAIT** names the missing mandatory condition and any failing evidence. **NO TRADE** names the mandatory condition that
  failed.
- No win probability is shown.

## 10. Integrity tests

- **No look-ahead.**
  - For every new indicator, the volume baseline, VSA labels and the matrix, a run on candles cut at *i* equals the full run at
    *i*.
  - VSA confirmations use only candles after the event, and only once they are complete.
- **Warm-up.** Before each indicator's first valid candle the value is NaN and the verdict is UNAVAILABLE.
- **Sessions.** VWAP anchors and hour-of-week baselines across both daylight-saving switches (New York and Europe) and the
  Sunday reopen.
- **Volume quality.** Missing, all-zero and constant volume make VSA UNAVAILABLE; a volume type is never mislabelled.
- **Replay equals live.** The engine replayed at a past candle gives the same matrix as the live path on the same candles.
- **Mandatory components unchanged.** The engine's decisions on the existing test fixtures are identical with the layer on
  and empty gates.
- **Each rule in section 7.** A worked example with hand-checked numbers for PASS, FAIL, NEUTRAL and UNAVAILABLE.

## 11. Not in scope

- An indicator-only signal generator.
- Win probabilities.
- Gates on instruments without research data.
- Order-flow or footprint data, which no free source provides.
- Gold VSA as a gate.
