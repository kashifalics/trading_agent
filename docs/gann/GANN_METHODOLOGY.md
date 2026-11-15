# W.D. Gann methodology audit

Status: research audit (Phase 1 of the Gann brief), written 2026-11-15 before any Gann code.
Nothing here is evidence that a method works. It defines each method precisely enough to test,
says where the definition comes from, and says what cannot be tested.

## 1. How to read this document

Every concept gets two grades.

**Source status**
- **P (primary):** stated in Gann's own published books (*Truth of the Stock Tape* 1923, *Wall Street Stock
  Selector* 1930, *New Stock Trend Detector* 1936, *How to Make Profits in Commodities* 1941/1951,
  *45 Years in Wall Street* 1949). The rule is Gann's, though often loosely worded.
- **S (secondary):** found only in courses attributed to Gann or in later authors' readings of them. The
  wording varies between sources.
- **M (modern):** a convention introduced by software or later authors (for example a scaling rule). Not Gann's.

**Testability class**
- **A:** objective as stated. One reasonable definition exists.
- **B:** testable only after we choose a convention (a scale, a tolerance, an anchor rule). Several reasonable
  choices exist, so each choice is a separate trial and is frozen before validation.
- **C:** not reproducible: no objective definition exists, or every definition is a modern invention
  presented as Gann's. Documented, not tested.
- **X:** experimental and kept apart from the core engine (astronomical methods, Square of Twelve).

## 2. What the research found

1. **No controlled published test supports Gann's methods.** The searches found only trading-education
   pages, indicator documentation and two 2025 papers. One applied Gann Fan and Square of Nine to XAUUSD
   minute charts from 2023-10-06 to 2024-04-03 (Mhmood et al., *Int. J. Financial Management and Economics*
   8(2), DOI 10.33545/26179210.2025.v8.i2.550). The other read GannZilla time angles on GBPUSD
   (Al-Husseini et al., *IJSBMES* 4(5), 2025). Both are descriptive chart readings. Neither uses transaction costs,
   a baseline, out-of-sample data or a multiple-testing correction. One uploaded backtest of a
   "traditional" Square of Nine system reported consistent losses. It is unverified.
2. **The relevant scientific result is about data snooping.** Sullivan, Timmermann & White (1999,
   *Journal of Finance* 54(5)) tested thousands of technical trading rules on 100 years of the Dow with
   White's Reality Check. The best rule's apparent edge vanished once the search over rules was accounted
   for. Gann's methods offer far more free choices than those rules (anchor, count, unit, scale, angle,
   tolerance), so the same correction is mandatory here.
3. **Gann withheld key details.** He called his "Master Time Factor" a secret he would not reveal.
   Anything sold as that method is someone else's reconstruction (class C).
4. **Many conventions conflict between sources.** Square of Nine step size, angle naming and the
   construction of the Square of Four and Square of Twelve all differ. Where the mathematics settles a
   conflict, section 4 says so. Where it does not, every reasonable convention is a separate trial.
5. **Cycle windows cover most of the calendar.** This is the most important design fact, computed here:

   | Windows from ONE swing, first 720 days, using the brief's 22 counts | Share of all days inside a window |
   |---|---|
   | whole cycles only, exact day | 18% |
   | whole cycles, ±1 day | 49% |
   | whole cycles, ±2 days | 73% |
   | whole cycles plus 1/8 … 7/8 divisions, ±1 day | 99% |
   | five swings, whole cycles only, ±1 day | 68% |

   So "the market turned on a Gann date" is true almost every day by construction. A cycle can only
   count as evidence if turns happen **more often inside its windows than outside them**, and more often
   than inside windows of random cycle lengths that cover the same share of days.

## 3. Shared definitions

- **Bar:** an OHLC candle of one timeframe built from the cleaned Dukascopy M1 bid/ask data (XAUUSD) or the
  Binance archive (BTCUSDT). Bars exist only for traded time, so a gap-free bar count is not calendar time.
- **Anchor:** a confirmed swing high or low. Price `P0`, extreme time `t0`, timeframe, and **confirmation
  time `tc`**. The anchor is unknown before `tc`, and nothing may be projected from it before `tc`.
  - Minor anchors: the existing fractal swing (`find_swings`, 3 bars each side; `tc = t0 + 3 bars`).
  - Major anchors: a swing that reverses by at least `k × ATR(14)` (a causal zigzag). Its `tc` is the first
    bar at which the reversal reaches the threshold. `k` is frozen before validation.
