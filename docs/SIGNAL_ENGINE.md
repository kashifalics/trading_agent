# Signal engine — design and methodology

_Status: built 2026-11-07 (sub-project 1 of the trading-bot brief). Analysis only: nothing here places orders or connects to a broker._

## Purpose
Produce actionable, explained trade plans on every timeframe that has enough data, using top-down multi-timeframe price action:
higher-timeframe bias → setup timeframe → confirmation timeframe. Each plan has a structural entry, stop loss, up to three
structural targets, a transparent 100-point confluence score, an entry state, a final instruction, and a measured track record.

**Confluence score is not a win probability.** A win probability is shown only where the same rules have been replayed on
history and passed out-of-sample validation (`app/data/signal_track_record.json`); otherwise every plan says
"Win probability: not yet statistically validated".

## Where it sits
```
frontend /signals ──REST──▶ /api/v1/signals/*  (app/api/v1/routes/signals.py)
                               │
  app/signals/ service.py     load candles per timeframe (single provider per instrument), quotes, market hours, cache, lifecycle memory
               engine.py      pure: frames (Bars per timeframe, as of time T) → per-timeframe plans + instrument summary + report
               context.py     per-timeframe market read (trend class, structure, liquidity, previous day/week levels)
               plan.py        entry / stop / targets / must-pass rules for one direction
               scoring.py     100-point confluence checklist
               track_record.py  reads the replay results
               config.py      chains, groups, weights, thresholds, spreads (one place, versioned)
  app/research/run_signal_track_record.py   replays engine.py bar by bar on stored history → JSON + docs/reports/SIGNAL_TRACK_RECORD.md
reused: market_data (providers, aggregation, calendars), price_action, market_structure, candlestick, levels, opportunities.analysis loaders
```
The engine is a pure, causal function of the candles it is given, so the live page and the historical replay run identical code.

## Timeframe chain
| Setup TF | Bias TFs (intermediate, higher) | Confirmation TF | Group |
|---|---|---|---|
| 1m, 3m | 15m, 1H | 1m | scalping |
| 5m | 1H, 4H | 1m | scalping |
| 15m | 1H, 4H | 5m | intraday |
| 30m | 4H, 1D | 5m | intraday |
| 1H, 2H | 4H, 1D | 15m | intraday |
| 4H | 1D, 1W | 1H | swing |
| 1D | 1W, 1M | 4H | swing |
| 1W | 1M, 3M | 1D | position |
| 1M | 3M, 12M | 1W | position |
| 3M, 6M | 12M | 1M | position |
| 12M | — | 3M | position |

Higher-timeframe candles are used only once **closed** at the setup bar's close. A setup timeframe needs ≥ 120 complete candles;
a bias timeframe needs ≥ 60. Missing timeframes are reported, never assumed.

| Group | Min R:R (TP1) | Stop size | Max cost / risk | Confirm window | Expires after | Max staleness | Session filter |
|---|---|---|---|---|---|---|---|
| scalping | 2.0 | 0.5–2.5 ATR | 0.25 R | 3 bars | 12 bars | 3 bars | yes |
| intraday | 2.0 | 0.6–3.0 ATR | 0.20 R | 4 bars | 16 bars | 4 bars | yes (≤ 2H) |
| swing | 2.0 | 0.75–4.0 ATR | 0.15 R | 4 bars | 20 bars | 3 bars | no |
| position | 2.0 | 0.75–4.0 ATR | 0.10 R | 3 bars | 12 bars | 2 bars | no |

## Per-timeframe market read
Direction class from three causal facts: `s` = last close-based break of structure (BOS/CHoCH) direction, `h` = swing sequence
(last two swing highs and lows rising = +1, falling = −1), `e` = close on the same side of EMA50 as EMA50's 10-bar slope.
* strong bullish/bearish: `s = h = e ≠ 0` · bullish/bearish: `s ≠ 0` and (`h = s` or (`h = 0` and `e ≠ −s`)) ·
  transitioning: `s ≠ 0` and (`h = −s` or (`h = 0` and `e = −s`)) · `s = 0`, `h ≠ 0`: bullish/bearish by `h` · otherwise ranging.
Also: swing labels (HH/HL…), last structural event, premium/discount position, nearest live zones, unswept equal highs/lows,
recent sweeps, previous day/week high and low.

## Setup types and entry
A plan needs a **logical entry location**. Candidate locations (same side as the trade): unmitigated order block, FVG,
supply/demand zone, breaker (≤ 300 bars old), support/resistance band, or the level broken by a recent BOS (retest).
* **At the zone** (traded into it within the last 2 × confirm-window bars and price is inside it or ≤ 0.5 ATR beyond its near edge):
  market entry at the last close.
* **Zone ahead** (≤ 1.5 ATR away): limit entry at the zone's near edge.
* **Liquidity sweep + structure break** with no zone: market entry, stop beyond the sweep extreme.
* Otherwise: no setup ("no logical entry location"). Price never gets chased.

Setup type: `liquidity_sweep_reversal` (same-direction sweep followed by a same-direction BOS/CHoCH), `bos_retest` (entry at a
broken level or a confirmed retest), `trend_pullback` (setup-TF structure agrees), `countertrend_zone` (zone against structure).

