# System audit for the strategy engine (2026-11-13)

Scope: everything the strategy-driven engine would build on. The trading engine, data, indicators, price action, ML, research,
backtesting, signals, risk, APIs, frontend and tests. Verdicts: **reliable** (keep as is), **incomplete** (extend), **redesign**.

## 1. Architecture today

```
providers (BiQuote, Binance, Twelve Data*, Dukascopy files)  ->  candles DB (SQLite on Railway; PostgreSQL supported)
   -> timeframes (native or aggregated from complete lower-TF buckets) -> price action (swings, BOS/CHoCH, FVG, OB, breakers,
      supply/demand, premium/discount, levels/ranges/breakouts) -> signal engine v1 (app/signals: score 100-point checklist,
      4 setup types, plan with structural stop and up to 3 structural targets, in-memory lifecycle)
   -> decision layer (app/decision: one call per instrument x timeframe) -> API (/api/v1/signals, /opportunities, /paper, ...)
   -> Next.js frontend (Signals, Scanner, Overview, Paper Trading, ...)
paper-trading cycle (every 60 s): sync -> analyse -> record every technically complete v1 setup -> simulate on 1-minute candles
```
\* Twelve Data needs a key and is quota-limited, so it is not synced automatically.

## 2. Component verdicts

| Area | What exists | Verdict |
|---|---|---|
| Market data | BiQuote (XAUUSD, EURUSD, GBPUSD, US30, USOIL: spot/CFD quotes and candles, keyless), Binance (BTCUSDT, keyless, deep history), Twelve Data (key, quota), Dukascopy M1 bid/ask XAUUSD 2003-2026 on disk (research only). One provider per instrument, never mixed. | Reliable for live analysis. **Incomplete for research:** see section 3. |
| Candle aggregation | Higher timeframes built only from complete lower-TF buckets; FX/metals calendar (closed-market bars dropped); 17:00 New York day anchor where configured; staleness per timeframe; gap detection. | Reliable (tested: aggregation equals direct M1 aggregation in the gold study). |
| Timeframes | 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 1D, 1W, 1M (+3M, 6M, 12M). | **H8 is missing**: it can be built from 1H the same way as other derived timeframes (added in v2). BiQuote has no monthly series. |
| Indicators | ATR, EMA, RSI, rolling sums (`feature_engineering/indicators.py`). | **Incomplete:** no ADX/DMI, Bollinger width or efficiency ratio as live indicators (the gold study computes ER and EMA slope internally). Added in v2. |
| Price action | Swings, BOS, CHoCH, liquidity sweeps, equal highs/lows, FVG, order blocks, breakers, supply/demand, premium/discount, S/R bands, trendlines, channels, breakouts, retests, failed breakouts. Look-ahead tests exist. | Reliable. Reused by every v2 strategy. |
| Regimes | `gold_research/regimes.py`: trend/range/volatility/structure/session labels, point-in-time, scale-free. Descriptive (study features), not a selector. | Reusable logic; **a live classifier with TRENDING / RANGING / CONSOLIDATING / HIGH-VOLATILITY / UNKNOWN does not exist.** Built in v2. |
| Signal engine v1 | 4 setup types (trend pullback, BOS retest, liquidity-sweep reversal, countertrend zone) chosen inside one 100-point confluence score; structural stop + 0.1 ATR buffer; targets = first structural levels at >= the group's minimum R:R (2R); market or limit entry; in-memory lifecycle. | Works and is tested. **Redesign needed for the brief:** the strategies are not independent modules, the regime does not select them, the score mixes all setups, and the lifecycle is lost on restart. **Kept unchanged** because the paper forward test evaluates exactly these rules. |
| Trade plan | Entry, structural stop, TP1-3 (often only TP1), risk in ATR, spread cost in R, blocked/warning reasons. | **Incomplete:** no tick-size rounding; TP2/TP3 often missing; no explicit side/ordering validation; no expiry fields in the customer output. Fixed in the v2 plan builder. |
| Decision layer | `app/decision`: one call per timeframe (ENTER / HOLD / WAIT / EXIT / NO TRADE); ENTER only for validated rules; open paper trades override the call. | **Redesign:** the new vocabulary is BUY / SELL / WAIT FOR BUY / WAIT FOR SELL / EXIT / NO TRADE. Technical status and research status are separate, and paper-trade management must not hide a new opportunity. |
| Risk | Position-size calculator (frontend), paper account rules (risk %, max open positions, daily loss limit), spread-cost filter in the plan. | **Incomplete:** there is no central module, no aggregate or correlated exposure, no drawdown stop, no session or volatility filters. Built in v2. |
| News / sessions | No economic calendar ("news not filtered" is shown). Sessions in New York time exist in the research code. | News: **unavailable** (section 3). Sessions: reusable, DST-correct via zoneinfo. |
| ML | Logistic/LightGBM/XGBoost toolkit, purged walk-forward, calibration, registry; models exist as "research only"; **no model passed validation**. | Reliable toolkit; nothing to promote. Phase 10 waits for a rule-based edge. |
| Research | Gold study (Experiments 1-4): 1,981 trials, matched random controls, BH/q, deflated Sharpe, sealed final test. **No validated candidate.** | Reliable method; **results are negative**. They are preserved, and the sealed period stays sealed. |
| Backtesting | Strategy replay with M1 intrabar resolution (`gold_research/sim.py`), bid/ask costs, signal-track-record replay for v1. | Reliable; reused by the experiment plan. |
| Paper trading | Forward test of v1: 223 closed trades, -0.25R per trade (95% CI -0.48 to +0.01), exits at stop or TP1 with no time stop. | Reliable record; **v1 shows no edge**. |
| API / frontend | Every page shows the backend decision; auto-refresh; CSP; accessibility AA (QA audit of 2026-11-12). | Reliable. Signals page redesigned in v2. |
| Tests | Backend about 400 (pytest), frontend 72 (vitest), end-to-end 8 (Playwright). | Reliable. Each v2 module gets its own tests. |

