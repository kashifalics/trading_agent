# Technical handover

For the engineer or operator who installs, runs and maintains AI Trading Intelligence. The customer-facing overview is the
[README](../README.md); day-to-day use is in the [User guide](USER_GUIDE.md).

**What the product is:** an analysis and decision-support tool for XAUUSD, EURUSD, GBPUSD, BTCUSDT, US30 and USOIL. It reads
candles, detects price-action structure on 14 timeframes and produces hypothetical trade plans (entry, stop, targets, confluence
checklist). **It never places orders and has no broker connection.** No strategy or model in it has a verified out-of-sample edge,
and every BUY/SELL is labelled **Not validated** (section 14).

---

## 1. Product overview and capabilities

| Capability | Where | Notes |
|---|---|---|
| Live quotes and data health | Overview, Data Sources | Delayed prices are labelled "delayed", never "live" |
| Multi-timeframe signal engine (scalping / intraday / swing / long-term) | Signals | Top-down: two higher timeframes give the bias, the setup timeframe the structural entry, a lower timeframe confirms. Per timeframe: state, instruction, entry, stop, up to 3 targets (min 1:2), 100-point checklist, reasons for/against, lot-size calculator |
| Forward test of those signals with simulated orders | Paper Trading | Records every signal when it appears and simulates it on later candles; no conclusion before 100 closed trades |
| Ranked setups across instruments and timeframes | Trade Opportunities | Evidence score (not a win probability) with validation status |
| Single-chart analysis with evidence, analogues and screenshot upload | Chart Analysis, Predictions | Decision engine (BUY / SELL / WAIT) with five separate confidence views |
| Pattern detections with measured history | Historical Patterns, Market Scanner | Descriptive; every pattern's measured track record is shown |
| Backtests and model training | Backtesting, Models, Performance | Research tools; models cannot be activated unless they pass validation |
| XAUUSD 20-year research results | Gold Research | Summary of the completed research; no validated candidate |

Not included: automated or live order execution, broker connectivity, an AI chat/LLM assistant (explanations are generated
deterministically from the computed results, so they cannot contradict them), TradingView/Pine Script integration, a news filter.

## 2. System architecture

```
Browser ──▶ Next.js 15 frontend (frontend/, static pages + client-side data fetching)
               │  HTTPS, JSON, X-API-Key header
               ▼
            FastAPI backend (backend/app, /api/v1, one process)
               ├─ market_data: provider adapters (BiQuote, Binance, Twelve Data, OANDA), normalisation, aggregation, coverage
               ├─ price_action / market_structure / candlestick / patterns: deterministic, causal detectors
               ├─ signals: multi-timeframe engine, lifecycle, track record, validation labels
               ├─ paper: simulated orders + in-process worker (every PAPER_TRADING_INTERVAL_SECONDS)
               ├─ opportunities, prediction, backtesting, ml_engine, chart_vision
               └─ database: SQLAlchemy 2 + Alembic  ──▶  SQLite (single instance) or PostgreSQL 16
            Optional: Celery worker + Redis (JOB_BACKEND=celery, used by docker compose)
```

* Stack: Python 3.12, FastAPI 0.162, SQLAlchemy 2, Alembic, polars/numpy, scikit-learn/LightGBM/XGBoost, OpenCV + optional
  Tesseract; Next.js 15.5, React 19, TypeScript, Tailwind 3, TanStack Query, Lightweight Charts, zustand.
* Detectors use only completed candles and record the bar at which each event became knowable; look-ahead is guarded by tests
  that change the future and require identical past output. Higher-timeframe context uses only candles complete at the decision time.
* Market data from different providers is never merged; each instrument × provider is a separate series.
* Research code (`app/historical`, `app/gold_research`, `app/research`) is not used by the running product except for bundled
  summary files (`app/data/*.json`). Its large datasets live in the git-ignored `data/historical/` folder and are not needed to run
  the product.

