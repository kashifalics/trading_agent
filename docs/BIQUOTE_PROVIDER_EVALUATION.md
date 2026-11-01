# BiQuote provider evaluation

_Evaluated live on **Sunday 2026-11-01, 16:20–16:40 UTC** against `https://biquote.io` (docs, terms, REST, SignalR). No mock data was used for any measurement; unit tests replay real captured responses. Nothing was deployed._

## Verdict
| Instrument | BiQuote symbol | Candles (1m … 1D) | Live ticks | Status in this platform |
|---|---|---|---|---|
| XAUUSD | `XAUUSD` (MetaTrader 5 broker CFD, OTC) | ✅ verified, shallow history | ⚠️ market closed during the test: seed + `closed` state verified, **live updates not verified** | **default** (`active`); Twelve Data stays registered |
| US30 | `US30` (MT5 CFD "US Wall Street 30 Index") | ✅ verified, shallow history | ⚠️ same as XAUUSD | **default** (`active`); OANDA stays registered |
| USOIL | `USOIL` (MT5 CFD "Crude Oil") | ✅ verified, shallow history | ⚠️ same as XAUUSD | **default** (`active`); OANDA stays registered |
| BTCUSDT | `BTCUSDT` (feed `aggr`) — also `BTCUSD` (MT5 CFD) | ✅ verified (BTCUSDT: only 41 daily bars) | ✅ verified: ~1 tick/s, 0.2–1.8 s latency | **default** (`active`); its closes match Binance (not an independent source); Binance stays registered and keeps years of history |
| Weekly / monthly (1W, 1M, 3M, 6M, 12M) | — | ❌ not provided (`1W` → HTTP 400; `1M` is silently **1 minute**) | — | 1W only by aggregation from 1D (~79 bars); 1M+ unsupported |
**Update (same day): BiQuote is now the default provider for all four instruments** (`PREFERRED_PROVIDER=biquote`, see §8). The verdict below describes what that means in practice.

**Overall:** a usable, keyless source of *recent* broker-CFD candles and a working live stream, but with **very shallow history** and an unverified live behaviour for three of the four instruments. It is not suitable for research, validation or deep-history analysis, and as the default it makes the product shallower than it was with Binance/Twelve Data (see §8 for the consequences and how to revert).

## 1. Documentation read (and where reality differs)
Pages read: `/docs/` (Base URL & Auth, Rate Limits, Error Handling, Ticks, Symbols, Market, OHLC, SignalR, Data Models), `/terms.html`, `/llms.txt`, the OpenAPI document exists at `/swagger/v1/swagger.json`.
* Base URL `https://biquote.io`, REST under `/api`, no key/signup, CORS open. `GET /health` returns service status.
* Documented limit: 15,000 requests/min per IP (fixed minute window); `429` with `Retry-After`. WebSocket (SignalR) traffic is unmetered.
* Documented OHLC: intervals `1m 5m 15m 30m 1h 4h 1d`, `limit` 1–1000, "up to 2000 bars per series", `from`/`to`, newest-first, in-progress bar prepended with `isOpen: true`.
| Documented | Observed |
|---|---|
| "up to 2000 bars per series" | **Fixed retention windows far smaller** (table in §3); `from`/`to` cannot reach older data |
| Errors: 404 for unknown symbol | Ticks: 404 for unknown symbols; **OHLC: HTTP 200 with an empty bar list** |
| `X-RateLimit-*` headers on 429 | Not present on 200 responses, so remaining quota cannot be read; 429 itself was **not provoked** (it would mean exceeding 15,000/min against a free service) |
| intervals list | `3m`, `2h`, `1w` → HTTP 400 `{"validIntervals": [...]}`; **`1M` returns HTTP 200 with the 1-minute bars** (case-insensitive match), identical to `1m`; `1H`/`1D` are accepted as aliases |
| `limit` | `limit=N` returns N closed bars **+ the open bar** (N+1); `limit=0`/`1` returns 2; values above the available retention return what exists |
| SignalR tick | Tick payload has **no** `marketState`/`stale`/`quoteAgeSeconds`; open/closed arrives only in a separate `ReceiveSubscriptionState` frame (the adapter derives staleness from the tick age) |

