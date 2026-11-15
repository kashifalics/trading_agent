# Gann engine and Experiment 7: design (spec)

Status: approved section by section by the owner on 2026-11-15. This file is the spec that the implementation plan
argues from. The methodology, definitions and sources are in `GANN_METHODOLOGY.md` (referred to as **M** below).

## 1. Goal and owner decisions

**Goal.** Find out, with evidence, whether W.D. Gann's time cycles, price cycles, angles, Square of Nine, price-time
squaring and confluence add anything to the existing strategies. Show the calculations in the product without
letting them change any decision unless they prove themselves.

**Owner decisions (2026-11-15):**

| Question | Decision |
|---|---|
| Markets | XAUUSD and BTCUSDT now. EURUSD/GBPUSD run as an addendum only if their download ever completes (Dukascopy is refusing it). |
| Astronomical cycles | A separate experimental test in its own family. It is never imported by the core engine. |
| Test approach | Three tracks (timing, filters B–I, Gann-only J), capped in advance. |
| Components | As in section 3. |
| Experiment design | As in section 4. |
| Live display, dashboard and signals | As in section 6. |
| Testing and documents | As in section 7. |

**Standing rules** (from the brief and earlier experiments, all binding):
- **Data:** never read the XAUUSD sealed period (from 2023-06-24) or the BTCUSDT sealed period (from 2025-06-16),
  directly or indirectly.
- **Performance claims:** never fabricate performance. Never present a Gann method as validated, or promote one,
  without passing confirmation.
- **Production:** no change to production behaviour, no push, merge or deploy without the owner's approval. No live
  broker execution, no paid data or services, no exposed credentials.
- **History:** every earlier report and result stays as it is.

## 2. Scope

