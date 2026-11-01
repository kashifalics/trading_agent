# Strategy validation — Trade Opportunities

**Result in one sentence: no setup rule set is validated.** Of 16 instrument × style × timeframe combinations replayed on real stored candles,
all 16 are `no_edge` (not distinguishable from zero, or too few trades to conclude). None is `validated`; none is rated `negative` because the sample
sizes are too small for the status rules. Full tables: [`reports/OPPORTUNITY_VALIDATION.md`](reports/OPPORTUNITY_VALIDATION.md).

## What was validated, and what was not
The thing validated is the **rule set that produces setups** (`app/opportunities/setup.py`, the exact function the live scan calls) replayed bar by bar
with only past information (`app/opportunities/rules_strategy.py`). Not validated: the evidence score and the analogue search (they are filters on
confidence, not entry rules) and any discretionary reading of the explanation text.

## Protocol (fixed before the first run; nothing was tuned)
* **Data:** stored real candles only. BTCUSDT from Binance, XAUUSD from Twelve Data. Fine timeframes use the most recent window (5m: 6,000 bars, 15m/1H: 8,000;
  4H/1D/1W: everything stored) because the replay costs ~60 ms per bar. Each experiment stores a content hash of the exact candles.
* **Execution:** a trade is opened at the **next bar's open** after a *fresh* trigger, with the setup's structural stop and first target; time stop = 2× the
  style's expected holding. Same-bar stop/target ambiguity is resolved against the trade. One position at a time, 1% of equity risked.
* **Costs:** BTCUSDT 0.10% taker fee + 0.01% slippage per side + 0.002% spread (0.222% round trip); XAUUSD 0.005% slippage per side + 0.01% spread (0.020% round trip).
  Gross (zero-cost) results are reported alongside.
* **Splits (chronological):** first 60% = development (reported, not used for any decision); last 40% = out-of-sample (OOS). Because the rules have no fitted parameters
  there was nothing to train; walk-forward therefore means "replay forward through time, judge only the later 40%", plus four equal-time OOS sub-periods for stability.
* **Baselines (same execution model and costs):** random-direction entries (mean of 10 seeds), EMA20/50 cross, buy-and-hold, SMA200 trend.
* **Status rule** (`validation.classify`, applied by code, never by hand): `validated` = ≥ 100 OOS trades **and** bootstrap 95% CI of net expectancy > 0 **and** p < 0.05
  **and** ≥ ⅔ of OOS sub-periods positive **and** better than random entries; `negative` = ≥ 100 OOS trades and CI entirely < 0; otherwise `no_edge`.
* **Reproducibility:** each run is an `experiments` row (kind `backtest`, name `opportunity:<style>:<symbol>:<tf>`) with config, dataset hash and code hash.
  `python -m app.research.reproduce 66` re-ran experiment 66 and matched all 68 numeric fields, the dataset snapshot and the code hash.

## Results (details and per-combination reasons in the report)
| | Combinations | OOS trades per combination | Verdict |
|---|---|---|---|
| BTCUSDT | 8 | 0, 0, 0, 2, 4, 16, 16, 9 | all `no_edge` |
| XAUUSD | 8 | 9, 16, 11, 27, 52, 19, 20, 4 | all `no_edge` |
* **Why so few trades.** The rules are strict by design (structural zone + HTF bias + confirmation + R/R floor + cost cap). On BTCUSDT, scalping and 15m/1H intraday produce
  **zero** trades: the round-trip cost (0.222%) consumes more than the style's cap of the risk. That is the cost gate working, not a bug: **BTC spot fees make scalping non-viable on these rules.**
* **Largest sample:** XAUUSD swing 4H, 52 OOS trades, net E[R] +0.06 (95% CI −0.23 … +0.35), gross +0.07. Indistinguishable from zero and above the random-entry baseline (−0.004) by a margin well inside the noise.
* **Worst:** XAUUSD scalping 15m, 16 OOS trades, net E[R] −0.55 (CI −0.89 … −0.16) and gross −0.43: the CI is entirely below zero, but 16 trades is below the 100-trade rule, so it is reported `no_edge`
  rather than `negative`. Treat it as a warning, not a conclusion.
* Several positive-looking numbers (BTCUSDT swing 1D +0.21 R, long-term 1W +0.35 R) rest on 9–16 trades with confidence intervals spanning zero by a wide margin. They are **not evidence of an edge**.
* **Absence of evidence is not evidence of absence**: with < 100 OOS trades the test has almost no power. It means "unproven", and the product treats it that way.

## Consequences in the product
* Every setup's score is capped (`untested` 65, `no_edge` 58, `negative` 49) and shown with a validation badge; unvalidated setups are ranked below validated ones; there are none of the latter.
* A strategy can only become `validated` through the same code path with ≥ 100 OOS trades. Loosening the rules to manufacture trades would be tuning to the result and was deliberately not done.
* The user's existing backtests (BTCUSDT 30m −1.3% / PF 0.94, XAUUSD 1H −12.1% / PF 0.73, plus the BTC 1H decision-engine run at −91% in the milestone report) are **left untouched** and shown in the validation panel as stored.

## Why the earlier engine looked like "mostly WAIT"
Audit on stored candles (last 600 hourly bars, price-action evidence only): the earlier decision engine returned BUY/SELL on 31% of BTCUSDT bars and 22% of XAUUSD bars; its blocks were
"confluence below threshold" (68% / 74% of bars) and "contradictory evidence" (28% / 31%). So it was **not** mostly WAIT bar by bar. What users saw as WAIT/failed came from (1) an empty production
candle store ("No stored candles… Sync data first"), (2) the live pipeline's extra gates (higher-timeframe disagreement, analogues, data-quality < 0.6 when candles are stale) and (3) the fact that
the signals it does emit have no demonstrated edge (BTC 1H net E[R] −0.26 over 914 trades). The new module is stricter and states, per timeframe and style, exactly what is missing.

## Limitations of this validation
* Two instruments and finite stored history (BTCUSDT hourly ~3.2 years, XAUUSD daily ~14 years, fine timeframes only weeks to months). Regime coverage is limited.
* The replay approximates the live scan: market orders at the next open instead of limit entries; UTC-aligned daily/weekly resampling for bias; no calendar-month bias timeframes (1W entries have no HTF filter);
  a 500-bar analysis window instead of 2,500.
* Fine timeframes cover only recent windows (weeks to months), too short to span regimes.
* Costs are assumptions (documented above), not measured broker spreads.
* Long-term (1D/1W/1M+) setups cannot reach 100 trades on any realistic history; they can only ever be "unproven" under this rule, which is the honest outcome.
