# Security

## Posture
* **Analysis only.** There is no broker/exchange integration that can place orders; Binance is accessed only through public market-data endpoints, no API key.
* Secrets live in environment variables (`.env`, gitignored; `scripts/setup.*` generates `APP_SECRET_KEY` and the Postgres password). `.env.example` contains placeholders only. Provider keys are backend-only; the only `NEXT_PUBLIC_*` variable is the public API URL.
* `APP_ENV=production` refuses to start with the default secret or with `AUTH_REQUIRED=false`.

## Controls implemented
| Area | Control |
|---|---|
| AuthN | `X-API-Key` on every endpoint except `GET /health`, enforced at router level (a test enumerates every route from the OpenAPI schema and requires `401` without a key). Keys stored as HMAC-SHA256 (keyed by `APP_SECRET_KEY`), never in plaintext; dev mode (`AUTH_REQUIRED=false`) maps to a single local user. `GET /auth/status` lets the UI verify a key |
| AuthZ / isolation | Server-side `user_id` filter on analyses, predictions, backtests, watchlists, extractions; foreign IDs return 404 (tested) |
| Input validation | Pydantic models with bounds on every request; timeframe/symbol/strategy whitelists; SQLAlchemy parameterised queries only |
| Uploads | ≤ 8 MB, magic-byte sniffing (PNG/JPEG/WebP), PIL verify, dimension and pixel-count limits (decompression-bomb guard), **re-encoded to PNG** (drops EXIF/payloads), random server-side filename, sanitized original name, per-user directory |
| Errors | Uniform envelope with request id; 500s never leak internals |
| Rate limiting | In-memory per-IP sliding window (`RATE_LIMIT_PER_MINUTE`, default 240/min) — per-process; idle clients are dropped every 5 min so the table cannot grow without bound. `/market/quotes` accepts at most 20 names and never calls a provider for (or caches) unknown names |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, `Cache-Control: no-store`; CORS: production allows only `FRONTEND_URL`, development also `localhost:3000` |
| Model promotion | `POST /models/{id}/activate` refuses (`409 not_promotable`) any model that is not calibrated and has not passed the out-of-sample checks. No model has passed, so none can be activated |
| Provider credentials | Read from the environment only; masked in `repr(settings)`; error messages report the exception class, never the request URL (Twelve Data's key travels as a query parameter) |
| Audit | `audit_events` for sync, analysis, prediction, backtest, chart upload |
| Containers | Backend runs as non-root; Postgres/API/UI bound to `127.0.0.1` in compose |

## Audit of 2026-11-10 (customer handover)

Fixed:
* **13 read endpoints answered without a key** when `AUTH_REQUIRED=true`, including `/market/quotes` (which calls the data providers, so anyone could spend the Twelve Data quota), `/patterns/*` (CPU-heavy) and `/models`. All non-health routes now require the key.
* `/market/quotes` cached every requested name, so arbitrary names could grow memory without bound.
* Production CORS also allowed `http://localhost:3000`.
* Research-only models could be activated through the API.
* Vulnerable backend dependencies (from `pip-audit`): starlette 0.41.3 (7 advisories), python-multipart 0.0.20 (6), pillow 11.1.0 (53; it decodes uploaded chart screenshots), lightgbm 4.5.0 (remote code execution when loading a crafted model file). Upgraded to fastapi 0.162.2 / starlette 1.10.0, python-multipart 0.0.33, pillow 13.0.0, lightgbm 4.6.0; the full test suite passes on a clean install and `pip-audit` of the new `requirements.txt` reports no known vulnerabilities.
* Checked and clean: no secrets in tracked files or in git history, no raw SQL built from strings, no logging of keys or headers.

## Known gaps and remaining risks (be aware)
* **Frontend dependencies (`npm audit`, 2 high, 1 moderate):** `zod` 3.x (memory exhaustion on oversized collection schemas: this app's schemas validate only the user's own form fields and contain no collections, so it is not reachable) and the PostCSS copy bundled inside Next.js 15 (build-time processing of attacker-controlled CSS: the app only builds its own CSS). Both fixes are major upgrades (zod 4 with new form resolvers; Next.js 16) and were not applied.
* No user registration, login form, roles or password reset: users and keys are created by script (`backend/scripts/create_user.py`) or `BOOTSTRAP_API_KEY`. One key per user.
* The API key is kept in the browser's `localStorage` (an XSS flaw would expose it); prefer a session-cookie flow before multi-user hosting.
* Rate limiter and quote cache are per-process memory. Behind a reverse proxy every client shares the proxy's address, so the limit applies to all users together; use a gateway limiter for public multi-user hosting.
* No TLS termination in the app: run behind HTTPS (Railway and Vercel provide it).
* `/docs` and `/openapi.json` stay public (they describe the API, not data); every data endpoint still needs a key.
* Dependency audit (`pip-audit`, `npm audit`) is not wired into CI: run both before each release.
* Only the 25 direct backend packages are pinned; their dependencies float, so two builds can differ (this broke the Celery worker
  once, see TECHNICAL_HANDOVER.md §13). A full lock file is recommended. The frontend is locked by `package-lock.json`.
