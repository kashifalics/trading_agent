# Implementation status — single source of truth

_Last verified: 2026-11-07 (local, Windows 10, Python 3.12, Node 24). Update this file whenever a status changes._

## Verification results
| Check | Result |
|---|---|
| Backend `pytest` | **249 passed, 30 skipped** (skipped = live-provider tests) on 2026-11-07, including 26 signal-engine and 18 paper-trading/sync tests; earlier milestones added the backtester audit, resumable backfill, data-quality auditor, snapshots, reproduction, provider retry/quota behaviour |
| Backend `ruff check` | clean |
| Frontend `vitest` / `tsc` / `eslint` / `next build` / Playwright | 54 passed / clean / clean / 18 routes incl. `/signals`, `/paper` / e2e not re-run this milestone |
| Alembic | `0001`, `0002`, `0004` upgrade/downgrade verified on SQLite (`0004`: columns match the models, downgrade and re-upgrade clean); `0001` verified on PostgreSQL 16 (later revisions are plain additive DDL, not yet run on PostgreSQL) |
| Live Binance | **Verified**: 3.2 years of BTCUSDT 1H (28,799) and 4H (7,199) candles, 0 missing, 0 invalid, re-run is a no-op |
| Live Twelve Data (XAUUSD) | **Verified with a real key** — see `reports/XAUUSD_COVERAGE.md` and the Twelve Data section below |
| Docker Compose | Verified in the previous milestone (postgres, redis, backend, worker, frontend); not re-run this milestone |

## Feature status
Legend: ✅ working & tested · 🟡 working with stated limits · ⛔ blocked/unsupported · ⬜ not started

