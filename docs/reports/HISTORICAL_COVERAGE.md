# Historical data coverage

Sources: XAUUSD: Dukascopy public datafeed (datafeed.dukascopy.com), 1-minute BID and ASK candles; BTCUSDT: Binance public data archive (data.binance.vision), spot 1-minute klines (one price; bid/ask = price -/+ the $1 half-spread cost model). Times in UTC. Generated 2026-11-14.

| Instrument | Timeframe | Earliest | Latest | Bars | Missing (M1: material gaps / minutes) |
|---|---|---|---|---:|---|
| XAUUSD | M1 | 2003-05-05 | 2026-11-06T21:59 | 7,996,910 | 813 / 188,575 |
| XAUUSD | M5 | 2003-05-05 | 2026-11-06T21:55 | 1,676,902 | rebuilt from M1 |
| XAUUSD | M15 | 2003-05-05 | 2026-11-06T21:45 | 566,290 | rebuilt from M1 |
| XAUUSD | M30 | 2003-05-05 | 2026-11-06T21:30 | 284,435 | rebuilt from M1 |
| XAUUSD | H1 | 2003-05-05 | 2026-11-06T21:00 | 142,588 | rebuilt from M1 |
| XAUUSD | H2 | 2003-05-05 | 2026-11-06T20:00 | 73,230 | rebuilt from M1 |
| XAUUSD | H4 | 2003-05-05 | 2026-11-06T20:00 | 37,752 | rebuilt from M1 |
| XAUUSD | H6 | 2003-05-05 | 2026-11-06T18:00 | 25,598 | rebuilt from M1 |
| XAUUSD | H8 | 2003-05-05 | 2026-11-06T16:00 | 19,511 | rebuilt from M1 |
| XAUUSD | H12 | 2003-05-05 | 2026-11-06T12:00 | 13,417 | rebuilt from M1 |
| XAUUSD | D1 | 2003-05-05 | 2026-11-06T00:00 | 7,322 | rebuilt from M1 |
| XAUUSD | W1 | 2003-05-05 | 2026-11-02T00:00 | 1,227 | rebuilt from M1 |
| XAUUSD | MN1 | 2003-05-01 | 2026-11-01T00:00 | 283 | rebuilt from M1 |
| XAUUSD | D1_NY | 2003-05-04 | 2026-11-05T22:00 | 6,098 | rebuilt from M1 |
| BTCUSDT | M1 | 2017-08-17 | 2026-10-31T23:59 | 4,833,919 | 32 / 30,160 |
| BTCUSDT | M5 | 2017-08-17 | 2026-10-31T23:55 | 966,793 | rebuilt from M1 |
| BTCUSDT | M15 | 2017-08-17 | 2026-10-31T23:45 | 322,270 | rebuilt from M1 |
| BTCUSDT | M30 | 2017-08-17 | 2026-10-31T23:30 | 161,142 | rebuilt from M1 |
| BTCUSDT | H1 | 2017-08-17 | 2026-10-31T23:00 | 80,581 | rebuilt from M1 |
| BTCUSDT | H2 | 2017-08-17 | 2026-10-31T22:00 | 40,302 | rebuilt from M1 |
| BTCUSDT | H4 | 2017-08-17 | 2026-10-31T20:00 | 20,160 | rebuilt from M1 |
| BTCUSDT | H6 | 2017-08-17 | 2026-10-31T18:00 | 13,446 | rebuilt from M1 |
| BTCUSDT | H8 | 2017-08-17 | 2026-10-31T16:00 | 10,086 | rebuilt from M1 |
| BTCUSDT | H12 | 2017-08-17 | 2026-10-31T12:00 | 6,725 | rebuilt from M1 |
| BTCUSDT | D1 | 2017-08-17 | 2026-10-31T00:00 | 3,363 | rebuilt from M1 |
| BTCUSDT | W1 | 2017-08-14 | 2026-10-26T00:00 | 481 | rebuilt from M1 |
| BTCUSDT | MN1 | 2017-08-01 | 2026-10-01T00:00 | 111 | rebuilt from M1 |
| BTCUSDT | D1_NY | 2017-08-16 | 2026-10-31T21:00 | 3,364 | rebuilt from M1 |

Total bars across timeframes: 17,314,306. Raw download size: 0.18 GB. Bid and ask: both.

| Instrument | First traded minute | Traded coverage | Feed coverage (incl. filler) | M1 published | Quiet minutes (no ticks, removed) | Duplicates | Invalid | Outlier moves (kept) | One side missing |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| XAUUSD | 2003-05-05T00:01 | 92.3% | 100.0% | 10,752,480 | 2,755,570 | 0 | 0 | 0 | 0 |
| BTCUSDT | 2017-08-17T04:00 | 99.38% | 99.38% | 4,833,919 | 0 | 0 | 0 | 0 | 0 |

Traded coverage = minutes with at least one tick / minutes the market was scheduled open (FX: Friday 17:00 to Sunday 17:00 New York closed; XAUUSD also 17:00-18:00 New York daily). Material gap = 30+ consecutive scheduled-open minutes missing from the feed, excluding 24-26 Dec and 1-2 Jan.