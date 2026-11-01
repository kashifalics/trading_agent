# Market data providers — qualification report

Status as of this build. "Verified" = exercised against the live service in this repo's development; everything else is stated as unverified.

## Per-instrument qualification

| Instrument | Intended source | Status | Evidence / blocker |
|---|---|---|---|
| **BTCUSDT** | Binance spot public klines | ✅ **Verified, working** | Live sync of 1H/4H/1D (1,500–3,000 bars each, 0 gaps) and live book-ticker quotes; `3m` native, `12M` aggregated from `1M`. |
| **XAUUSD** | Twelve Data `XAU/USD` (spot) | ✅ **Verified live on the free plan** (1H, 4H, 1D) with data caveats | `reports/XAUUSD_COVERAGE.md`: 1D since 1979, 4H since 2020-01, 1H from at least 2020-07. **Native 4H is off our grid for ~April-September** and the feed contains weekend candles (below). |
| **GBPUSD** | Twelve Data `GBP/USD` (spot FX) | ✅ **Available on the free plan** (1H, 1D probed live 2026-11-01) | 2H/4H are built from 1H (see Twelve Data caveat 1). |
| **US30** | OANDA `US30_USD` (broker CFD) | 🟡 **Adapter built and unit-tested with mocked HTTP; not verified live** until you add a free practice-account token | **Twelve Data's free plan does not serve the Dow index**: searching `DJI`/`US30` returns only ETFs/warrants (e.g. `DJIA` = a covered-call ETF), which are different instruments and are never substituted. |
| **USOIL** | OANDA `WTICO_USD` (WTI CFD) | 🟡 Same adapter, same status (needs `OANDA_API_TOKEN`) | Not NYMEX `CL` futures (roll/contango); never substituted. |

Deliberately *not* used: PAXG/XAUT (tokenised gold ≠ spot gold), ETFs as index/oil proxies, Yahoo/Stooq/TradingView extraction (unofficial or licence-unclear).

## Provider facts

### Binance (`binance`)
* Auth: none for public market data; no account, no keys. Base URL configurable (`BINANCE_API_BASE_URL`, alt `https://data-api.binance.vision`).
* Timeframes native: 1m 3m 5m 15m 30m 1H 2H 4H 1D 1W 1M. `3M/6M/12M` aggregated from `1M`.
* Limits: 1,200 request-weight/min/IP; klines ≤ 1,000 rows/request (adapter paginates). HTTP 418/429 surfaces as `provider_error` with `Retry-After`.
* History: since listing. Volume = base-asset volume (`volume_type=base`).
* Licence: see `DATA_LICENSING.md`.

