# Implementation status — single source of truth

_Last verified: 2026-11-01 (local, Windows 10, Python 3.12, Node 24). Update this file whenever a status changes._

## Verification results
| Check | Result |
|---|---|
| Backend `pytest` | **135 passed** — adds backtester audit (accounting identity, sizing, costs, no overlap/duplicates, no look-ahead on the real strategy), resumable/idempotent backfill, data-quality auditor, dataset snapshots, experiment reproduction, baselines/verdict logic, Binance retry/backoff, Twelve Data error/quota/paging behaviour |
| Backend `ruff check` | clean |
| Frontend `vitest` / `tsc` / `eslint` / `next build` / Playwright | 28 passed / clean / clean / 12 pages / 6 passed (e2e not re-run this milestone) |
| Alembic | `0001`, `0002` upgrade/downgrade verified on SQLite; `0001` verified on PostgreSQL 16 (`0002` is plain additive DDL, not yet run on PostgreSQL) |
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
| LLM explanations, paper trading, S3 | ⬜ | |

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
