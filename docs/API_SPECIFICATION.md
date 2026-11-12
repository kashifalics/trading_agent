# API specification

Interactive, always-current reference: **`/docs`** (Swagger UI) and **`/openapi.json`** on the backend. This page records the contract rules and the endpoint map.

## Conventions

* Base: `/api/v1`. JSON in/out. Timestamps ISO-8601 UTC (candles use epoch seconds).
* **Auth**: `X-API-Key` header on **every endpoint except `GET /health`** (enforced at router level, so new endpoints cannot be added without it). `AUTH_REQUIRED=false` (local development) maps anonymous calls to one local user; `true` requires a valid key and is mandatory when `APP_ENV=production`. A missing or wrong key gets `401`. Resources of other users return `404`. `GET /auth/status` confirms that a key works.
* **Errors** (all non-2xx): `{"error": {"code", "message", "details", "request_id"}}`. Codes: `validation_failed` (422), `unsupported` (422), `not_found` (404), `unauthorized` (401), `not_promotable` (409), `busy` (409), `rate_limited` (429), `provider_error` (502), `provider_not_configured` (503), `internal_error` (500, no internals leaked).
* **Pagination**: `?limit=&offset=` → `{items,total,limit,offset}`.
* **Jobs**: long operations return `202 {id, status, poll_url}`; poll the resource until `status ∈ {completed, failed}`.
* **Rate limit**: `RATE_LIMIT_PER_MINUTE` per client IP (health exempt).

## Endpoints