## 3. Data-quality assessment (what the data can and cannot support)

Live store on the production server (2026-11-13). Candle counts, oldest candle in brackets:

| Instrument (provider) | 1m | 5m | 15m | 1H | 4H | 1D | 1W |
|---|---|---|---|---|---|---|---|
| XAUUSD (BiQuote) | 6,472 (11-06) | 1,525 (11-05) | 605 (11-04) | 272 (10-28) | 208 (09-28) | 505 (2025-03) | 80 |
| EURUSD, GBPUSD (BiQuote) | ~4,740 (11-10) | ~1,180 | 489 | 242 (10-30) | 199 (09-30) | 502 (2025-04) | 81 |
| US30, USOIL (BiQuote) | ~6,470 | 1,524 | 604 | 271 | 208 | 505 | ~80 |
| BTCUSDT (Binance) | 8,607 | 2,200 | 1,132 | 732 | 632 | 605 | 482 |

Consequences:
- **Live analysis is supported** on every timeframe up to 1D (enough candles for structure, ATR, ADX and Bollinger width).
- **Live history is far too short for research.** Two weeks of 1H data cannot test a strategy. The only deep data is Dukascopy XAUUSD
  M1 bid/ask (2003-2026). Its final 15% is sealed, so development and validation must stay inside the 2003-~2022 training and
  validation segments.
- **FX majors have no deep history on disk.** Dukascopy publishes EURUSD and GBPUSD M1 bid/ask for free, the same source as gold.
  Downloading it is a data step listed in the experiment plan, not run yet.
- **No volume data.** Spot FX and gold have no real volume; Dukascopy tick counts are a broker-specific activity proxy. Strategy F
  must therefore not depend on volume. Tick activity is reported only as an optional research feature.
- **News:** there is no free, documented and reliable economic-calendar API. The commonly used ForexFactory weekly XML feed is
  unofficial, has no history and no service guarantee. The news filter therefore stays **unavailable** and the product says so.
  The design keeps a pluggable interface for a future source.
- **Spreads:** live bid/ask comes from BiQuote quotes (delayed flag honoured); the research has real Dukascopy bid/ask. Slippage and
  commission are scenario assumptions, not measurements.
- **Timestamps:** stored in UTC; sessions are computed in Europe/London and America/New_York with zoneinfo, so DST changes are
  handled by the tz database.

## 4. What must be redesigned, and what is kept

Kept as is: data pipeline, aggregation, price-action detectors, research method and results, sealed split, paper forward test of v1,
backtest simulator, ML toolkit, API/security/frontend infrastructure.

Built new (v2, beside v1):
- live regime classifier;
- six independent strategy modules with documented rules;
- strategy selector with conflict resolution;
- trade-plan builder (tick rounding, side checks, TP1-3, costs, expiry);
- central risk module and session filter;
- persistent signal lifecycle;
- the BUY / SELL / WAIT FOR BUY / WAIT FOR SELL / EXIT / NO TRADE decision;
- the redesigned Signals page.

Not built without approval: any profitability experiment (the plan is in `EXPERIMENT_PLAN.md`) and any promotion of a strategy to
"validated".
