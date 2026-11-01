# Local setup

Everything runs on your machine at $0. No account is created for you; the only optional external credential is a free Twelve Data key (for XAUUSD).

## Option A — Docker (Postgres + Redis + API + worker + UI)

**PowerShell**
```powershell
.\scripts\setup.ps1 -DockerOnly      # creates .env with generated secrets
docker compose up --build            # first build downloads images + Python wheels (several minutes)
docker compose down                  # stop (add -v to also delete the database volume)
```
**bash / zsh**
```bash
./scripts/setup.sh --docker-only && docker compose up --build
```
Open <http://localhost:3000> (UI), <http://localhost:8000/docs> (API). The backend container runs `alembic upgrade head` on start. Then pull some data: *Data Sources → Sync BTCUSDT 1H*, or run an analysis with auto-sync (default).

## Option B — without Docker (SQLite, inline jobs)

**PowerShell**
```powershell
.\scripts\setup.ps1                                  # venv, deps, .env, migrations, npm ci
cd backend;  .\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
cd frontend; npm run dev                             # http://localhost:3000
```
**bash**: `./scripts/setup.sh`, then `cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000` and `cd frontend && npm run dev`.

## Commands

| Task | Command |
|---|---|
| Backend tests | `cd backend; .\.venv\Scripts\python -m pytest` (or `pytest` in an activated venv) |
| Backend lint | `ruff check app tests --select E,F,W,I --ignore E501` |
| Frontend lint / types / unit tests | `cd frontend; npm run lint; npm run typecheck; npm test` |
| Frontend build | `npm run build` |
| E2E (mocked API, desktop + mobile) | `npx playwright install chromium` once, then `npm run e2e` |
| New migration | `cd backend; alembic revision --autogenerate -m "msg"` |

## Credentials & optional tools

| Item | Needed for | Where |
|---|---|---|
| `TWELVE_DATA_API_KEY` (free plan) | XAUUSD data | sign up yourself: <https://twelvedata.com/pricing>; put it in the project-root `.env` (compose and the backend both read it) or in `backend/.env` (wins if both are set). Verify with `python scripts/xau_verify.py` (about 8 minutes, about 60 of the 800 daily credits) |
| Tesseract OCR | Reading symbol/timeframe/price axis from screenshots | Windows: UB-Mannheim build; Linux `apt install tesseract-ocr`; the Docker image already includes it. Without it, manual calibration points still work |
| `AUTH_REQUIRED=true` + API keys | Multi-user / non-localhost | see `SECURITY.md` |
| S3, LLM, Sentry | nothing in v0.1 | reserved variables, unused |

## Research workflow (from `backend/`, own database)
```powershell
$env:DATABASE_URL = "sqlite:///./research.db"
python -m app.research.run_milestone backfill --days 1200   # resumable; re-running is a no-op
python -m app.research.run_milestone backtest               # 1H and 4H, 4 cost scenarios + baselines
python -m app.research.run_milestone ml                     # 3 algorithms x {gross, base} costs, both timeframes
python -m app.research.run_milestone report                 # writes docs/reports/*.md from stored experiments
python -m app.research.reproduce 7                          # re-run experiment 7 and diff against its stored results
```

### Pattern study (gold + Bitcoin, all timeframes)
```powershell
python -m app.research.run_patterns data      # resumable; gold is rate-limited (8 req/min): ~25 min
python -m app.research.run_patterns study     # ~1 min per instrument
python -m app.research.run_patterns report    # docs/reports/PATTERN_EDGE_*.md + data/*.csv
python scripts/export_pattern_evidence.py     # refresh backend/app/data/pattern_evidence.json (served by /patterns/scan)
```

## Troubleshooting
* *"backend unreachable"* in the UI → backend not running or `NEXT_PUBLIC_API_URL` wrong (it is baked at build time; rebuild the frontend after changing).
* `docker compose` complains about `APP_SECRET_KEY` → run the setup script first.
* Port 8000/3000 busy → stop the local dev servers before `docker compose up`.
* XAUUSD shows "API key required" → expected until you add the Twelve Data key.
