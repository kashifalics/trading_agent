# Strategy engine v2: implementation and testing report (2026-11-13)

Covers both briefs of 2026-11-13: the clear BUY/SELL signal system and the strategy-driven engine. Companion documents: `AUDIT.md`
(audit and data quality), `DESIGN.md` (architecture, regime classifier, six strategy specifications, entry/SL/TP rules, risk,
sessions), `EXPERIMENT_PLAN.md` (**awaiting approval, nothing run**).

**Status: implemented and tested locally. Not pushed, merged or deployed** (owner approval needed).

## 1. What was built

| Part | Where | Notes |
|---|---|---|
| Indicators | `app/feature_engineering/indicators.py` | ADX with +DI/-DI (Wilder), Bollinger width, efficiency ratio, trailing percentile; causal, NaN until defined |
| Regime classifier | `app/strategy_engine/regime.py` | TRENDING, RANGING, CONSOLIDATING, HIGH_VOLATILITY, UNKNOWN (insufficient data / transitional); returns every input and criterion; no probability |
| Six strategies | `app/strategy_engine/strategies/*.py` | One module each, own rules and messages; returns ready / pending / forming / rejected |
| Trade plan | `app/strategy_engine/plan.py` | Stop beyond the invalidation + 0.1 ATR + spread; TP1-TP3 from structure, else labelled risk objectives; tick rounding; hard validation; entry status; expiry |
| Selector | `app/strategy_engine/selector.py` | Regime compatibility, de-duplication, conflict resolution (never averaged), ranking, one action per timeframe |
| Service + API | `app/strategy_engine/service.py`, `/api/v1/engine`, `/engine/{symbol}`, `/engine/signals` | Same candles and provider as v1; H8 from complete 4H pairs; live spread; session; paper-trade management kept separate; EXIT alert; risk check |
| Risk | `app/strategy_engine/risk.py` | Sizing by risk %, maximum concurrent trades, maximum open risk, daily loss limit, drawdown halt, minimum R:R, volatility, session and correlated currency exposure; never sizes up after losses |
| Sessions / news | `app/strategy_engine/sessions.py` | London/New York in their own time zones (DST from tzdata), rollover and weekly-open blocks; news filter reported **unavailable** |
| Signal lifecycle | `signal_records` table (migration 0006), `app/strategy_engine/lifecycle.py` | Each plan stored once, stepped every minute on 1-minute candles, from DETECTED through to TP1/TP2/TP3 HIT, STOP LOSS HIT, INVALIDATED, EXPIRED or ENTRY MISSED |
| Minute cycle | `app/paper/service.py::run_engine_v2` | Runs after v1's paper step; an engine failure is logged and never stops the v1 forward test |
| Signals page | `/signals` (v1 checklist moved to `/signals/classic`) | One card per instrument, best first. The action is in large type, then entry, SL, TP1-3 with R and basis, R:R, spread cost, entry status, expiry, why, invalidation and next action; plus the research and plan labels, a separate paper-trade block, expandable timeframes and strategies, and the signal history |
| Overview, Scanner | `/`, `/scanner` | Same engine: the action and Entry · SL · TP1 per instrument; the live grid of every instrument × timeframe |
| Hypothetical plans | Settings store v1 | "Show hypothetical trade plans (unvalidated)" is **on by default**, as the owner required. When it is off, unvalidated prices are hidden and the action is still shown |

v1 (`app/signals`, the paper forward test and its frozen rules) is unchanged.

## 2. Worked examples (local run on stored live candles, 2026-11-13 10:51 UTC)

Calculated by the backend from BiQuote candles synced at the time. Prices are rounded to each instrument's tick. **All four are
UNVALIDATED — HYPOTHETICAL TRADE PLANS with research status INSUFFICIENT EVIDENCE.** They are worked examples of the arithmetic,
not recommendations.

**SELL: XAUUSD 1m, Breakout and retest, regime Trending down** (ADX 28, ER 0.40, EMA50 slope −1.11 ATR)
- Source candles (open time UTC): 10:48 O3892.50 H3893.13 L3890.09 C3890.09 · 10:49 O3890.32 H3891.14 L3889.36 C3889.63 ·
  10:50 O3889.68 H3891.58 L3889.68 C3890.99.
- Setup: a 20-candle box 3,891.79-3,900.29 (5.7 ATR), broken by a strong-bodied close at 3,890.09. The retest on the last candle
  (high 3,891.58, within 0.3 ATR of 3,891.79) closed back below the level, so the setup is ready.
- Entry: market, at the trigger close **3,890.99** (live price 3,891.25, within 0.3R, so the status is READY).
- Invalidation: level + 0.5 ATR = 3,891.79 + 0.5 × 1.6487 = 3,892.61.
- Stop: 3,892.61 + 0.1 ATR (0.165) + live spread 0.168 = 3,892.947, rounded away from the entry to **3,892.95**. Risk 1.96 =
  1.19 ATR (scalping band 0.5-3.0).