| Area | Status | Notes |
|---|---|---|
| Separate `frontend/` and `backend/` apps; REST-only coupling | ✅ | Contracts unchanged; `POST /market/sync` result gained an additive `misaligned` field |
| Provider abstraction + symbol mapping | ✅ | |
| Binance adapter (BTCUSDT) | ✅ | Pagination, Retry-After/backoff on 429/5xx, no retry on 418 ban, pauses near the 1,200-weight/min limit |
| **Historical backfill** | ✅ | `market_data/ingestion/backfill.py`: computes expected open-times, fetches only what is missing in span-based windows, validates (OHLC, grid alignment, forming candle excluded), checkpoints each window, records `ingestion_runs`. Resumable and idempotent (tested, and shown on real data) |
| **Data-quality report** | ✅ | `app/research/data_quality.py` → `reports/BTCUSDT_DATA_QUALITY.md`; recomputed from stored rows, independent count check |
| Twelve Data adapter (XAUUSD) | 🟡 | **Works** on the free (`basic`) plan for 1H/4H/1D, but native 4H cannot be used as-is and the feed has weekend candles (below) |
| GBPUSD | ✅ | Twelve Data free plan, 1H/1D native, 2H/4H built from 1H |
| US30, USOIL | 🟡 | **OANDA adapter** (`oanda`, read-only candles/quotes, UTC-aligned buckets), unit-tested with mocked HTTP; **not verified live: needs `OANDA_API_TOKEN`** (free practice account). Twelve Data free plan does not serve the Dow index |
| Timeframe registry, aggregation, DST, gaps, coverage | ✅ | |
| Price-action/candlestick/structure detectors; analogues; features; labels | ✅ | |
| **Backtester** | ✅ | Audited. Fixed: reported `costs` over-counted spread on target exits; added percentage-of-price spread/slippage (`spread_pct`, `slippage_pct`) for long price histories. Documented, not changed: entries are market orders at the next open (the plan's entry zone is not used in backtests) |
| **Pattern study + `/patterns/scan` + all-timeframe UI** | ✅ | See section above; results are negative |
| **Quantitative evaluation (1H, 4H)** | ✅ | `reports/BTCUSDT_BACKTEST_1H.md`, `_4H.md`: four cost scenarios, long/short, regimes, six walk-forward folds, significance tests, baselines |
| **ML evaluation** | ✅ pipeline / ⛔ no promoted model | `reports/BTCUSDT_ML_EVALUATION.md`: logistic, LightGBM, XGBoost, baselines; gate now also requires beating the best simple baseline. **All 12 runs `research_only`** |
| **Experiment registry & reproduction** | ✅ | `experiments` table: dataset snapshot id, config, code hash, library versions, results. `python -m app.research.reproduce <id>` re-runs and diffs; 22 independent duplicate runs agreed on 994/994 numeric fields; 4 re-executions matched exactly |
| Decision policy, MTF, outcome tracking, screenshot analysis, REST API, 12-page UI, Celery jobs | ✅ / 🟡 | As in the previous milestone (OCR verified on synthetic charts only) |
| Auth | 🟡 | API-key auth + isolation; no registration UI |
| **Paper trading (forward test)** | 🟡 | Working and verified live; the record starts empty and needs ~100 closed trades before it says anything (section below) |
| LLM explanations, S3 | ⬜ | |

## Signal engine + Signals page (2026-11-07)
New sidebar tab **Signals** (directly below Overview) — sub-project 1 of the trading-bot brief; design and methodology in `docs/SIGNAL_ENGINE.md`.
* **What it does:** every timeframe is analysed top-down (two higher timeframes set the bias, the setup timeframe supplies the structural entry, a lower
  timeframe confirms). Each timeframe gets an entry state (`ENTRY_READY`, `WAITING_FOR_CONFIRMATION`, `SETUP_DEVELOPING`, `WATCHLIST`, `NO_SETUP`,
  `TRADE_INVALIDATED`, `TRADE_EXPIRED`), a final instruction (EXECUTE NOW / WAIT FOR CONFIRMATION / PLACE LIMIT ORDER / NO TRADE), a structural entry
  (market at a zone, limit at a zone ahead, or sweep + structure break), a structural stop, up to three structural targets (min 1:2; none invented), a
  100-point confluence checklist (HTF 20 · structure 20 · liquidity 15 · entry zone 15 · LTF confirmation 15 · R:R 10 · session/volatility 5; signal
  at ≥ 60, limit orders only at ≥ 70), reasons for/against and a deterministic analyst report. Spreads: BTC $2, gold $0.30 (`SIGNAL_SPREADS`).
* **Backend:** `app/signals/*` (pure engine shared by live and replay), `/api/v1/signals`, `/signals/{symbol}`, `/signals/{symbol}/sync`,
  `/signals/config`, `/signals/track-record`; BTCUSDT is routed to Binance (deep history) and the others to BiQuote (`SIGNAL_PROVIDER_OVERRIDES`).
  `opportunities.analysis.prepare_tf` gained a backward-compatible `lookback` argument; nothing else in existing modules changed.
* **Frontend:** `/signals` page (instrument tabs, overview, best setup, 14-timeframe table, checklist, levels, reasons, chart, lot-size calculator,
  live refresh every 60 s). Trade Opportunities stays available one row lower.
* **Verified live (2026-11-07):** sync from Binance (BTCUSDT, 11 timeframes) and BiQuote (XAUUSD, US30) and full analysis through the API and the page.
  At that moment every instrument was NO TRADE (BTC setups blocked by wide stops / nearby opposing order blocks; gold and US30 markets closed).
* **Track record:** `python -m app.research.run_signal_track_record run|export|report` replays the exact engine on the research database →
  `app/data/signal_track_record.json` (shown next to every plan), `docs/reports/SIGNAL_TRACK_RECORD.md`. First run (BTCUSDT Binance, XAUUSD Twelve
  Data; 5m/15m/1H/4H/1D): **1,027 trades, −0.048 R per trade pooled after spread — no demonstrated edge**. Every series is `no_edge` (fewer than 100
  out-of-sample trades). Out-of-sample CIs entirely below zero: BTCUSDT 1H, BTCUSDT 5m, XAUUSD 15m. Entirely above zero but tiny: XAUUSD 1D (10 trades).
  XAUUSD 4H +0.15 R (78 OOS trades, CI −0.22…+0.54). Higher scores do not reliably mean better outcomes, so the score stays a quality checklist and no
  win probability is shown. Signal frequency on history: roughly one trade per 40–100 candles per intraday timeframe.
* **Tests:** `tests/test_signals_engine.py` (21: plan, stop/targets, must-pass rules, score, states, live downgrades, no look-ahead across
  timeframes, lifecycle), `tests/test_signals_api.py` (5: API end to end, sync routing, replay accounting); frontend `signals.test.tsx` (6).
* **Not built yet (later sub-projects):** alerts, AI chat analyst, broker execution. Paper trading and signal history: see the next section.
  News filter: unavailable (reported on every plan).

## Paper trading (2026-11-07)
New sidebar tab **Paper Trading** (below Signals), sub-project 3 of the trading-bot brief. Design: `docs/PAPER_TRADING.md`.
* **What it does:** while the backend runs, a cycle every 60 s (`PAPER_TRADING_INTERVAL_SECONDS`) syncs due candles, records every EXECUTE NOW
  (market) and PLACE LIMIT ORDER (limit) signal the moment it appears, with the plan exactly as shown, and simulates it on later candles. Stop or
  TP1, 1-minute exits, gaps honoured, the configured spread charged, one trade per instrument × timeframe, nothing backfilled. A paper account
  applies risk rules on top: risk % per trade, max open trades, daily loss limit. Skipped signals are still tracked for the forward test.
* **Backend:** `app/paper/` (pure simulator, service, stats, in-process worker), `app/signals/execution.py` (fill/exit rules now shared with the
  replay), tables `paper_accounts` and `paper_trades` (migration `0004`, unique per instrument/timeframe/setup), endpoints `/api/v1/paper/summary`,
  `/trades`, `/trades/{id}`, `/account` (GET/PATCH), `/account/reset`, `/run`. The verdict uses the backtest's rule; below 100 closed trades it
  draws no conclusion.
* **Replay refactor proven safe:** `run_signal_track_record` now calls the shared execution functions. Re-running three series (XAUUSD 4H, BTCUSDT
  1H, XAUUSD 15m; 600 steps each) gave byte-identical trades before and after (33 trades), so the published track record still matches the code.
* **Fixed in the signal sync (affects the Signals page too):** (1) `ensure_data` tolerates one missing candle on long series, so BTCUSDT (Binance,
  more than 540 stored candles) was analysed one candle late on most timeframes (seen live: the 12:00–16:00 4H candle was still missing at 18:25 UTC).
  `signals.sync` now ingests a due timeframe directly. (2) A candle the provider never delivers (thin feeds at the Friday close, provider gaps) used
  to be re-downloaded every cycle, and short series every cycle too. Now a timeframe is fetched only when a candle closed since the last attempt,
  missing candles are retried every 30 min and short series every 6 h (`signals.service.is_due`).
* **Verified live (2026-11-07, Saturday):** migration `0004` applied to `dev.db` at startup; the worker synced and analysed all four instruments
  every cycle with no errors; the page rendered with no console errors. Cycle time fell from ~100 s to 11–12 s with the sync fix below. No signal fired during the check (gold, US30 and oil closed; BTC setups
  blocked), so the live record is empty. The page shows the backtest's out-of-sample part beside it: −0.19 R per trade over 414 trades.
* **Tests:** `tests/test_paper_simulator.py` (11: execution rules, candle path, market/limit fills, chase/gap skips, gap exits, expiry,
  invalidation, idempotency), `tests/test_paper_api.py` (6: record once → fill at next open → TP1 with exact R and P&L, account rules, daily loss
  limit, account endpoints and validation, run endpoint and lock, worker timing), `tests/test_signals_api.py` (+1: when a timeframe is due);
  frontend `paper.test.tsx` (6).

## Data provider routing (2026-11-01)
**BiQuote** (free keyless API, MT5 broker-CFD quotes; `docs/BIQUOTE_PROVIDER_EVALUATION.md`) is the default provider for BTCUSDT, XAUUSD, US30 and USOIL (`PREFERRED_PROVIDER=biquote`); Binance, Twelve Data and OANDA stay registered and selectable with `provider=`. Trade-off: BiQuote keeps only a fixed recent window (1H ~7 days, 4H ~30 days, 1D ~500 bars, no 1W/1M), so most analysis beyond 1D/4H reports insufficient data. Live streaming during market hours for XAUUSD/US30/USOIL is not yet verified.

## Trade Opportunities module (2026-11-02)
New sidebar tab **Trade Opportunities** (below Overview): one scan analyses XAUUSD, US30, BTCUSDT and USOIL on all 14 timeframes, builds candidate setups for scalping / intraday / swing / long-term, adds historical-analogue evidence and a transparent evidence score, ranks the results and explains each. US30 and USOIL are reported **unavailable** (no OANDA token); nothing is substituted.
* Docs: `TRADE_OPPORTUNITIES_ARCHITECTURE.md`, `MULTI_TIMEFRAME_ANALYSIS.md`, `TRADE_SCORING_METHODOLOGY.md`, `STRATEGY_VALIDATION.md`, `TRADE_OPPORTUNITIES_TEST_REPORT.md`; report `reports/OPPORTUNITY_VALIDATION.md`.
* Backend: `app/opportunities/*`, `price_action/levels.py` (S/R, trendlines, channels, breakouts/retests), migration `0003` (4 tables; also marks the live-verified Twelve Data XAUUSD mapping `active`), `/api/v1/opportunities/*`, optional scheduler (`OPPORTUNITY_SCAN_INTERVAL_MINUTES`).
* Frontend: `/opportunities` page; the whole UI was re-themed (light dashboard: white cards on a pale-blue canvas, navy type, green positives, amber call-to-action, Poppins) from a reference design the user supplied. Data and logic are unchanged.
* **No setup rule set is validated.** See `STRATEGY_VALIDATION.md`; scores are capped by validation status and are labelled "Evidence Score — Not Win Probability".
* Why the old engine looked "mostly WAIT": on stored data it was *not* mostly WAIT bar by bar (BTCUSDT 1H last 600 bars: 31% BUY/SELL; XAUUSD 22%), but (1) production has no candles, (2) the live pipeline adds multi-timeframe, analogue and data-quality gates, and (3) its signals have no demonstrated edge (BTC 1H net E[R] −0.26). The new module is deliberately stricter and says why it waits.

## Gold and Bitcoin, all timeframes: pattern study (2026-11-01)
Focus is now **BTCUSDT and XAUUSD** (`FOCUS_SYMBOLS`; GBPUSD, US30, USOIL stay registered and reachable with `?all=true`).

* **What was measured** (`docs/reports/PATTERN_EDGE_BTCUSDT.md`, `..._XAUUSD.md`, full catalogue in `docs/reports/data/*.csv`): ~600 hypotheses per instrument = every candlestick pattern, BOS/CHoCH, liquidity sweeps, equal highs/lows, FVG / order block / breaker / supply-demand zones (at formation and on first retest), inside-bar breakouts, EMA20/50 and SMA200 crosses, RSI exits, Donchian-20 breakouts and hour-of-day, on 10 timeframes (1m to 1W; 1M and above lack history). Each is traded with a 2:1 ATR bracket, net of costs, and compared with taking the same direction on every bar (so market drift is not mistaken for skill).
* **Protocol:** discovery on the first 60% of history, FDR control; confirmation on the last 40% with Holm correction; and a **one-bar execution-delay check** (added after the first gold run produced eight 1-minute "confirmations" that were fill-price artifacts and vanished with a one-bar delay). The engine is unit-tested to find a planted effect, ignore pure noise and drift, and reject first-fill-only effects.
* **Result:** BTCUSDT 637 tested, **0** discovery candidates. XAUUSD 596 tested, 30 candidates, 8 passed out-of-sample but **all 8 failed the delay check: 0 confirmed**. No pattern on any timeframe shows a robust edge, gross or net.
* **Power caveat:** with typical event counts the study only detects advantages of roughly 0.25R/trade (30m-1H) to 0.6-0.8R (1m, 4H, 1D). "None found" = no large, robust edge; small ones cannot be excluded.
* **In the product:** `GET /patterns/scan` and the Historical Patterns page show, for every timeframe with stored candles, the structure/zone state and every pattern firing now with its measured track record (`confirmed` / `no edge` / `failed OOS` / `no track record`). Every BUY/SELL carries the study caveat while nothing is validated. Scanner covers all 14 timeframes; "Sync all timeframes" loads history per instrument.
* Twelve Data adapter: transient network failures now retry with backoff. History depth per timeframe is capped by how much was requested (about 30,000 bars each, 1D ~14 years), not by a measured provider limit; gold 1m/3m therefore cover only about a month, which is far too little for firm conclusions.

## Research results (details in `docs/reports/`)
* **Rule-based engine** (defaults, untuned): 1H — 914 trades, net expectancy −0.261 R, 95% CI [−0.338, −0.183], PF 0.60, return −91% at `base` costs (0.10% fee/side): **statistically negative**. Gross (zero-cost) expectancy −0.048 R, CI [−0.125, +0.026]: **no gross edge either**. 4H — 235 trades, −0.054 R, CI [−0.203, +0.088], PF 0.90: **no evidence of edge**; gross +0.041 R, p = 0.29. On 1H its expectancy is indistinguishable from random entries with the same execution and costs (-0.261 vs -0.275 R); its return is worse (-91% vs -71%) because its stops are tighter, so fixed percentage costs weigh more per R.
* **Models** (walk-forward, purged, calibrated): Brier skill is **negative for every model on both timeframes** (−0.003 … −0.018), 42–68 OOS trades each, none profitable after costs. Nothing promoted; predictions keep exposing no probability.
* Interpretation: at these fee levels hourly price-action rules lose mostly to costs, and there is no demonstrable gross signal to recover. This is a null result on one asset over 3.2 years, not a proof that no edge exists.

## Twelve Data / XAUUSD (live-verified 2026-11-01)
* Key is read from the environment (root `.env` or `backend/.env`; the latter wins). Settings, logs and reports never contain it (`repr(settings)` previously would have; now masked, tested).
* Plan: `basic` — **8 requests/minute, 800/day** (provider-reported). Symbol `XAU/USD` = "Gold Spot / US Dollar" (COMMODITY, Precious Metal). No plan restriction hit on 1H/4H/1D. Per-minute 429 is handled by one 62 s wait and retry (observed live); daily-limit errors fail fast.
* History available: **1D from 1979-12-26**; **4H from 2020-01-24**; **1H at least back to 2020-07-31** (probe stopped there by its page budget). Retrieved: 1H 22,595 · 4H 2,768 (see below) · 1D 2,602. Prices 1,128–5,562, no volume, no invalid OHLC, no duplicates, UTC, 1H and 1D on-grid.
* **Issues found** (details and numbers in the report):
  1. **Native 4H grid shifts with the season**: epoch-aligned (00/04/08… UTC) ≈ October–March, one hour later (01/05/09…) ≈ April–September, every year. Ingestion rejects the off-grid half (3,090 of 5,858) rather than store inconsistent candles. **Smallest fix:** aggregate XAUUSD 4H from 1H (remove 4H from the Twelve Data native set); our 1H→4H aggregation matched the provider's own 4H on 2,502/2,502 comparable buckets (close 2,501).
  2. **Weekend candles**: 12.2% of 1H rows fall in the assumed FX weekend closure (mostly Sat/Sun; median range 0.27 vs 7.5 when open): thin indicative quotes. Treat as non-tradable (filter by calendar when loading) before analysing XAUUSD.
  3. **Real gaps**: 2025-04-15/16 are fully missing (not a holiday); known holidays (Dec 25, Jan 1, Good Friday) and a daily break at 21:00/22:00 UTC are absent, as expected.
  4. The latest daily bar is stamped in the future relative to wall clock (next session label); it is correctly stored as incomplete.
* Registry status of the XAUUSD mapping is still `unverified` in the seed data; flip to `active` after deciding on items 1–2.

## Blockers / credentials still needed
1. US30 and USOIL: a free OANDA practice-account token (`OANDA_API_TOKEN`) to verify the adapter live.
2. Decision on XAUUSD 4H (aggregate) and weekend-candle filtering before XAUUSD analyses are trusted.
3. Tesseract on the host for OCR outside Docker; OCR untested on real broker screenshots.
4. No model has predictive information on BTCUSDT 1H/4H with the current features; further research should change the information set (e.g. longer horizons, other features/instruments) and be validated on data not used here.

## Known limitations
* `data_quality.py` assumes a continuous market (right for BTCUSDT; XAUUSD verification uses its own calendar-aware audit in `scripts/xau_verify.py`).
* Backtests enter at the next open at market; the entry-zone logic of live predictions is evaluated separately by outcome tracking.
* Research database `backend/research.db` (git-ignored) holds the experiments and 3.2 years of candles; recreate with `python -m app.research.run_milestone backfill|backtest|ml|report`.
