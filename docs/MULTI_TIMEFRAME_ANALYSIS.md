# Multi-timeframe analysis

## Timeframes and statuses
Analysed independently: `1m 3m 5m 15m 30m 1H 2H 4H 1D 1W 1M 3M 6M 12M`. Each gets one status per scan:
| Status | Meaning |
|---|---|
| Completed | ≥ 120 complete candles (native, or derived from a lower stored timeframe) and analysis succeeded |
| Running | A scan is in progress (summary shows `running_scan`) |
| Insufficient data | Fewer than 120 complete candles, or none stored; the reason and the count are shown |
| Unsupported | The provider cannot serve this timeframe and it cannot be derived |
| Failed | The analysis raised an error; the error is shown. One failed timeframe never fails the scan (tested) |

## Data integrity rules
* **Complete candles only.** The forming candle is excluded (tested with an absurd-range incomplete candle).
* **UTC.** Candle open times are UTC; daily and longer buckets use the instrument's session anchor and market calendar.
* **Derivation, only when necessary and valid.** If the stored native series has < 120 bars, the timeframe may be built from
  `3m←1m, 2H←1H, 4H←1H, 1W←1D, 3M/6M/12M←1M` with the existing aggregator: only buckets whose every expected base candle (per the market
  calendar) is present are emitted; incomplete buckets are dropped. A derived timeframe is labelled in the UI and scalping refuses derived candles.
* **No invented data.** Missing OHLC is never filled. Gaps are counted inside the analysed window: 1–2 missing intraday candles
  (maintenance breaks, holidays) are listed but not penalised; longer holes are penalised.
* **Freshness.** `stale_bars` = completed candles expected by the market calendar but not stored. Scalping needs ≤ 3.
* **Caching.** Signature = hash(config version, instrument, provider, timeframe, bar count, first/last open time, first/last close,
  derivation, gap count). Unchanged ⇒ reuse; the style level reuses opportunities when every timeframe it uses is unchanged.
* **Provider limits.** A scan reads stored candles. `refresh_data` syncs at most `OPPORTUNITY_MAX_SYNC_TFS` stale timeframes per
  instrument through the existing rate-limited adapters; scheduled scans only refresh providers in `OPPORTUNITY_REFRESH_PROVIDERS`.

## Per-timeframe analysis (trade-agnostic)
Structure trend and bias (swing HH/HL/LH/LL), last BOS/CHoCH, premium/discount position, ATR, momentum (10-bar move, 20-bar slope, RSI),
live FVG / order-block / breaker / supply-demand zones, support/resistance bands, trendlines and channels, breakouts/retests/failed
breakouts, candlestick patterns of the last 5 bars, notable sweeps and breaks.

## Concept definitions (all explicit, parameterised and tested)
| Concept | Definition (defaults) |
|---|---|
| Swing high/low | Strictly higher/lower than 3 bars each side; known only 3 bars later (`confirm_idx`) |
| HH/HL/LH/LL | Compared with the previous swing of the same kind |
| BOS / CHoCH | Close beyond the last confirmed unbroken swing in the direction of / against the prevailing trend |
| Equal highs/lows | Two swings within 0.1 ATR |
| Liquidity sweep | Wick beyond a resting swing level with a close back inside |
| FVG | `low[i] > high[i-2]` (bullish) or mirror, ≥ 0.1 ATR |
| Order block | Last opposite candle before an impulse that breaks structure with ≥ 1.5 ATR displacement |
| Breaker block | An order block that failed and flipped polarity |
| Supply/demand | 1–3 bar base followed by a ≥ 1.5 ATR impulse |
| Premium/discount | Close position within the last confirmed swing range (equilibrium 50% ± 5%) |
| **Support/resistance** | ≥ 2 confirmed swing extremes within 0.5 ATR; role from where price sits (new, `price_action/levels.py`) |
| **Trendline / channel** | Line through two swings with ≥ 3 touches within 0.3 ATR and no close beyond it by > 0.3 ATR; channel = parallel support+resistance (slopes within 25%) |
| **Breakout** | Close beyond a band by ≥ 0.25 ATR, in the direction **away from the side price had been on** (median of 10 prior closes) |
| **Retest** | Within 12 bars of a breakout, price re-enters the band and closes on the breakout side |
| **Failed breakout** | Within 5 bars of a breakout, a close back on the original side |
Order blocks, sweeps and the rest are detections of a stated rule, never labels for "institutional" activity. All are causal (uses only
information confirmed by the bar at which the event is stamped); the S/R detector has an explicit no-look-ahead test.