## 2. Symbols (provider's actual catalogue)
`GET /api/symbols` → 2,079 catalogued symbols; `quotedWithinDays=7` → 718 (Forex 218, Stock 297, Crypto 115, Commodity 74, Index 14). `hasData` is false for MT5 symbols whenever the market is closed, so it is not a catalogue-validity flag.
| Wanted | Exact name(s) found | Type / exchange / source | Notes |
|---|---|---|---|
| XAUUSD | **`XAUUSD`** | Commodity / OTC / MT5 Broker 1, digits 2, contract 100 | Also `XAUUSDT` (Commodity, `aggr`, gold perpetual), `XAUUSD_HRM` and `XAUUSD_HKN` (Turkish dealer rates, `kapalicarsi`), `XAUTUSDT` (tokenised gold). **Different instruments; not used.** |
| US30 | **`US30`** (and an identical duplicate **`US30_X10`**) | Index / INDEX / MT5 Broker 1, digits 2 | Broker CFD price (~51,8xx), **not** the exchange index. Naming is `US30`, not `US30_USD`/`DJI`/`WS30`. |
| BTCUSDT | **`BTCUSDT`** (`aggr`, Crypto, USDT) and **`BTCUSD`** (MT5 CFD, USD) | | `aggr` = aggregated venue feed; see §5 |
| USOIL | **`USOIL`** ("Crude Oil") | Commodity / OTC / MT5 Broker 1 | Also `UKOIL` (Brent), `CLUSDT` ("WTI Crude Oil", `aggr` perpetual). Name does not say WTI; its price tracks the WTI perpetual within ~0.8%, so it is a WTI-style CFD, **not NYMEX CL futures**. |

## 3. Candles (live retrieval, paged with `to`, 2026-11-01)
Timeframes requested: 1m 3m 5m 15m 30m 1H 2H 4H 1D 1W 1M.
| Interval | Natively served? | Bars returned (closed + open) | Earliest → latest (XAUUSD) | History depth |
|---|---|---|---|---|
| 1m | ✅ | 301 | 2026-10-30 15:57 → 20:57Z | **~5 hours** |
| 3m | ❌ HTTP 400 | — | built from 1m by the ingestion planner: **100 bars** | ~5 hours |
| 5m | ✅ | 289 | 2026-10-29 19:55 → 10-30 20:55Z | ~1 day |
| 15m | ✅ | 193 | 10-28 18:45 → 10-30 20:45Z | ~2 days |
| 30m | ✅ | 193 | 10-26 16:30 → 10-30 20:30Z | ~4 days |
| 1H | ✅ | 169 | 10-21 13:00 → 10-30 20:00Z | ~7–9 days (BTC: 7.0) |
| 2H | ❌ HTTP 400 | — | built from 1H: **81 bars** | ~7–9 days |
| 4H | ✅ | 181 | 09-21 16:00 → 10-30 20:00Z | ~30–39 days |
| 1D | ✅ | 500 (aggregated feeds: 35–41) | 2025-03-23 → 2026-10-30 | ~1.4–1.6 years |
| 1W | ❌ HTTP 400 | — | built from 1D: **79 bars** | ~1.5 years |
| 1M | ❌ — (`1M` = 1 minute) | — | **unsupported** | — |
US30 and USOIL are identical in shape (same windows; US30 1D 2025-03-24 →, USOIL 1D 2025-03-21 →). BTCUSD (MT5) is 1m 301 … 1d 500 (since 2025-06-20). Bars after closed-market filtering as ingested through the real pipeline: XAUUSD 1m 300, 5m 288, 15m 192, 30m 192, 1H 168, 2H 81, 4H 175, 1D 415, 1W 79.
**Consequence:** most intraday and weekly series are below the platform's 120-bar structure minimum or 200-bar analogue-library minimum (1H 168, 2H 81, 3m 100, 1W 79), scalping needs 300 bars (5m has 288), and nothing here can support out-of-sample validation. Only 1D (415) and 4H (175) are comfortably usable.

### Data-quality results (35 series: 5 symbols × 7 intervals, all raw bars analysed)
* **Timestamp format:** ISO 8601 with `Z` (UTC), bar **open** time, newest-first. No timezone offsets. Daily bars open at **00:00Z (UTC days)**; 4H on the epoch grid (00/04/08/…); all 35 series have **0 off-grid** timestamps.
* **Duplicates:** 0. **Invalid OHLC** (non-finite, ≤ 0, high < max(open, close), low > min(open, close)): **0** in all series.
* **Zero-range bars:** MT5 series 0; `BTCUSDT` (aggr) 55/301 one-minute bars and 3/289 five-minute bars (flat, illiquid minutes).
* **Current candle:** exactly one bar per series has `isOpen: true` — the newest. While a market is closed (Friday ~20:55Z → Sunday ~22:00Z) the **last hour before the close stays flagged open** (e.g. XAUUSD 1H `2026-10-30T20:00Z`); whether it flips to closed when the market reopens could not be observed today. The adapter never reports an `isOpen` bar as complete.
* **Missing intervals** (FX calendar applied): XAUUSD/US30/USOIL 1H 7 gaps of one candle each (the daily maintenance hour ~22:00–23:00Z, not modelled in our calendar); 5m: one 12-candle gap (= that hour); 15m 2 gaps (max 4); 30m 4 gaps (max 2); 1D 3–5 one-day gaps. BTCUSD: only a 3-candle 5m gap; BTCUSDT: none.
* **Out-of-session bars:** the FX CFDs publish Sunday daily "stub" bars stamped 00:00Z (84 of 500 daily bars fall inside our fx_weekly closure window) with very low tick counts. Our existing closed-market filter drops them before analysis and aggregation. Five 4H bars stamped Sunday 20:00Z are likewise dropped.
* **Volume:** `volume` is always 0 (CFD); `tickVolume` = tick count, stored with `volume_type="tick"`.

