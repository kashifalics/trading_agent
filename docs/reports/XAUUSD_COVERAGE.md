# XAUUSD / Twelve Data — live integration verification

_Generated 2026-10-31T23:11:24.767626+00:00 by `python scripts/xau_verify.py` against the real Twelve Data API (no mocks, no substitute provider). The API key is never printed or stored in this report._

## Mapping

```json
{
  "instrument": "XAUUSD",
  "provider": "twelve_data",
  "provider_symbol": "XAU/USD",
  "market_kind": "spot",
  "status_in_registry": "unverified",
  "calendar": "fx_weekly",
  "session_anchor": "UTC 00:00"
}
```

## Instrument discovery (`/symbol_search`)

```json
[
  {
    "symbol": "XAU/USD",
    "name": "Gold Spot / US Dollar",
    "instrument_type": "Precious Metal",
    "exchange": "COMMODITY",
    "currency_base": null,
    "currency_quote": null,
    "country": ""
  }
]
```

## Plan / quota (provider-reported, verbatim)

Before:
```json
{
  "timestamp": "2026-10-31 23:11:25",
  "current_usage": 2,
  "plan_limit": 8,
  "daily_usage": 188,
  "plan_daily_limit": 800,
  "plan_category": "basic"
}
```
After backfill:
```json
{
  "timestamp": "2026-10-31 23:15:28",
  "current_usage": 4,
  "plan_limit": 8,
  "daily_usage": 219,
  "plan_daily_limit": 800,
  "plan_category": "basic"
}
```
Last credit headers seen: `{
  "api-credits-used": "4",
  "api-credits-left": "4"
}`

## Coverage probe (what the current plan serves)

| Timeframe | Available | Earliest candle | Earliest is only a lower bound | Latest candle | Volume |
|---|---|---|---|---|---|
| 1H | True | 2020-07-31T03:00:00+00:00 | True | 2026-10-31T23:00:00+00:00 | False |
| 4H | True | 2020-01-24T00:00:00+00:00 | False | 2026-10-31T20:00:00+00:00 | False |
| 1D | True | 1979-12-26T00:00:00+00:00 | False | 2026-11-01T00:00:00+00:00 | False |

## Retrieval and validation

| Timeframe | Requested from | Requests | Stored | Rows | Distinct ts | Duplicates | Invalid OHLC | Misaligned | Non-UTC | First | Last | Close min–max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1H | 2023-07-19 | 24 | 22595 | 22595 | 22595 | 0 | 0 | 0 | 0 | 2023-07-20T00:00 | 2026-10-30T20:00 | 1815.14001–5561.96958 |
| 4H | 2023-07-19 | 6 | 2768 | 2768 | 2768 | 0 | 0 | 0 | 0 | 2023-10-01T20:00 | 2026-10-30T20:00 | 1815.58997–5548.48862 |
| 1D | 2016-11-02 | 3 | 2602 | 2602 | 2602 | 0 | 0 | 0 | 0 | 2016-11-04T00:00 | 2026-10-30T00:00 | 1128.43005–5400.25 |

## Ingestion (this run; backfill windows are span-based, so re-runs are cheap)

| Timeframe | Status | Requests | Fetched | Stored | Rejected misaligned (off our grid) | Rejected invalid | Provider duplicates | Missing before → after |
|---|---|---|---|---|---|---|---|---|
| 1H | partial | 24 | 22595 | 22595 | 0 | 0 | 0 | 20565 → 728 |
| 4H | partial | 6 | 5858 | 2768 | 3090 | 0 | 0 | 5142 → 2386 |
| 1D | partial | 3 | 2603 | 2602 | 0 | 0 | 0 | 2607 → 8 |

## Missing intervals (against the FX weekly calendar: closed Fri 17:00 → Sun 17:00 New York)