| Method & path | Purpose |
|---|---|
| `GET /health` | Public. DB/Redis/OCR/job-backend status, `mode: analysis_only`, `auth_required` (whether clients need a key) |
| `GET /auth/status` | `{authenticated, auth_required, mode, key_used}`: confirms the key in `X-API-Key` is accepted (used by Settings → Save & verify) |
| `GET /market/instruments?all=` · `/instruments/{symbol}` | Instruments with provider mappings and `supported` flag (`FOCUS_SYMBOLS` by default: all six signal instruments XAUUSD, EURUSD, GBPUSD, BTCUSDT, US30, USOIL) |
| `GET /market/timeframes` | 14-timeframe registry + which providers serve each natively |
| `GET /market/candles?symbol&timeframe&provider&limit&start&end&include_incomplete` | Stored candles (complete only by default) |
| `GET /market/coverage?symbol` | Counts, first/last, gaps, last sync per series |
| `GET /market/quotes?symbols` | Latest quote per instrument (at most 20 names); `status` ∈ ok/unsupported/not_configured/error — never invented. `delayed: true` (with a message) when it is the last known price (market closed or stale quote), never a live one |
| `GET /market/providers` | Provider metadata, limits, licensing, mappings |
| `POST /market/sync` | Ingest candles (idempotent; aggregates when not native) |
| `POST /market/coverage/probe` | Ask the provider what it serves on the current plan |
| `POST /analysis/run` → `202` · `GET /analysis` · `GET /analysis/{id}` · `GET /analysis/{id}/analogues` | Analysis jobs and results |
| `POST /predictions/run` → `202` · `GET /predictions` · `GET /predictions/{id}` · `GET /predictions/stats` · `POST /predictions/refresh-outcomes` | Predictions, evidence, outcome tracking |
| `POST /charts/analyze` (multipart: `file`, `symbol?`, `timeframe?`, `calibration_points?`) · `GET /charts/extractions/{id}` | Screenshot analysis |
| `GET /patterns?symbol&timeframe` · `GET /patterns/scan?symbol` · `GET /patterns/definitions` | Detections on stored candles, the all-timeframe scan with each pattern's measured track record, operational definitions |
| `GET /signals` | Signal engine summary per configured instrument (`SIGNAL_SYMBOLS`): overall bias, best plan, active plans, counts, and `as_of` (when that analysis ran). Each instrument's latest analysis is reused for up to `refresh_s` (90) seconds; the paper-trading cycle and every `GET /signals/{symbol}` or sync store a fresh one, so the summary normally answers at once |
| `GET /signals/{symbol}` | Full top-down analysis: 14 per-timeframe plans (state, instruction, entry/stop/targets, 100-point checklist, reasons for/against, track record, `validation` — `not_validated` unless the rules passed out-of-sample validation), multi-timeframe table, analyst report (states the validation status) |
| `POST /signals/{symbol}/sync` | Fetch due candles from the instrument's keyless provider (BiQuote/Binance), then return the fresh analysis |
| `GET /signals/config` · `GET /signals/track-record` | Chains, weights, thresholds, spreads in force · historical replay results (docs/SIGNAL_ENGINE.md) |
| `GET /paper/summary` | Paper trading: account (balance, equity, today's P&L, rule status), forward-test metrics and verdict, equity curves, breakdowns (with the backtest beside each instrument × timeframe), open/pending trades, worker status (docs/PAPER_TRADING.md) |
| `GET /paper/trades?status&symbol&timeframe&limit&offset` · `GET /paper/trades/{id}` | Recorded signals and their simulated outcome; `status` ∈ pending/open/closed/cancelled/missed/expired/skipped/live/finished/unfilled/all. The detail includes the plan as shown when the signal fired |
| `GET /paper/account` · `PATCH /paper/account` · `POST /paper/account/reset` | Active paper account; change risk per trade (≤ 5%), max open trades, daily loss limit; start a new account (signal history kept). Audited |
| `POST /paper/run?sync=true` | Run one paper-trading cycle now (sync keyless providers → analyse → simulate → record). `409 busy` while another cycle runs. Audited |
| `POST /backtests/run` → `202` · `GET /backtests` · `GET /backtests/{id}` · `GET /backtests/strategies` | Backtests |
| `GET /models` · `GET /models/{id}` · `POST /models/train` → `202` · `POST /models/{id}/activate` | Model registry. Activation is refused with `409 not_promotable` unless the model is calibrated **and** passed the out-of-sample checks |
| `POST /opportunities/scan` → `202` · `GET /opportunities/summary` · `GET /opportunities` · `GET /opportunities/{id}` · `GET /opportunities/scans[/{id}]` · `GET /opportunities/timeframes` · `/config` · `/validation` | Trade Opportunities: multi-instrument, 14-timeframe scans ranked by an evidence score (not a win probability) with validation status (docs/TRADE_OPPORTUNITIES_ARCHITECTURE.md) |
| `GET /research/gold` | Bundled summary of the XAUUSD historical research (dataset, split, pattern and model results); never includes sealed final-test figures |
| `GET/POST/DELETE /watchlists…` | Per-user watchlists |

## Decision object (`call`)

Every response with a trade idea carries `call` (docs/DECISION_ENGINE.md); each of those endpoints accepts `?experimental=true`.

| Field | Meaning |
|---|---|
| `decision` | `ENTER`, `WAIT`, `EXIT` or `NO TRADE` |
| `label` / `headline` / `next_condition` | e.g. `WAIT — UNVALIDATED SETUP`; one-sentence reason; what must happen next (always present) |
| `symbol`, `timeframe`, `direction` (`BUY`/`SELL`/`NONE`), `setup`, `entry_mode` (`immediate`/`conditional`, ENTER only) | The setup |
| `levels` | `{entry, entry_zone, stop_loss, targets[{label, price, rr}], risk_reward, invalidation}`, **only with ENTER**, else `null` |
| `hypothetical` | Same fields plus `label: "HYPOTHETICAL — UNVALIDATED"`, only with `experimental=true` and never with ENTER |
| `watch` | `{zone, invalidation}`: the price condition without entry/stop/targets |
| `checks[]`, `failed_checks[]` | `{name, passed, detail, fix}` mandatory conditions |
| `validation` | `{status: validated / not_validated, label, note, research_status}` |
| `data_quality`, `alignment` | `{status, detail}`; higher-timeframe agreement and confirmation timeframe status |
| `reasons_for[]`, `reasons_against[]`, `invalidation`, `score`, `score_note` | Evidence; the score is a quality checklist, not a probability |
| `trade` | Management of a tracked paper trade on this timeframe, if any |
| `wait_kind`, `technical_status`, `technical_detail`, `price_now`, `price_source` | Diagnostics |

Paper trades (`/paper/trades`, `/paper/summary`) that are open or pending carry `management`: `{action: HOLD/EXIT/WAIT/NO TRADE,
reason, current_price, stop_distance, target_distance, unrealized_r, unrealized_pnl, ...}`.

## Prediction object (essentials)

```json
{ "decision": "BUY|SELL|WAIT", "entry_low": 0, "entry_high": 0, "stop_loss": 0, "take_profit": [0],
  "risk_reward": 1.5, "invalidation_level": 0,
  "probabilities": null,                 // only for a calibrated, validated model
  "historical_frequency": {…},           // analogue frequencies with Wilson CIs and base rates
  "confluence_score": -0.54, "data_quality_score": 1.0, "warnings": [], "explanation": "…" }
```
`GET /predictions/{id}` adds `evidence[]`, `confidence` (the five separate views) and `wait_reasons[]`.