- **Time units:** bars of the anchor timeframe; trading sessions (FX day boundary 17:00 New York); calendar
  days; weeks; months; years. Every projection stores its unit.
- **Scale `s`:** price units per time unit. It is needed by angles and by price-time squaring. Three conventions:
  - `S_swing` (M): the anchor swing's own range divided by its own duration. This is the swing's "natural 1x1".
  - `S_atr` (M): ATR(14) of the anchor timeframe at `tc`, per bar.
  - `S_fixed` (P in spirit, M in value): a fixed dollar amount per calendar day. Gann used 1 point per day
    and larger blocks for high-priced markets.

  Gann's own 1-point-per-day rule cannot be applied to gold that moved from $350 to $4,000. Every scale is
  therefore a convention, and the angle and squaring results are reported for each scale.
- **Tolerance:** price tolerance in ATR multiples, rounded to the instrument's tick (XAUUSD 0.01, BTCUSDT
  0.01). Time tolerance in units. Both are frozen before validation.
- **Price normalization for the Squares:** the price is mapped to a number before taking square roots.
  XAUUSD uses dollars. EURUSD and GBPUSD would use pips ×10⁴. BTCUSDT uses dollars. The mapping is part of
  the convention and is stored.

## 4. The concepts

Each entry: **claim → definition → parameters → class → limitations**.

### 4.1 Time cycles (brief items 1, 11, 12, 15)
- **Claim (P):** important highs and lows recur at fixed counts of days, weeks, months and years from a
  previous major high or low. Gann stresses 30, 45, 60, 90, 120, 180 and 360 units and their divisions.
- **Definition:** for anchor `(t0, tc)`, cycle `N` and multiple `m = 1, 2, …`, the window is
  `[t0 + m·N − w, t0 + m·N + w]` in a stated unit. A window is used only if it starts after `tc`.
  Fractional windows use `m·N·f` with `f ∈ {1/8, 1/4, 1/3, 3/8, 1/2, 5/8, 2/3, 3/4, 7/8}`.
