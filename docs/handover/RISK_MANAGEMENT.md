# Risk management guide

AI Trading Intelligence is an **analysis-only** platform: it never sends orders to a broker. The risk controls below protect the
**paper-trading account** (simulated) and decide whether a new signal is *eligible* under your rules. They are configurable limits,
not a promise of safety.

## 1. What is checked for every signal

The checks are made by the backend (`backend/app/strategy_engine/risk.py`) and shown with the signal.

| Control | Default | What happens |
|---|---|---|
| Risk per trade | 0.5% of equity | Position size = risk amount / stop distance / contract size |
| Maximum concurrent trades | 5 | No new trade above the limit |
| Maximum open risk | 2% of equity | No new trade that would exceed it |
| Daily loss limit | 2% of the day's starting balance | No new trades until 00:00 UTC |
| Drawdown halt | 10% below the equity peak | No new trades until you reset the account |
| Minimum reward:risk | TP1 at 1.5R or more | Plans below it are rejected, never shown |
| Spread filter | the spread may use at most 0.25R (scalping), 0.20R (intraday), 0.15R (swing), 0.10R (position) | Plan rejected |
| Volatility filter | ATR in its top 5%, or a 3-ATR shock candle | NO TRADE in that regime |
| Correlated exposure | at most 1.5% net open risk per currency (EURUSD BUY = +EUR, −USD) | No new trade that would exceed it |
| Session filter | daily rollover (16:55-17:10 New York), first hour after the weekly open, closed market | WAIT instead of BUY/SELL |
| Stale data | latest candle more than 3 candles late | NO TRADE for that timeframe |
| News | **not filtered**: no free, reliable economic calendar is connected | Shown as "not available" |

Contract sizes used for sizing: XAUUSD 100 oz, FX 100,000 units, US30 1 per point, USOIL 1,000 barrels, BTCUSDT 1 coin. Check
your broker's contract specification before using a size.

## 2. What the platform never does

- It never places a trade or connects to a broker.
- It never increases size after a loss: no martingale, grid or averaging down. Size is always risk % × current equity / stop
  distance.
- It never moves a stop to "repair" a plan: an invalid plan is rejected and the rule is named.
- It never shows a win probability unless a calibrated model passes validation. None has.

## 3. Paper-trading account settings

On the Paper Trading page:
- **Risk per trade %**, **Max open trades** and **Daily loss limit %** can be changed. The change applies to signals recorded from
  then on.
- **Reset account** starts a new account. The forward-test record is kept.

## 4. Before you trade real money

No strategy in the platform has passed research validation (`docs/reports/XAUUSD_EXPERIMENT5.md`). Treat every plan as
analysis. If you act on one, use your own risk limits, check the price on your broker's platform, and never risk money you cannot
afford to lose.
