# Strategy engine v2: design

Status: implemented as `backend/app/strategy_engine/` (see `IMPLEMENTATION_REPORT.md`). Every threshold below is an **initial,
frozen hypothesis**: none was fitted to results. Whether each one is useful is a question for the experiment in
`EXPERIMENT_PLAN.md`, which needs the owner's approval before it runs. Experiment 5 (2026-11-13, docs/reports/XAUUSD_EXPERIMENT5.md) tested them: none passed, so five strategies are **NOT VALIDATED**
and range mean reversion is **INSUFFICIENT EVIDENCE**; every plan is marked **UNVALIDATED — HYPOTHETICAL TRADE PLAN**.

## 1. Architecture

```
candles (same store, same provider per instrument as v1; complete candles only; H8 built from complete 1H buckets)
  └─ for each signal timeframe T (chain: context TF above, trigger TF below; section 6)
       regime(T), regime(context)            app/strategy_engine/regime.py
       six strategies on T (+ trigger on the lower TF where the rule needs it)
                                             app/strategy_engine/strategies/*.py   -> candidates (ready / pending / forming / rejected)
       trade plan for each candidate         app/strategy_engine/plan.py           -> validated levels, or rejected with the reason
       selector                              app/strategy_engine/selector.py       -> one action for T
  └─ instrument: best action over its timeframes, tracked paper-trade exits, risk check (risk.py), session (sessions.py)
  └─ signal lifecycle record (DB) updated every minute from 1-minute candles      app/strategy_engine/lifecycle.py
  └─ API /api/v1/engine, /api/v1/engine/{symbol}, /api/v1/engine/signals          -> Signals page, Scanner, Overview
```
v1 (`app/signals`) is unchanged: the paper forward test keeps evaluating its frozen rules.

## 2. Indicators (completed candles only)

- **ATR(14)**: Wilder.
- **ADX(14) with +DI/-DI**: Wilder.
- **EMA(20), EMA(50)**: slope = EMA50 change over 10 bars, in ATR units.
- **Bollinger width(20, 2σ)**: (upper − lower) / middle. Its percentile is measured against the trailing 200 bars.
- **Efficiency ratio ER(20)**: |close − close 20 bars ago| / sum of |close-to-close changes|.
- **ATR percentile**: against the trailing 200 bars.
- **RSI(14)**: Wilder.

## 3. Market-regime classifier

Input: the bars of one timeframe, plus the context timeframe's regime. It needs at least 120 complete candles, else **UNKNOWN
(insufficient data)**. Rules are applied in this order:

| Regime | Rule |
|---|---|
| HIGH-VOLATILITY / ABNORMAL | ATR percentile ≥ 0.95, or the last candle's range ≥ 3 × ATR of the previous candle (shock bar) |
| TRENDING | ADX ≥ 25 and ER ≥ 0.30 and EMA20/EMA50 aligned with the dominant DI and with \|EMA50 slope\| ≥ 0.5 ATR per 10 bars; direction = sign |
| CONSOLIDATING | Bollinger-width percentile ≤ 0.20 and ADX < 20 (compression) |
| RANGING | ADX < 20 and ER < 0.25 and the 50-bar high-low span is 3-12 ATR |
| UNKNOWN (transitional) | none of the above (e.g. ADX 20-25, mixed alignment) |

The output carries every input value and the list of criteria met or missed. No probability is attached. "Quality" is only the
count of criteria met, labelled as such.

## 4. Strategies

Each strategy is an independent module with its own rules, its own failed-condition messages and its own tests. Each returns:
- **ready**: the trigger is met on the last complete candle, so it is a market entry;
- **pending**: the setup is valid but needs a price condition, so it is a limit or stop entry at an exact price;
- **forming**: listed with the missing conditions, never a plan;
- **rejected**: a hard rule failed, with the reason.

Buffers are in ATR of the signal timeframe. *d* = +1 BUY, −1 SELL; the SELL rules mirror the BUY rules.

### A. Trend-following pullback (regimes: TRENDING)
1. Trend: regime TRENDING with direction *d*; structure trend = *d*; the context timeframe is not opposite (TRENDING −*d* rejects;
   UNKNOWN is shown as "context unavailable", never as agreement).
