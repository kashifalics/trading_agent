# XAUUSD data-quality report

_Generated 2026-11-09 16:47 UTC by `python -m app.historical quality`. Every number is measured from the files on disk._

## What the data is

| Item | Value |
|---|---|
| Source | Dukascopy public datafeed (datafeed.dukascopy.com), 1-minute BID and ASK candles |
| Price type | **Bid and ask**, separately, for every minute (not midpoint). Research uses bid candles for patterns, ask for long entries and short exits |
| Price precision | integer multiples of 0.001 (Dukascopy stores integer points); 0 values off that grid |
| Timestamps | candle OPEN time, UTC, whole minutes. Sessions are computed in New York time with daylight saving |
| Volume | Dukascopy's own per-minute traded volume on its feed (not exchange volume, not tick count). Summed when aggregating |
| Raw format | one LZMA-compressed binary file per UTC day and side (24-byte records); kept byte-for-byte, never modified |
| Raw files | 14,934 (0 empty-day markers), 183 MB. SHA-256 of the manifest: `391ccbf141e619e290c87ded167d37cb7bee15d502c5c28caea8686d3adfa824` |
| Processed | normalized M1 255 MB, clean data (all timeframes) 357 MB (Parquet, zstd) |
| First traded minute | 2003-05-05T00:01:00+00:00 (Dukascopy publishes flat filler before this; not counted as data) |
| Last minute | 2026-11-06T21:59:00+00:00 |
| Clean M1 candles | 7,996,910 |

## Validation of the clean M1

| Check | Result |
|---|---|
| Timestamps strictly increasing | yes |
| Whole-minute timestamps | yes |
| High >= open, close, low and low <= open, close (bid and ask) | 0 violations |
| Positive, finite prices | 0 violations |
| Ask >= bid | 0 violations |
| Duplicate timestamps in the feed (removed by the build) | 0 |
| Minutes with only one side (removed) | 0 |
| Invalid candles (removed) | 0 |
| Filler minutes: feed alive, no tick (removed, never filled) | 2,755,570 |
| One-minute moves above 3% (kept: real events) | 0 |
| Traded minutes with zero reported volume | 106 |

## Market closures versus missing data

Scheduled closures: Friday 17:00 to Sunday 17:00 New York, and for gold also 17:00-18:00 New York every day. Missing data = scheduled-open minutes without a traded candle. Nothing is fabricated to fill either.

| Measure | Value |
|---|---|
| Scheduled-open minutes since the first traded minute | 8,587,680 |
| Of which traded (have a candle) | 7,926,780 (92.3%) |
| Missing | 660,900 |
| Scheduled-closed minutes in the same span (weekends, daily metals break) | 3,777,479 |
| Missing runs: material (30+ min, not holiday) | 813 runs, 188,575 minutes |
| Missing runs: holiday (24-26 Dec, 1-2 Jan) | 5,344 runs, 59,897 minutes |
| Missing runs: short (<30 min) | 169,496 runs, 412,428 minutes |

Material gaps are saved in `clean/{SYMBOL}/gaps.parquet`; research excludes trades whose window crosses one.

| Time between consecutive traded minutes | Count |
|---|---|
| 1 min | 7,791,635 |
| 2-29 min | 199,980 |
| 30 min - 2 h | 3,941 |
| 2 h - 3 days | 1,309 |
| 3 days + | 21 |

## Timeframes

All timeframes are rebuilt from clean M1 (open first, high max, low min, close last, volume summed) on UTC boundaries; D1_NY candles start at 17:00 New York.

| TF | Earliest | Latest | Bars | Identical to direct M1 aggregation |
|---|---|---|---|---|
| M1 | 2003-05-05T00:01 | 2026-11-06T21:59 | 7,996,910 | - |
| M5 | 2003-05-05T00:00 | 2026-11-06T21:55 | 1,676,902 | yes |
| M15 | 2003-05-05T00:00 | 2026-11-06T21:45 | 566,290 | yes |
| M30 | 2003-05-05T00:00 | 2026-11-06T21:30 | 284,435 | yes |
| H1 | 2003-05-05T00:00 | 2026-11-06T21:00 | 142,588 | yes |
| H2 | 2003-05-05T00:00 | 2026-11-06T20:00 | 73,230 | yes |
| H4 | 2003-05-05T00:00 | 2026-11-06T20:00 | 37,752 | yes |
| H6 | 2003-05-05T00:00 | 2026-11-06T18:00 | 25,598 | yes |
| H8 | 2003-05-05T00:00 | 2026-11-06T16:00 | 19,511 | yes |
| H12 | 2003-05-05T00:00 | 2026-11-06T12:00 | 13,417 | yes |
| D1 | 2003-05-05T00:00 | 2026-11-06T00:00 | 7,322 | yes |
| W1 | 2003-05-05T00:00 | 2026-11-02T00:00 | 1,227 | yes |
| MN1 | 2003-05-01T00:00 | 2026-11-01T00:00 | 283 | yes |
| D1_NY | 2003-05-04T21:00 | 2026-11-05T22:00 | 6,098 | yes |