- **Parameters:** the counts (the brief's list: 7 … 360, 365/366), the unit, the multiples, the fractions, the window `w`.
- **Class:** B. The rule is objective once counts, unit and `w` are frozen.
- **Limitations:** coverage (section 2.5). The list mixes numbers from different traditions
  (7, 49 = 7²; 144 = 12²; 72, 108, 216, 288 as divisions of 360). There are a large number of variants:
  22 counts × 6 units × 9 fractions × anchors.

### 4.2 Price cycles and geometric divisions (items 2, 10, 16)
- **Claim (P):** a range from a major low `L` to high `H` divides into eighths and thirds. The 50% point is the
  most important. Price often stops at these levels.
- **Definition:** `level(f) = L + f·(H − L)` for `f ∈ {1/8, 2/8, 1/3, 3/8, 1/2, 5/8, 2/3, 6/8, 7/8}`, and
  extensions `f > 1` (1 1/8, 1 1/4, 1 1/2, 2). Measured down from `H` for falls. Rounded to tick.
- **Square-root relationships:** distances measured in √price (see 4.6).
- **Swing symmetry:** for successive swings `k-1, k`: price ratio `|ΔP_k| / |ΔP_{k-1}|` and time ratio
  `Δt_k / Δt_{k-1}`. The claim is that these cluster at simple ratios (1/2, 1, 2).
- **Class:** A for divisions, B for symmetry (the tolerance around a "simple ratio").
- **Limitations:** with nine levels inside every range, some level is always within about 6% of the range
  of any price. A test needs reaction rates at levels versus at random offset levels.

### 4.3 Squaring price and time (items 3, 16, 20)
- **Claim (P/S):** a trend change is likely when price and time "balance". Forms:
  - (a) **Squaring the range:** time elapsed since the range ended equals the range in price units.
  - (b) **Squaring the low or high:** time elapsed from a low (or high) equals that price in time units.
  - (c) Comparing the previous swing's duration with the current swing's price movement, and the reverse.
- **Definition with a scale `s`:**
  - (a) `t − t_end = (H − L) / s`
  - (b) `t − t0 = P0 / s`
  - (c) `ΔP_k / s = Δt_{k-1}` and `Δt_k = ΔP_{k-1} / s`
- **Identity:** form (a) and every price-time "balance point" with scale `s` lie on the **1x1 angle** drawn
  with the same `s` (section 4.4). In the confluence engine they are the **same evidence**, not two confirmations.
- **Class:** B. The scale decides everything. Form (b) on gold at $1 per day means a low at $1,045 is "squared"
  after 1,045 days. It is meaningful only for daily and weekly anchors.
- **Limitations:** results may hold for one scale and fail for another. Each scale is its own trial,
  and a method that works under only one of several scales is treated as unconfirmed.

### 4.4 Gann angles and fans (items 4, 5, 17, 18)
- **Claim (P):** lines from a major low (rising) or high (falling) at fixed price-per-time rates act as
  support and resistance. The 1x1 is the most important. A break of the 1x1 signals a change of trend.
- **Definition:** `angle_r(t) = P0 ± r · s · (t − t0)` for
  `r ∈ {1/8, 1/4, 1/3, 1/2, 1, 2, 3, 4, 8}`.
  - **Naming:** price × time. "2x1" means 2 price units per 1 time unit (steeper). "1x2" means 1 price unit
    per 2 time units (flatter). Some sources reverse the names, so the stored value is the numeric `r`, not the label.
  - **Commonly quoted degrees:** Gann's figures are 1x1 = 45°, 2x1 = 63¾°, 1x2 = 26¼°, 3x1 = 71¼°,
    4x1 = 75°, 8x1 = 82½°. These are only true on a chart drawn at scale `s`. True arctan(2) is 63.43°,
    so Gann's figures are rounded.
  - **A fan** is the set of all nine angles from one anchor.
- **Events:** touch (within tolerance), close-through (break), retest after a break, transition to the next
  angle, and intersections of angles from different anchors.
- **Class:** B (scale, time unit).
- **Limitations:** on a screen, the "45°" depends on chart zoom. Here it depends only on `s`, which is stored.
  Angles are never redrawn from later anchors.

### 4.5 Gann trend lines and swing charts (items 12, 17, 21)
- **Claim (P):** Gann's "trend line" is a swing chart. With an N-day chart, the line turns up after N
  consecutive higher highs and down after N consecutive lower lows. A trend change is confirmed when price
  breaks the last swing bottom (or top). A campaign is the sequence of swings in one trend.
- **Definition:** the N-bar swing chart (N = 1, 2, 3), a mechanical rule known at the bar it turns.
  Trend change means a break of the previous swing extreme, close to the existing BOS/CHoCH detectors.
- **Class:** A.
- **Limitations:** it largely overlaps the existing market-structure module. It must be tested for
  *incremental* value over BOS/CHoCH, not as new information.

### 4.6 Square of Nine (items 6, 9)
- **The chart:** the integers spiral out from 1 at the centre, and ring `k` holds `8k` numbers. On one diagonal
  sit the odd squares 1, 9, 25, 49, …, whose square roots rise by **2 per full turn (360°)**. This settles the step-size conflict in the sources: the convention used by some tools
  (360° = +1 in the square root) does not match the spiral itself, so it is not used.
- **Anchored levels (S):** `level(θ) = (√(P0) ± θ/180)²` for `θ ∈ {45°, 90°, 135°, 180°, 225°, 270°, 315°, 360°, …}`.
  Worked example: anchor $2,000.00, +90° → (44.7214 + 0.5)² = $2,045.0. −180° → (44.7214 − 1)² = $1,911.6.
- **Cross membership (S):** exact integer sets on the spiral, for ring `k`.
  - **Cardinal cross:** 4k² − 3k + 1, 4k² − k + 1, 4k² + k + 1, 4k² + 3k + 1.
    That gives 2, 4, 6, 8, 11, 15, 19, 23, 28, 34, 40, 46, …
  - **Diagonal cross:** 4k² − 2k + 1, 4k² + 1, 4k² + 2k + 1, (2k + 1)².
    That gives 3, 5, 7, 9, 13, 17, 21, 25, 31, 37, 43, 49, …
  - Both were checked by building the spiral numerically.
- **"Fixed cross":** in Gann literature this term comes from astrology (the fixed signs, 45° from the
  cardinal points). On the Square of Nine it is read as the diagonal cross. In time it is read as the
  mid-season dates. We use those two readings and label the term as ambiguous.
- **Parameters:** the anchor, the price normalization (section 3), the degree set, and the tolerance.
- **Class:** B.
- **Limitations:** levels are dense. 45° steps near $2,000 are about $22 apart, so price is never more than
  about $11 from a level. "Price reacted near a level" therefore needs a random-level control.

### 4.7 Square of Four (item 7)
- **Status:** S/M. Gann never published its construction. Software (Optuma) draws a spiral starting with
  four numbers in the centre, whose rings carry the even squares 4, 16, 36, …
- **Mathematical finding:** the even squares also rise by 2 in √ per ring. Anchored projections
  `(√P0 ± θ/180)²` are therefore **identical** to the Square of Nine's. Only the absolute cross sets differ
  (even squares instead of odd squares).
- **Plan:** implement the absolute cross sets only, as experimental. Never count an anchored Square of Four
  level as separate from the Square of Nine.
- **Class:** X.

### 4.8 Square of Twelve (item 8)
- **Status:** S/M. Gann courses mention a 12×12 "Square of 144". No construction rule is published, and modern
  tools disagree (for example Mikula's 12×24 layout).
- **Plan:** an experimental reading as **twelfths**: price levels `L + (j/12)(H − L)`, and time divisions of a
  cycle into twelfths (30° steps of 360). Labelled "modern interpretation".
- **Overlap:** the twelfths coincide with 1/4, 1/3, 1/2, 2/3 and 3/4 from 4.2 at j = 3, 4, 6, 8, 9, and those
  are not counted twice.
- **Class:** X.

### 4.9 Anniversary dates (item 13)
- **Claim (P):** markets react near the calendar anniversary of a major high or low.
- **Definition:** the window `[same month-day in year y + n] ± w days`, for major anchors.
- **Identity:** this is the 365/366-day cycle in calendar days (4.1), and must not be counted twice.
- **Class:** A/B (`w`).

### 4.10 Seasonal cycles and natural periods (items 14, 15)
- **Claim (P):** "seasonal time changes" matter. Gann watched dates near the equinoxes and solstices
  (about Mar 21, Jun 21, Sep 23, Dec 21) and the mid-season dates (about Feb 4, May 6, Aug 8, Nov 8).
- **Definition:** fixed calendar windows ± `w` days, independent of any anchor (the "cardinal" and
  "fixed" dates in time).
- **Class:** A.
- **Limitations:** for gold, this overlaps known calendar effects (month-end, holidays), which must be
  controlled by comparing with other calendar dates.

### 4.11 Support and resistance, vibration and price levels (items 18, 19)
- **Support and resistance (P):** old tops and bottoms, range divisions and angles. These are already covered by
  4.2, 4.4 and the existing level detector. No new method is added.
- **"Law of vibration" (P, undefined):** Gann never defined it mathematically. Versions sold as "the
  vibration of gold" (fixed dollar increments) are modern and arbitrary. **Class C.** The testable remainder,
  "repeated price intervals", is part of the swing-symmetry test in 4.2.

### 4.12 Time and price confluence (items 20, 22)
- **Definition:** a cluster forms when at least two **independent families** give a time window and a price
  zone that overlap within the frozen tolerances.
- **Independent families (after removing the identities above):**
  1. time cycles, including anniversaries;
  2. seasonal dates;
  3. range divisions, including the Square of Twelve twelfths;
  4. Square of Nine levels, including the Square of Four;
  5. angles, including price-time squaring;
  6. swing symmetry.
- **Score:** the score counts families, not levels. Twenty Square of Nine levels near a price count once.
- **Class:** B.

### 4.13 Major trend changes and campaigns (item 21)
- **Definition:** campaign length (bars, price) is the sum of the swings between trend changes (4.5).
- **Use:** comparisons with previous campaigns are descriptive only.
- **Class:** B, descriptive. It is not a trading rule.

### 4.14 Reversal windows (item 22)
A projected window is a **timing alert**. A trade still needs a price trigger from the existing engine:
a rejection from the projected zone, a confirmed BOS or CHoCH, a liquidity sweep, a failed breakout, or a
confirmed momentum reversal. A window alone never produces BUY or SELL.

### 4.15 Astronomical cycles (brief, separate module)
- **Status:** some Gann readers link his time counts to planetary cycles. This is not established in his
  published books, and there is no scientific mechanism for it.
- **If implemented:** a separate experimental module, never inside the core engine.
  - Geocentric ecliptic longitudes from NASA JPL's public DE ephemeris, read by a free Python library
    (Skyfield; its licence is to be confirmed before any install).
  - Events: conjunctions, squares (90°) and oppositions (180°) between named pairs, and ingresses into
    cardinal signs.
  - Tested exactly like seasonal dates: event-window rates against random-date windows with the same coverage.
- **Class:** X.

## 5. Not testable (class C), and why

| Item | Reason |
|---|---|
| Master Time Factor | Gann kept it secret. Every version sold today is a reconstruction. |
| Law of vibration | It has no mathematical definition in Gann's books. |
| "Natural" or esoteric numerology beyond the stated counts | It has no rule that could be checked. |
| Hand-drawn angle choice ("the right anchor") | It is decided after seeing the chart, so it can't be tested without look-ahead. Anchors here are chosen by fixed rules only. |

## 6. Consequences for the test design (inputs to the spec)

1. **Coverage control.** Every time test compares event rates inside versus outside windows, against random
   cycle lengths and random anchors with the **same coverage**.
2. **Level control.** Every price-level test compares reaction rates at Gann levels against randomly offset
   levels with the same density.
3. **Identities removed** before counting confirmations (sections 4.3, 4.6–4.10, 4.12).
4. **Scale, unit, tolerance and anchor rule** are trial dimensions. They are frozen and registered before
   validation, and added to the running trial count (2,115 after Experiment 6).
5. **Outcomes defined before testing:**
   - reversal (a confirmed swing extreme of at least `k × ATR` inside the window);
   - volatility (true range / ATR);
   - range expansion;
   - continuation versus reversal of the prior N-bar direction.

   A volatility effect without a direction effect is reported as timing information, not as a trading edge.
6. **Research rules from Experiments 5 and 6 still apply:**
   - the XAUUSD sealed test (from 2023-06-24) is never read;
   - the BTCUSDT sealed period (from 2025-06-16) is never read;
   - the validation period runs once, after pre-registration is committed;
   - Holm correction across the family;
   - realistic bid/ask costs with M1 intrabar ordering.

## 7. Sources

- Gann, W.D.: *How to Make Profits in Commodities* (1941, rev. 1951); *45 Years in Wall Street* (1949).
  Secondary summaries were used where scans were not available. Rules marked P are as commonly quoted from
  these, and are to be confirmed against a full text where possible.
- Sullivan, Timmermann & White (1999), "Data-Snooping, Technical Trading Rule Performance, and the
  Bootstrap", *Journal of Finance* 54(5): 1647–1691.
- Mhmood, Ghaffoori & Mhameed (2025), "Analysis of the effect of fan Gann and square nine in the forex
  market (XAUUSD)", *Int. J. Financial Management and Economics* 8(2): 26–36.
- Al-Husseini, Al-Janabi & Al-Majidi (2025), "Analyzing forex market prices using the circular shape and
  the hexagonal star…", *IJSBMES* 4(5).
- Gann angles: [Wikipedia](https://en.wikipedia.org/wiki/Gann_angles), [Barchart](https://www.barchart.com/trader/help/chart/gann.php),
  [LuxAlgo](https://www.luxalgo.com/library/concept/gann-fan-and-angles/).
- Square of Nine conventions: [LuxAlgo](https://www.luxalgo.com/library/concept/gann-square-of-9-levels/),
  [TradingSim](https://www.tradingsim.com/day-trading/day-trade-using-gann-square).
- Square of Four and Twelve: [Optuma, Square of Four](https://help.optuma.com/kb/faq.php?id=652),
  [Optuma, price units](https://www.optuma.com/kb/optuma/gann-and-astro/price-units-factors-and-harmonics-for-gann-tools).
- Time cycles and anniversaries: [LuxAlgo](https://www.luxalgo.com/library/concept/gann-time-cycles-anniversaries/),
  [Cycles Research Institute](https://cyclesresearchinstitute.org/cycles-research/economy/markets/w-d-gann/).
- Ephemeris: [Skyfield](https://rhodesmill.org/skyfield/planets.html).
