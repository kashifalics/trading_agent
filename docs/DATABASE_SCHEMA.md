# Database schema

PostgreSQL in Docker; SQLite for unit tests and zero-setup local runs. Managed by Alembic (`backend/alembic`, revision `0001`). `init_db()` runs `alembic upgrade head` at startup (`AUTO_MIGRATE=true`) and seeds providers/instruments/mappings idempotently.

## Conventions

* **Time**: every timestamp is timezone-aware UTC (`UTCDateTime` type rejects naive datetimes; SQLite's tz loss is repaired on read). Candle `ts` = candle **open** time.
* **Prices**: `NUMERIC(28,10)` (exact on PostgreSQL). On SQLite they degrade to floats — tests only.
* **JSON**: `JSONB` on PostgreSQL, `JSON` on SQLite.
* **Idempotent ingestion**: `INSERT … ON CONFLICT (provider_id, instrument_id, timeframe, ts) DO UPDATE` — re-running a sync converges (also upgrades an in-progress candle to its final values).

## Tables (21)

| Group | Table | Purpose / notable columns |
|---|---|---|
| Identity | `users` | `email`, `api_key_hash` (HMAC-SHA256 with `APP_SECRET_KEY`), `is_active` |
| | `audit_events` | `user_id`, `action`, `entity_type/id`, `ip`, `meta` |
| Reference | `instruments` | canonical symbol, name, `asset_class`, `quote_currency`, `price_precision`, `tick_size`, `calendar` (`continuous`\|`fx_weekly`), `session_tz`, `session_open`, `trading_session`, `contract_size`, `meta` |
| | `data_providers` | `code`, `base_url`, `requires_api_key`, `is_enabled`, `meta` |
| | `provider_instruments` | `(provider, instrument)` unique; `provider_symbol`, `exchange`, `market_kind` (spot/cfd/index/futures), `status` (`active`\|`unverified`\|`unsupported`), `notes` |
| Market data | `candles` | `(provider_id, instrument_id, timeframe, ts)` **unique**; OHLC, `volume`, `volume_type` (base/quote/tick/none), `is_complete`, `origin` (native/aggregated), `source_meta`; index `ix_candle_lookup` |
| | `data_coverage` | per (instrument, provider, timeframe): first/last ts, count, `gap_count`, `gaps` JSON, `last_sync_at/status/error` |
| Analysis | `analyses` | job row: `status` queued→running→completed/failed, `params`, `result` JSON (decision, overlay events, swings, analogues, mtf), `as_of_ts` |
| | `price_action_events` | persisted detections of an analysis (kind, direction, ts, levels, status, evidence) |
| | `historical_analogues` | top neighbours: similarity (**not a probability**), forward return, MFE/MAE (ATR), TP-before-SL flags |
| | `predictions` | decision, entry zone, stop, targets, R:R, invalidation, `probabilities` (only if calibrated+validated), `historical_frequency`, confluence, data-quality, warnings, `outcome` tracking |
| | `prediction_evidence` | per-evidence row: category, name, direction, weight, signed score, detail |
| Vision | `screenshots` | hash, size, dims, storage path (re-encoded PNG) |
| | `chart_extractions` | OCR availability, detected symbol/timeframe, calibration, extracted candles, quality score, market match, warnings |
| ML | `model_versions` | algorithm, instrument/timeframe, data range, feature names, label config, OOS `metrics`, `validation_status` (`research_only`\|`passed_minimum_checks`) + reasons, `is_calibrated`, `artifact_path`, `is_active` |
| Backtests | `backtest_runs` | config, metrics, downsampled equity curve, status |
| | `backtest_trades` | every simulated trade with costs and R multiple |
| User data | `watchlists`, `watchlist_items` | per-user lists |
| Research (migration `0002`) | `ingestion_runs` | each backfill/sync: range, requests, fetched/stored/rejected/duplicates/misaligned, missing before and after, status, error |
| | `experiments` | reproducible research runs: `dataset` (snapshot id = content hash of the candles), `config` (full spec), `code_version` (source hash + library versions), `results` |

## Deliberate omissions

* No separate raw-provider-payload table: candles keep `source_meta`; raw responses are reproducible from the provider and storing them adds volume without a current consumer.
* Gaps are tracked in `data_coverage.gaps` (capped at 200 ranges) rather than a gap table.
* Alembic migration was generated against SQLite and verified up/down; run it once against your PostgreSQL (done by the compose `backend` container on start).
