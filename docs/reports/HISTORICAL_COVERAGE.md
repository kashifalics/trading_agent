# Historical data coverage

Source: Dukascopy public datafeed (datafeed.dukascopy.com), 1-minute BID and ASK candles. Times in UTC. Generated 2026-11-09.

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

Total bars across timeframes: 10,851,563. Raw download size: 0.18 GB. Bid and ask: both.

| Instrument | First traded minute | Traded coverage | Feed coverage (incl. filler) | M1 published | Quiet minutes (no ticks, removed) | Duplicates | Invalid | Outlier moves (kept) | One side missing |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| XAUUSD | 2003-05-05T00:01 | 92.3% | 100.0% | 10,752,480 | 2,755,570 | 0 | 0 | 0 | 0 |

Traded coverage = minutes with at least one tick / minutes the market was scheduled open (FX: Friday 17:00 to Sunday 17:00 New York closed; XAUUSD also 17:00-18:00 New York daily). Material gap = 30+ consecutive scheduled-open minutes missing from the feed, excluding 24-26 Dec and 1-2 Jan.