## Higher-timeframe bias
For a setup timeframe the bias timeframes are fixed in `BIAS_TFS` (e.g. `5m→30m,1H`, `15m→1H,4H`, `1H→4H,1D`, `4H→1D,1W`, `1D→1W,1M`).
Only higher-timeframe candles that were **complete when the setup bar closed** are used (`htf_as_of`). Bias = weighted structure direction
(higher 0.5, intermediate 0.3); `conflict` = the two disagree. A bias opposing the trade blocks it; a conflict is penalised.

## Trading styles
| Style | Setup timeframes | Min R/R | Stop (ATR) | Max cost | Notes |
|---|---|---|---|---|---|
| Scalping | 1m 3m 5m 15m | 1.5 | 0.5–2.5 | 0.20 R | Native-resolution candles only; ≤ 3 bars stale; refuses when round-trip cost eats > 0.20 R |
| Intraday | 5m 15m 30m 1H 2H | 1.8 | 0.6–3.0 | 0.15 R | Session structure through HTF bias |
| Swing | 1H 2H 4H 1D | 2.0 | 0.75–4.0 | 0.10 R | |
| Long-term | 1D 1W 1M 3M 6M 12M | 2.0 | 0.75–4.0 | 0.10 R | **Technical price-structure view, not a fundamental or macro forecast** |

## Setup generation (`setup.py`)
Allowed only when: (1) HTF bias is not opposed **and** either setup-timeframe structure agrees (*trend pullback*) or a sweep was followed
by a same-direction BOS/CHoCH (*sweep reversal*); (2) a **structural** entry exists — an unmitigated same-side zone or an S/R band at, or within
1.5 ATR of, price; (3) a structural stop exists beyond the zone/protecting swing (+0.25 ATR) within the style's ATR bounds; (4) a structural
first target ≥ min R exists with no strong opposing structure (opposing zone, S/R band, equal highs/lows) before it — if price has no structure
beyond it at all, a *labelled* volatility multiple is used; TP2 is the next level (or a labelled 1.5× extension); TP3 only if a third level exists;
(5) round-trip cost ≤ the style's cap; (6) the first target has not already been reached after the zone touch.
Status: `waiting_for_confirmation` until price has traded into the zone **and** a confirming event (rejection candle, BOS/CHoCH, sweep, retest)
appeared at or after the touch → `entry_triggered`. Later scans move it to `invalidated` (a close beyond the invalidation level), `expired` (target
reached or lifetime elapsed). A published plan's levels never drift between scans, and a trigger is never un-triggered.
If the evidence score is below the style's publish threshold the row is shown as **WAIT / Watchlist** with *reference levels only*.

## Historical analogues (`analogue.py`)
The existing point-in-time engine: 22 scale-free features (returns in ATR, body/wick proportions, volatility, slope, EMA distance, range position,
RSI, structure trend, premium/discount, FVG/sweep/break counts), robust scaling fitted on library rows only, library = bars whose outcome
(triple barrier, style-specific target/stop/horizon) was fully known at the query bar, picks ≥ 12 bars apart. Added: direction-aware TP-first / SL-first /
MFE / MAE, forward returns at H/4, H/2, H bars (ATR units), Wilson CIs, base-rate comparison, a sample-quality verdict (`<30 insufficient`, `<100 limited`,
else `moderate`) and a "within sampling noise" flag. They are **historical frequencies of similar situations, not the probability the current trade works.**
