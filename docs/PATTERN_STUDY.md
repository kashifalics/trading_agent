# Gold pattern study: method

Code: `backend/app/gold_research/`. Data: the sealed Dukascopy history (`docs/HISTORICAL_DATA.md`). Results:
`docs/reports/PATTERN_STUDY_XAUUSD.md`. This is analysis only: nothing here places orders.

## Questions it answers

For every price-action pattern, timeframe and direction:
1. When the pattern appeared, what happened next?
2. Does a trade taken on it beat the same kind of trade taken at random?
3. Does that hold in later data that played no part in finding it?

## Segments

The history is split once, chronologically, by clean-M1 observation count: **70% training, 15% validation, 15% final test.**
- The boundaries move forward to the next Saturday 00:00 UTC. They are frozen in `docs/research/XAUUSD_split.json`, which carries a SHA-256 hash, so an edit is detected.
- All research reads data through `app/historical/store.py`:
  - Training work sees only candles that closed before the end of training.
  - Validation sees candles up to the end of validation.
  - The final-test period is refused unless `final_test=True` is passed, and every such read is appended to `docs/research/XAUUSD_seal_log.md`.
- Trades simply run out of candles at a boundary, so no outcome ever reaches into a later segment.

## A trade

| Step | Rule |
|---|---|
| Signal | the candle whose close confirms the pattern (every detector is causal; tested on a data prefix versus the full data) |
| Entry | **market:** next candle's open. **Zones** (FVG, order block, breaker, supply/demand): a limit order at the zone's near edge, live for 50 candles, cancelled if a candle closes through the far edge first |
| Prices | longs buy at the ask and exit at the bid; shorts sell at the bid and exit at the ask, so the real spread of the day is paid |
| Stop | the pattern's invalidation level plus 0.1 ATR, at least 0.25 ATR away (equal highs/lows have no level: 1 ATR) |
| Outcome | targets 0.5 to 5R; holding periods of 12, 24, 48 and 96 candles. Target first gives +kR; stop first gives -1R, or worse if price gapped through; neither gives the R at the last close |
| Inside a candle | the stop candle and the limit-fill candle are replayed minute by minute. Inside one minute the stop counts first, and the share of results that would change otherwise is reported. In the fill minute only adverse prices count |
| Data gaps | trades whose window crosses a material gap (30+ missing open minutes) are excluded |

The simulator is tested against a slow minute-by-minute reference implementation; results must match exactly.

## Controls: what does "edge" mean

A shared pool of random trades per timeframe and segment is simulated with the same engine:
- **Market controls:** fixed stop sizes.
- **Limit controls:** fake zones at fixed distances and widths, with the same waiting and cancel rules.

Each pattern trade is compared with the controls of its stratum:
- entry type;
- stop size, or zone distance and width;
- New York session of the fill;
- volatility (ATR against its own trailing median);
- year and segment.

Sparse strata back off to coarser ones, and the level used is recorded.

**Edge = trade R minus its control mean.** This takes out gold's 20-year uptrend, its daily rhythm and the mechanical effect of the entry type. On synthetic Brownian data the whole pipeline gives edges of about zero (tested).

## Statistics

- **Main test, fixed before any result was seen:** natural entry, structural stop, 2R target, 48-candle hold, real spread.
- **Standard errors** are clustered on blocks of max(one week, holding period), and include the sampling error of the control means. Each test reports its smallest detectable edge (80% power).
- **Training:**
  - Benjamini-Hochberg across every test with at least 100 trades; q < 0.10 with a positive edge makes a **candidate**.
  - The candidate list is frozen in `docs/research/XAUUSD_candidates.json`, with a hash, before validation is read.
- **Validation:** only frozen candidates are tested. A candidate is **confirmed** only if it passes all four:
  1. Holm correction (alpha 0.05) with a positive edge;
  2. market entries keep the edge when entered one candle later;
  3. average R after spread is positive with p < 0.05;
  4. at least 100 trades.
- **Description only:** other targets, holding periods, sessions and structure context. They never select anything.
- **Cost scenarios:** your broker's $0.30 round-trip spread, and $0.10 slippage per side. Overnight swap comes with the swing study.

## Commands

```
cd backend
.venv\Scripts\python -m app.gold_research run --segment train      # trades + control pools, M5 to D1 (resumable)
.venv\Scripts\python -m app.gold_research discover                 # training statistics, frozen candidate list, report
.venv\Scripts\python -m app.gold_research run --segment validation # only after discover
.venv\Scripts\python -m app.gold_research validate                 # frozen candidates only, report
```

`Run Gold Research.bat`, in the `trading project` folder, runs the data foundation and the training study unattended.

## Limits of this phase

- Patterns are the platform's existing detectors. The full library, regimes, combinations and multi-timeframe profiles come next and join the same validation family.
- A single data source (Dukascopy). No news calendar.