## Cross-check against Dukascopy's own hourly and daily candles

Independent candles built by Dukascopy from ticks, compared on the timestamps both have (tolerance 1.5 points). Opens can differ when the first minutes of a period had no trade (their open is then the previous close).

| Candles | Compared | Open match | High match | Low match | Close match |
|---|---|---|---|---|---|
| hourly | 12,186 | 99.09% | 98.06% | 97.83% | 99.16% |
| daily | 3,745 | 93.17% | 96.58% | 96.26% | 92.5% |

## Per year

| Year | Clean M1 | Bid range | Median spread | 95th pct spread | Max spread | Median spread (bp) |
|---|---|---|---|---|---|---|
| 2003 | 104,058 | 339.00 - 417.30 | 0.410 | 0.556 | 0.71 | 11.19 |
| 2004 | 211,464 | 370.63 - 456.48 | 0.410 | 0.556 | 0.71 | 10.35 |
| 2005 | 278,588 | 409.64 - 540.50 | 0.460 | 0.556 | 0.71 | 9.73 |
| 2006 | 333,198 | 514.95 - 730.05 | 0.460 | 0.556 | 0.71 | 7.40 |
| 2007 | 346,941 | 601.59 - 845.33 | 0.460 | 0.556 | 0.71 | 6.43 |
| 2008 | 363,465 | 682.00 - 1,031.83 | 0.478 | 0.556 | 0.71 | 5.44 |
| 2009 | 363,585 | 801.83 - 1,225.94 | 0.492 | 0.584 | 0.71 | 4.85 |
| 2010 | 365,764 | 1,044.70 - 1,430.94 | 0.506 | 0.706 | 1.00 | 4.17 |
| 2011 | 363,850 | 1,308.23 - 1,920.66 | 0.414 | 0.724 | 3.00 | 2.74 |
| 2012 | 362,994 | 1,526.92 - 1,795.85 | 0.364 | 0.526 | 2.98 | 2.18 |
| 2013 | 352,469 | 1,180.27 - 1,696.66 | 0.351 | 0.570 | 2.95 | 2.40 |
| 2014 | 351,953 | 1,131.55 - 1,389.12 | 0.284 | 0.382 | 2.80 | 2.23 |
| 2015 | 353,861 | 1,046.23 - 1,307.47 | 0.311 | 0.403 | 2.95 | 2.67 |
| 2016 | 354,379 | 1,061.73 - 1,375.08 | 0.304 | 0.402 | 2.95 | 2.44 |
| 2017 | 352,815 | 1,146.04 - 1,357.50 | 0.241 | 0.300 | 2.95 | 1.92 |
| 2018 | 353,923 | 1,160.17 - 1,366.00 | 0.239 | 0.314 | 2.98 | 1.87 |
| 2019 | 353,349 | 1,266.19 - 1,556.96 | 0.294 | 0.350 | 3.00 | 2.12 |
| 2020 | 355,495 | 1,451.15 - 2,074.80 | 0.397 | 1.167 | 14.53 | 2.17 |
| 2021 | 354,346 | 1,670.49 - 1,959.23 | 0.354 | 0.454 | 5.22 | 1.98 |
| 2022 | 354,633 | 1,614.71 - 2,070.36 | 0.368 | 0.486 | 4.24 | 2.04 |
| 2023 | 352,969 | 1,804.59 - 2,145.14 | 0.330 | 0.407 | 5.87 | 1.69 |
| 2024 | 355,892 | 1,984.09 - 2,790.01 | 0.380 | 0.487 | 5.98 | 1.59 |
| 2025 | 354,435 | 2,614.37 - 4,549.72 | 0.580 | 0.864 | 14.74 | 1.73 |
| 2026 | 302,484 | 3,869.06 - 5,596.81 | 0.670 | 1.020 | 12.61 | 1.48 |

## Limitations

* Dukascopy is one liquidity provider's feed, not a consolidated market; other brokers' prices and spreads differ slightly.
* Volume is Dukascopy's own, useful for relative comparisons only.
* Spreads widen sharply around the daily 17:00 New York rollover and on thin holidays; research reports results with a capped rollover spread as well as the raw spread.
* No news calendar is available, so news-driven moves are not labelled.
