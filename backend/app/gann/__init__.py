"""W.D. Gann analysis: pure, causal maths (docs/gann/GANN_METHODOLOGY.md, docs/gann/GANN_ENGINE_DESIGN.md).

Nothing here reads files, the database or the network, except `astro`, which is a separate experimental module that the
core never imports. Every projection carries the anchor, unit, scale, tolerance and convention that produced it.
"""
