# Price-action rules (operational definitions)

Implemented in `backend/app/{candlestick,market_structure,price_action}` and exposed at `GET /patterns/definitions`. All detectors are deterministic, configurable via parameter dataclasses, return `Event`s (kind, direction, **confirmation time**, origin time, price/zone levels, evidence text, parameters) and are unit-tested in `tests/test_price_action.py`.

Notation: `body=|C−O|`, `range=H−L`, `upper=H−max(O,C)`, `lower=min(O,C)−L`. `ATR` = Wilder ATR(14). A detection describes the market; it does **not** imply a profitable trade.

## Candlestick (`CandleParams`)
| Pattern | Definition (defaults) |
|---|---|
| Bullish/Bearish engulfing | Opposite-colour prior bar; current body covers prior body (`O ≤ prior C` and `C ≥ prior O`, mirrored) and is larger |
| Hammer | `lower ≥ 2×body`, `upper ≤ 15% range`, `body ≥ 5% range`, after a decline (`close[i−1] < close[i−1−5]`, switchable) |
| Shooting star | Mirror of hammer after an advance |
| Doji | `body ≤ 10% range` |
| Pin bar | One wick ≥ 66% range, body ≤ 33% range, opposite wick ≤ 20% range |
| Morning / Evening star | Long (≥50% range) opposite bar; middle body ≤ 30% of first body; third bar closes beyond the first bar's midpoint |
| Inside / Outside bar | Range inside / engulfing the prior bar |

## Market structure
* **Swing high/low**: strictly higher/lower than `left=3` bars before and `right=3` after. Known only at `confirm_idx = idx + right` (no look-ahead). Labelled HH/LH/HL/LL against the previous swing of the same kind.
* **BOS**: first **close** beyond the latest confirmed, unbroken swing level in the direction of the prevailing trend (the very first break from "no trend" is a BOS flagged `initial`).
* **CHoCH**: a close beyond the latest swing level *against* the prevailing trend. Wick-only breaches are not breaks.
* **Equal highs/lows**: two swing highs (lows) within `0.1 ATR`, earlier one not exceeded in between.
* **Liquidity sweep**: a wick through a resting swing level with a close back inside; the level is consumed by the first bar that trades through it.

## Price-action concepts
| Concept | Definition (defaults) |
|---|---|
| **FVG** | Bullish: `low[i] > high[i−2]` (zone `[high[i−2], low[i]]`); bearish mirrored; size ≥ 0.1 ATR. Status: active → partially_filled → filled |
| **Order block** | For a structure break at bar *j*: take the impulse origin (extreme between the broken swing and *j*); OB = last opposite-colour candle at/before it (lookback 6), valid if displacement ≥ 1.5 ATR. Status: fresh → tested → invalidated (a **close** through the far edge) |
| **Breaker block** | An invalidated OB, polarity flipped, same zone |
| **Supply/Demand** | 1–3 bar base (each range ≤ 0.8 ATR) followed by an impulse bar (range ≥ 1.5 ATR, body ≥ 60%) closing beyond the base; status fresh/tested/broken |
| **Premium/Discount** | Position of the last close in the last confirmed swing range; >55% premium, <45% discount, else equilibrium |

Status fields of zones are computed as of the last bar given; features used for ML/analogues use only event *counts* keyed by confirmation bar, never statuses that peek forward.