## 4. Live-data tests
* **`GET /health`** → 200 `healthy`; Redis connected; 225 SignalR connections; top subscriptions XAUUSD 154, EURUSD 102 … USOIL 54.
* **Latest prices** (`/api/{symbol}`, batched `/api/latest?symbols=…&symbols=…`): all four answer 200. XAUUSD/US30/USOIL: `marketState: "closed"`, `stale: true`, `quoteAgeSeconds` ≈ 156,000 (last quote Friday 2026-10-30 20:54–20:58Z) — correctly **not** presented as live. BTCUSDT/BTCUSD: `open`, age 0–1 s. (Comma-separated `symbols` does not work; the parameter must be repeated.)
* **WebSocket (SignalR over WebSocket, `/hubs/tick`)**: negotiate → handshake → `Subscribe` worked first time; 60 s run on 7 symbols:
| Symbol | Ticks in 60 s | Median gap | Latency (receipt − tick timestamp) |
|---|---|---|---|
| BTCUSD (MT5 CFD) | 61 | 1.0 s | median 0.80 s, max 1.82 s |
| BTCUSDT (aggr) | 60 | 1.0 s | median 0.19 s, max 0.85 s |
| XAUUSDT (aggr) | 56 | 1.06 s | median 0.18 s |
| CLUSDT (aggr) | 33 | 1.47 s | median 0.19 s |
| XAUUSD, US30, USOIL | **1 each (the seed)** | — | seed is 2 days old; `ReceiveSubscriptionState` says `closed`, `seeded: true` |
  Live prices are **real-time but throttled to roughly one update per second per symbol** (MT5 timestamps have 1-second resolution); latency includes unmeasured clock skew. **Not verified:** streaming of XAUUSD, US30 and USOIL while their markets are open (opens Sunday ~22:00 UTC). Re-run: `BIQUOTE_LIVE=1 pytest backend/tests/test_biquote_provider.py -k live_stream` once the market is open.
* No polling loops were used for live data; REST was only used for single snapshots.

## 5. Comparison with existing providers (never merged)
Matched on identical UTC open times; differences in basis points of the stored provider's close. BiQuote and our stored data are **separate series** and stay separate (`provider_id = biquote`).
**XAUUSD (MT5 CFD) vs Twelve Data XAU/USD:**
| TF | matched | bias | median \|diff\| | p95 | return correlation |
|---|---|---|---|---|---|
| 1m | 300 | −0.4 bp | 2.1 bp | 6.7 bp | **0.04** |
| 5m | 288 | −0.3 bp | 1.8 bp | 7.4 bp | 0.84 |
| 15m | 192 | −0.1 bp | 1.7 bp | 6.6 bp | 0.945 |
| 1H | 168 | −0.2 bp | 1.3 bp | 6.1 bp | 0.983 |
| 4H | 180 | +0.2 bp | 1.2 bp | 5.4 bp | 0.996 |
| 1D | 416 | +6.3 bp | 10.8 bp | 73 bp | 0.954 |
From 15m up the two agree to about 1–2 bp. At 1m–5m the return correlation collapses (0.04 / 0.84): our earlier audit already showed Twelve Data's 1m bars are artefact-prone (opens never equal the prior close), so this does **not** show BiQuote is wrong, but it does mean the two cannot be treated as the same series at that resolution; no third source was available to arbitrate. Daily differences are larger (median 11 bp, worst days 140–270 bp, all on high-volatility days; first and second halves of the history behave the same, so the docs' "Yahoo Finance bootstrap" does not show up as an older-data problem). Likely causes: different day-end cut-off (BiQuote UTC midnight vs Twelve Data), broker bid/ask midpoint vs reference spot, and volatility.
**BTC vs Binance spot BTCUSDT:**
| BiQuote series | TF | bias | median \|diff\| | return corr |
|---|---|---|---|---|
| `BTCUSDT` (aggr) | 1m … 1D | −0.03 … +0.04 bp | **0.00 bp** | 0.999 – 1.000 |
| `BTCUSD` (MT5 CFD) | 5m / 1H / 1D | −19.0 / −16.3 / −3.2 bp | 19.2 / 15.9 / 4.7 bp | 0.980 / 0.999 / 0.999 |
The aggregated `BTCUSDT` closes are **identical to Binance** in the median (0.00 bp), i.e. it is consistent with being derived from Binance trades: it adds no independent confirmation (and has only 41 daily bars). `BTCUSD` trades ~16–19 bp **below** Binance on short timeframes: USD vs USDT basis, the broker's own bid/ask (mid of a 4.5-wide spread), and a different venue.
**No independent source exists for US30** (no other provider configured). **USOIL / XAUUSD vs BiQuote's own aggregated perpetuals** (a different instrument class, for reference only): MT5 XAUUSD sits −21 bp below `XAUUSDT` and MT5 USOIL −83 bp below `CLUSDT` on 1H (return correlation 0.998): CFD spot vs perpetual-futures pricing.
**Why feeds differ:** bid/ask midpoint vs trade price; CFD vs spot vs perpetual/futures; the broker's session (maintenance hour, Sunday stubs) vs 24/7 venues; daily and 4H boundaries (UTC midnight/epoch grid vs provider-specific); provider timestamps in UTC but stamped by different clocks.