**Part 1 (this spec's first plan):**
- the `app/gann` maths package;
- the astro module;
- Experiment 7 (timing, filter and Gann-only tracks);
- the parameter register and pre-registration;
- the backtest report and limitations documents.

**Part 2 (planned after Part 1 results):**
- the live Gann layer;
- the API;
- the Gann Analysis page and chart overlays;
- the integration report.

**Out of scope:**
- the class C items in M §5;
- FX until its data exists;
- any automatic promotion of a Gann condition.

## 3. Components

### 3.1 `backend/app/gann/` (pure maths: no database, network or file access)

| Module | Responsibility |
|---|---|
| `anchors.py` | Minor anchors: `market_structure.swings.find_swings` (3/3). Major anchors: causal zigzag, reversal ≥ 5 × ATR(14) of the timeframe. Gann N-bar swing chart (N = 1, 2, 3). Every anchor has `t0`, `P0`, `kind`, `tf`, `tc` (confirmation time). |
| `time_cycles.py` | Windows from anchors in bars, sessions, calendar days, weeks, months and years. Fractional divisions, Square of Nine time counts, anniversaries, seasonal dates. A window exists only if it starts after `tc`. |
| `price.py` | Range divisions, extensions, swing price and time ratios, tick rounding. |
| `angles.py` | Fan lines `P0 ± r·s·(t − t0)` for r ∈ {1/8, 1/4, 1/3, 1/2, 1, 2, 3, 4, 8}, at scales `S_swing`, `S_atr` and `S_fixed`. Touch, break, retest and intersection events. Price-time balance points. |
| `squares.py` | Square of Nine: anchored levels `(√P0 ± θ/180)²` and exact cardinal and diagonal cross sets. Square of Four cross sets and Square of Twelve twelfths, both flagged experimental. |
| `confluence.py` | Clusters scored by the 6 independent families of M §4.12. Identities are merged before counting. |
| `state.py` | `gann_state(bars, i, params) -> GannState`: everything known at candle `i`, with its parameters. This is the only entry point research and live code may use. |
| `astro/` | Separate: ephemeris-based event dates, read with Skyfield from the public JPL DE421 file (licence checked before install). Never imported by `state.py`. |

**Conventions:**
- Every price is rounded to the instrument tick (XAUUSD 0.01, BTCUSDT 0.01).
- Every projection stores its anchor, unit, scale, tolerance and convention, so it can be reproduced exactly.

### 3.2 `backend/app/gold_research/exp7/`

**Modules:**
- `params.py`: loads and hashes the frozen register.
- `timing.py`: the timing track.
- `filters.py`: re-scores the Experiment 5 trades with the Gann state.
- `rules.py`: the J rules, turned into `sim.Orders`.
- `stats.py`: coverage-matched controls, reusing `exp6/stats.py`.
- `run.py`: `prereg` / `develop` / `confirm`, reusing Experiment 6's `write_once`, `require_committed` and `guard_once`.
- `report.py` and `__main__.py`.

**Reused parts:**
- signals and the simulator: Experiment 5 (`sim.simulate`, bid/ask, M1 intrabar resolution);
- controls and pre-registration guards: Experiment 6;
- data: the sealed-period refusal in `historical.store`.

## 4. Experiment 7

### 4.1 Data and stages

| | Development | Confirmation (run once) | Sealed (never read) |
|---|---|---|---|
| XAUUSD | 2003-05-05 → 2020-02-08 | 2020-02-08 → 2023-06-24 | from 2023-06-24 |
| BTCUSDT | 2017-08-17 → 2024-01-29 | 2024-01-29 → 2025-06-16 | from 2025-06-16 |

**Stages:**
1. **Register and pre-registration.** `docs/research/EXP7_parameters.json`, mirrored in
   `docs/gann/GANN_PARAMETER_REGISTER.md`, is hashed into `docs/research/EXP7_preregistration.json`. Both are
   committed before any outcome is computed, and `develop` refuses to run otherwise.
2. **Development run.** It only selects candidates from the fixed list, and nothing is tuned.
3. **Confirmation run.** It runs once, on the candidates.

**Rules for the confirmation period and for changes:**
- **Earlier use of the confirmation period.** Experiment 6 has already used the XAUUSD and BTCUSDT confirmation
  periods once. The report discloses this.
- **Late changes.** Any change after an outcome has been seen is a new, recorded trial.
- **Projections.** A window or level that falls in a sealed period is discarded, never evaluated.

### 4.2 Frozen settings (the register's initial values)

| Setting | Value |
|---|---|
| Cycle counts | 7, 14, 21, 28, 30, 45, 49, 60, 72, 90, 108, 120, 135, 144, 180, 216, 240, 270, 288, 360, 365.25 (calendar days; 365/366 merged). Multiple m = 1. |
| Fractions | 1/8, 1/4, 1/3, 3/8, 1/2, 5/8, 2/3, 3/4, 7/8 |
| Time window | ±max(1, round(0.025·N)) units |
| Seasonal dates | Mar 21, Jun 21, Sep 23, Dec 21 (cardinal); Feb 4, May 6, Aug 8, Nov 8 (mid-season), ±2 calendar days |
| Anniversary | the anchor's month-day in later years, ±2 calendar days (major anchors only) |
| Square of Nine | 45° steps, ±8 steps (±720°). Time counts: cardinal-cross numbers ≤ 400. Price normalization: dollars. |
| Angles | r ∈ {1/8 … 8}. Scales: `S_swing` (anchor swing range ÷ duration), `S_atr` (ATR(14) per bar at `tc`), `S_fixed` ($1 per calendar day, D1 only) |
| Anchors used | the latest 2 confirmed major highs and 2 major lows at each candle |
| Price tolerance | 0.1 × ATR(14), at least one tick |
| Coverage rule | if a method's windows cover more than 90% of candles, it is reported as "not testable: covers nearly every candle" and is not counted as a test |

### 4.3 Timing track (no trading)

**Unit of analysis.** Candles on H1, H4 and D1 (tested). M15 and W1 are reported for information only.

**Outcomes** (defined before testing; ATR is Wilder's ATR(14) of the previous candle):

| Outcome | Definition | Direction tested |
|---|---|---|
| Reversal | the candle is a 10-left/10-right fractal high or low | inside > outside |
| Volatility | true range ÷ ATR | inside > outside |
| Range expansion | true range > 1.5 × ATR | inside > outside |
| Direction change | sign(C[t+10] − C[t]) ≠ sign(C[t] − C[t−10]) | two-sided (direction change versus continuation) |

**Methods and timeframes.**

| Method | Timeframes |
|---|---|
| Whole cycles in candles | H1, H4, D1 |
| Whole cycles in calendar days | D1 |
| Fractions | H1, H4, D1 (subject to the coverage rule) |
| Anniversary | D1 |
| Seasonal | D1 |
| Price-time balance, `S_swing` | H1, H4, D1 |
| Price-time balance, `S_atr` | H1, H4, D1 |
| Price-time balance, `S_fixed` | D1 |
| Square of Nine time counts | H1, H4, D1 |

That is 19 method-timeframe pairs × 4 outcomes × 2 instruments = **152 time tests**.

**Price-level tests.**
- **Reaction outcome:** price touches the level (within tolerance), then reverses by 1 × ATR before it closes 1 × ATR
  beyond the level (first passage on M1).
- **Methods:** range divisions, Square of Nine levels, angles at `S_swing`, and angles at `S_atr`.
- **Count:** 4 methods × 3 timeframes × 2 instruments = **24 level tests**.

**Experimental levels, descriptive only.** Square of Four cross levels and Square of Twelve twelfths are run as
level tests on the same timeframes, with the same control. They belong to no family and cannot pass. Their numbers
are reported with that label.

**Statistic.** lift = mean outcome inside ÷ mean outside (for levels: reaction rate at Gann levels ÷ at control levels).

**Controls.**
- **Primary control:** 20,000 draws of random cycle lengths. Lengths are drawn uniformly from [7, 366], excluding
  every Gann count's tolerance band, applied to the same anchors, and matched to the same coverage. For levels,
  the draws are random offset levels at the same spacing.
- **p-value:** the share of draws whose lift is at least the real one.
- **Secondary control:** random shifts of the anchor times, reported only.

**Fallback if 20,000 draws prove too slow.** Measured on one year of data, before any outcome: 4,000 draws with a
Gaussian tail fit. The choice is recorded in the register.

**Family.** The timing family has 176 tests at most, minus any removed by the coverage rule.

### 4.4 Filter track (combinations B–I)

**Base trades.** The Experiment 5 baseline trades of both instruments (the set Experiment 6 used). Each trade is
re-scored with `gann_state` at its own signal candle, and the stored signal must be reproduced exactly (as in
Experiment 6).

**Arms.** A trade is kept when:

| Arm | Condition |
|---|---|
| B | a whole-cycle window (candles) is active |
| C | entry is within tolerance of a range division on the trade's supporting side |
| D-swing, D-atr | entry is at a price-time balance point |
| E-swing, E-atr | entry is on the trend side of the 1x1 angle from the latest major anchor |
| F | entry is within tolerance of a Square of Nine level |
| G | 2 or more independent families agree at entry |
| H | G holds and VSA is PASS |
| I | G holds and trend is PASS |

This gives 10 arms × 2 instruments = **20 tests**, pooled across strategies. The per-strategy breakdown is
descriptive.

**Control.** Experiment 6's random filter with the same keep rate, stratified by timeframe × direction × year
(20,000 draws).

**Pass rules.** Experiment 6's six development conditions (`EXPERIMENT_6_PLAN.md` §6): kept mean above baseline;
Holm p < 0.05 across the trading family; kept profit factor and Sharpe at least the baseline's; positive in ≥ 60% of
development years with ≥ 20 kept trades; still positive at doubled costs; ≥ 300 kept trades. Confirmation follows §4.7.

### 4.5 Gann-only track (J)

| Rule | Trigger (all from the existing detectors where possible) | Direction |
|---|---|---|
| J1 | CHoCH on a candle inside an active whole-cycle window from a major anchor | CHoCH direction |
| J2 | wick touches a Square of Nine level (latest major anchor) and closes ≥ 0.25 × ATR back | away from the level |
| J3 | the same, at the 50% level of the latest major swing | away from the level |
| J4 | close through the `S_swing` 1x1, then a retest within 10 candles that closes back in the break direction | break direction |
| J5 | J2-style rejection at a zone where 2 or more families overlap | away from the zone |
| J6 | liquidity sweep inside a seasonal window | sweep-reversal direction |

**Execution.**
- **Timeframes:** H1, H4 and D1, which gives 6 rules × 3 timeframes × 2 instruments = **36 tests**.
- **Entry:** the next candle's open.
- **Stop:** structural, beyond the trigger's extreme. The minimum risk is Experiment 5's (0.25 × ATR).
- **Primary exit (pre-registered):** 2R, the stop, or Experiment 5's time stop, whichever comes first.
- **TP1 to TP3:** TP1 is the nearest Gann level at least 1R away (otherwise 1R), TP2 is 2R, and TP3 is the next
  Gann level (otherwise 3R). These are reported descriptively.
- **Control:** direction-matched random entries in the same timeframe and session (Experiment 5's `with_controls`).

**Trading family.** The trading family is filters + J = **56 tests** at most.

### 4.6 Astro family (separate)

**Data.** Geocentric ecliptic longitudes, from Skyfield and DE421.

**Events, each with a ±2 calendar day window on D1:**
- new and full moon;
- Mercury stations;
- Mars–Jupiter conjunction, square and opposition;
- Mars–Saturn conjunction, square and opposition.

Sun ingresses into cardinal signs are left out, because they are the seasonal cardinal dates (an identity).

**Outcomes and tests.** Reversal and volatility, giving 4 events × 2 outcomes × 2 instruments = **16 tests**. Its own
Holm correction. It never affects the other families.

### 4.7 Statistics and pass criteria

**Sample-size floors.** These look at counts only:
- timing: at least 200 candles inside windows and 30 inside-window events;
- filters: at least 300 kept trades in development (as Experiment 6);
- J rules: at least 100 trades in development (new rules fire less often; the floor is fixed before any outcome).

**Development candidate** (as strict as Experiment 6). The effect is in the claimed direction, and the control
p-value is Holm-adjusted p < 0.05 across the whole family. For filters, the other five Experiment 6 conditions also
hold (§4.4). For J, the mean R after costs is above 0 at both normal and doubled costs, and positive in ≥ 60% of
development years with ≥ 20 trades.

**Confirmation.** Holm-adjusted p < 0.05 across each family's candidates, with the effect in the same direction.
For trading, the mean R after costs must also be above 0.

**Intervals.** Cluster-robust by week.

**Also reported:**
- for every trading test: win rate, average win and loss, expectancy, profit factor, maximum drawdown, Sharpe,
  Sortino, holding period;
- breakdowns by timeframe, instrument, regime, year and direction;
- cost sensitivity: real bid/ask, plus $0.10 and $0.30 slippage (XAUUSD) and the 0.1% per side taker fee (BTCUSDT);
- the swap scenario for holds past 17:00 New York;
- DSR, with the trial count updated from 2,115 by every test run.

**Interpretation.** A volatility or expansion effect without a reversal or direction effect is reported as timing
information, not as a trading edge.

## 5. Planted-effect and null checks (must pass before the development run)

1. **Random-walk data.** The timing lifts have a median of about 1. The share of tests with p < 0.05 is at most about
   5%. The filters are indistinguishable from random.
2. **A planted effect.** Reversals are injected at cycle dates, and the timing track must detect them. A planted
   trading edge at Square of Nine levels must also be detected.
3. **No look-ahead.** `gann_state` at candle `i` must be identical on full data and on data cut at `i`.

## 6. Part 2: live display, dashboard and signals (planned after Part 1)

**The live engine.**
- **Same calculation as the research.** The engine calls `gann_state` on the same candles the engine uses. A test
  asserts that the live block equals the research calculation.
- **Signal card.** Each signal card gets a Gann block: windows, anchor, cycle, levels, families and parameters.
  The VSA, momentum and structure verdicts come from the existing confirmation layer.
- **No effect on decisions.** Gann never changes BUY, SELL, WAIT FOR BUY, WAIT FOR SELL, EXIT or NO TRADE. A Gann
  condition becomes a gate only if it passes confirmation **and** the owner approves (the same mechanism as
  `config.GATES`).

**History depth.** The live layer loads daily and weekly history at least as long as the research used. If it can't,
the block shows UNAVAILABLE. It never shows a calculation from a shorter window.

**J-rule plans.** These appear only on the Gann page, labelled "hypothetical, not validated", with the fields from
Phase 11 of the brief. They never reach the main signals or the paper account unless a J rule passes and the owner
approves.

**API.** `GET /gann/{symbol}?tf=`, `GET /gann/{symbol}/calendar` and `GET /gann/research`, all behind the existing
key authentication.

**Frontend.**
- **Gann Analysis page.** A new `/gann` page, after Gold Research in the sidebar. It shows:
  - the cycle calendar and upcoming windows;
  - anchors, fan levels and Square of Nine levels;
  - balance points, confluences and cycle status;
  - the VSA and structure verdicts;
  - a research panel.
- **Chart overlays.** Overlays on `/chart`, each labelled *historical observation*, *calculated projection*,
  *confirmed reaction* or *hypothetical opportunity*.

**Release.** Production changes only with the owner's approval. Paper trading is unchanged.

## 7. Testing and documents

**Tests:**
- **Formulas:** every formula, checked against hand-computed values (for example, Square of Nine at $2,000 +90° =
  $2,044.97, and the cross sets equal the built spiral).
- **Calendar:** the 17:00 New York boundary across DST changes, month arithmetic, 365/366, weekends, holidays and
  missing candles.
- **No look-ahead:** prefix equality; no anchor before `tc`; no projection from a later anchor.
- **Guards:** `develop` refuses without a committed pre-registration, `confirm` runs once, and loading sealed
  timestamps is refused.
- **Checks:** the null and planted checks of section 5.
- **Part 2:** API, frontend unit, end-to-end (with `/gann` added), accessibility and phone-width tests.
- **No weakening:** no existing test is weakened, and the full suite runs at every task.

**Documents** (in `docs/gann/`):
- `GANN_METHODOLOGY.md`: done.
- `GANN_ENGINE_DESIGN.md`: this file.
- `GANN_PARAMETER_REGISTER.md`.
- `GANN_BACKTEST_REPORT.md`: generated. It includes every failed variant, the trial count and the Phase 20 answers.
- `GANN_LIMITATIONS.md`.
- `GANN_INTEGRATION_REPORT.md`: Part 2.

**Runtime.** Time one year of data first, then quote the full-run estimate.

## 8. Phase 20 questions and where each is answered

| Question | Answered by |
|---|---|
| 1–2. Implemented and reproducible | the module list (§3) and the formula tests (§7) |
| 3. Timing information | the timing family (§4.3) |
| 4. Directional accuracy | the reversal and direction-change outcomes, and J (§4.3, §4.5) |
| 5. Expectancy after costs | the filters and J (§4.4–4.5) |
| 6. Drawdown | the trading metrics (§4.7) |
| 7. No improvement | every test that fails, all listed |
| 8. Too subjective | the class C list in M §5 |
| 9. Improvement over baseline | the filter family against random filters |
| 10. Deserves forward paper testing | only methods that pass confirmation, and only with the owner's approval |