### Twelve Data (`twelve_data`) — free plan only
* Auth: API key (`TWELVE_DATA_API_KEY`), sign up yourself at <https://twelvedata.com/pricing>; the build never creates accounts.
* Native timeframes used: 1m 5m 15m 30m 1H 1D 1W 1M. **2H and 4H are built from 1H** on our UTC grid (their native grid shifts with US DST); `3m` and `3M/6M/12M` are aggregated.
* **Measured** (provider `/api_usage`): plan `basic`, **8 requests/minute and 800/day**; at most 5,000 points per request. The adapter paces at 7.6 s, waits 62 s once on a per-minute 429 (observed live), fails fast on daily exhaustion, maps 401/403 to a key error and plan errors to `unsupported`; provider messages are scrubbed of the key.
* **Paging semantics (verified live):** a request returns the *most recent* `outputsize` points of `[start_date, end_date]` whatever `order` says, so long ranges are fetched **backwards**. (An earlier forward-paging assumption would have silently dropped old data.)
* FX/metals carry no volume (`volume_type=none`). Daily bars are UTC-midnight aligned; the newest daily bar can carry a next-session (future) label and is stored as incomplete.
* Available here: `XAU/USD` "Gold Spot / US Dollar" (COMMODITY, Precious Metal). Other symbols are probed, never assumed.
* **Caveat 1 - 4H grid**: epoch-aligned (00/04/08... UTC) roughly October-March, shifted +1 h (01/05/09...) roughly April-September, every year. Ingestion and backfill reject off-grid candles. Recommended fix: aggregate 4H from 1H for this provider (our aggregation matched the provider's own 4H on 2,502 of 2,502 comparable buckets).
* **Caveat 2 - weekend candles**: ~12% of 1H rows are stamped Fri 22:00 through Sunday, inside the FX closure, with roughly 1/27 of the normal range; filter by calendar before analysis.
* **Caveat 3 - gaps**: a daily break at 21:00/22:00 UTC, holidays, and a genuine provider gap on 2025-04-15/16.

### OANDA v20 (`oanda`) - US30 and USOIL
* Free **fxTrade Practice (demo)** account; sign up yourself at <https://www.oanda.com/register/#/sign-up/demo>, then create a personal API token in the account portal (*Manage API Access*). The build never creates accounts.
* Set `OANDA_API_TOKEN` (Railway: `railway variable set -s backend OANDA_API_TOKEN=...`; local: root or `backend/.env`). `OANDA_BASE_URL` defaults to the practice host `https://api-fxpractice.oanda.com`.
* Read-only: only `/v3/instruments/{instrument}/candles` is called (never order or account endpoints). Candles up to 5,000 per request, forward paging, `complete` flag from the API, tick volume. Requests set `dailyAlignment=0, alignmentTimezone=UTC, weeklyAlignment=Monday` so H2/H4/D/W sit on the platform's UTC grid.
* Prices are **broker CFD quotes**, not exchange index prices; they are stored under provider `oanda` and never mixed with other providers' candles. Licence: demo-account/API terms (personal use, no redistribution) - see <https://www.oanda.com/legal/>.
* Verification after you add the token: `POST /market/coverage/probe {symbol: US30, timeframe: 1H}` then `POST /market/sync`. Until then the mapping stays `unverified` and quotes report `not_configured`.

## Symbol mapping

`provider_instruments` stores per (provider, instrument): provider symbol, exchange, market kind, status, notes. Canonical `XAUUSD` ↔ `XAU/USD`; `BTCUSDT` ↔ `BTCUSDT`. Candles are keyed by provider, so two providers' series for one instrument never mix.

## Timeframe conventions (implemented in `market_data/timeframes.py`)

* All stored timestamps are UTC candle **open** times.
* Intraday (< 1D) buckets align to the UTC epoch (4H → 00/04/08/12/16/20 UTC).
* 1D+ buckets align to the instrument's `SessionAnchor` (time zone + daily open) using `zoneinfo`, so DST is handled: e.g. an `America/New_York 17:00` anchor yields 22:00 UTC in winter, 21:00 UTC in summer, and a 23-hour day across spring-forward. Defaults are `UTC 00:00` (matches Binance and Twelve Data daily bars).
* `1W` starts Monday; `1M/3M/6M/12M` are calendar month/quarter/half/year.
* Aggregation uses only **complete** base candles; a bucket is complete only if its end ≤ the last complete base candle's end **and** every expected base candle (per market calendar) is present. Otherwise it is stored with `is_complete=false` and excluded from analysis. Missing OHLC is never filled.
* Calendars: `continuous` (crypto) and `fx_weekly` (closed Fri 17:00 → Sun 17:00 New York, DST-aware). Holidays and daily maintenance breaks are not modelled, so such days are reported as gaps (conservative).

## Before recommending a paid plan

Run, per target instrument/timeframe: `POST /market/coverage/probe`; review `GET /market/coverage` for depth and gaps; run a model training and see whether the history is long enough to ever reach `passed_minimum_checks` (≥ ~1,000 OOS rows, ≥ 100 OOS trades). Only then price a plan against the licence terms in `DATA_LICENSING.md`.
