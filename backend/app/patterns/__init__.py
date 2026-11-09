"""Pattern library (brief Part 4): registry of definitions plus one detector module per family.

FAMILY_DETECTORS lists the detect(ctx) functions run on every chunk; importing the modules registers their PatternSpecs."""
from app.patterns import (  # noqa: F401  (registration side effects)
    candles,
    chart,
    imbalance,
    liquidity,
    platform,
    sr,
    structure,
    volatility,
    zones,
)

FAMILY_DETECTORS = [candles.detect_ctx, structure.detect, liquidity.detect, imbalance.detect, zones.detect, sr.detect,
                    volatility.detect, chart.detect]