2. Pullback: within the last 8 bars price traded back to within 0.3 ATR of EMA20, or into an unmitigated order block / FVG / demand
   zone in direction *d* that is at most 2 ATR wide (wider "zones", such as gaps over a market close, are not precise pullback areas). It did so without a close beyond EMA50 by more than 0.5 ATR (deeper means the trend is in doubt).
3. Momentum recovery: RSI crossed back above 50 (below for SELL) within the last 3 bars, or the last candle closed beyond the prior
   candle's high (low).
4. Trigger: the last complete candle closes beyond the high (low) of the deepest pullback candle, so the setup is **ready** at that
   close. Otherwise it is **pending** with a stop entry one tick beyond that high (low).
5. Invalidation: the pullback extreme (lowest low of the pullback for BUY).

### B. Breakout and retest (regimes: RANGING, CONSOLIDATING, TRENDING, UNKNOWN-transitional)
1. Base: a box of ≥ 20 bars, ending 1-15 bars ago, whose high-low span is ≤ 6 ATR.
2. Breakout: a candle after the box closes beyond the boundary by ≥ 0.25 ATR with a body ≥ 60% of its range.
3. No failure: no close back inside the box since the breakout (a failure rejects the setup as a false breakout).
4. Not too far: the current close is ≤ 2 ATR from the broken level (further means the move travelled too far, so no chase).
5. Retest: a candle since the breakout touched within 0.3 ATR of the level and closed beyond it. If that is the last candle, the
   setup is **ready**. If there is no retest yet, it is **pending** with a limit entry 0.1 ATR beyond the level.
6. Invalidation: the broken level minus 0.5 ATR (a close back into the box).

### C. Momentum continuation (regimes: TRENDING)
1. Displacement: within the last 6 bars, a candle with body ≥ 1.5 ATR, close in the outer 25% of its range, direction *d*.
2. Momentum: ADX ≥ 20 and rising (higher than 3 bars ago); the most recent BOS is in direction *d* and within the last 12 bars.
3. Not exhausted: the close is ≤ 3 ATR from EMA20, and RSI is ≤ 80 (≥ 20 for SELL).
4. Controlled pullback: at least one candle after the displacement retraced ≤ 50% of the displacement candle's range.
5. Trigger: a close beyond the pullback's high (low), so the setup is **ready**. Otherwise it is **pending** with a stop entry one tick
   beyond it.
6. Invalidation: the pullback low (high), or the displacement candle's midpoint if that is further.

### D. Range mean reversion (regimes: RANGING only; disabled when ADX ≥ 25 or the last close is outside the range)
1. Range: the 50-bar high and low, each touched (within 0.25 ATR) by ≥ 2 separate swing points; span 3-12 ATR.
2. Location: the last candle's high (low) is in the top (bottom) 15% of the range.
3. Rejection: the last candle closes back inside, with an upper (lower) wick ≥ 50% of its range or an engulfing close.
4. Exhaustion: RSI ≥ 60 (≤ 40 for BUY) and turning (lower than the previous bar for SELL).
5. **Ready** at the close of the rejection candle; there is no pending form (the entry is the rejection itself).
6. Invalidation: the range extreme ± 0.5 ATR. Targets: midpoint, 75% across, the opposite boundary minus 0.25 ATR.

### E. Liquidity-sweep reversal (regimes: all except HIGH-VOLATILITY)
1. Liquidity: a meaningful level is either (a) a confirmed swing high/low that is the extreme of ≥ 10 bars, (b) the previous day's
   high/low, or (c) an equal-high/low cluster from the detector.
2. Sweep: within the last 10 bars, a candle traded beyond the level and **closed back inside** (a close beyond is a breakout, not a
   sweep).
3. Market-structure shift **(required)**: after the sweep, a close beyond the last opposite swing (the swing that started the leg
   into the sweep). **A sweep alone is never a trade.**
4. Trigger: the shift on the last candle makes the setup **ready**. A shift earlier makes it **pending** with a limit entry at the
   broken swing level (retest).
5. Invalidation: the sweep extreme.

### F. Volatility expansion (regimes: CONSOLIDATING, or UNKNOWN-transitional after compression)
1. Compression: within the 10 bars before the expansion, Bollinger-width percentile ≤ 0.15 and ATR(5)/ATR(50) < 0.8. The box is
   the high/low of those compressed bars.
