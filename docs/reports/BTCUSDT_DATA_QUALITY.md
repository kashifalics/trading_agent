# BTCUSDT data quality report

_Generated 2026-10-31T23:11:32.906664+00:00 by `python -m app.research.run_milestone` from the stored database; provider: Binance spot public klines. Values below are recomputed from stored candles, not copied from API responses._

## Summary

| Metric | 1H | 4H |
|---|---|---|
| Ingestion status (latest run) | completed | completed |
| Dataset status | clean | clean |
| First available candle (UTC) | 2023-07-19T23:00:00+00:00 | 2023-07-20T00:00:00+00:00 |
| Last completed candle (UTC) | 2026-10-31T21:00:00+00:00 | 2026-10-31T16:00:00+00:00 |
| Span (days) | 1199.9 | 1199.7 |
| Stored rows | 28799 | 7199 |
| Complete candles | 28799 | 7199 |
| Incomplete candles stored | 0 | 0 |
| Expected candles (first→last) | 28799 | 7199 |
| **Missing candles** | 0 | 0 |
| **Coverage %** | 100.0 | 100.0 |
| Gap ranges | 0 | 0 |
| Largest gap (candles) | 0 | 0 |
| Duplicate timestamps in DB | 0 | 0 |
| Duplicates returned by provider (all runs) | 0 | 0 |
| Invalid OHLC (re-validated, stored) | 0 | 0 |
| Rejected at ingestion (all runs) | 0 | 0 |
| Misaligned timestamps (stored) | 0 | 0 |
| Non-monotonic timestamps | 0 | 0 |
| All timestamps UTC | True | True |
| Zero-volume candles | 0 | 0 |
| Flat (high = low) candles | 0 | 0 |

## 1H

* Independent check: (last − first) ÷ step + 1 = 28,799 vs 28,799 complete rows → **agree**.

Ingestion run history (idempotence: later runs find nothing to fetch):

| Run | Kind | Status | Requests | Fetched | Stored | Missing before → after | Started (UTC) |
|---|---|---|---|---|---|---|---|
| #1 | backfill | completed | 29 | 28799 | 28799 | 28799 → 0 | 2026-10-31T22:33:17 |
| #3 | backfill | completed | 0 | 0 | 0 | 0 → 0 | 2026-10-31T22:34:25 |

* Spacing histogram (seconds → count): `{'3600': 28798}`

### Gaps by date

No missing candles between the first and last completed candle.

### Large single-candle moves (> 15.0%; informational, kept as-is)

None.

## 4H

* Independent check: (last − first) ÷ step + 1 = 7,199 vs 7,199 complete rows → **agree**.

Ingestion run history (idempotence: later runs find nothing to fetch):

| Run | Kind | Status | Requests | Fetched | Stored | Missing before → after | Started (UTC) |
|---|---|---|---|---|---|---|---|
| #2 | backfill | completed | 8 | 7199 | 7199 | 7199 → 0 | 2026-10-31T22:34:00 |
| #4 | backfill | completed | 0 | 0 | 0 | 0 → 0 | 2026-10-31T22:34:26 |

* Spacing histogram (seconds → count): `{'14400': 7198}`

### Gaps by date

No missing candles between the first and last completed candle.

### Large single-candle moves (> 15.0%; informational, kept as-is)

None.

## Interpretation notes

* A candle is *expected* when its open time falls on the timeframe grid between the first and last completed candle (BTCUSDT trades 24/7, so every grid slot should exist). Anything absent is reported as missing, never filled.
* The still-forming candle is never stored as history. Open times before Binance's first BTCUSDT candle are not counted as gaps.
* Anomalous moves are listed, not removed: removing real volatility would bias every downstream test.
