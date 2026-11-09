# Historical market data (Phases 1–3 of the historical-intelligence upgrade)

Code: `backend/app/historical/` (Dukascopy client, resumable downloader, validation, timeframe reconstruction, coverage report).
Data: `data/historical/` at the repository root, git-ignored. Run on the laptop; the hosted backend does not hold this data.

## Source: Dukascopy public datafeed

| Item | Finding (checked live 2026-11-08) |
|---|---|
| Access | Free, no account: `datafeed.dukascopy.com/datafeed/{SYMBOL}/{YYYY}/{MM from 00}/{DD}/{BID\|ASK}_candles_min_1.bi5` |
| Resolution | 1-minute candles, bid and ask separately, one LZMA file per UTC day. Every minute of the day is published, including filler minutes with no trades |
| Depth | EURUSD files from 2004 (2003 returns 404). XAUUSD files from January 2003, but those months are filler: the first traded minute is 2003-05-05. Other pairs: see the coverage report |
| Limits | Rate-limited (HTTP 429/503 after a few quick requests). The downloader paces requests (1.5 s) and backs off from 60 s up to 15 min |
| Volume | Dukascopy's own per-minute volume; summed when candles are aggregated |

Real start dates come from the coverage report, not from file availability.

## Pipeline

1. **Download** (`python -m app.historical download --symbols XAUUSD`): `raw/dukascopy/{SYMBOL}/{BID|ASK}/{YYYY}/{date}.bi5`, byte-for-byte as served,
   written atomically. Days without a file are recorded as `{date}.none`, except the last 7 days, which may still be published. Saturdays are skipped.
   A rerun resumes at the first missing day and later fetches only new days.
2. **Normalize**: `normalized/{SYMBOL}/M1/{YYYY}.parquet`, bid and ask side by side, UTC. Rebuilt only when that year's raw files change.
3. **Validate** to `clean/{SYMBOL}/M1/{YYYY}.parquet`:
   * duplicate timestamps are removed;
   * minutes missing one side are removed;
   * filler minutes (volume 0 and open = high = low = close) are removed and counted as quiet, never forward-filled;
   * invalid candles are removed: non-finite or non-positive values, high below open or close, low above open or close, or ask below bid;
   * one-minute moves above 2% (3% for gold) are counted but kept, because real events such as the CHF floor removal on 2015-01-15 are not errors.
4. **Gaps**: a scheduled-open minute with no traded candle. The market is closed from Friday 17:00 to Sunday 17:00 New York time, with daylight saving
   handled; gold is also closed 17:00–18:00 New York every day. A run of 30 or more such minutes is a material gap, saved in
   `clean/{SYMBOL}/gaps.parquet` for research to exclude. Gaps on 24–26 Dec and 1–2 Jan are labelled holidays.
5. **Timeframes**: M5, M15, M30, H1, H2, H4, H6, H8, H12, D1, W1 and MN1 are rebuilt from clean M1 only: open = first, high = max,
   low = min, close = last, volume = sum. Boundaries are UTC: intraday candles are aligned to multiples of their length from 00:00, days start
   at 00:00, weeks on Monday 00:00, months on the 1st. `D1_NY` candles are trading days that start at 17:00 New York, with daylight saving
   handled. `n_minutes` gives the number of traded minutes in each candle; `spread` is ask close minus bid close. `verify` rebuilds every
   timeframe straight from M1 and requires an identical result. `crosscheck` compares H1 and D1 with Dukascopy's own hourly and daily
   candles for 24 sampled months.
6. **Report**: `reports/{SYMBOL}_coverage.json` and `docs/reports/HISTORICAL_COVERAGE.md`. The report gives earliest and latest dates and bar counts
   per timeframe, the first traded minute, and traded coverage (minutes with ticks divided by scheduled-open minutes). Feed coverage, which counts
   filler, is shown separately and is never used as evidence of data. It also lists duplicates, invalid candles, outlier moves, material gaps and
   the raw download size.

7. **Quality**: `docs/reports/XAUUSD_DATA_QUALITY.md` covers formats, sizes, time range, precision, bid/ask source, volume meaning,
   validation checks, closures versus missing data, spreads per year, the timeframe checks, and a SHA-256 manifest of every raw file.
8. **Split and seal**: `split` freezes the chronological 70/15/15 split once (`docs/research/XAUUSD_split.json`). `app/historical/store.py`
   is the only loader research uses. It refuses the final-test period unless explicitly asked by the one-time final test, and logs every
   such read. `m1store` writes the memory-mapped M1 arrays used for intrabar resolution. `app/historical/sync.py` gives, for any decision
   time, the last candle of every timeframe that had already closed.

## Running and updating

Double-click `Start Trading Platform.bat`'s sibling **`Download Historical Data.bat`** in the `trading project` folder. It goes through the instruments
one at a time (XAUUSD, EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD), building and reporting each as soon as its download finishes.
Closing the window pauses the download; running the file again resumes it, and later runs add only the new days.

Manual use: `cd backend` then `.venv\Scripts\python -m app.historical all --symbols EURUSD`.

To add an instrument, add a line to `INSTRUMENTS` in `app/historical/config.py`, with the point size (1e-5 for most FX, 1e-3 for JPY pairs and XAUUSD).

## Known limitations

* At a polite request rate, the first full download takes about 12 hours per instrument, roughly 4 days for all eight. The laptop must stay on and
  awake; interruptions only pause it.
* D1 uses UTC midnight, so a short Sunday-evening session forms its own D1 candle; D1_NY (17:00 New York days) avoids that.
* The independent check uses Dukascopy's own aggregated candles; Twelve Data and BiQuote candles are a different feed and are not used.