2. Expansion: a candle with range ≥ 1.8 × ATR, closing beyond the box and in its outer 30%.
3. Structure: that close also breaks the last swing in direction *d*.
4. **No volume rule**: spot FX and gold have no real volume.
5. **Ready** if the expansion is the last candle and the close is ≤ 1 ATR beyond the box edge. Otherwise it is **pending** with a
   limit entry at the box edge (retest).
6. Invalidation: the box midpoint.

Regime compatibility:

| Regime | Strategies |
|---|---|
| TRENDING | A, B, C, E |
| RANGING | B, D, E |
| CONSOLIDATING | B, F |
| UNKNOWN-transitional | B, E, F |
| HIGH-VOLATILITY or UNKNOWN-insufficient | none: NO TRADE |

## 5. Trade plan (entry, stop-loss, targets)

- **Entry:** set by the strategy trigger. Market = the trigger candle's close, or the live mid when it is fresh. Limit / stop = the
  exact price above. A zone is reported when the strategy defines one.
- **Stop-loss:** invalidation − (0.1 ATR + spread) for BUY, mirrored for SELL. The distance must be 0.5 to 3.0 ATR for scalping /
  intraday and up to 4.0 ATR for swing; outside that band the setup is rejected, never widened silently.
- **Targets:**
  - TP1 = the nearest structural level beyond entry between 1.5R and 4R. Levels are swing highs/lows, liquidity pools, the previous
    day/week high or low and opposite zones (v1 detector). With no such level, TP1 = 2R, labelled "risk objective".
  - TP2 = the next structural level ≤ 6R and at least 0.75R beyond TP1, else max(TP1 + 1R, 3R).
  - TP3 = the next ≤ 10R and at least 0.75R beyond TP2, else max(TP2 + 1R, 5R).
  - Range reversion uses its own range targets (section D).
- **Rounding to the instrument's tick (10^−precision):** entry to the nearest tick; stop away from entry; targets toward entry
  (conservative).
- **Hard validation:**
  - BUY must satisfy SL < entry < TP1 < TP2 < TP3; SELL the mirror.
  - Every reward:risk must be > 0, and every number finite.
  - Entry must be within 5 ATR of the current price.
  - Spread cost must be ≤ the group limit (0.25R scalping, 0.20R intraday, 0.15R swing).
  - Data must be fresh and complete.
  - Any failure means **no plan**: the setup is rejected, with the rule named.
- **Costs:** the spread (live bid/ask when fresh, else the configured model spread) in price units and in R, plus net R:R per target
  after the spread.
- **Entry status:**
  - READY: market trigger met and price within 0.3R of entry.
  - WAITING FOR ENTRY: pending.
  - ENTRY MISSED: price beyond entry by more than 0.3R, or TP1 already traded.
  - EXPIRED: older than the expiry window.
- **Expiry:** ready setups expire after 2 signal-TF candles. Pending setups expire after the group's expiry bars (scalping 12,
  intraday 16, swing 20), or as soon as a candle closes beyond the invalidation.
- **Timestamps:** signal time = close of the trigger candle; data time = close of the latest candle (and the quote time); generated
  at = the computation time.

## 6. Timeframes and profiles

Signal timeframes: M1, M3, M5, M15, M30, H1, H4, H8, D1, W1, MN1. MN1 needs 120 monthly candles, so it is UNKNOWN on today's data
and is reported that way. Each signal timeframe has a context timeframe (regime and direction) and a trigger timeframe (lower-TF
confirmation where a rule uses it):

| Group (stop and cost limits) | Signal TF -> context TF / trigger TF |
|---|---|
| Scalping | M1 -> M15 / -, M3 -> M30 / M1, M5 -> H1 / M1 |
| Intraday | M15 -> H1 / M5, M30 -> H4 / M5, H1 -> H4 / M15 |
| Swing | H4 -> D1 / H1, H8 -> D1 / H1, D1 -> W1 / H4 |
| Position | W1 -> MN1 / D1, MN1 -> - / W1 |

Groups and chains are configuration (`strategy_engine/config.py`, `CHAINS`, `GROUPS`). The trigger timeframe is reported, not required, in this version. Missing context data means the context is "unavailable": it is never
treated as agreement, and a strategy whose rule needs the context (A, C) then reports it as a missing condition.

## 7. Selector and conflicts

For each signal timeframe:
1. Classify the regime and list the compatible strategies.
2. Run them and build a plan for each ready or pending candidate. Rejected plans keep their reason.
3. **Duplicates:** same direction with entries within 0.5 ATR count as one market event. The most specific strategy is kept
   (E > B > F > A > C > D) and the other names are listed as agreeing.