- Targets: no structural level between 1.5R and 4R below the entry, so the labelled risk objectives apply: **TP1 3,887.07 (2R),
  TP2 3,885.11 (3R), TP3 3,881.19 (5R)**. Spread cost 0.086R. Expires 2 candles after the signal (10:53).

**BUY: US30 5m, Breakout and retest, regime Trending up** (ADX 28, ER 0.43)
- Source candles: 10:35 O52426.9 H52436.9 L52421.9 C52433.9 · 10:40 O52432.9 H52435.9 L52419.9 C52427.9 · 10:45 O52426.9
  H52427.9 L52406.1 C52417.9.
- Setup: a box 52,222.05-52,401.95 (6.0 ATR), broken by a strong close at 52,439.95. The last candle retested (low 52,406.1, within
  0.3 ATR of 52,401.95) and closed above the level.
- Entry **52,417.9** (market).
- Invalidation: 52,401.95 − 0.5 × 25.256 = 52,389.32.
- Stop: 52,389.32 − (2.526 + spread 0.9) = 52,385.89, rounded to **52,385.8**. Risk 32.1 = 1.27 ATR.
- Targets: **TP1 52,476.9 (1.84R, swing high), TP2 52,507.0 (2.78R, order block), TP3 52,560.9 (4.45R, swing high)**. Spread cost
  0.028R.

**WAIT FOR BUY: US30 15m, Breakout and retest, regime Unknown (transitional)**
- Setup: a box 52,222.05-52,369.95 broken by a strong close at 52,401.95, no retest yet.
- Entry: **BUY limit 52,374.6** (level + 0.1 ATR), zone 52,369.95-52,374.6.
- Invalidation: 52,369.95 − 0.5 × 46.476 = 52,346.7. Stop **52,341.1** (risk 0.72 ATR).
- Targets: **TP1 52,435.9 (1.83R, order block), TP2 52,476.9 (3.05R, swing high), TP3 52,551.0 (5.27R, swing high)**.
- Status WAITING FOR ENTRY. It expires after 16 candles (14:00) or on a 15m close below 52,346.7.

**WAIT FOR SELL: EURUSD 3m, Breakout and retest, regime Trending down**
- Setup: a box 1.10495-1.10598 broken by a close at 1.10466.
- Entry: **SELL limit 1.10492**, retest of 1.10495. Stop **1.10517** (risk 0.98 ATR).
- Targets: **TP1 1.10442 (2R), TP2 1.10417 (3R), TP3 1.10367 (5R)**, all risk objectives.
- The spread costs 0.24R, close to the scalping limit of 0.25R: costs dominate on very short timeframes.

**Lifecycle seen live:** after one cycle 22 records existed: WAITING FOR ENTRY, ACTIVE (market entries), and one USOIL 5m plan
already ENTRY MISSED (TP1 traded before its limit filled).

**Bugs found by checking these examples by hand, fixed and covered by tests:**
- **Look-ahead (fixed):** the sweep strategy could use the last daily candle's high as the "previous day high" for a sweep that
  happened before that candle. The previous-day level is now used only on intraday timeframes, and only after that day has closed.
- **Wrong structure-shift level (fixed):** for a BUY, the "market-structure shift" could be measured against a swing high *below* the
  swept low, which is trivially passed. The shift now uses the swing that began the leg into the sweep. This removed a spurious US30
  BUY.
- **Session-gap "zones" (fixed):** an FVG 34 ATR wide (a gap over a market close) counted as a pullback zone. Zones wider than 2 ATR
  are no longer used.
- **Cosmetic (fixed):** target and zone labels were not rounded ("5.55566R", "1.1049245…").

## 3. Verification

| Check | Result |
|---|---|
| Backend: v2 engine and API (`test_strategy_engine.py`, `test_engine_api.py`) | **28 passed**: indicators; regimes; tick-grid plans across 4 tick sizes, BUY and SELL; rejections that never repair a plan; entry status; risk-objective labels; each strategy's trigger and its refusals (false breakout, no chase, a sweep alone is not a trade, exhaustion, range-only, compression + expansion without volume); selector (abnormal volatility, insufficient data, closed market); sessions across DST; sizing, exposure and limits; H8; the API contract; the EXIT separation; the lifecycle (detection through targets, invalidation, missed entry, expiry, no duplicates) |
| Backend: affected suites (paper, signals, decision, API, handover, foundation) | **111 passed** (with v2 running inside the paper cycle) |
| Migration 0006 | applies cleanly on a fresh SQLite database and on the local dev database |
| Frontend unit tests | **78 passed** (5 new Signals-page tests, plus updated Overview and Scanner tests) |
| Type check, lint (backend ruff, frontend eslint) | clean |
| Production build + end-to-end (Playwright, desktop + phone) | **8 / 8 passed** |
| Local browser run on real data | Signals, Overview and Scanner render with no page errors and no sideways scrolling at 1440 px and 390 px |

