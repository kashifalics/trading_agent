# Backtesting methodology

Engine: `backend/app/backtesting`. Strategies implement `signal(bars_up_to_i) -> Signal | None`; the engine only ever passes `bars[: i+1]`, and a test rewrites the future and demands identical earlier trades.

## Execution model (all mid prices, spread applied as ± half-spread)
| Aspect | Rule |
|---|---|
| Entry | Signal on the close of bar *i* → fill at the **open of bar i+1** (never the signal bar's close), buying the ask / selling the bid, plus slippage |
| Stop & target | Evaluated from the entry bar onward on bid/ask-adjusted ranges (long exits trigger on bid: target needs `high ≥ TP + ½spread`) |
| Same bar contains both | **Stop assumed first** (conservative; no finer data) |
| Gaps | Open beyond the stop fills **at the open** (worse); favourable gap fills the target at the target price |
| Slippage | Paid on stop/market/time exits; limit targets pay none |
| Commission | `% of notional per side` |
| Sizing | Risk `risk_pct` of current equity ÷ stop distance (× contract size), capped by `max_leverage` (20×) |
| Invalid signals | Stop on the wrong side of the actual fill (e.g. after a gap) → skipped and counted |
| Exits | Stop, target, `max_bars_in_trade` (time), or `end_of_data` (closed at the last close) |
| Session filter | Optional `allowed_hours_utc` on the signal bar |
| One position at a time | Yes |

## Metrics
Return, win rate, profit factor, expectancy (cash and R, with 95% CI), average win/loss, max drawdown %, annualised Sharpe from per-bar equity changes (approximate for markets with closures), costs paid, exposure, longest losing streak, exit-reason breakdown. Results, config and all trades are persisted (`backtest_runs`, `backtest_trades`); the equity curve is downsampled to ≤ 1,000 points.

## Predictions vs trades
Prediction quality is tracked **separately** (`prediction/outcome.py`, `POST /predictions/refresh-outcomes`): for each stored BUY/SELL plan the engine checks whether the entry zone was reached, then whether the stop or first target came first (stop first on ambiguity; no TP in the fill bar unless filled at the open), expiring after 100 bars. This does not depend on any backtest.

## Not modelled
Holidays/maintenance breaks, intrabar path, partial fills, funding/swap, margin calls, order-book depth, spread widening in news. Treat results as optimistic in those respects.

## Costs, audit and evaluation protocol
* Costs can be fixed price units (`spread`, `slippage`) and/or percentages of price (`spread_pct`, `slippage_pct`, `commission_pct`); the reports use percentages so costs stay realistic across a 16k to 120k price history. The `costs` field is the exact spread + slippage + commission paid (a limit target pays only the entry half-spread).
* Audit tests (`tests/test_backtest_audit.py`): entry exactly on the bar after the signal; final equity = initial + sum of P&L; risk-per-trade sizing; leverage cap; no overlapping trades or reused signals; stops never fill better than the stop; fair-coin entries have about zero expectancy at zero cost; identical earlier trades when the future is rewritten (including for the real decision engine).
* Quantitative evaluation (`reports/BTCUSDT_BACKTEST_*.md`): `zero_cost / optimistic / base / stress` scenarios, six chronological folds, bootstrap CI and t-test on R, long/short and regime splits, and baselines (no trade, buy and hold, SMA200 trend, EMA20/50, random entries). Verdict rule: positive only if CI above 0, p < 0.05, at least 2/3 of folds positive and at least 100 trades.

## Interpretation warning
On 3.2 years of BTCUSDT the untuned rule engine has no gross edge and a significantly negative net expectancy on 1H, and no evidence of edge on 4H (`reports/QUANTITATIVE_VALIDATION_SUMMARY.md`). Do not tune on the window you evaluate on; any rule change needs data not used here.