4. **Conflicts:** qualified BUY and SELL on the same timeframe are never averaged. The side agreeing with the context direction
   wins when the context is known. Otherwise the result is **NO TRADE (conflict)**, explained with both setups.
5. **Ranking:** ready > pending, then context-aligned, then TP1 reward:risk, then the order above.

Instrument level: the best timeframe action by the same ranking. Scalping timeframes rank after intraday and swing ones when tied,
because costs weigh more there.

## 8. Decision vocabulary (customer-facing)

| Action | When |
|---|---|
| BUY / SELL | a ready candidate with a valid plan, data fresh, market open, spread normal |
| WAIT FOR BUY / WAIT FOR SELL | a pending candidate with a valid plan (exact entry price and condition), or a ready one blocked only by market hours or spread |
| EXIT | a tracked paper trade on the instrument meets an exit rule (stop, target, invalidation). It becomes the instrument's primary action, shown with the rule in an alert. The new-opportunity analysis stays visible beneath it, unchanged by the paper trade. |
| NO TRADE | nothing qualifies: per strategy the first failed rule, or the regime / data / conflict reason |

Each action carries:
- **technical status:** QUALIFIED, DEVELOPING, INVALIDATED or NO SETUP;
- **research status:** VALIDATED, NOT VALIDATED or INSUFFICIENT EVIDENCE. After Experiment 5 (no cell passed), five strategies are
  NOT VALIDATED and range mean reversion is INSUFFICIENT EVIDENCE (never enough signals to test); v1 rules are NOT VALIDATED;
- **the plan label:** "UNVALIDATED — HYPOTHETICAL TRADE PLAN" unless the strategy is validated.

Paper-trade management (HOLD / EXIT with the reason, entry, current price, SL, TP, unrealised R) is a separate block.

## 9. Signal lifecycle

States:
- DETECTED;
- WAITING FOR ENTRY or ENTRY READY;
- ENTRY TRIGGERED;
- ACTIVE;
- TP1 HIT, TP2 HIT, TP3 HIT;
- STOP LOSS HIT, INVALIDATED, EXPIRED, ENTRY MISSED.

Each new qualified plan is stored once (unique key: instrument, timeframe, strategy, direction, signal candle). The tracker steps
open records through 1-minute candles each minute:
- **Before entry:** a close beyond the invalidation means INVALIDATED; passing the expiry means EXPIRED; TP1 trading first means
  ENTRY MISSED; touching the entry price means ENTRY TRIGGERED, then ACTIVE.
- **After entry:** the stop is checked before targets inside a candle (conservative). TP1, TP2 and TP3 are recorded in order. TP3
  or the stop ends the record. The stop stays at the original level: no trailing, nothing invented.

These records are hypothetical signal tracking. They are not paper trades and never touch the paper account.

## 10. Risk management (`risk.py`)

Configurable:
- risk per trade (default 0.5% of equity);
- maximum concurrent trades (5);
- maximum aggregate open risk (2%);
- daily loss limit (2%);
- maximum drawdown from the equity peak (10%), which halts new entries;
- minimum TP1 reward:risk (1.5);
- spread filter (section 5);
- volatility filter (no entries in HIGH-VOLATILITY);
- currency exposure: each trade adds its risk to its currency legs (EURUSD BUY = +EUR −USD; XAUUSD BUY = +XAU −USD), and net
  exposure per currency is capped at 1.5%;
- session filter (below).

Position size = risk amount / (stop distance × contract size). Contract sizes: XAUUSD 100 oz, FX 100,000 units, US30 1 per point,
USOIL 1,000 barrels, BTCUSDT 1 coin. Sizing never increases after losses: no martingale, no grid, no averaging down.

## 11. Sessions and news

Sessions use zoneinfo:
- **Asia:** 00:00-07:00 London time.
- **London:** 08:00-16:30 London.
- **New York:** 08:00-17:00 New York.
- **Overlap:** London and New York both open.
- **Rollover:** 16:55-17:10 New York; no new entries.
- **Weekend reopen:** the first 60 minutes after the Sunday open; no new entries.

News: no free, reliable economic-calendar source exists (`AUDIT.md`, section 3), so the filter reports **unavailable**. It never
claims news is filtered.