More detail: [ARCHITECTURE.md](ARCHITECTURE.md), [SIGNAL_ENGINE.md](SIGNAL_ENGINE.md), [PAPER_TRADING.md](PAPER_TRADING.md),
[MULTI_TIMEFRAME_ANALYSIS.md](MULTI_TIMEFRAME_ANALYSIS.md), [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).

## 3. Feature list

* **Instruments:** XAUUSD (gold), EURUSD, GBPUSD, BTCUSDT (default view), US30, USOIL (reachable with `?all=true` and on
  Signals/Opportunities).
* **Data sources:** BiQuote (default, free, no key; indicative MT5 broker quotes), Binance public API (BTCUSDT, deep history), Twelve
  Data free plan (key required), OANDA practice (token required; unverified). See [MARKET_DATA_PROVIDERS.md](MARKET_DATA_PROVIDERS.md).
* **Timeframes:** 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 1D, 1W, 1M, 3M, 6M, 12M (non-native ones are aggregated; if a provider's history
  is too short the timeframe reports "insufficient data" instead of guessing).
* **Signals:** states `ENTRY_READY`, `WAITING_FOR_CONFIRMATION`, `SETUP_DEVELOPING`, `WATCHLIST`, `NO_SETUP`, `TRADE_INVALIDATED`,
  `TRADE_EXPIRED`; instructions EXECUTE NOW / WAIT FOR CONFIRMATION / PLACE LIMIT ORDER / NO TRADE; structural stops and targets;
  must-pass rules (structural stop, R:R ≥ 1:2, spread, fresh data); 100-point checklist (HTF 20, structure 20, liquidity 15, entry
  zone 15, LTF confirmation 15, R:R 10, session/volatility 5; signal at ≥ 60, limit orders at ≥ 70).
* **Safety rules:** stale or insufficient data → no signal for that timeframe; delayed quotes flagged; a plan that cannot reach 2R
  to a structural target is blocked with the reason shown; no win probability unless validated (none is).
* **Paper trading:** account with risk % per trade, max open positions and daily loss limit; market and limit fills on later
  candles, gaps honoured, spread charged; forward-test verdict only after 100 closed trades.
* **Position sizing:** lots = (balance × risk %) ÷ (stop distance × contract size); contract sizes editable (defaults: XAUUSD 100 oz,
  FX 100,000, BTC 1, US30 1, USOIL 1,000).

## 4. Installation and setup

Prerequisites: Docker Desktop (for option A) **or** Python 3.12 + Node.js 20+ (option B). Optional: Tesseract OCR (screenshot reading).

**A. Docker Compose (PostgreSQL, Redis, API, worker, UI)**
```powershell
.\scripts\setup.ps1 -DockerOnly     # bash: ./scripts/setup.sh --docker-only   (creates .env with generated secrets)
docker compose up --build           # UI http://localhost:3000 · API http://localhost:8000/docs
docker compose down                 # stop (add -v to delete the database volume)
```
**B. Without Docker (SQLite)**
```powershell
.\scripts\setup.ps1                                          # venv, dependencies, .env, migrations, npm ci
cd backend;  .\.venv\Scripts\python -m uvicorn app.main:app --port 8000
cd frontend; npm run dev                                      # http://localhost:3000
```
First steps after installing: open the UI, go to **Signals** and press **Refresh now** (downloads candles from the keyless
providers), or **Data Sources → Sync**. Full detail: [LOCAL_SETUP.md](LOCAL_SETUP.md).

**Create a user key** (needed whenever `AUTH_REQUIRED=true`, always in production): either set `BOOTSTRAP_API_KEY` (the owner key is
created or rotated at every start; generate one with
`python -c "import secrets; print('ati_' + secrets.token_urlsafe(32))"`), or run
`python scripts/create_user.py you@example.com` from `backend/` with the same `DATABASE_URL` and `APP_SECRET_KEY` as the service
(prints a new key once). The user enters the key under **Settings → Platform API key → Save & verify**.

