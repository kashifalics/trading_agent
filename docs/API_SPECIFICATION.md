# API specification

Interactive, always-current reference: **`/docs`** (Swagger UI) and **`/openapi.json`** on the backend. This page records the contract rules and the endpoint map.

## Conventions

* Base: `/api/v1`. JSON in/out. Timestamps ISO-8601 UTC (candles use epoch seconds).
* **Auth**: `X-API-Key` header. `AUTH_REQUIRED=false` (dev) maps anonymous calls to one local user; `true` requires a key (mandatory in production). Resources of other users return `404`.
* **Errors** (all non-2xx): `{"error": {"code", "message", "details", "request_id"}}`. Codes: `validation_failed` (422), `unsupported` (422), `not_found` (404), `unauthorized` (401), `rate_limited` (429), `provider_error` (502), `provider_not_configured` (503), `internal_error` (500, no internals leaked).
* **Pagination**: `?limit=&offset=` → `{items,total,limit,offset}`.
* **Jobs**: long operations return `202 {id, status, poll_url}`; poll the resource until `status ∈ {completed, failed}`.
* **Rate limit**: `RATE_LIMIT_PER_MINUTE` per client IP (health exempt).

## Endpoints

| Method & path | Purpose |
|---|---|
| `GET /health` | DB/Redis/OCR/job-backend status, `mode: analysis_only` |
| `GET /market/instruments` · `/instruments/{symbol}` | The four instruments with provider mappings and `supported` flag |
| `GET /market/timeframes` | 14-timeframe registry + which providers serve each natively |
| `GET /market/candles?symbol&timeframe&provider&limit&start&end&include_incomplete` | Stored candles (complete only by default) |
| `GET /market/coverage?symbol` | Counts, first/last, gaps, last sync per series |
| `GET /market/quotes?symbols` | Live quote per instrument; `status` ∈ ok/unsupported/not_configured/error — never invented |
| `GET /market/providers` | Provider metadata, limits, licensing, mappings |
| `POST /market/sync` | Ingest candles (idempotent; aggregates when not native) |
| `POST /market/coverage/probe` | Ask the provider what it serves on the current plan |
| `POST /analysis/run` → `202` · `GET /analysis` · `GET /analysis/{id}` · `GET /analysis/{id}/analogues` | Analysis jobs and results |
| `POST /predictions/run` → `202` · `GET /predictions` · `GET /predictions/{id}` · `GET /predictions/stats` · `POST /predictions/refresh-outcomes` | Predictions, evidence, outcome tracking |
| `POST /charts/analyze` (multipart: `file`, `symbol?`, `timeframe?`, `calibration_points?`) · `GET /charts/extractions/{id}` | Screenshot analysis |
| `GET /patterns?symbol&timeframe` · `GET /patterns/definitions` | Detections on stored candles + operational definitions |
| `GET /signals` | Signal engine summary per configured instrument (`SIGNAL_SYMBOLS`): overall bias, best plan, active plans, counts |
| `GET /signals/{symbol}` | Full top-down analysis: 14 per-timeframe plans (state, instruction, entry/stop/targets, 100-point checklist, reasons for/against, track record), multi-timeframe table, analyst report |
| `POST /signals/{symbol}/sync` | Fetch due candles from the instrument's keyless provider (BiQuote/Binance), then return the fresh analysis |
| `GET /signals/config` · `GET /signals/track-record` | Chains, weights, thresholds, spreads in force · historical replay results (docs/SIGNAL_ENGINE.md) |
| `POST /backtests/run` → `202` · `GET /backtests` · `GET /backtests/{id}` · `GET /backtests/strategies` | Backtests |
| `GET /models` · `GET /models/{id}` · `POST /models/train` → `202` · `POST /models/{id}/activate` | Model registry |
| `GET/POST/DELETE /watchlists…` | Per-user watchlists |

## Prediction object (essentials)

```json
{ "decision": "BUY|SELL|WAIT", "entry_low": 0, "entry_high": 0, "stop_loss": 0, "take_profit": [0],
  "risk_reward": 1.5, "invalidation_level": 0,
  "probabilities": null,                 // only for a calibrated, validated model
  "historical_frequency": {…},           // analogue frequencies with Wilson CIs and base rates
  "confluence_score": -0.54, "data_quality_score": 1.0, "warnings": [], "explanation": "…" }
```
`GET /predictions/{id}` adds `evidence[]`, `confidence` (the five separate views) and `wait_reasons[]`.
