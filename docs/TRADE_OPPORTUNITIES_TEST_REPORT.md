# Trade Opportunities — test and verification report

_Run locally on Windows 10, Python 3.12, Node 24, 2026-11-02. Nothing was deployed or pushed._

## Automated suites
| Suite | Result |
|---|---|
| Backend `pytest` (whole project) | **179 passed** (135 existing + 44 new: 26 in `test_opportunities_logic.py`, 18 in `test_opportunities_scan_api.py`) |
| Backend `ruff check .` | clean |
| Frontend `vitest` | **40 passed** (28 existing + 12 new in `opportunities.test.tsx`) |
| Frontend `tsc --noEmit`, `eslint --max-warnings 0`, `next build` | clean; 13 pages build including `/opportunities` |
| Alembic `0003` | upgrade → downgrade → upgrade verified on SQLite, including the XAUUSD mapping data change and its reversal; also applied automatically to a copy of the research database at API start-up |
| Playwright e2e (existing 6) | **not re-run** this round (the UI was re-themed; selectors are text/role based but this is unverified) |
| PostgreSQL | **not run** for `0003` (plain additive DDL, no dialect-specific code beyond the existing JSON/JSONB type) |

## What the new tests prove
**Detectors** — support/resistance needs repeated touches and is causal (levels at bar *k* are identical with or without later bars); trendlines need 3 touches and are rejected once a close breaks them;
breakout / retest / failed-breakout work, and a drop below a *resistance* is correctly **not** a breakout (this test found and fixed a real direction bug); a level whose second touch was not yet confirmed is ignored.
**Setup rules** — entries are structural zones, never "price ± x"; stop beyond the zone; TP1 < TP2 < TP3 from swing structure; `waiting_for_confirmation` vs `entry_triggered` depends on a confirmation **at or after** the zone touch (an earlier candle does not count);
WAIT when HTF opposes, no zone, costs too high, stop too far, strong opposing structure before the minimum R, or the target was already hit; deterministic output.
**Scoring** — weights sum to 1; label and `calibrated: false` always present; untested / no-edge / negative caps are enforced and a negative strategy can never reach the publish threshold; penalties apply for conflict, staleness, gaps and weak samples.
**Ranking** — validated outranks unvalidated whatever the score; WAIT is unranked; same-instrument same-direction setups are flagged as one exposure.
**Analogues** — outcome windows finish before "now" (no look-ahead); BUY and SELL statistics mirror exactly; insufficient history returns "unavailable", never invented evidence.
**Validation** — `classify` cannot validate small samples, unstable folds or results no better than random entries; missing validation is `untested`; the OOS split uses only later trades; resampling never leaks a still-forming bucket.
**Scan orchestration (database)** — 14 timeframes reported with correct statuses (completed / derived / insufficient); unavailable instruments (US30, USOIL, XAUUSD without key or candles) create no rows and no candles; the forming candle is excluded;
a failing timeframe is reported without failing the scan; unchanged data is not re-analysed (reuse pointers, zero duplicates) while new data triggers recomputation; overlapping scans are deduplicated;
open opportunities are invalidated / closed on target / expired with history rows; the same setup is updated in place, its levels never drift and a trigger is never undone.
**API** — scan flow, summary, filters, pagination bounds (`limit=0` → 422), invalid enum values → 422, unknown ids → 404, scan history, per-timeframe analysis, validation and config endpoints; `401` for missing or wrong API key when auth is on; empty state before any scan.
**Frontend** — loading skeleton, backend outage with retry, empty (no scan), WAIT-only, BUY and SELL rows with every level, watchlist rows shown as "WAIT, lean BUY" (never as BUY), unsupported/unavailable instruments with no prices, scan start and deduplication notice, scan failure message,
full evidence view (levels, chart overlays, score breakdown with cap and penalties, analogues with the "not a probability" caveat, risks, invalidation), row selection, validation panel showing the user's existing negative backtests unchanged, sidebar order (Overview → Trade Opportunities).

## Verification against real stored data (not mocks)
* **Scan on a copy of the research database** (BTCUSDT: 1m–1W from Binance; XAUUSD: 1m–1W from Twelve Data; 2,500 most recent bars per timeframe): 2 instruments scanned, US30 and USOIL reported unavailable ("OANDA_API_TOKEN is not configured"), 20 of 28 timeframes completed
  (1M–12M have no stored candles and are reported as insufficient), first scan ≈ 8 s, repeat scan on unchanged data ≈ 5 s with every style reused from cache.
  Result: 0 actionable setups, 2 gold watchlist items (evidence 47 and 45), 6 WAIT with reasons (stale candles for scalping, strong opposing zones, no structural alignment). That is what the evidence supports; nothing was forced.
* **Validation replay** on the same stored candles: 16 combinations, see `STRATEGY_VALIDATION.md`. Experiment 66 re-executed with identical results (68/68 numeric fields, same dataset hash, same code hash).
* **Browser check** (Playwright, real backend, real stored data): page, ranking table, instrument/timeframe panel, evidence view with chart, score table, and an existing page (Chart Analysis) rendered in the new theme.

## Instruments and timeframes actually exercised
| | 1m | 3m | 5m | 15m | 30m | 1H | 2H | 4H | 1D | 1W | 1M | 3M | 6M | 12M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT (Binance, stored) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | no data | no data | no data | no data |
| XAUUSD (Twelve Data, stored) | ✔ | ✔ (built from 1m) | ✔ | ✔ | ✔ | ✔ | ✔ (built from 1H) | ✔ (built from 1H) | ✔ | ✔ | no data | no data | no data | no data |
| US30, USOIL | unavailable: no `OANDA_API_TOKEN`, no candles |
Analyses used the most recent 2,500 bars per timeframe; the validation replays used the windows stated in `STRATEGY_VALIDATION.md`.

## Not verified / known gaps
* Live provider calls were not made this round (a normal scan is database-only by design); `refresh_data` and the scheduler are covered by unit logic and code review, **not** by a live end-to-end run against Twelve Data or Binance.
* The scheduler loop (`scheduler.py`) has no automated test; `run_scheduled_scan` shares `create_scan`/`execute_scan` with the tested path.
* Production (Railway/Vercel) was not touched. Production still needs candles synced and a user API key created by the user before this page shows anything.
* Cross-instrument correlation is not measured.
* Frontend `next/font` fetches Poppins at build time (needs network); the CSS falls back to the system font if unavailable.
