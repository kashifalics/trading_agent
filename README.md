# AI Trading Intelligence Platform

An **analysis-only** market-intelligence terminal. It reads candles, detects price-action structure, compares the present with history, optionally consults a validated ML model, and returns **BUY / SELL / WAIT** with the evidence behind it. It never places orders and never connects to a trading account.

> **Honesty rules built in:** no fabricated prices or candles; no "probability" unless a model is calibrated *and* passed out-of-sample checks; `WAIT` whenever evidence is weak, contradictory, stale or incomplete; unsupported instruments say so instead of showing placeholder data.

## Status at a glance
| Instrument | Data source | State |
|---|---|---|
| BTCUSDT | Binance public API | ✅ working (live-verified) |
| XAUUSD | Twelve Data free plan | 🟡 verified live (1H/4H/1D); native-4H grid and weekend-candle caveats, see the status doc |
| GBPUSD | Twelve Data free plan | ✅ available (1H/1D; 2H/4H built from 1H) |
| US30, USOIL | OANDA practice account | 🟡 adapter ready - add a free `OANDA_API_TOKEN` (Twelve Data's free plan has no Dow index) |

Full detail: [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).

## Signals
The **Signals** tab (directly below Overview) analyses every timeframe top-down (higher-timeframe bias → setup → lower-timeframe confirmation) and gives, per timeframe: an entry state (`ENTRY_READY`, `WAITING_FOR_CONFIRMATION`, `SETUP_DEVELOPING`, `WATCHLIST`, `NO_SETUP`, …), a final instruction (EXECUTE NOW / WAIT FOR CONFIRMATION / PLACE LIMIT ORDER / NO TRADE), a structural entry, stop loss and up to three targets (minimum 1:2 reward:risk), a 100-point confluence checklist with reasons for and against, and a lot-size calculator. The page syncs fresh candles every 60 s (BiQuote / Binance, keyless). The score is **setup quality, not a win probability**; the measured track record of the same rules is in [`docs/reports/SIGNAL_TRACK_RECORD.md`](docs/reports/SIGNAL_TRACK_RECORD.md). Design: [`docs/SIGNAL_ENGINE.md`](docs/SIGNAL_ENGINE.md).

## Trade Opportunities
The **Trade Opportunities** tab (below Overview) scans every supported instrument on all 14 timeframes and ranks scalping / intraday / swing / long-term setups by an *evidence score* (not a win probability). WAIT is a normal result. Start a scan from the page, or `POST /api/v1/opportunities/scan`; set `OPPORTUNITY_SCAN_INTERVAL_MINUTES` to scan automatically. See [`docs/TRADE_OPPORTUNITIES_ARCHITECTURE.md`](docs/TRADE_OPPORTUNITIES_ARCHITECTURE.md) and [`docs/STRATEGY_VALIDATION.md`](docs/STRATEGY_VALIDATION.md) (no rule set is validated yet).

## Quick start (Docker)
```powershell
.\scripts\setup.ps1 -DockerOnly     # PowerShell   (bash: ./scripts/setup.sh --docker-only)
docker compose up --build
```
UI <http://localhost:3000> · API docs <http://localhost:8000/docs>. Stop with `docker compose down`.

Without Docker (SQLite): `.\scripts\setup.ps1`, then run the backend (`uvicorn app.main:app --reload`) and `npm run dev` in `frontend/`. Exact steps: [`docs/LOCAL_SETUP.md`](docs/LOCAL_SETUP.md).

## Checks
```
cd backend  && pytest                       # 179 tests
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
cd frontend && npx playwright install chromium && npm run e2e
```

## Layout
```
ai-trading-intelligence/
  backend/   FastAPI · SQLAlchemy · Alembic · ML · vision · backtesting   (own Dockerfile, tests, migrations)
  frontend/  Next.js · TypeScript · Tailwind · Lightweight Charts · TanStack Query   (own Dockerfile, tests)
  docs/      architecture, schema, API, providers, licensing, rules, ML, backtesting, security, setup, roadmap, status
  scripts/   setup.ps1 / setup.sh        .github/workflows/ci.yml        docker-compose.yml
```
The frontend talks to the backend only through the documented `/api/v1` REST API.

## What the UI offers
Overview · Chart Analysis (candles, structure/zone overlays, trade plan, multi-timeframe, screenshot upload) · Market Scanner · Predictions · Prediction Details (evidence, analogues, five separate confidence views, outcome tracking) · Historical Patterns · Backtesting · Performance Analytics · Watchlists · Data Sources · Model Management · Settings.

## Documentation
[Architecture](docs/ARCHITECTURE.md) · [Schema](docs/DATABASE_SCHEMA.md) · [API](docs/API_SPECIFICATION.md) · [Providers](docs/MARKET_DATA_PROVIDERS.md) · [Licensing](docs/DATA_LICENSING.md) · [Price-action rules](docs/PRICE_ACTION_RULES.md) · [ML](docs/ML_METHODOLOGY.md) · [Backtesting](docs/BACKTESTING_METHODOLOGY.md) · [Security](docs/SECURITY.md) · [Setup](docs/LOCAL_SETUP.md) · [Roadmap](docs/ROADMAP.md) · [Status](docs/IMPLEMENTATION_STATUS.md)

_Not financial advice. Past patterns do not guarantee future results._