## 5. Environment variables and configuration

Set in the project-root `.env` (docker compose) or `backend/.env` (wins when both exist), or in the hosting platform's variables.
With docker compose, the core variables are composed in `docker-compose.yml` and every optional one below is passed through when it
is set in `.env` (unset ones keep the application defaults).
Templates: `.env.example`, `backend/.env.example`, `frontend/.env.example`. **Never commit a `.env` file.**

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | `production` refuses to start with the default secret or with `AUTH_REQUIRED=false` |
| `APP_SECRET_KEY` | placeholder | HMAC key for API-key hashes. **Changing it invalidates every issued key** |
| `AUTH_REQUIRED` | `false` | `true` = every endpoint except `/health` needs `X-API-Key` |
| `BOOTSTRAP_API_KEY` | – | Owner key ensured at startup (hosts without a shell) |
| `DATABASE_URL` | `sqlite:///./dev.db` | SQLite or PostgreSQL (`postgres://…` is converted to the psycopg driver) |
| `MIGRATION_DATABASE_URL` | – | Optional separate URL for Alembic |
| `AUTO_MIGRATE` | `true` | Run `alembic upgrade head` at startup |
| `FRONTEND_URL` | `http://localhost:3000` | The only CORS origin allowed in production |
| `RATE_LIMIT_PER_MINUTE` | `240` | Per client IP, per process |
| `PREFERRED_PROVIDER` | `biquote` | Default data source when a request names none; empty = route by mapping status |
| `TWELVE_DATA_API_KEY` | – | Twelve Data free-plan key (optional) |
| `OANDA_API_TOKEN`, `OANDA_BASE_URL` | –, practice host | OANDA practice account (optional, read-only) |
| `BINANCE_API_BASE_URL`, `BIQUOTE_BASE_URL` | public hosts | Override only for mirrors |
| `FOCUS_SYMBOLS` | `BTCUSDT,XAUUSD,EURUSD,GBPUSD` | Instruments shown by default |
| `SIGNAL_SYMBOLS` | `XAUUSD,EURUSD,GBPUSD,BTCUSDT,US30,USOIL` | Instruments on the Signals page and in paper trading |
| `SIGNAL_SPREADS` | `BTCUSDT:2,XAUUSD:0.30` | Round-trip spread in price units per instrument; others pay 0.02% of price (conservative for FX: about 2 pips). **Set your broker's spreads**, e.g. `EURUSD:0.00012` |
| `SIGNAL_PROVIDER_OVERRIDES` | `BTCUSDT:binance` | One provider per instrument for the signal engine |
| `SIGNAL_REFRESH_PROVIDERS` | `biquote,binance` | Providers the Signals page may sync automatically |
| `OPPORTUNITY_SYMBOLS`, `OPPORTUNITY_SCAN_INTERVAL_MINUTES`, `OPPORTUNITY_REFRESH_PROVIDERS`, `OPPORTUNITY_MAX_SYNC_TFS` | see `backend/.env.example` | Trade Opportunities scans (0 = manual only) |
| `PAPER_TRADING_INTERVAL_SECONDS` | `60` | In-process paper cycle; `0` = off |
| `PAPER_START_BALANCE`, `PAPER_RISK_PCT`, `PAPER_MAX_OPEN_POSITIONS`, `PAPER_MAX_DAILY_LOSS_PCT` | 10000, 0.5, 5, 2 | Defaults for a new paper account |
| `JOB_BACKEND`, `REDIS_URL` | `inline`, – | `celery` + Redis for a separate worker |
| `MODEL_DIR`, `UPLOAD_DIR`, `MAX_UPLOAD_BYTES` | `./model_store`, `./uploads`, 8 MB | Storage paths and upload limit |
| `SENTRY_DSN` | – | Error reporting if `sentry-sdk` is installed |
| `NEXT_PUBLIC_API_URL` (frontend) | `http://localhost:8000` | Backend URL, **baked in at build time**: rebuild the frontend after changing it. Never put secrets in `NEXT_PUBLIC_*` |