## 6. Integration (existing architecture, no replacement of Binance/Twelve Data)
Created:
* `backend/app/market_data/biquote/provider.py` — `BiQuoteProvider(MarketDataProvider)`: configurable base URL (`BIQUOTE_BASE_URL`), sync interface for the existing ingestion plus **async** `aget_candles`, `aget_latest_quotes` (batched, repeated `symbols`) and `stream_ticks` (SignalR over WebSocket with keep-alive and reconnect/backoff, tick staleness derived from age, state frames surfaced). Retry with backoff (network errors 1/2/4 s, 5xx honouring `Retry-After`, 429 waits `Retry-After` then fails clearly), client-side limiter (default 12,000/min, under the documented 15,000), UTC `Decimal` normalisation, `isOpen` → incomplete, duplicate removal, unparseable bars skipped (never repaired), `1M`/unsupported timeframes refused **before** any request, coverage with gap detection (`find_gaps`).
* `backend/app/market_data/biquote/__init__.py`, `backend/tests/test_biquote_provider.py` (22 offline + 30 live), `backend/tests/fixtures/biquote/*.json` (8 small real captured responses).
Modified (additive): `registry.py` (provider, `get_provider`, 4 mappings, all `active`), `core/config.py` (`biquote_base_url`), `ingestion/service.py` (preferred-provider routing, deterministic tie-break, fixed-retention sync), `api/v1/routes/market.py` (closed-market quote message), `core/config.py` (`preferred_provider`, default refresh providers), `opportunities/analysis.py` (BiQuote needs no key), `.env.example`, `tests/test_biquote_provider.py`.
WebSocket: the platform has no streaming layer (the UI polls quotes), so `stream_ticks` is provided and live-tested but **not wired** into the API/UI.

## 7. Licensing and security (https://biquote.io/terms.html, last updated 30 Sep 2026)
* **Allowed:** use in your own product, commercial or non-commercial; display current and historical prices to your users **including authenticated users**; cache/store quotes and OHLC for your product; derived signals, charts, analytics and backtests are yours. Attribution ("Market data by biquote") is appreciated, not required. → **Private internal analysis: permitted. Multi-user display: permitted.**
* **Forbidden:** reselling or redistributing the raw feed, "expos[ing] biquote quotes or OHLC data through your own public API", bulk downloads as a data product, sublicensing, competing market-data service; presenting the data as exchange-licensed, official index values or tradable prices.
* **Caveats:** prices are *indicative* third-party broker quotes (MT5 "Broker 1") and may be delayed, wrong or removed at any time; **no SLA**, no notice of changes, may throttle/block any IP at any time; "we can only give you the rights we have" and the upstream sources' terms may also apply; liability limit is zero; indemnity clause.
* **For this platform:** the analysis-only product with authenticated users is within the stated permissions. Our API (`/market/candles`, `/market/quotes`) does return stored BiQuote candles to authenticated clients; that is "display to your users" but sits near the "own API" restriction, so keep it behind API-key authentication (already the case in production), offer **no bulk export** of BiQuote data, show the attribution and the "indicative price" label, and consider asking BiQuote for written confirmation before any wider launch. This is a reading of the published terms, not legal advice.
* **Security:** no credentials are used or stored; requests expose only the server's IP and user agent; the adapter never logs response bodies beyond 120 characters of error text; the base URL is configurable and validated only as a string, so point it only at a trusted host.

