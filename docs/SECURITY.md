# Security

## Posture
* **Analysis only.** There is no broker/exchange integration that can place orders; Binance is accessed only through public market-data endpoints, no API key.
* Secrets live in environment variables (`.env`, gitignored; `scripts/setup.*` generates `APP_SECRET_KEY` and the Postgres password). `.env.example` contains placeholders only. Provider keys are backend-only; the only `NEXT_PUBLIC_*` variable is the public API URL.
* `APP_ENV=production` refuses to start with the default secret or with `AUTH_REQUIRED=false`.

## Controls implemented
| Area | Control |
|---|---|
| AuthN | `X-API-Key`; keys stored as HMAC-SHA256 (keyed by `APP_SECRET_KEY`), never in plaintext; dev mode maps to a single local user |
| AuthZ / isolation | Server-side `user_id` filter on analyses, predictions, backtests, watchlists, extractions; foreign IDs return 404 (tested) |
| Input validation | Pydantic models with bounds on every request; timeframe/symbol/strategy whitelists; SQLAlchemy parameterised queries only |
| Uploads | ≤ 8 MB, magic-byte sniffing (PNG/JPEG/WebP), PIL verify, dimension and pixel-count limits (decompression-bomb guard), **re-encoded to PNG** (drops EXIF/payloads), random server-side filename, sanitized original name, per-user directory |
| Errors | Uniform envelope with request id; 500s never leak internals |
| Rate limiting | In-memory per-IP sliding window (`RATE_LIMIT_PER_MINUTE`) — per-process; use a Redis/gateway limiter if you scale out |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, `Cache-Control: no-store`; CORS restricted to `FRONTEND_URL`/localhost:3000 |
| Audit | `audit_events` for sync, analysis, prediction, backtest, chart upload |
| Containers | Backend runs as non-root; Postgres/API/UI bound to `127.0.0.1` in compose |

## Known gaps (be aware)
* No user registration/login UI or key-issuing endpoint yet: create users/keys by script (`app/core/security.py` helpers) — see ROADMAP.
* Rate limiter and quote cache are per-process memory.
* No TLS termination (put behind a reverse proxy for anything beyond localhost).
* API key is kept in the browser's `localStorage` (XSS would expose it); prefer a session-cookie flow before multi-user hosting.
* Dependency audit (`pip-audit`, `npm audit`) is not wired into CI.
