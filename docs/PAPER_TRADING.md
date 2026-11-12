# Paper trading (forward test)

Paper trading records every actionable signal the moment the backend sees it, then simulates the order against the candles that follow.
No broker is involved and no real order is placed. The point is evidence the backtest cannot provide: each signal is recorded before its
outcome exists, so the live record cannot be tuned after the fact.

Code: `backend/app/paper/` (simulator, service, stats, worker), shared fill and exit rules in `backend/app/signals/execution.py`, API in
`backend/app/api/v1/routes/paper.py`, page at `frontend/src/app/(terminal)/paper/`.

## What counts as a signal

The source is the same `analyze()` output the Signals page shows, including its live downgrades (market closed, abnormal spread).
It records the engine's **technical** states, not the customer decision (docs/DECISION_ENGINE.md): it is the forward test of the
unvalidated rules, so it records setups whose decision is `WAIT — UNVALIDATED SETUP`. Open and pending trades carry `management`
(HOLD / EXIT / WAIT / NO TRADE with the reason, distances to stop and target and unrealised R), shown as **Recommendation**.

| Plan on the Signals page | Paper order |
|---|---|
| `ENTRY_READY` / `EXECUTE NOW` | market order |
| `PLACE LIMIT ORDER` | limit order at the plan's entry |
| anything else (`WAIT FOR CONFIRMATION`, `WATCHLIST`, `NO TRADE`) | nothing |

* One paper trade per instrument, timeframe and setup (`setup_key`, enforced by a unique index). A setup is never traded twice.
* While an instrument × timeframe has a pending or open paper trade, new signals on it are ignored. The backtest uses the same rule.
* The plan is stored with the trade exactly as it was shown: checklist, reasons for and against, targets and score.

## Execution model

The rules are the backtest's (`app/signals/execution.py` is shared by both), with three changes for live candles:

1. **Orders start when the backend saw the signal.** A market order fills at the open of the first candle that starts after detection.
   The backtest used the next setup-timeframe candle, so the two agree when the backend is running.
2. **Exits use 1-minute candles** where they are stored, so a stop or target is recognised within about a minute. Gaps in 1m data, for
   example while the backend was off, are bridged with the finest stored candles (5m, 15m, 1H, 4H, 1D). A candle that started before
   the cursor is never used.
3. **Gaps are honoured.** A candle that opens beyond the stop exits at that open, and one that opens beyond TP1 exits at that open. The
   backtest exits at the level, which is the simpler rule its published numbers were produced with.

Rules shared with the backtest:

* **Market order:** skipped if the fill price is already beyond the stop or TP1, or more than 0.3R past the planned entry (the plan's
  own "never chase" rule).
* **Limit order:** rests until `valid_until`. It is cancelled when a setup-timeframe candle closes beyond the invalidation level, and
  missed when TP1 trades before the entry is touched.
* **Exit:** at the stop or TP1. A candle that touches both counts as a loss. On a limit order's fill candle only the stop counts.
* **Costs:** the configured round-trip spread is charged on every trade (`R net = R gross − spread / risk`).

Statuses: `pending` → `open` → `closed` (exit reason `target` or `stop`). Orders that never fill end as `cancelled` (invalidated),
`missed` (TP1 first), `expired` or `skipped` (chased or gapped).

## Paper account

The account sits on top of the forward test. Every signal is tracked; the account only takes those its rules allow.

| Rule | Default | Effect |
|---|---|---|
| Starting balance | 10,000 | used when a new account starts |
| Risk per trade | 0.5% of the realised balance | fixed in currency when the signal is recorded; P&L = R net × risk amount |
| Max open trades | 5 | pending and open trades the account holds at once |
| Daily loss limit | 2% of the start-of-day balance | no new trades until 00:00 UTC once realised losses reach it |

A skipped signal keeps `account_taken = false` and the reason. Changing the rules affects signals recorded from then on. A reset closes
the account and opens a new one; the recorded signals and the forward-test record are kept.

## Statistics and verdict

* **Forward test:** every closed paper trade, whether or not the account took it. The reported metrics are win rate, expectancy with a
  95% CI, total R, profit factor, max drawdown, limit-order fill rate and the cumulative R curve.
* **Account:** balance, equity (with open P&L), today's realised P&L, drawdown, and how many signals the rules skipped.
* **Breakdowns:** by instrument × timeframe (with the backtest's out-of-sample expectancy beside it), timeframe, instrument, setup, score
  band, side, order type and session.
* **Verdict:** below 100 closed trades it reads "collecting evidence" and draws no conclusion. From 100 trades it uses the backtest's
  bar (`app.opportunities.validation.classify`): bootstrap CI > 0, p < 0.05 and at least 2 of 3 chronological thirds positive.

## Running it

The backend runs a cycle in-process every `PAPER_TRADING_INTERVAL_SECONDS` (default 60; `0` turns it off). Each cycle starts a few
seconds after the interval boundary, just after candles close. It syncs the candles that are due from the keyless providers (BiQuote,
Binance), analyses every instrument in `SIGNAL_SYMBOLS`, steps open and pending trades through new candles, then records new signals.
"Run cycle now" on the page (`POST /api/v1/paper/run`) does the same on demand. Only one cycle runs at a time.

Settings (`backend/.env`): `PAPER_TRADING_INTERVAL_SECONDS`, `PAPER_START_BALANCE`, `PAPER_RISK_PCT`, `PAPER_MAX_OPEN_POSITIONS`,
`PAPER_MAX_DAILY_LOSS_PCT`.

## Limitations

* Signals are only recorded while the backend runs. Nothing is backfilled, so a signal that fired while it was off is lost.
* Fills assume the configured spread and no slippage except on gaps. Real fills can be worse, especially around news.
* No news filter. High-impact events are not avoided, as on the Signals page.
* Exits use TP1 only, as in the backtest. Partial exits at TP2/TP3 and break-even stops are not simulated; the recorded MFE shows
  how far trades ran.
* With a single uvicorn worker the in-process loop is safe. With several workers, set the interval to 0 on all but one; the unique index
  still prevents duplicate trades.
