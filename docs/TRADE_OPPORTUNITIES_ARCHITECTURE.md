# Trade Opportunities — architecture

_Analysis only. Nothing in this module places orders, connects to a broker or promises a result._

## What it is
The **Trade Opportunities** tab (sidebar, directly below Overview) is the platform's main decision view. One scan analyses every
supported instrument on all 14 timeframes, builds candidate setups for four trading styles (scalping, intraday, swing, long-term),
attaches historical-analogue evidence and a transparent evidence score, ranks the results and explains each one. **WAIT is a valid
and frequent result.**

## Where it sits in the existing system
It is an extension of the modular monolith; no new service, no new infrastructure.

```
frontend/  /opportunities page ──REST──▶ backend/app/api/v1/routes/opportunities.py
                                              │
                    app/opportunities/        ▼
   scanner.py   orchestrator: scan → instrument → timeframe → style → persistence → lifecycle
   analysis.py  per-timeframe load / derive / freshness / signature / descriptive result / HTF bias
   setup.py     deterministic setup rules (entry zone, stop, targets, status)   ◀── also replayed by the validation backtest
   analogue.py  direction-aware historical analogues (wraps historical_engine)
   scoring.py   evidence score (components, penalties, validation cap)
   validation.py status lookup + classify()  ◀── app/data/opportunity_validation.json (exported from experiments)
   evidence.py  thesis / risks / structure / candle / chart-overlay builders
   service.py   read side: serialisation, ranking, correlation flags, page summary
   scheduler.py optional in-process automatic scans
   config.py    profiles, weights, caps, penalties, costs (one place; versioned)
   rules_strategy.py  setup rules as a backtest Strategy
 reused unchanged: market_data (providers, registry, aggregation, calendars, coverage), price_action, market_structure, candlestick,
 feature_engineering, historical_engine, multi_timeframe, backtesting engine, research/strategy_eval, experiments registry, auth, jobs
 added to price_action: levels.py (support/resistance, trendlines/channels, breakouts/retests/failed breakouts)
```

## Data flow of one scan
1. `POST /opportunities/scan` creates a `market_scans` row (or returns the one already queued/running — **deduplication**) and
   dispatches a job (`inline` thread pool, or Celery when `JOB_BACKEND=celery`).
2. Per instrument (`OPPORTUNITY_SYMBOLS`, default `XAUUSD,US30,BTCUSDT,USOIL`): resolve the provider mapping; if the provider is not
   configured and no candles are stored, the instrument is reported **unavailable** with the reason. No substitute, no synthetic data.
3. Per timeframe (14): load complete candles (forming candle excluded), derive from a lower stored timeframe **only** when the
   native series is too short, compute freshness and gaps, hash the content into a **signature**. Same signature as an earlier
   analysis ⇒ the new `timeframe_analyses` row just points at it (`reused_from_id`); nothing is recomputed.
4. Per style: if the signatures of every timeframe the style uses are unchanged since the last scan (and the validation file is
   unchanged), the previous opportunities are carried over (`last_scan_id` bumped). Otherwise candidates are generated on each of the
   style's setup timeframes, analogues and the evidence score are computed, the best is chosen, and rows are persisted.
5. Open opportunities are reconciled against the latest candles (invalidated / target reached / expired) and every transition is
   written to `opportunity_status_history`.
6. The scan stores its summary, per-instrument status, config version and code hash.

## Database (migration `0003`)
| Table | Purpose |
|---|---|
| `market_scans` | One scan: trigger, params, per-instrument status, summary, config version, code hash |
| `timeframe_analyses` | One row per instrument × timeframe × scan: status, signature, candle range, derived-from, result JSON or `reused_from_id` |
| `trade_opportunities` | Headline (or WAIT) per instrument × style, plus up to 3 further candidates: levels, status, evidence score, validation status, full evidence JSON, dedupe key |
| `opportunity_status_history` | Every status transition with reason |
Strategy validation reuses the existing `experiments` table (reproducible backtests); `historical_analogues` evidence is stored inside the
opportunity's evidence JSON (point-in-time per scan) rather than in the per-analysis table. Migration `0003` also flips the verified
Twelve Data XAUUSD mapping from `unverified` to `active` (documented in `docs/reports/XAUUSD_COVERAGE.md`) and is reversible.

## API (`/api/v1/opportunities`, all authenticated like the rest of the API)
| Method & path | Purpose |
|---|---|
| `POST /scan` | Start a scan (`symbols?`, `refresh_data?`). 202; `deduplicated: true` if one is already running |
| `GET /summary` | Everything the page needs: scan status/freshness, best per style, consolidated ranking, instrument/timeframe status, next-scan info |
| `GET /` | Opportunities (latest scan or `scope=all`); filters `symbol`, `style`, `direction`, `status`, `actionable_only`, `headline_only`; `limit` ≤ 200 / `offset` |
| `GET /{id}` | Full evidence: thesis, multi-timeframe table, structure, candles, analogues, score breakdown, reasoning, risks, invalidation, chart overlays, status history |
| `GET /scans`, `GET /scans/{id}` | Scan history and one scan (per-instrument status, versions) |
| `GET /timeframes?symbol=` | Independent per-timeframe analysis of the latest (or a given) scan |
| `GET /validation` | Strategy-validation results + the user's existing backtest runs, unmodified |
| `GET /config` | The weights, thresholds and profiles in force |
Validation: Pydantic request models, `Literal` query types, bounded pagination, `422` with field details, uniform error envelope, `404` for
unknown ids, `401` without a valid API key when `AUTH_REQUIRED=true`.

## Configuration (`.env`)
| Variable | Default | Meaning |
|---|---|---|
| `OPPORTUNITY_SYMBOLS` | `XAUUSD,US30,BTCUSDT,USOIL` | Instruments scanned |
| `OPPORTUNITY_SCAN_INTERVAL_MINUTES` | `15` | `> 0` enables automatic scanning inside the API process (first run 30 s after start; 2 retries with backoff when a scan fails) |
| `OPPORTUNITY_REFRESH_PROVIDERS` | `biquote,binance` | Providers a **scheduled** scan may sync. Quota-limited providers (Twelve Data free: 8/min, 800/day) are only synced when a user asks for "Refresh data & scan" |
| `OPPORTUNITY_MAX_SYNC_TFS` | `4` | Timeframes refreshed per instrument by a refresh scan |
Everything analytical (style profiles, weights, caps, penalties, costs) is in `app/opportunities/config.py` and versioned by `CONFIG_VERSION`.

## Reproducibility
Each scan stores `config_version` and the code-source hash (`experiments.code_version`, now including `opportunities/`). Timeframe analyses store the
signature of the exact candles. Validation experiments store a content hash of the candles they used and can be re-executed with
`python -m app.research.reproduce <id>`.

## Guarantees and deliberate limits
* Never fabricates candles, substitutes instruments or mixes providers inside one analysis (the provider is stored with every opportunity).
* Never treats a forming candle as complete; derived timeframes use complete buckets only and are labelled `built from 1H`.
* Provider quotas are never spent implicitly: a normal scan reads the database only.
* US30 and USOIL are served by BiQuote (keyless, default provider since 2026-11-01) and appear as **unavailable** until their candles are synced; with `PREFERRED_PROVIDER=` empty they fall back to OANDA, which needs `OANDA_API_TOKEN`.
* The scan is as fresh as the stored candles. Without a sync or a scheduled refresh, "latest" means "latest stored".
* Cross-instrument correlation is **not measured**; only same-instrument, same-direction setups are flagged as one exposure.
