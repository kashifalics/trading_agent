# User guide

AI Trading Intelligence analyses the market and shows you possible trade setups with the reasoning behind them. **It never places
orders and is not connected to any broker.** Every setup is a hypothetical idea for your own analysis: none of its strategies has a
proven, validated edge, which is why setups carry a **Not validated** label.

## 1. Getting connected

1. Open the web address you were given (for a local installation: <http://localhost:3000>).
2. If a yellow bar says **"This server requires a platform API key"**, open **Settings**, paste the key you received into
   **Platform API key** and press **Save & verify**. "Key accepted by the server" means you are connected. The key is stored only
   in this browser; enter it again on another device.
3. The dot at the top right shows the connection: green "backend online", red "backend unreachable".

## 2. The pages

| Page | What it is for |
|---|---|
| **Overview** | Latest prices, data health, recent analyses. A **delayed** badge means the market is closed or the price is old: it is the last known price, not a live one |
| **Signals** | The main analysis screen (section 3) |
| **Paper Trading** | A simulated account that records every signal automatically and follows it on later candles (section 5) |
| **Trade Opportunities** | Setups ranked across instruments and timeframes by an evidence score (not a win probability) |
| **Chart Analysis** | Analyse one instrument and timeframe in depth, or upload a chart screenshot |
| **Market Scanner** | The latest stored analysis per instrument and timeframe |
| **Historical Patterns** | Which patterns and structures are present now on every timeframe, each with its measured history |
| **Predictions** | Every analysis you ran, with its evidence and what happened afterwards |
| **Gold Research** | Results of the 20-year gold study (no validated strategy was found) |
| **Backtesting / Models / Performance** | Research tools for testing rules and models on history |
| **Watchlists, Data Sources, Settings** | Your lists, data status and synchronisation, connection and defaults |

## 3. Reading a signal (Signals page)

1. Pick an instrument tab (XAUUSD, EURUSD, GBPUSD, BTCUSDT, US30, USOIL). Press **Refresh now** to load the latest candles; with
   **Live refresh** on, the page updates every 60 seconds.
2. The top card shows the price, the session and the **overall bias** per trading style (short-term, intraday, swing, long-term).
3. **Best setup** shows the strongest current plan:
   * **Direction and instruction:** EXECUTE NOW (market entry), PLACE LIMIT ORDER (entry at a price ahead), WAIT FOR CONFIRMATION,
     or NO TRADE.
   * **Entry, stop loss, TP1–TP3** with the reward-to-risk of each target (minimum 1:2) and the invalidation level.
   * **Score /100:** how many quality checks the setup passes (trend alignment, structure, liquidity, entry zone, confirmation,
     reward-to-risk, session). It is **not** a probability of winning.
   * **Not validated:** these rules have no proven out-of-sample edge. Treat the plan as an idea to check, not a recommendation.
4. **All timeframes** lists every timeframe from 1 minute to 12 months. "Insufficient data" means the data source does not yet hold
   enough history for that timeframe. Click a row for its full checklist, reasons for and against, and chart.
5. A plan that cannot reach a 1:2 target, has no structural stop, faces too wide a spread or uses stale data is shown as blocked
   with the reason. **NO TRADE is a normal, frequent answer.**

## 4. Position size

Under a plan, **Position size** turns your account balance and risk per trade into lots:
lots = (balance × risk %) ÷ (stop distance × contract size). Example: $10,000 at 1% with a 20-pip EURUSD stop and a
100,000-unit lot = 0.5 lots. Check the contract size against your broker's specification (defaults: gold 100 oz, FX 100,000 units)
and remember that spread and slippage are not included.

## 5. Paper trading

While the server runs, every EXECUTE NOW and PLACE LIMIT ORDER signal is recorded the moment it appears and simulated on the
following candles: stop or first target, your spread charged, no real money. The page shows open and pending trades, history, win
rate and expectancy. It gives **no verdict before 100 closed trades**, because fewer cannot separate skill from luck. You can change
risk per trade, maximum open trades and the daily loss limit, or start a new account.

## 6. What the labels mean

| Label | Meaning |
|---|---|
| Not validated | The rules behind this setup have not passed an out-of-sample test. No strategy in the product has |
| Score / Evidence score | Setup quality on a checklist. Not a chance of winning |
| delayed | Last known price; the market is closed or the quote is old |
| Insufficient data | Not enough history for this timeframe yet |
| Blocked: … | The plan failed a safety rule (reason shown) |
| research only (models) | A model that did not pass validation; its output never affects decisions |

## 7. Important

* Analysis only: nothing is executed and no account is connected. You decide and act in your own trading platform.
* Past patterns do not guarantee future results. High-impact news is not filtered. Never risk money you cannot afford to lose.
* Prices come from free data sources (indicative broker quotes and public exchange data) and can differ slightly from your broker's.
