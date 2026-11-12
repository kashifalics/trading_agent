# Trading decision engine

Every place in the product that shows a trade idea (Signals, Overview, Trade Opportunities, Chart Analysis, Predictions, Market
Scanner, Watchlists, Gold Research, Paper Trading) shows **one decision computed by the backend**: `ENTER`, `WAIT`, `EXIT` or
`NO TRADE`. The frontend only displays it; it never decides.

* Code: `backend/app/decision/core.py` (the rules), `backend/app/decision/adapters.py` (one adapter per source module).
* Tests: `backend/tests/test_decision.py` (including a 3,000-case property test), plus API and frontend tests.

## Technical state versus customer decision

The analysis modules keep their own **technical** states (signal engine: `ENTRY_READY`, `SETUP_DEVELOPING`, `WAITING_FOR_CONFIRMATION`,
`WATCHLIST`, `NO_SETUP`, ...; opportunity scanner: `entry_triggered`, `waiting_for_confirmation`, ...; decision engine: BUY / SELL /
WAIT). These are unchanged and still drive the Paper Trading forward test and the backtests.

The **decision** is a separate layer on top. A technically complete setup is not a recommendation: `ENTER` also requires
research-validated rules. No rule set has passed out-of-sample validation (docs/STRATEGY_VALIDATION.md, Gold Research experiments
1–3), so today a technically complete setup is shown as **WAIT — UNVALIDATED SETUP**.

## Rules, in order (first match wins)

| # | Condition | Decision |
|---|---|---|
| 1 | A tracked paper trade hit its stop, its target, or closed beyond its invalidation level | `EXIT — STOP-LOSS HIT` / `EXIT — TARGET REACHED` / `EXIT — SETUP INVALIDATED` |
| 2 | Data missing, stale or insufficient for this timeframe | `NO TRADE — DATA` |
| 3 | A tracked paper trade is open or pending here | `WAIT — TRADE OPEN` / `WAIT — ORDER PENDING` (manage it, no new entry); a pending order whose setup failed → `NO TRADE — CANCEL PENDING ORDER` |
| 4 | The setup was invalidated or expired / no setup | `NO TRADE — SETUP INVALIDATED` / `— EXPIRED` / `NO TRADE` |
| 5 | Any mandatory check fails (structural stop distance, reward:risk to a structural target, opposing obstacle, spread cost, required timeframes have data, no higher timeframe against the trade) | `NO TRADE — CONDITION FAILED` (the failed check and what would fix it) |
| 6 | The live price is beyond the stop, already at the first target, more than 0.3R past a market entry (never chase), or outside stop–target | `NO TRADE — PRICE BEYOND STOP` / `— TARGET ALREADY REACHED` / `— ENTRY MISSED` / `— PRICE OUTSIDE PLAN` |
| 7 | Setup still forming, price not yet at the zone, confirmation missing, market closed or spread abnormal | `WAIT — SETUP DEVELOPING` / `— PRICE NOT AT ENTRY ZONE` / `— CONFIRMATION PENDING` / `— MARKET CONDITIONS` |
| 8 | Everything above passes and the rules **are** research-validated | `ENTER` (immediate, or conditional on a limit fill), with entry, stop, targets and reward:risk |
| 9 | Everything above passes but the rules are **not** validated | `WAIT — UNVALIDATED SETUP` |

Guarantees (enforced by tests):

* The score never overrides a failed mandatory check, and no failed check, bad data or unvalidated rule can produce `ENTER`.
* A missing timeframe is never assumed aligned: it fails the "Required timeframes" check.
* Entry, stop and targets (`levels`) are present **only** with `ENTER`.
* Every decision has a headline and a **next condition** (what must happen next).
* `EXIT`, `HOLD` and trade management apply only to trades the Paper Trading module is tracking.
* The words `EXECUTE NOW` and `PLACE LIMIT ORDER` are never shown to customers.

## Experimental analysis mode

Off by default (Settings → Trading decisions, or the checkbox on the Signals page). It sends `experimental=true` and the backend
then adds `hypothetical` levels to unvalidated or incomplete setups, labelled **HYPOTHETICAL — UNVALIDATED**. It never changes the
decision: an unvalidated setup stays `WAIT — UNVALIDATED SETUP`.

## Instrument headline

Each instrument shows its most relevant timeframe decision: `EXIT` > `ENTER` > `WAIT` (trade open, order pending, unvalidated,
confirmation pending, market conditions, price not at zone, developing) > `NO TRADE`; ties go to the higher setup score.

## Trade management (Paper Trading)

Open and pending paper trades carry `management`: `HOLD` (between stop and target, no exit condition), `EXIT` (stop, target or
invalidation reached), `WAIT` (pending order not filled yet) or `NO TRADE` (cancel a pending order whose setup failed), with the
current price, distances to stop and target, and unrealised R.

## API

Every response that carries a trade idea has a `call` object: `GET /signals` (per item), `GET /signals/{symbol}` (headline and each
plan), `POST /signals/{symbol}/sync`, `GET /opportunities/summary|/opportunities|/opportunities/{id}`, `GET /analysis/{id}`,
`GET /predictions[/{id}]`. Each accepts `?experimental=true`. Paper trades have `management`. Field list: docs/API_SPECIFICATION.md.

Stored explanations that contain a plan line ("Plan: entry …, stop …") have that line withheld unless the call shows levels
(`ENTER`) or hypothetical levels (experimental mode). The stored data itself is never modified.

## Limitations

* No rule set is validated, so `ENTER` cannot appear today; the ENTER path is covered by tests with a hypothetical validated rule.
* The decision uses the live quote when it is fresh, otherwise the last closed candle; quotes are indicative (free sources).
* High-impact news is not filtered (no calendar integration).
* Paper Trading still records every technically complete setup: that is the forward test of the unvalidated rules, not advice.
