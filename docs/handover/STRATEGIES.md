# Trading strategies (customer guide)

The strategy engine first classifies each timeframe's **market regime**. It then runs only the strategies that suit that regime,
picks the strongest qualifying setup, and turns it into a plan. The exact rules, with every threshold, are in
[`docs/engine_v2/DESIGN.md`](../engine_v2/DESIGN.md). **No strategy has passed research validation**; their plans are hypothetical
(see the [research report](../reports/XAUUSD_EXPERIMENT5.md)).

## Market regimes

| Regime | Measured by | Strategies that may run |
|---|---|---|
| Trending (up or down) | ADX ≥ 25, efficiency ratio ≥ 0.30, aligned EMA20/EMA50 and a sloping EMA50 | Trend pullback, Breakout and retest, Momentum continuation, Liquidity-sweep reversal |
| Ranging | ADX < 20, efficiency ratio < 0.25, a 50-candle span of 3-12 ATR | Breakout and retest, Range mean reversion, Liquidity-sweep reversal |
| Consolidating | Bollinger width in its lowest 20%, ADX < 20 | Breakout and retest, Volatility expansion |
| High volatility / abnormal | ATR in its top 5%, or a 3-ATR shock candle | none: NO TRADE |
| Unknown | not enough data (fewer than 120 candles), or no rule fully met | none (no data), or Breakout and retest, Liquidity-sweep reversal, Volatility expansion (transitional) |

## The six strategies

| Strategy | In one sentence | It refuses when |
|---|---|---|
| **Trend-following pullback** | In a trend, buy (sell) a pullback to EMA20 or a fresh zone once momentum returns and price closes beyond the pullback candle | no trend; the higher timeframe trends the other way; the pullback is too deep |
| **Breakout and retest** | A tight 20-candle box breaks with a strong close; enter on the retest of the broken level | price closed back inside (false breakout); price ran more than 2 ATR away (no chase) |
| **Momentum continuation** | After a strong displacement candle and a controlled pullback, enter as price resumes | momentum or structure not confirmed; price stretched more than 3 ATR from EMA20, or RSI above 80 / below 20 |
| **Range mean reversion** | In a proven range, sell a rejection of the top (buy the bottom), targeting the middle and the far side | not a range; ADX ≥ 25; the range is not established by repeated touches |
| **Liquidity-sweep reversal** | Price takes out a meaningful high (low), closes back inside, and then breaks structure the other way | **a sweep alone is never a trade**: the market-structure shift is required |
| **Volatility expansion** | After a compression, a wide candle closes out of the box and breaks structure | no compression before; the expansion fails back into the box |

## How a plan is calculated

- **Entry:**
  - at market, at the close that triggered the setup;
  - or a limit price (retest);
  - or a stop price (continuation).
- **Stop-loss:** beyond the setup's invalidation level, plus 0.1 ATR and the spread. A stop that is too tight or too wide rejects the
  plan.
- **Targets:**
  - TP1, TP2 and TP3 are the next structural levels: swing highs and lows, liquidity, previous day/week highs and lows, opposite
    zones.
  - Where there is none, a stated risk multiple is used (2R, 3R, 5R), labelled "risk objective".
- **Rounding:** every price is rounded to the instrument's tick.
- **Rejection:** a plan whose levels are on the wrong side, or whose TP1 is below 1.5R, is rejected, never shown.
- **Entry status:**
  - READY: price is at the entry;
  - WAITING FOR ENTRY;
  - ENTRY MISSED: price ran away, or TP1 already traded;
  - EXPIRED.

## Signal lifecycle

Every plan is recorded once and followed on 1-minute candles to its outcome:
- **Entry:** DETECTED → WAITING FOR ENTRY or ENTRY READY → ENTRY TRIGGERED → ACTIVE.
- **Outcome:** then TP1 / TP2 / TP3 HIT, or STOP LOSS HIT, INVALIDATED, EXPIRED or ENTRY MISSED.

This is hypothetical tracking. It is not a paper trade and not an order.
