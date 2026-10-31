# Architecture

Analysis-only platform: **no order execution, no broker connectivity**. A modular monolith (one FastAPI process + one worker image) and a separate Next.js frontend that talks to it only through the versioned REST API.

```
 Browser ── Next.js (frontend/) ──HTTP /api/v1──▶ FastAPI (backend/app)
                                                    │
        ┌───────────────┬───────────────┬──────────┴──────┬──────────────┐
   market_data      price_action /   historical_engine   ml_engine    chart_vision
 (providers,        candlestick /    feature_engineering (train, calib,  (upload, OpenCV,
  normalise,        market_structure (analogues)         registry)       OCR, match)
  aggregate,              └────────────┬──────────────────┘
  coverage)                      prediction (decision engine, risk, confidence)
        │                              │               backtesting (engine, metrics)
        ▼                              ▼
   PostgreSQL (SQLite for tests/local) ◀── services/ ◀── jobs (inline | Celery+Redis)
```

## Layers and rules

| Layer | Path | Rule |
|---|---|---|
| API | `app/api/v1/routes` | Thin: validate → call a service → return schema. All owned resources are filtered by `user.id`. |
| Services | `app/services` | Orchestration + persistence. `pipeline.py` is the **pure** analytical pipeline (no DB/network). |
| Domain | `market_data`, `price_action`, `candlestick`, `market_structure`, `historical_engine`, `feature_engineering`, `ml_engine`, `multi_timeframe`, `prediction`, `backtesting`, `chart_vision` | No FastAPI/SQLAlchemy imports (except `market_data.ingestion`, `ml_engine.model_registry`). Deterministic and unit-tested. |
| Persistence | `app/database` | SQLAlchemy 2 models, `UTCDateTime` type, Alembic migrations. |

## Data flow of one analysis

1. `POST /analysis/run` validates, creates an `analyses` row (`queued`), dispatches a job → `202 {id, poll_url}`.
2. Job: `ensure_data` (optional auto-sync, never fatal) → load **complete** candles → `analyze_price_action` → point-in-time features → triple-barrier labels → historical analogues → (optional) model inference → multi-timeframe views → `decide()` → persist `analyses.result`, `predictions`, `prediction_evidence`, `price_action_events`, `historical_analogues`.
3. The same pipeline is used for screenshots: `chart_service` produces `Bars` either from matched provider candles or from pixel extraction and calls `execute_analysis(bars_override=…)`.

## Point-in-time discipline (no look-ahead)

* Swing points carry `confirm_idx = idx + right`; BOS/CHoCH, liquidity and zones use confirmed swings only.
* Every `Event` records the bar at which it became *knowable* (`idx`) separately from where it started (`start_idx`).
* Feature row *i* uses bars ≤ *i*; analogue libraries only include bars whose outcome window ended before the query bar.
* Higher-timeframe bars are filtered to those complete at the entry bar's close (`htf_as_of`).
* All of this is asserted by tests that corrupt the future and require identical past output.

## Decision policy

`WAIT` unless data quality, confluence threshold, multi-timeframe agreement, contradiction limit, analogue sanity and a valid risk plan all pass. Probabilities are exposed only for a **calibrated model that passed minimum out-of-sample checks**; otherwise model output is labelled research-only and weighted zero. Five notions of certainty are kept separate: model probability, historical frequency, analytical confluence, data quality, uncertainty.

## Jobs

`JOB_BACKEND=inline` (default): FastAPI background tasks, no Redis needed. `celery`: tasks `ati.analysis`, `ati.backtest`, `ati.train_model` on the `worker` compose service. The frontend polls `GET /analysis/{id}` / `GET /backtests/{id}`.

## Key decisions

* Modular monolith: one deployable, clear module seams, no premature microservices.
* Sync SQLAlchemy + threadpool endpoints: CPU-bound analysis dominates; async DB would add complexity without benefit.
* Prices are `Decimal` in storage; analysis uses float64 arrays (`Bars`) for speed.
* Providers are adapters behind `MarketDataProvider`; symbol mapping lives in `provider_instruments`; candles of different providers are never merged.
