# Candle Range Theory (CRT): research implementation

**Status: experimental, unvalidated, and not part of Experiment 5.** CRT was added as a separate strategy candidate on 2026-11-18.
It does not gate or modify the other strategies. The engine may show its hypothetical plans, which remain subject to the same
data, spread, session, stop, target, and risk checks as other plans. The platform does not place orders.

## What CRT means

CRT most plausibly means **Candle Range Theory** (also called Candlestick Range Theory). Practitioner material describes using a
completed higher-timeframe candle's high and low as a range, then looking for price to take one boundary and return inside before
reversing toward the other boundary. The exact confirmation and entry rules vary. One description uses a three-candle sequence:
range candle, false break that closes back inside, then a move out in the opposite direction. Another uses a higher-timeframe
range raid followed by a lower-timeframe market-structure shift (MSS) and a retest.

The implementation chooses the latter, explicit variant:

1. Use the latest completed context-timeframe candle as the CRT range. Only signal-timeframe candles opening after that candle
   closed may interact with its levels.
2. A bullish candidate requires a signal-timeframe low below the range low and a close back above it. A bearish candidate mirrors
   this at the range high.
3. Require a pre-raid, confirmed signal-timeframe swing inside the range. A later close beyond that swing in the reversal
   direction is the MSS. A sweep alone is never a trade.
4. Enter only after the MSS retest: if the latest completed candle retests and closes back beyond the MSS level, the candidate is
   ready at that close; otherwise it is pending at the MSS level. A missed earlier retest is rejected rather than chased.
5. Invalidation is the raid candle's extreme. The first target is the opposite edge of the higher-timeframe range. The shared plan
   builder applies its normal ATR buffer, spread, stop-width, tick-rounding, and minimum-reward checks; a target that cannot pass
   those checks does not produce a plan.
6. Only the immediately following context-timeframe interval is eligible. Dual-sided raids, a failed MSS, a broken raid extreme,
   missing context candles, stale anchors, and abnormal volatility are not eligible setups.

This is a deterministic implementation choice, not a canonical CRT definition. The source's discretionary "key support or
resistance" context is not automated; all completed context candles are eligible anchors. No parameter was tuned on trade
outcomes.

## Evidence and limitations

- The CRT-specific sources reviewed are practitioner/educational descriptions, not independent performance studies:
  [Inner Circle Trader: Candle Range Theory](https://innercircletrader.net/tutorials/candle-range-theory-crt/) explicitly says CRT
  is not an ICT concept; it describes a higher-timeframe range, a raid that closes back inside, lower-timeframe MSS/retest, a stop
  beyond the raid, and the opposite range boundary as a target.
  [ForexBee: Candlestick Range Theory](https://forexbee.co/candlestick-range-theory-in-forex-trading/) describes a three-candle
  version and adds discretionary structure/order-block confluences. The disagreement is why this implementation names and
  documents one variant rather than implying universal rules.
- No CRT-specific peer-reviewed or independently reproduced evidence was located in this search. This is a search limitation, not
  proof that no such study exists. Park and Irwin's review of technical-analysis studies (not a test of CRT) describes mixed
  evidence and methodological concerns including data snooping and transaction costs:
  [Journal of Economic Surveys (2007)](https://doi.org/10.1111/j.1467-6419.2007.00519.x).
- Frequent-trading costs and losses are general risks, not CRT-specific findings:
  [FINRA: Frequent Intraday Trading](https://www.finra.org/investors/insights/frequent-intraday-trading).

CRT is therefore labelled **INSUFFICIENT EVIDENCE**. It must not be described as profitable or validated. A future validation
requires a separate pre-registration covering the exact variant, instruments, timeframes, realistic bid/ask costs, matched
controls, out-of-sample handling, and multiple-testing correction. Experiment 5's result and sealed data are unchanged.
