# User guide

AI Trading Intelligence analyses the market and gives one clear decision for each instrument and timeframe: **ENTER**, **WAIT**,
**EXIT** or **NO TRADE**, with the reasons and what must happen next. **It never places orders and is not connected to any
broker.** None of its strategies has a proven, validated edge yet, so it does not tell you to enter: a technically complete setup is
shown as **WAIT — UNVALIDATED SETUP**.

## 1. Getting connected

1. Open the web address you were given (for a local installation: <http://localhost:3000>).
2. If a yellow bar says **"This server requires a platform API key"**, open **Settings**, paste the key you received into
   **Platform API key** and press **Save & verify**. "Key accepted by the server" means you are connected. The key is stored only
   in this browser; enter it again on another device.
3. The dot at the top right shows the connection: green "backend online", red "backend unreachable".

## 2. The pages

| Page | What it is for |
|---|---|
| **Overview** | Latest prices, **Decisions now** (one decision per instrument, the same as on Signals), data health, recent analyses. A **delayed** badge means the market is closed or the price is old: it is the last known price, not a live one |
| **Signals** | The main analysis screen (section 3) |
| **Paper Trading** | A simulated account that records every technically complete setup automatically and follows it on later candles, with a HOLD / EXIT / WAIT recommendation for open trades (section 5) |
| **Trade Opportunities** | Setups ranked across instruments and timeframes by an evidence score (not a win probability) |
| **Chart Analysis** | Analyse one instrument and timeframe in depth, or upload a chart screenshot |
| **Market Scanner** | The live decision for every instrument and timeframe on one grid (updated every minute; click a cell for its checklist), plus on-demand deep analyses |
| **Historical Patterns** | Which patterns and structures are present now on every timeframe, each with its measured history |
| **Predictions** | Every analysis you ran, with its evidence and what happened afterwards |
| **Gold Research** | Results of the 20-year gold study (no validated strategy was found) |
| **Backtesting / Models / Performance** | Research tools for testing rules and models on history |
| **Watchlists, Data Sources, Settings** | Your lists, data status and synchronisation, connection and defaults |

## 3. Reading a signal (Signals page)

Each instrument has one card, best opportunity first:
- **The action, in large type:**
  - **BUY / SELL:** a strategy's entry conditions are met now.
  - **WAIT FOR BUY / WAIT FOR SELL:** a valid setup waiting for an exact entry price (limit or stop).
  - **EXIT:** a tracked paper trade on that instrument must be closed; the reason is shown in a red alert.
  - **NO TRADE:** nothing qualifies, with the reasons.
- **Strategy, timeframe and market regime:** one of six strategies; Trending, Ranging, Consolidating, High volatility or Unknown.
- **Entry, stop loss, TP1, TP2 and TP3:** each target with its reward:risk and what it is based on (a swing high, an order block, or a
  "risk objective" when no structural level is near). Then the overall R:R, the spread cost, the entry status (READY, WAITING FOR
  ENTRY) and when the signal expires.
- **Why, what invalidates it, and the next action.**
- **"UNVALIDATED — HYPOTHETICAL TRADE PLAN" and "Research: INSUFFICIENT EVIDENCE":** no strategy has passed research yet, so these
  are analysis, not proven recommendations, and no win probability is ever shown. Untick **Show hypothetical trade plans** to hide
  the prices of unvalidated plans.
- **Paper trades on that instrument:** shown in their own block. They are the forward test of the older v1 rules and never hide a new
  signal.
- **All timeframes and strategies** opens every timeframe's action; click a timeframe to see each strategy's verdict. **Signal history**
  lists each signal once and follows it to its outcome (TP1/TP2/TP3 hit, stop-loss hit, invalidated, expired or entry missed).

The previous Signals page (the v1 100-point checklist) is still available at **Engine v1 checklist** (`/signals/classic`).

## 3b. The v1 checklist (Engine v1 checklist page)

1. The **All signals** table at the top lists every instrument (XAUUSD, EURUSD, GBPUSD, BTCUSDT, US30, USOIL) on one screen: its
   decision now, its bias, every timeframe with a live setup (side, score and that timeframe's decision) and what must happen next.
   Click an instrument or a timeframe to open its detail below (or use the instrument tabs). Nothing needs a manual refresh: the
   server re-analyses every instrument each minute, every page fetches new data by itself (the list every 30 seconds, most pages every
   60 seconds, and at once when you come back to the tab), and the table says how long ago the analysis ran. **Refresh now** loads
   the latest candles at once; with **Live refresh** on, the open instrument also fetches new candles every 60 seconds.
2. The **Decision now** card at the top tells you, in this order:
   * **The decision:** ENTER, HOLD, WAIT, EXIT or NO TRADE, with the reason in capitals (for example WAIT — CONFIRMATION PENDING).
   * The instrument, direction, timeframe and setup, and **Research: Not validated / Validated**.
   * One sentence on why, and **Next:** what must happen before anything changes.
   * The price condition (zone and invalidation level), confirmation, data quality, how the timeframes line up, and the reasons for
     and against.
   * **Entry, stop loss, targets and reward:risk appear only with ENTER.** None appears today, because no rules are validated.
3. The decisions:

   | Decision | Meaning |
   |---|---|
   | **ENTER** | Every mandatory condition passes **and** the rules passed out-of-sample validation. Shown with entry, stop and targets |
   | **WAIT — UNVALIDATED SETUP** | The setup is technically complete, but the rules have not proven a profitable edge, so the system does not recommend entering |
   | **WAIT — CONFIRMATION PENDING / PRICE NOT AT ENTRY ZONE / SETUP DEVELOPING / MARKET CONDITIONS** | A possible setup that is not complete yet; **Next** says what is missing |
   | **HOLD — PAPER TRADE OPEN** | The paper-trading test already holds a trade here: keep it until its stop or first target (shown with its entry, stop, target and open profit in R); no new entry |
   | **WAIT — PAPER ORDER PENDING** | The paper-trading test has a limit order waiting here: wait for the fill; no new entry |
   | **EXIT** | A tracked paper trade reached its stop, its target or its invalidation level |
   | **NO TRADE — …** | No valid setup, bad or missing data, a failed mandatory condition, or price already past the plan |

4. **All timeframes** lists every timeframe from 1 minute to 12 months with its decision and its technical state. Click a row for
   its decision card, full checklist, reasons and chart. A timeframe without data is never assumed to agree: it fails the
   "Required timeframes" check.
5. **Score /100** counts quality checks (trend alignment, structure, liquidity, entry zone, confirmation, reward-to-risk, session).
   It is **not** a probability of winning and never overrides a failed condition. **NO TRADE and WAIT are normal, frequent answers.**
6. **Experimental mode** (checkbox on Signals, or Settings → Trading decisions) shows the technical entry, stop and targets of
   unvalidated setups in a dashed box marked **HYPOTHETICAL — UNVALIDATED**. It is for study only and does not change any decision.

## 4. Position size

With an ENTER decision (or hypothetical levels in experimental mode), **Position size** turns your account balance and risk per
trade into lots:
lots = (balance × risk %) ÷ (stop distance × contract size). Example: $10,000 at 1% with a 20-pip EURUSD stop and a
100,000-unit lot = 0.5 lots. Check the contract size against your broker's specification (defaults: gold 100 oz, FX 100,000 units)
and remember that spread and slippage are not included.

## 5. Paper trading

While the server runs, every technically complete setup (immediate or limit entry) is recorded the moment it appears and simulated
on the following candles: stop or first target, your spread charged, no real money. This is the forward test of the unvalidated
rules, so it records setups even while their decision is WAIT — UNVALIDATED SETUP. Open and pending trades show a
**Recommendation**: HOLD, EXIT or WAIT, with the reason. A trade is held until its stop or first target, with no time limit (the
same rule as the backtest); on short timeframes the first target can be far away (its size is shown in R), so a 3m or 5m trade can
stay open for days. The page shows open and pending trades, history, win
rate and expectancy. It gives **no verdict before 100 closed trades**, because fewer cannot separate skill from luck. You can change
risk per trade, maximum open trades and the daily loss limit, or start a new account.

## 6. What the labels mean

| Label | Meaning |
|---|---|
| ENTER / HOLD / WAIT / EXIT / NO TRADE | The decision; the text after the dash is the reason (section 3) |
| Not validated | The rules behind this setup have not passed an out-of-sample test. No strategy in the product has |
| HYPOTHETICAL — UNVALIDATED | Technical levels shown only in experimental mode; not a recommendation |
| Score / Evidence score | Setup quality on a checklist. Not a chance of winning |
| delayed | Last known price; the market is closed or the quote is old |
| Insufficient data | Not enough history for this timeframe yet |
| NO TRADE — CONDITION FAILED | The setup failed a mandatory rule (reason and fix shown) |
| research only (models) | A model that did not pass validation; its output never affects decisions |

## 7. Important

* Analysis only: nothing is executed and no account is connected. You decide and act in your own trading platform.
* Past patterns do not guarantee future results. High-impact news is not filtered. Never risk money you cannot afford to lose.
* Prices come from free data sources (indicative broker quotes and public exchange data) and can differ slightly from your broker's.
