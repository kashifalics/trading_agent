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
| **Market Scanner** | The latest stored analysis per instrument and timeframe |
| **Historical Patterns** | Which patterns and structures are present now on every timeframe, each with its measured history |
| **Predictions** | Every analysis you ran, with its evidence and what happened afterwards |
| **Gold Research** | Results of the 20-year gold study (no validated strategy was found) |
| **Backtesting / Models / Performance** | Research tools for testing rules and models on history |
| **Watchlists, Data Sources, Settings** | Your lists, data status and synchronisation, connection and defaults |

## 3. Reading a decision (Signals page)

1. Pick an instrument tab (XAUUSD, EURUSD, GBPUSD, BTCUSDT, US30, USOIL). Each tab already shows that instrument's decision. Press
   **Refresh now** to load the latest candles; with **Live refresh** on, the page updates every 60 seconds.
2. The **Decision now** card at the top tells you, in this order:
   * **The decision:** ENTER, WAIT, EXIT or NO TRADE, with the reason in capitals (for example WAIT — CONFIRMATION PENDING).
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
   | **WAIT — TRADE OPEN / ORDER PENDING** | A paper trade is already tracked here: manage it (HOLD), no new entry |
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
**Recommendation**: HOLD, EXIT or WAIT, with the reason. The page shows open and pending trades, history, win
rate and expectancy. It gives **no verdict before 100 closed trades**, because fewer cannot separate skill from luck. You can change
risk per trade, maximum open trades and the daily loss limit, or start a new account.

## 6. What the labels mean

| Label | Meaning |
|---|---|
| ENTER / WAIT / EXIT / NO TRADE | The decision; the text after the dash is the reason (section 3) |
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
