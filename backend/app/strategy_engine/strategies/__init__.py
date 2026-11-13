"""The six independent strategy modules (DESIGN section 4), in the order of specificity used for de-duplication."""
from app.strategy_engine.strategies.breakout_retest import BreakoutRetest
from app.strategy_engine.strategies.momentum_continuation import MomentumContinuation
from app.strategy_engine.strategies.range_reversion import RangeReversion
from app.strategy_engine.strategies.sweep_reversal import SweepReversal
from app.strategy_engine.strategies.trend_pullback import TrendPullback
from app.strategy_engine.strategies.volatility_expansion import VolatilityExpansion

STRATEGIES = {s.key: s for s in (TrendPullback(), BreakoutRetest(), MomentumContinuation(), RangeReversion(), SweepReversal(),
                                 VolatilityExpansion())}