| Timeframe | Missing open slots | Gap ranges | Largest gap (slots) | Coverage vs calendar | Missing by UTC hour | Days with most missing |
|---|---|---|---|---|---|---|
| 1H | 728 | 467 | 65 | 96.879% | `{0: 9, 1: 8, 2: 9, 3: 8, 4: 7, 5: 7, 6: 7, 7: 8, 8: 7, 9: 7, 10: 8, 11: 8, 12: 8, 13: 8, 14: 8, 15: 8, 16: 10, 17: 10, 18: 10, 19: 15, 20: 39, 21: 312, 22: 197, 23: 10}` | `{'2025-04-15': 24, '2025-04-16': 24, '2023-12-25': 23, '2024-01-01': 23, '2024-12-25': 23, '2025-01-01': 23, '2024-03-29': 21, '2025-04-14': 13}` |
| 4H | 2386 | 25 | 780 | 53.706% | `{0: 395, 4: 395, 8: 395, 12: 395, 16: 395, 20: 411}` | `{'2024-03-29': 6, '2024-04-08': 6, '2024-04-09': 6, '2024-04-10': 6, '2024-04-11': 6, '2024-04-12': 6, '2024-04-15': 6, '2024-04-16': 6}` |
| 1D | 8 | 8 | 1 | 99.693% | `{0: 8}` | `{'2018-03-30': 1, '2018-12-25': 1, '2019-04-19': 1, '2023-04-07': 1, '2024-03-29': 1, '2024-12-25': 1, '2025-01-01': 1, '2025-04-18': 1}` |

Holidays and the spot-gold daily maintenance break are **not** in the calendar model, so they appear above as missing; a concentration in one UTC hour indicates a systematic daily break rather than data loss.

## Weekend / closed-time candles (feed vs. assumed FX weekly closure)

| Timeframe | Rows stamped inside closure | % of rows | Flat (H=L) | Median range in closure | Median range when open | By weekday |
|---|---|---|---|---|---|---|
| 1H | 2758 | 12.21% | 8 | 0.272 | 7.467 | `{'Fri': 222, 'Sat': 1512, 'Sun': 1024}` |
| 4H | 324 | 11.71% | 0 | 0.295 | 13.9 | `{'Sun': 176, 'Sat': 148}` |
| 1D | 4 | 0.15% | 0 | 5.968 | 21.94 | `{'Sat': 2, 'Sun': 2}` |

## Native 4H alignment by DST period (hours are UTC)

```json
{
  "2023-08 (US summer time)": {
    "candles": 132,
    "hours_utc": {
      "1": 22,
      "5": 22,
      "9": 22,
      "13": 22,
      "17": 22,
      "21": 22
    },
    "epoch_aligned_share": 0.0
  },
  "2023-12 (US winter time)": {
    "candles": 119,
    "hours_utc": {
      "0": 20,
      "4": 20,
      "8": 20,
      "12": 20,
      "16": 20,
      "20": 19
    },
    "epoch_aligned_share": 1.0
  },
  "2025-06 (US summer time)": {
    "candles": 148,
    "hours_utc": {
      "1": 24,
      "5": 24,
      "9": 24,
      "13": 29,
      "17": 22,
      "21": 25
    },
    "epoch_aligned_share": 0.0
  },
  "2026-01 (US winter time)": {
    "candles": 187,
    "hours_utc": {
      "0": 32,
      "4": 31,
      "8": 31,
      "12": 31,
      "16": 31,
      "20": 31
    },
    "epoch_aligned_share": 1.0
  }
}
```

## 1H to 4H internal consistency (one provider)

```json
{
  "complete_buckets_compared": 2502,
  "open_match": 2502,
  "high_match": 2502,
  "low_match": 2502,
  "close_match": 2501
}
```

## Rate-limit behaviour (10 unpaced requests)

```json
{
  "requests": 10,
  "events": [
    {
      "n": 1,
      "result": "ok",
      "price_present": true,
      "seconds": 0.6
    },
    {
      "n": 2,
      "result": "ok",
      "price_present": true,
      "seconds": 0.5
    },
    {
      "n": 3,
      "result": "ok",
      "price_present": true,
      "seconds": 0.5
    },
    {
      "n": 4,
      "result": "ok",
      "price_present": true,
      "seconds": 0.4
    },
    {
      "n": 5,
      "result": "ok",
      "price_present": true,
      "seconds": 62.9
    },
    {
      "n": 6,
      "result": "ok",
      "price_present": true,
      "seconds": 0.4
    },
    {
      "n": 7,
      "result": "ok",
      "price_present": true,
      "seconds": 0.4
    },
    {
      "n": 8,
      "result": "ok",
      "price_present": true,
      "seconds": 0.4
    },
    {
      "n": 9,
      "result": "ok",
      "price_present": true,
      "seconds": 0.4
    },
    {
      "n": 10,
      "result": "ok",
      "price_present": true,
      "seconds": 0.4
    }
  ],
  "adapter_waits_seconds": [
    62.0
  ],
  "credit_headers_after": {
    "api-credits-used": "6",
    "api-credits-left": "2"
  }
}
```
