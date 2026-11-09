"""Registry entries for the patterns produced by the platform's existing detectors (app/market_structure, app/price_action), which
the live signal engine also uses. Their code is reused unchanged; only the definitions are recorded here."""
from app.patterns.registry import spec

spec(id="BOS", family="B", name="Break of Structure (bullish / bearish)", direction="both",
     definition="first close beyond the most recent confirmed, unbroken swing high (low) (swings 3 left / 3 right), in the direction of "
                "the prevailing structure or from no structure",
     invalidation="the origin of the move that broke the level (lowest low / highest high since the broken swing)")
spec(id="CHoCH", family="B", name="Change of Character (bullish / bearish)", direction="both",
     definition="a break of structure against the prevailing structure trend",
     invalidation="the origin of the move that broke the level")
spec(id="liquidity_sweep", family="C", name="Swing Liquidity Sweep (buy-side / sell-side)", direction="both",
     definition="a candle trades beyond a confirmed swing high (low) of the last 150 candles and closes back inside; bearish above highs, "
                "bullish below lows", invalidation="the sweep candle's extreme")
spec(id="equal_highs", family="C", name="Equal Highs", direction="bearish",
     definition="two confirmed swing highs within 0.1 ATR, the earlier not exceeded in between (resting buy-side liquidity)",
     invalidation="1 ATR (no structural level)")
spec(id="equal_lows", family="C", name="Equal Lows", direction="bullish",
     definition="two confirmed swing lows within 0.1 ATR, the earlier not exceeded in between (resting sell-side liquidity)",
     invalidation="1 ATR (no structural level)")
spec(id="fvg", family="D", name="Fair Value Gap (bullish / bearish), first mitigation", direction="both", entry="zone_limit",
     definition="three candles with low[i] > high[i-2] (bullish) or high[i] < low[i-2] (bearish), gap >= 0.1 ATR; traded on the first "
                "return into the gap", invalidation="the far edge of the gap")
spec(id="order_block", family="E", name="Order Block (bullish / bearish), first mitigation", direction="both", entry="zone_limit",
     definition="last opposite candle before the impulse that produced a break of structure, displacement >= 1.5 ATR",
     invalidation="the far edge of the block")
spec(id="breaker_block", family="E", name="Breaker Block", direction="both", entry="zone_limit",
     definition="an order block that a candle closed through; the zone flips polarity", invalidation="the far edge of the zone")
spec(id="demand_zone", family="E", name="Demand Zone (bullish supply/demand reaction)", direction="bullish", entry="zone_limit",
     definition="1-3 base candles (range <= 0.8 ATR) followed by an up impulse (range >= 1.5 ATR, body >= 60%) closing above the base",
     invalidation="the base low")
spec(id="supply_zone", family="E", name="Supply Zone (bearish supply/demand reaction)", direction="bearish", entry="zone_limit",
     definition="1-3 base candles followed by a down impulse closing below the base", invalidation="the base high")
spec(id="breakout", family="F", name="Support / Resistance Breakout", direction="both",
     definition="close beyond a support/resistance band (2+ clustered swings within 0.5 ATR) by >= 0.25 ATR after closing behind it",
     invalidation="the far side of the broken band")
spec(id="retest", family="F", name="Breakout Retest (role flip)", direction="both",
     definition="within 12 candles of a breakout, price trades back into the band and closes on the breakout side",
     invalidation="the far side of the band")
spec(id="failed_breakout", family="F", name="Failed Breakout / False Breakdown (breakout trap)", direction="both",
     definition="within 5 candles of a breakout, a close back on the original side of the band; direction is against the breakout",
     invalidation="the extreme since the breakout")