## 8. Provider routing: BiQuote is the default for everything (decision of 2026-11-01)
* **How:** the setting `PREFERRED_PROVIDER` (default `biquote`) is applied whenever a request names no provider: every instrument with a non-unsupported BiQuote mapping (BTCUSDT, XAUUSD, US30, USOIL) uses it. An explicit `provider=binance|twelve_data|oanda` always wins, GBPUSD (no BiQuote mapping) still uses Twelve Data, and `PREFERRED_PROVIDER=` (empty) restores the previous status-based routing (Binance / Twelve Data / OANDA / BiQuote for US30 and USOIL).
* **Nothing was removed:** Binance, Twelve Data and OANDA adapters and mappings keep their own honest statuses. The research scripts and validation reports name their provider explicitly and are unaffected.
* **Sync:** a fixed-retention provider is now asked for everything it holds instead of a relative time window, because a relative window is empty over a closed weekend market. Verified live with the exact request the UI's *Sync* button sends (`bars=1500`): 1m 300, 5m 288, 1H 168, 2H 81, 4H 175–180, 1D 415 (BTCUSDT 40), 1W 78–80 (BTCUSDT 4); `1M` is reported unsupported.
* **Consequences you should expect (measured, not guesses):**
  * BTCUSDT loses its years of Binance history in the product: only ~7 days of 1H, ~30 days of 4H, 40 days of 1D (weekly: 4 bars). The earlier BTC studies and validation were run on stored Binance data and remain valid as research results but cannot be reproduced from BiQuote data.
  * The Trade Opportunities scan will mostly report `insufficient_data` or WAIT: styles need 200–300 bars on their setup timeframes (swing 200, intraday/scalping 300) and the analogue library needs ≥ 200 bars; only 1D (≈415) and, for scalping, 1m (300, but stale on weekends) qualify. 1H/2H/1W/3m fall under the 120-bar structure minimum or the style minimums. These thresholds were deliberately **not** lowered to fit the shallow data.
  * Pattern-study evidence and strategy validation shipped with the app were measured on Binance/Twelve Data history; they still describe those datasets, not BiQuote's.
  * US30 and USOIL now work with no key (previously unavailable). Gold quotes come from an MT5 broker CFD (indicative), not Twelve Data spot.
  * The quotes endpoint labels a closed-market price as "Last known price … not a live price".
* **Still unverified:** XAUUSD / US30 / USOIL live streaming during market hours (FX reopens Sunday ~22:00 UTC), and BiQuote reachability from Railway's network (BiQuote may throttle or block any IP and has no SLA).
* **To revert for one instrument or globally:** set `PREFERRED_PROVIDER=` (empty) in the environment, or pass `provider=` per request.

## 9. Test results
| Suite | Result |
|---|---|
| Offline unit tests (real captured responses; documented 429/503 modes simulated; one local SignalR hub replaying captured frames) | **22 passed** |
| Live tests against the real API (4 symbols × 7 native timeframes validity; real ingestion of XAUUSD/US30/USOIL incl. aggregated 3m/2H/1W and `1M` refused; live stream seed/state for 4 symbols) | **30 passed** (run twice; first run exposed two real issues that were fixed: weekend relative windows are legitimately empty, and SignalR ticks lack `stale`/`marketState`) |
| Whole backend suite | **204 passed, 30 live tests skipped by default**, ruff clean (four older tests were updated because US30/USOIL now resolve to BiQuote; one of them no longer hits the network) |
| Not tested | streaming of XAUUSD/US30/USOIL in market hours; behaviour of the Friday "open" bar after reopening; a real 429 or 503 (documented only); weekend/holiday behaviour beyond one Sunday |

## 10. Limitations summary
Shallow fixed history (5 h of 1m … 500 days of 1d); no 3m/2H/1W/1M natively; `1M` alias trap; unknown symbols return empty lists on OHLC; MT5 CFD prices differ from spot references by 0–20 bp (BTC CFD) and from perpetuals by 20–80 bp; aggregated `BTCUSDT` duplicates Binance; no volume; no SLA; terms forbid re-exposing the raw feed publicly; live behaviour in market hours still to be confirmed for gold, US30 and oil.