Reserved and unused: `S3_*`, `LLM_PROVIDER`, `LLM_MODEL`, `OPENAI_API_KEY`.

## 6. Database setup and migrations

* **Engines:** PostgreSQL 16 (docker compose) or SQLite (local, single-instance hosting). 28 tables; schema in
  [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).
* **Migrations:** Alembic revisions `0001`–`0004`, applied automatically at startup (`AUTO_MIGRATE=true`) and by the Docker
  image's start command. Reference data (instruments, providers, mappings) is seeded at every start, additively: new instruments
  or mappings are added, existing rows are never changed.
* **Verified on 2026-11-10** on SQLite and PostgreSQL 16: upgrade to head → schema identical to the models (0 differences) →
  downgrade to base → upgrade again → seeding twice (idempotent).
* **Manual commands** (from `backend/`, with the service's `DATABASE_URL`): `alembic upgrade head`, `alembic downgrade -1`,
  `alembic current`. On Windows, run them as
  `python -c "from app.database.init_db import run_migrations; run_migrations()"` if the local `alembic/` folder shadows the package.
* **New migration:** change the models, then `alembic revision --autogenerate -m "message"`, review the file, test upgrade and
  downgrade on a copy of the data.
* **This release adds no migration.** At its first start it seeds the EURUSD instrument and BiQuote mappings for EURUSD and
  GBPUSD (new rows only).

## 7. API documentation

* Interactive reference: `http://<backend>/docs` (Swagger UI) and `/openapi.json`, always current.
* Contract rules and the endpoint map (60 endpoints): [API_SPECIFICATION.md](API_SPECIFICATION.md).
* Every endpoint except `GET /api/v1/health` needs `X-API-Key` when `AUTH_REQUIRED=true`. Errors use one envelope:
  `{"error": {"code", "message", "details", "request_id"}}`; the `request_id` also appears in the server log.

## 8. User guide

See [USER_GUIDE.md](USER_GUIDE.md): connecting with a key, reading a signal, sizing a position, paper trading, opportunities,
chart analysis and the meaning of every label.

## 9. Known limitations

* **No validated edge** (section 14). Signals are hypothetical setups.
* **Shallow history from the keyless default feed:** BiQuote keeps about 7 days of 1H, 6 weeks of 4H and 500 daily bars, and no
  1W/1M; higher timeframes therefore often show "insufficient data" until history accumulates in your database (or use Binance for
  BTCUSDT, Twelve Data with a key). BiQuote quotes are indicative broker CFD prices with no service-level guarantee, and its terms
  forbid re-exposing the raw feed publicly.
* **No economic-news filter.** High-impact news is not taken into account.
* US30 and USOIL come from BiQuote CFD quotes; the OANDA route is untested without a token. Twelve Data's free plan has daily and
  per-minute credit limits.
* Default spreads exist only for BTCUSDT and XAUUSD; other instruments use a conservative 0.02% of price until `SIGNAL_SPREADS` is set.
* Screenshot (OCR) reading was verified on synthetic charts only and needs Tesseract.
* Accounts: no registration, login form, roles or password reset; one API key per user, stored in the browser.
* The paper-trading worker runs inside the API process: run **one** backend instance (more instances would run duplicate cycles).
  The same applies to SQLite.
* `GET /signals` analyses every configured instrument in turn: about 2 s per instrument (about 10 s for the six defaults, measured
  locally). The first sync of an instrument downloads every timeframe and takes 30–65 s; later syncs fetch only due candles.

## 10. Security and privacy

Summary (full list and remaining risks: [SECURITY.md](SECURITY.md)):
* Analysis only: no order execution, no broker or exchange account access; market data is read-only.
* API keys hashed with HMAC-SHA256; provider keys only in environment variables, never in the frontend, logs or responses.
* Every endpoint except health requires a key in production; production CORS allows only `FRONTEND_URL`; uniform error envelope
  without internals; upload validation and re-encoding; per-IP rate limit; security headers.
* Dependencies audited on 2026-11-10; vulnerable backend packages upgraded. Two frontend advisories remain (not reachable as used;
  fixes need major upgrades).
* Personal data stored: user email (or a placeholder) and the hashed key; paper-trading records; watchlists; uploaded screenshots
  (re-encoded, per-user folder). No payment data.

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| UI shows "Backend unreachable" | Backend not running, or the frontend was built with the wrong `NEXT_PUBLIC_API_URL` (rebuild after changing it); check CORS: `FRONTEND_URL` must equal the UI's origin exactly |
| "API key required" / "Invalid API key" | Enter the key under Settings → Save & verify. After changing `APP_SECRET_KEY` all keys must be re-issued |
| Backend refuses to start in production | `APP_SECRET_KEY` is the default or `AUTH_REQUIRED` is not `true` |
| A timeframe says "insufficient data" | The provider's history is too short for that timeframe (see section 9); it is not an error |
| "delayed" price on Overview | Market closed or the provider's last quote is old; it is shown as the last known price on purpose |
| XAUUSD/GBPUSD on Twelve Data: "API key required" | Only when `provider=twelve_data` is chosen or `PREFERRED_PROVIDER` is empty; the default BiQuote route needs no key |
| No signals at all | Normal when no setup passes the must-pass rules; the table shows why (blocked reasons). Press Refresh now to sync |
| `docker compose` complains about `APP_SECRET_KEY` | Run the setup script first (creates `.env`) |
| Port 3000/8000 busy | Stop local dev servers before `docker compose up` |
| `429 rate_limited` | More than `RATE_LIMIT_PER_MINUTE` requests per minute from one address |
| Analyses or scans stay "queued" (docker compose) | The `worker` container is not running: `docker compose logs worker`. If Celery cannot accept a job the backend now runs it inline and logs a warning |

Logs go to standard output (`docker compose logs backend`, the hosting platform's log view); every error response carries a
`request_id` that is also in the log.

## 12. Deployment and rollback

**Recommended layout:** backend as one container (the `backend/Dockerfile`, health check `/api/v1/health`) on any Docker host;
frontend on any Node host or static-capable platform (the `frontend/Dockerfile` produces a standalone server). The current
deployment uses Railway (backend, SQLite on a persistent volume) and Vercel (frontend); this branch has **not** been deployed.

Release steps (each needs the owner's approval):
1. Merge the release branch into `main` after review; CI (`.github/workflows/ci.yml`) runs lint, type checks, all tests, the build
   and the end-to-end tests.
2. Back up the database (below).
3. Backend: set the variables in section 5 (`APP_ENV=production`, `AUTH_REQUIRED=true`, a strong `APP_SECRET_KEY`,
   `FRONTEND_URL`, `BOOTSTRAP_API_KEY`, `DATABASE_URL` on persistent storage), deploy the backend folder
   (Railway: `railway up --service backend --detach` from `backend/`). Migrations and seeding run at start.
4. Frontend: set `NEXT_PUBLIC_API_URL` to the backend's public HTTPS URL and deploy the frontend folder (Vercel: `vercel --prod`
   from `frontend/`, or set the project's root directory to `frontend`).
5. Verify: `GET /api/v1/health` returns `ok` with `auth_required: true`; a request without a key returns 401; open the UI, enter
   the key in Settings (Save & verify), open Signals and press Refresh now.

**Rollback:** redeploy the previous successful deployment (Railway: service → Deployments → previous deployment → Redeploy;
Vercel: Deployments → previous production deployment → Promote / Instant Rollback), or check out the previous release commit and
deploy it the same way. This release has no schema migration, so code rollback needs no database change (the extra instrument
rows it seeds are ignored by older code). If a future release adds a migration, restore the backup or run `alembic downgrade -1`
**before** rolling the code back.

**Backups:** SQLite: stop the service or use `sqlite3 app.db ".backup backup.db"`, keep the copy off the server (on Railway, use
the volume's backup feature if your plan includes it). PostgreSQL: `docker compose exec postgres pg_dump -U ati ati > backup.sql`;
restore with `psql`.

## 13. Maintenance

* **Before every release:** `cd backend; pytest` and `ruff check app tests --select E,F,W,I --ignore E501`;
  `cd frontend; npm run lint; npm run typecheck; npm test; npm run build; npm run e2e`; `pip-audit -r backend/requirements.txt`
  and `npm audit` (not yet automated in CI).
* **Pin transitive dependencies:** `requirements.txt` pins the 25 direct packages, but their own dependencies float. One of them
  (`kombu`) broke the Celery worker in a fresh image; it is now pinned. Generating a full lock file (for example with `pip-tools`)
  and building from it is recommended before the next release.
* **Keys:** rotate the owner key by changing `BOOTSTRAP_API_KEY` and restarting; other users with `scripts/create_user.py` (the
  old key stops working). Rotate provider keys at the provider and update the variable.
* **Data:** candles accumulate in the database; BiQuote serves a fixed recent window, so history grows only while the service runs.
  Coverage and gaps: Data Sources page or `GET /market/coverage`.
* **Spreads and instruments:** adjust `SIGNAL_SPREADS`, `SIGNAL_SYMBOLS`, `FOCUS_SYMBOLS`; restart to apply.
* **Paper trading:** reset or reconfigure the account on the Paper Trading page; the forward-test record is kept.
* **Research:** the XAUUSD research pipeline (`python -m app.gold_research …`, `python -m app.historical …`) is documented in
  [PATTERN_STUDY.md](PATTERN_STUDY.md) and [HISTORICAL_DATA.md](HISTORICAL_DATA.md). Its sealed final-test period must not be read
  without the owner's explicit decision; reports and frozen files under `docs/research/` and `docs/reports/` are records and must
  not be edited.

## 14. Research limitations and unvalidated trading signals

* **Signal engine replay** (same rules, BTCUSDT and XAUUSD, 5m–1D): 1,027 trades, −0.048 R per trade after spread; the
  out-of-sample part alone −0.19 R over 414 trades; every series "no edge" ([SIGNAL_TRACK_RECORD.md](reports/SIGNAL_TRACK_RECORD.md)).
* **Pattern studies** (about 600 hypotheses per instrument, all timeframes): BTCUSDT 0 candidates; XAUUSD 0 confirmed
  ([PATTERN_EDGE_XAUUSD.md](reports/PATTERN_EDGE_XAUUSD.md)).
* **Rule-based decision engine and ML models** (BTCUSDT 1H/4H): negative or zero net expectancy; every model research-only
  ([QUANTITATIVE_VALIDATION_SUMMARY.md](reports/QUANTITATIVE_VALIDATION_SUMMARY.md)).
* **XAUUSD 20-year research** (Dukascopy 1-minute bid/ask, 2003–2026): experiment 1 tested 1,931 pattern hypotheses; 0 of 62 frozen
  candidates were confirmed on the validation period; models reached validation AUC 0.555–0.585 but their best decile still lost
  money, so none was promoted. Experiment 2 (structural limit entries, longer holds, financing costs): 0 of 36 pre-registered tests
  became candidates. The sealed final-test period was never read. Reports: `docs/reports/XAUUSD_*.md`.
* **Consequence in the product:** every plan, prediction and opportunity carries a **Not validated** label; no win probability is
  shown anywhere; the confluence/evidence score measures setup quality, not the chance of winning; the paper-trading forward test
  draws no conclusion before 100 closed trades. These labels are driven by the data: a series would only show "validated" after
  passing out-of-sample validation, and the shipped records contain none (a test enforces this).