Screenshots (local run): `docs/screenshots/engine-v2-signals-desktop.png`, `engine-v2-signals-mobile.png`,
`engine-v2-card-detail.png`, `engine-v2-history.png`, `engine-v2-overview.png`, `engine-v2-scanner.png`.

## 4. Unresolved limitations and blockers

1. **No strategy is validated.** All six are untested hypotheses. `EXPERIMENT_PLAN.md` must be approved before any performance test.
   Until then every plan is UNVALIDATED and research status is INSUFFICIENT EVIDENCE. Nothing here is a claim of accuracy or
   profitability.
2. **Data depth.**
   - Live intraday history is days to weeks (1H about 2 weeks, 4H about 6 weeks). Enough to analyse, far too little to test.
   - **H8** (about 100 candles from BiQuote's 4H), **W1** (about 80) and **MN1** (none on BiQuote) usually fall below the
     120-candle minimum and honestly report NO TRADE (insufficient data).
   - Deep FX history needs the Dukascopy download listed in the experiment plan.
3. **News filter unavailable.** There is no free, reliable economic calendar. The product says so and does not claim filtering.
4. **No volume** for spot FX and gold. No strategy uses volume.
5. **Lower-timeframe trigger confirmation** is reported in the chain but not required by any rule in this version. The strategies
   confirm on their own signal timeframe.
6. **Short timeframes are cost-heavy.** M1-M5 plans often spend 0.1-0.25R on the spread. They are ranked after intraday and swing
   ones on ties.
7. **The lifecycle tracker runs inside the paper cycle**, so it needs `PAPER_TRADING_INTERVAL_SECONDS > 0`, which is the case in
   production. It adds about 2 seconds of CPU per instrument per minute.
8. **Paper trading still evaluates the v1 rules.** A v2 forward test needs its own frozen evaluation period after the research (see
   Phase 12 in the brief). Starting it now would test unvalidated rules, so it was not started.
9. **ML** was not added (Phase 10): first the rule-based strategies must show defensible value.
10. **Deploying** needs the owner's approval. It also needs migration 0006, which runs automatically on start (`alembic upgrade head`).

## 5. Confirmation layer and Experiment 6 (2026-11-14, branch `feature/confirmation-engine`)

**What was built**
- **Confirmation layer** ([design](CONFIRMATION_DESIGN.md)):
  - volume type and reliability, with relative volume normalised by session;
  - the missing indicators: EMA 200, MACD, Stochastic RSI, ROC, Keltner Channels, historical volatility, session VWAP, OBV, MFI;
  - objective VSA events with causal confirmation;
  - the ten-component matrix on every chosen setup.
- **Signal cards** show the confirmation chips and an evidence panel.
- **Gates** (`config.GATES`) stay empty unless research promotes a category.
- **BTCUSDT history** from the Binance public archive: 111 monthly files, all checksums verified, 4,833,919 one-minute candles at
  99.38% coverage. The split is frozen with the final 15% sealed.

**Experiment 6** ([plan](EXPERIMENT_6_PLAN.md), [report](../reports/EXPERIMENT6_CONFIRMATIONS.md))
- **Re-scoring:** every signal reproduced its stored entry and stop: 193,287 gold signals and 229,937 BTCUSDT signals.
- **Pre-registration:** 50 arms, 36 in the test family, committed before any outcome.
- **BTCUSDT baseline** (Experiment 5 rules): 47 cells and 70,651 trades at −0.066R per trade; no candidate.
- **Development:** 4 of 36 arms passed, all four the trend filter on breakout-and-retest and sweep-reversal. They added +0.020 to
  +0.035R per trade.
- **Confirmation (run once):** none held. The improvements fell to −0.001 to +0.017R, with Holm p between 0.49 and 0.91.
- **VSA, momentum, volatility and the combinations** lowered results on average in development.
- **Result:** no category is a gate. Tested categories show "did not pass Experiment 6".
- **Trials counted from here on:** 2,115. The sealed periods of both instruments were never read.

**Verification (2026-11-14):**

| Check | Result |
|---|---|
| Backend tests | 563 passed, 30 skipped (they need optional local data), 0 failed |
| Frontend unit tests | 85 passed |
| End-to-end (production build) | 8 of 8 passed |
| Typecheck, lint, production build | clean |
| Decisions with gates empty | identical to before: tested by forcing every evidence verdict to FAIL |