## Stop loss and targets
* Stop: beyond the furthest of zone far edge, protecting confirmed swing (within 1 ATR of the zone) and, for sweep setups, the sweep
  extreme; plus a 0.25 ATR buffer. Too tight → widened to the group minimum (noted). Too wide → **blocked**.
* Targets: confirmed swing highs/lows, S/R bands, equal highs/lows (liquidity), opposing zones, previous day/week high/low.
  TP1 = nearest target at ≥ min R:R. A **strong** opposing level (S/R band, unswept equal highs/lows, opposing OB/supply/demand/breaker)
  closer than 1R **blocks** the plan (no room to move); one between 1R and the minimum R:R costs the risk-to-reward points and is listed
  as a reason against ("consider partial profit there"). If no structural target reaches the minimum R:R the plan is **blocked**.
  TP2/TP3 = next targets ≥ 0.5 ATR apart, only if real structure exists (none are invented).
  Price discovery (no structure at all beyond entry) → TP1 is a labelled 2R volatility multiple.
* Cost: round-trip spread (BTCUSDT $2, XAUUSD $0.30; configurable `SIGNAL_SPREADS`) must stay ≤ the group's max share of risk.
* Invalidation: a close beyond the stop's structural anchor.

## Confluence score (100 points)
| Factor | Max | Checks |
|---|---|---|
| Higher-timeframe alignment | 20 | each bias TF agreeing with the direction: 10 (strong or normal class); opposing or unavailable: 0 |
| Market structure | 20 | setup-TF class agrees 10 · same-direction BOS/CHoCH within 20 bars 10 |
| Liquidity event | 15 | sweep (swing low/high, equal lows/highs, previous day/week level) within 3 × confirm window followed by a same-direction break 15; sweep only 8 |
| Entry-zone quality | 15 | entry at a valid zone/level 7 · discount (BUY) / premium (SELL) half of the dealing range 4 · confluence with another zone, an S/R band (≥ 2 touches) or a trendline (≥ 3 touches) 4 |
| Lower-timeframe confirmation | 15 | same-direction BOS/CHoCH on the confirmation TF after the zone touch 8 · rejection candle (engulfing, hammer, pin bar, star) at the zone after the touch 7 |
| Risk-to-reward | 10 | 5 at the minimum R:R rising linearly to 10 at twice the minimum; 0 when a strong opposing level sits between entry and TP1 |
| Session and volatility | 5 | ATR between its 15th and 90th percentile 3 · candle closed 07:00–20:00 UTC (London/New York) 2 (TF ≥ 4H: not applicable, awarded) |

Anything that cannot be measured scores 0. Weights were set a priori, not fitted.

## Entry states and final instruction
| State | Condition | Final instruction |
|---|---|---|
| NO_SETUP | no plan, score < 40, stale data, or unclear structure | NO TRADE |
| WATCHLIST | score 40–59, or ≥ 60 but blocked by a must-pass rule | NO TRADE (reason shown) |
| SETUP_DEVELOPING | ≥ 60, zone ahead (limit plan) | PLACE LIMIT ORDER if ≥ 70, else WAIT FOR CONFIRMATION |
| WAITING_FOR_CONFIRMATION | ≥ 60, price at the zone, no confirmation yet | WAIT FOR CONFIRMATION (conditions listed) |
| ENTRY_READY | ≥ 60, price at the zone (or sweep + break) and confirmation present | EXECUTE NOW |
| TRADE_INVALIDATED / TRADE_EXPIRED | the previous actionable plan on this TF was closed through / reached TP1 / timed out | NO TRADE |

Live-only downgrades: market closed (calendar) or live spread > 3× the configured spread → ENTRY_READY / limit become WAIT.
If BUY and SELL both qualify the higher score wins; a tie is NO_SETUP (conflict). The news filter is **unavailable** (no calendar
integration) and is reported as such on every plan.

## Instrument summary
Overall bias = weighted vote of timeframe classes (1W 3, 1D 3, 4H 2, 1H 2, 15m 1, 5m 1). Best plan = highest state
(ENTRY_READY > WAITING > DEVELOPING), then score, then higher timeframe. The report contains: market overview, multi-timeframe table,
decision, execution plan, reasons for, reasons against, final instruction.

## Track record (honest confidence)
`python -m app.research.run_signal_track_record run|export|report` replays `engine.py` bar by bar on stored candles
(BTCUSDT Binance, XAUUSD Twelve Data): market entries at the next bar's open after a new ENTRY_READY, limit orders for
PLACE LIMIT ORDER plans, exits at stop or TP1, same-bar stop+target counted as a loss, spread charged per round trip, one position
per instrument × timeframe. First 60% development, last 40% out-of-sample; status via the existing `classify()` rules. Reported per
instrument × timeframe: trades, TP1 hit rate, expectancy (R), profit factor, by score bucket, setup type, session and direction, plus
the Brier score and reliability of `score/100` read as a probability (to show whether the score is calibrated).

## Limitations
* Single provider per instrument (no mixing). BTCUSDT uses Binance (deep history); XAUUSD uses BiQuote broker quotes
  (shallow history: ~1 week of 1H, ~500 days of 1D, no weekly/monthly), so some timeframes report insufficient data.
* Lifecycle states (invalidated / expired) are kept in memory and reset when the API restarts; signal history is sub-project 3.
* No position sizing beyond the page's lot-size calculator (sub-project 2), no alerts (4), no execution (6).
