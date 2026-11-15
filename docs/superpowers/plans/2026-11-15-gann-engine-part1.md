# Gann engine and Experiment 7 (Part 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure Gann maths package and run Experiment 7 (timing, filter and Gann-only tracks, plus the separate astro family) on XAUUSD and BTCUSDT, up to the backtest report.

**Architecture:**
- `backend/app/gann/` is pure maths, with no I/O except the astro ephemeris loader. A causal `panel()` serves research and a `gann_state()` serves display. Both share the same helpers, and both are proved causal by prefix tests.
- `backend/app/gold_research/exp7/` reuses the Experiment 5 simulator and signals and the Experiment 6 controls and guards.

**Tech Stack:** Python 3.12, numpy, polars, the existing `gold_research` modules, Skyfield (astro only, licence checked first), pytest, ruff.

**Spec:** `docs/gann/GANN_ENGINE_DESIGN.md`. Definitions are in `docs/gann/GANN_METHODOLOGY.md`.

## Global Constraints

- **Sealed data:** never read the XAUUSD sealed period (from 2023-06-24) or the BTCUSDT sealed period (from 2025-06-16).
  - Development loads use `upto="train"` and confirmation loads use `upto="validation"`.
  - Any window or level falling in a sealed period is discarded.
- **Order of runs:** every setting is frozen in `EXP7_parameters.json` and hashed into a **committed**
  `EXP7_preregistration.json` before any outcome is computed. `confirm` runs once.
- **Production:**
  - Nothing in `app/strategy_engine`, `app/paper`, the API or the frontend changes in Part 1.
  - No push, merge or deploy without the owner's approval.
  - No paid services.
- **Prices** are rounded to the instrument tick (XAUUSD 0.01, BTCUSDT 0.01). Every projection carries its anchor, unit,
  scale, tolerance and convention.
- **Tests:** existing tests are never weakened. Each task ends with the full backend suite and ruff passing.
- **Commands** run from `backend/` with `.venv/Scripts/python.exe`. Lint:
  `.venv/Scripts/python.exe -m ruff check app tests --select E,F,W,I --ignore E501`.
- **Commits:** each commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Projection before confirmation.** An anchor must never contribute before `tc`. A window must never start at or
   before `tc`. A superseded anchor must stop contributing at the `tc` of the anchor that replaces it. Covered by Task 2
   `test_major_prefix_equality` and Task 5 `test_state_prefix_equality`.
2. **Time units.**
   - Bar counts are not calendar time (weekends, holidays, gaps).
   - Sessions roll at 17:00 New York across DST.
   - 365.25 days, and month clamping.

   Covered by Task 3 `test_session_day_dst` and `test_add_months_clamps`, and Task 5 `test_calendar_vs_bar_counts_differ_over_weekend`.
3. **Sealed or confirmation leakage.** `develop` must load `upto="train"` only, and loading outside the allowed segments
   must fail. Covered by Task 7 `test_exp7_loader_segments`.
4. **Control mismatch.**
   - Control windows must use the same anchors, active spans and tolerance rule, with coverage within one percentage point.
   - Level controls must keep the same spacing.

   Covered by Task 8 `test_control_coverage_matched` and the null and planted tests.
5. **Identities counted twice.**
   - Square of Four, Square of Twelve and price-time balance must merge into their families.
   - Twenty Square of Nine levels count once.

   Covered by Task 5 `test_families_merge_identities`.

---

### Task 1: Price maths and the Squares

**Files:**
- Create: `backend/app/gann/__init__.py`, `backend/app/gann/price.py`, `backend/app/gann/squares.py`
- Test: `backend/tests/test_gann_math.py`

**Interfaces — Produces:**
- `price.round_tick(x: float | np.ndarray, tick: float) -> float | np.ndarray`
- `price.DIVS = (1/8, 1/4, 1/3, 3/8, 1/2, 5/8, 2/3, 3/4, 7/8)` and `price.EXT = (1.125, 1.25, 1.5, 2.0)`
- `price.divisions(low: float, high: float, tick: float, ext: bool = True) -> list[tuple[float, float]]`: (fraction, price), sorted by price.
- `price.twelfths(low: float, high: float, tick: float) -> list[tuple[float, float]]`: j/12 for j = 1..11.
- `price.swing_ratios(p: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]`: |ΔP_k|/|ΔP_{k−1}| and Δt_k/Δt_{k−1} over alternating extremes.
- `squares.sq9_levels(p0: float, tick: float, steps: int = 8, step_deg: float = 45.0) -> list[tuple[float, float]]`:
  (degrees, price) for ±1..steps steps, computing `(√p0 + deg/180)²` and skipping non-positive roots.
- `squares.spiral(n_max: int, core: int = 1) -> dict[int, tuple[int, int]]`: built by the rule "turn left when the left
  cell is empty".
  - `core=1` is the Square of Nine: 1 at (0,0), 2 at (1,0).
  - `core=4` is the Square of Four: 1..4 at (0,0), (1,0), (1,1), (0,1).
- `squares.cross(kind: str, n_max: int, square: int = 9) -> list[int]`.
  - **Square of Nine:** `"cardinal"` or `"diagonal"`, by the closed formulas in M §4.6.
  - **Square of Four:** only `"diagonal"` (cells with |x−½| = |y−½|). `"cardinal"` raises `ValueError`.
- `squares.cross_levels(numbers: list[int], lo: float, hi: float, norm: float = 1.0) -> list[float]`: the numbers ÷ norm
  that lie in [lo, hi].

- [ ] **Step 1: Write the failing tests**
```python
def test_sq9_worked_example():
    lv = dict(sq9_levels(2000.0, 0.01))
    assert lv[90.0] == 2044.97 and lv[-180.0] == 1911.56
    assert abs(lv[45.0] - 2000.0 - 22.42) < 0.01
def test_sq9_full_turn_adds_two_to_root():
    assert abs(math.sqrt(dict(sq9_levels(1234.5, 0.01))[360.0]) - (math.sqrt(1234.5) + 2)) < 1e-3
def test_cross_formulas_match_spiral():   # spiral(2000) cells with x==0 or y==0 / |x|==|y|, excluding 1
    ...  # cross("cardinal", 2000) == built set; same for "diagonal"
def test_sq4_even_squares_on_diagonal():
    assert {4, 16, 36, 64, 100} <= set(cross("diagonal", 200, square=4))
    with pytest.raises(ValueError): cross("cardinal", 200, square=4)
def test_divisions_eighths_thirds():
    assert [p for _, p in divisions(100, 200, 0.01, ext=False)] == [112.5, 125.0, 133.33, 137.5, 150.0, 162.5, 166.67, 175.0, 187.5]
def test_twelfths():
    assert [p for _, p in twelfths(0, 120, 0.01)] == [10.0 * j for j in range(1, 12)]
def test_swing_ratios():
    pr, tr = swing_ratios(np.array([100., 110, 105, 125]), np.array([0, 10, 15, 35]))
    assert np.allclose(pr, [0.5, 4.0]) and np.allclose(tr, [0.5, 4.0])
def test_round_tick():
    assert round_tick(2044.9712, 0.01) == 2044.97
```
- [ ] **Step 2:** Run `.venv/Scripts/python.exe -m pytest tests/test_gann_math.py -q`. Expected: FAIL (ImportError).
- [ ] **Step 3:** Implement `price.py` and `squares.py` to the interfaces above.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(gann): price divisions and Square of Nine/Four maths`.

### Task 2: Anchors

**Files:**
- Create: `backend/app/gann/anchors.py`
- Test: `backend/tests/test_gann_anchors.py`

**Interfaces — Consumes:**
- `market_structure.swings.find_swings`
- `feature_engineering.indicators.atr`
- `market_data.bars.Bars`

**Interfaces — Produces:**
- `@dataclass(frozen=True) class Anchor: idx: int; tc: int; price: float; kind: str; tier: str`.
  - `kind` is "high" or "low".
  - `tier` is "minor", "major" or "chart{n}".
- `minor_anchors(b: Bars) -> list[Anchor]`: `find_swings(b, 3, 3)`, with `tc = idx + 3`.
- `major_anchors(b: Bars, atr: np.ndarray, k: float = 5.0) -> list[Anchor]`: causal zigzag.
  - It tracks the running extreme since the last pivot.
  - A pivot is confirmed at the first candle whose low (or high) is at least `k·atr[candle]` beyond the running extreme.
    That candle is its `tc`.
  - The new opposite extreme starts from the candles after the pivot.
  - Candles before the first valid ATR are skipped.
- `swing_chart(b: Bars, n: int) -> list[Anchor]`: Gann's N-bar swing chart.
  - The line turns up after `n` consecutive higher highs, and down after `n` consecutive lower lows.
  - The pivot is the previous swing's extreme, with `tc` = the turn candle.
- `active_spans(anchors: list[Anchor], n: int, per_kind: int = 2) -> list[tuple[Anchor, int, int]]`:
  (anchor, start = tc, end exclusive).
  - The end is the `tc` of the anchor that pushes it out of the latest `per_kind` anchors of its kind, or `n`.

- [ ] **Step 1: Write the failing tests**
  - `test_major_anchor_known_path`: constant ATR 1, a path rising 10 then falling 6 then rising 3 then falling 7.
    - Expected pivots: a high at the top of the rise, with `tc` = the first candle 5 below it, and the following low.
    - The 3-point rise produces no pivot.
  - `test_major_prefix_equality`: on a 3,000-candle seeded random walk, for j in {500, 1200, 2999}:
    `major_anchors(cut(b, j)) == [a for a in major_anchors(b) if a.tc < j]`.
  - `test_minor_tc_is_idx_plus_3`.
  - `test_swing_chart_two_bar`: a hand-built series checks the turn candles and pivots.
  - `test_active_spans_latest_two`: four lows confirmed at 10, 20, 30 and 40 give spans [10, 30), [20, 40), [30, n), [40, n).
- [ ] **Step 2:** Run `pytest tests/test_gann_anchors.py -q`. Expected: FAIL (ImportError).
- [ ] **Step 3:** Implement `anchors.py`. Add `cut(b: Bars, stop: int) -> Bars` (all arrays sliced `[:stop]`) to `anchors.py`;
  later tasks reuse it.
- [ ] **Step 4:** Run it again. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(gann): causal anchors (minor, major zigzag, swing chart)`.

### Task 3: Time cycles

**Files:**
- Create: `backend/app/gann/time_cycles.py`
- Test: `backend/tests/test_gann_time.py`

**Interfaces — Produces:**
- `COUNTS = (7, 14, 21, 28, 30, 45, 49, 60, 72, 90, 108, 120, 135, 144, 180, 216, 240, 270, 288, 360, 365.25)`
- `FRACS = (1/8, 1/4, 1/3, 3/8, 1/2, 5/8, 2/3, 3/4, 7/8)`
- `SEASONAL = ((3,21),(6,21),(9,23),(12,21),(2,4),(5,6),(8,8),(11,8))`
- `tol(n: float) -> int`: `max(1, round(0.025·n))`.
- `session_day(ts: np.ndarray) -> np.ndarray`: the FX session index. The day rolls at 17:00 America/New_York (via `zoneinfo`).
- `add_months(ts: int, m: int) -> int` and `add_years(ts: int, y: int) -> int`: day clamped to the month's end.
- `calendar_window(t0: int, n: float, unit: str) -> tuple[int, int]`: `unit ∈ {"day","week","month","year"}`, ± `tol(n)` units.
- `bar_cycle_mask(n: int, spans, counts, fracs=None) -> np.ndarray[bool]`.
  - Centre: `round(anchor.idx + N·f)`. Window: ± `tol(N·f)`.
  - A window is kept only if its first candle is greater than `anchor.tc`.
  - It marks only candles within the anchor's active span.
  - Implemented with +1/−1 difference arrays.
- `calendar_cycle_mask(bar_ts: np.ndarray, anchor_ts: np.ndarray, spans, counts_days) -> np.ndarray[bool]`: the same rule,
  in calendar seconds.
- `sq9_time_counts(max_n: int = 400) -> list[int]`: `squares.cross("cardinal", max_n)`.
- `anniversary_mask(bar_ts, spans_major, anchor_ts, tol_days=2)`.
- `seasonal_mask(bar_ts, tol_days=2)`.
- `coverage(mask) -> float`.

- [ ] **Step 1: Write the failing tests**
  - `test_tol_values`: `tol(7) == 1`, `tol(90) == 2`, `tol(360) == 9`.
  - `test_window_must_start_after_confirmation`:
    - An anchor at idx 100 with tc 103, count 7, marks candles 106–108.
    - The same anchor with tc 108 marks nothing.
  - `test_mask_respects_active_span`: a window outside [start, end) marks nothing.
  - `test_session_day_dst`: around 2019-03-10 and 2019-11-03, 16:30 and 17:30 New York local times fall in different sessions.
    The UTC boundary is 22:00 before the March change and 21:00 after it.
  - `test_add_months_clamps`: 2019-01-31 + 1 month is 2019-02-28, and 2020-01-31 + 1 month is 2020-02-29.
  - `test_seasonal_mask_dates`: Mar 19–23 inside, Mar 24 outside (2019).
  - `test_anniversary_window`: an anchor on 2005-06-15 marks 2006-06-13..17.
  - `test_calendar_window_units`: week, month and year.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(gann): time-cycle windows, sessions, anniversaries, seasonal dates`.

### Task 4: Angles, fans and price-time balance

**Files:**
- Create: `backend/app/gann/angles.py`
- Test: `backend/tests/test_gann_angles.py`

**Interfaces — Produces:**
- `RATES = (1/8, 1/4, 1/3, 1/2, 1, 2, 3, 4, 8)` and `LABEL: dict[float, str]` (`8 → "8x1"`, `1/8 → "1x8"`).
- `scale_swing(prev: Anchor, a: Anchor) -> float`: `|a.price − prev.price| / (a.idx − prev.idx)` in price per candle.
- `scale_atr(atr: np.ndarray, a: Anchor) -> float`: `atr[a.tc]`.
- `S_FIXED = 1.0`: dollars per calendar day, D1 only.
- `fan(a: Anchor, scale: float, elapsed: np.ndarray, rates=RATES) -> np.ndarray`.
  - Shape: (len(rates), len(elapsed)).
  - Lines rise from lows and fall from highs.
  - `elapsed` is in candles, or in calendar days for `S_FIXED`.
- `angle_events(b: Bars, a: Anchor, scale: float, r: float, tol: np.ndarray, start: int) -> dict[str, np.ndarray]`: boolean
  arrays `touch`, `break_`, `retest`.
  - `break_` is a close beyond the line, beyond tolerance, on the side opposite to the anchor.
  - `retest` is a touch within 10 candles after a break that closes back on the broken side.
- `balance_centres(prev: Anchor, a: Anchor, scale: float) -> list[float]`:
  - squaring the range: `a.idx + |a.price − prev.price| / scale`;
  - squaring the anchor price: `a.idx + a.price / scale`.

  Both are in the scale's time unit.

- [ ] **Step 1: Write the failing tests**
  - `test_fan_rates`: a low anchor at P0 = 100, scale 2, 4 candles later gives 1x1 = 108, 2x1 = 116, 1x2 = 104.
  - `test_down_fan_from_high`.
  - `test_scale_swing`: a low of 100 at 0 and a high of 150 at 25 give 2.0.
  - `test_balance_equals_1x1_identity`: at the "squaring the range" centre, `fan(...)[1x1] − P0 == range`. This is the
    identity of M §4.3.
  - `test_angle_events_break_and_retest`: a constructed series.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(gann): angles, fans, balance points`.

### Task 5: Parameters, confluence, panel and state

**Files:**
- Create: `backend/app/gann/params.py`, `backend/app/gann/confluence.py`, `backend/app/gann/state.py`
- Test: `backend/tests/test_gann_state.py`

**Interfaces — Produces:**
- `@dataclass(frozen=True) class GannParams`. It holds every value in spec §4.2:
  - counts, fracs, `tol_frac=0.025`, `major_k=5.0`, `per_kind=2`;
  - `sq9_steps=8`, `sq9_step_deg=45.0`, `sq9_time_max=400`;
  - `price_tol_atr=0.1`, rates, seasonal, `seasonal_tol_days=2`, `anniv_tol_days=2`;
  - `fixed_scale=1.0`, `tick`, `atr_n=14`.

  It provides `.to_dict()` and `.sha()` (sha256 of the sorted JSON).
- `FAMILIES = ("cycles", "seasonal", "divisions", "square9", "angles", "symmetry")`.
  - `MERGE`: twelfths → divisions, sq4 → square9, balance → angles, anniversary → cycles.
- `confluence.families_at(levels: list[dict], windows: list[dict], price: float, tol: float) -> set[str]`: identities merged;
  one family counts once however many of its levels are near.
- `state.panel(b: Bars, p: GannParams, *, daily: bool) -> pl.DataFrame`: one causal row per candle.
  - Time masks: `t_cycle_bars`, `t_cycle_days` (daily only), `t_fraction`, `t_anniversary`, `t_seasonal`,
    `t_balance_swing`, `t_balance_atr`, `t_balance_fixed` (daily only), `t_sq9_time`.
  - Distance from the close to the nearest level, in ATR: `d_division`, `d_square9`, `d_angle_swing`, `d_angle_atr`,
    `d_twelfths`, `d_sq4`, `d_symmetry`.
  - `side_swing` and `side_atr`: the sign of (close − the 1x1 of the latest major anchor).
  - `families` (int).
  - Levels are piecewise constant between anchor events, so they are computed per segment.
- `state.levels_at(b: Bars, i: int, p: GannParams) -> list[dict]`: every price level known at `i`, with family, method,
  anchor idx and parameters. Filters and J use it with an arbitrary entry price.
- `state.gann_state(b: Bars, i: int, p: GannParams, *, daily: bool) -> GannState`.
  - It computes from `cut(b, i + 1)` only.
  - Fields: `i`, `ts`, `anchors`, `windows`, `levels`, `fans`, `families`, `confluence`, `params_sha`.

- [ ] **Step 1: Write the failing tests**
  - `test_state_prefix_equality`: a 1,500-candle seeded walk; for 20 sampled `i`, `gann_state(b, i) == gann_state(cut(b, i+1), i)`.
  - `test_panel_matches_state`: the time masks and `families` of panel row `i` equal those derived from `gann_state(b, i)`
    for the sampled `i`.
  - `test_no_projection_from_later_anchor`: every anchor in the state has `tc <= i`, and every window's anchor too.
  - `test_families_merge_identities`: 20 Square of Nine levels, a Square of Four level and a twelfth near the price give
    `{"square9", "divisions"}`, a count of 2.
  - `test_calendar_vs_bar_counts_differ_over_weekend`: on D1 candles with weekend gaps, a 7-candle cycle and a 7-day
    cycle mark different candles.
  - `test_params_sha_stable`.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(gann): params, confluence families, causal panel and state`.

### Task 6: Astro module (separate)

**Files:**
- Create: `backend/app/gann/astro/__init__.py`, `backend/app/gann/astro/events.py`
- Modify: `backend/requirements.txt` (add `skyfield`)
- Test: `backend/tests/test_gann_astro.py`

**Interfaces — Produces:**
- `load_ephemeris() -> object`: reads `data/ephemeris/de421.bsp`, downloading it once from JPL through Skyfield's
  loader if it is absent. The `data/` folder is already git-ignored; verify that.
- `moon_phases(t0: int, t1: int) -> list[tuple[int, str]]`: "new" and "full".
- `mercury_stations(t0, t1) -> list[tuple[int, str]]`: "retrograde" and "direct", where daily geocentric ecliptic motion
  changes sign.
- `aspects(body1: str, body2: str, t0, t1, angles=(0, 90, 180, 270)) -> list[tuple[int, float]]`.
- `event_mask(bar_ts, event_ts, tol_days=2) -> np.ndarray`.
- Nothing in `app/gann/state.py` imports `astro`. A test asserts this.

- [ ] **Step 0:** Check Skyfield's licence on PyPI before installing. **Stop and report if it is not permissive (MIT/BSD).**
  Then run `.venv/Scripts/python.exe -m pip install skyfield` and pin the version in `requirements.txt`.
- [ ] **Step 1: Write the failing tests.** All allow ±1 day.
  - `test_full_moon_2019_01_21`.
  - `test_jupiter_saturn_conjunction_2020_12_21`.
  - `test_mars_jupiter_conjunction_2018_01_07`.
  - `test_mercury_station_retrograde_2019_03_05`.
  - `test_core_does_not_import_astro`.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(gann): separate astro event module (Skyfield + JPL DE421)`.

### Task 7: Register, pre-registration and guards

**Files:**
- Create: `backend/app/gold_research/exp7/__init__.py`, `params.py`, `run.py`, `__main__.py`
- Generated (Task 11): `docs/research/EXP7_parameters.json`, `docs/gann/GANN_PARAMETER_REGISTER.md`
- Test: `backend/tests/test_exp7.py`

**Interfaces — Consumes:**
- `exp6.run.write_once`, `require_committed`, `guard_once`
- `historical.store.load_tf` and `load_m1`

**Interfaces — Produces:**
- `params.register() -> dict`: the GannParams dict plus `outcomes`, `timing`, `filters`, `rules`, `astro`, `controls`,
  `floors`, `costs`, `families`, and `sha`.
- `params.test_ids() -> dict[str, list[str]]`:

  | Family | ID format | Count |
  |---|---|---|
  | `timing` | `T\|sym\|tf\|method\|outcome` and `L\|sym\|tf\|method` | 152 + 24 |
  | `trading` | `F\|sym\|arm` and `J\|sym\|tf\|rule` | 20 + 36 |
  | `astro` | | 16 |
  | `descriptive` | Square of Four and twelfths | 12 |

- `run.load(symbol, tf, segment)`: allows only `"train"` (`develop`) and `"validation"` (`confirm`); anything else raises
  `ValueError`.
- `run.prereg()`, `run.develop()`, `run.confirm()`, and the CLI `python -m app.gold_research.exp7 {prereg,develop,confirm,report}`.

- [ ] **Step 1: Write the failing tests**
  - `test_family_sizes`: 176, 56, 16 and 12.
  - `test_register_sha_stable`.
  - `test_develop_refuses_uncommitted_prereg` (monkeypatch the path to an uncommitted temporary file).
  - `test_confirm_runs_once`.
  - `test_exp7_loader_segments`.
  - `test_prereg_records_prior_trials_2115_and_split_hashes`.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(exp7): register, pre-registration and run guards`.

### Task 8: Timing track and its statistics

**Files:**
- Create: `backend/app/gold_research/exp7/stats.py`, `backend/app/gold_research/exp7/timing.py`
- Test: `backend/tests/test_exp7_timing.py`

**Interfaces — Produces:**
- `timing.outcomes(b: Bars, atr: np.ndarray) -> dict[str, np.ndarray]`:
  - `reversal`: 10/10 fractal; this outcome uses hindsight.
  - `vol`: true range ÷ ATR[t−1].
  - `expansion`: true range > 1.5 × ATR[t−1].
  - `dchange`: with N = 10, NaN at the edges.
- `timing.reaction(b: Bars, atr: np.ndarray, level_at: np.ndarray, touch: np.ndarray, horizon: int = 20) -> np.ndarray`.
  - Reaction: price reaches the level ± 1 × ATR on the rejection side before any candle **closes** 1 × ATR beyond the level.
  - If the same candle does both, the reaction wins, because the close is the candle's last price. That is why no M1
    replay is needed. Record this as a ruling against the spec's "first passage on M1".
- `stats.lift(y: np.ndarray, inside: np.ndarray) -> float`.
- `stats.p_one_sided(real: float, null: np.ndarray) -> float`: `(1 + #(null ≥ real)) / (1 + len(null))`.
  - `dchange` is two-sided on |log lift|.
- `stats.random_length_masks(n, spans, k, draws, rng, target_cov, band_exclude) -> Iterator[np.ndarray]`.
  - It draws k lengths uniformly from [7, 366], excluding every Gann count ± tol.
  - It uses the same anchors and spans as the real mask.
  - It redraws until coverage is within 1 percentage point of the real mask (up to 50 tries, otherwise keeps the closest).
- `stats.random_offset_levels(levels, spacing, tol, rng)`.
- `timing.run(symbol: str, tf: str, segment: str, draws: int, rng_seed: int = 7) -> list[dict]`.
  - One row per test ID.
  - Each row has lift, p, n_inside, events_inside, coverage, and a status from: tested, not testable (coverage),
    below floor, descriptive.

- [ ] **Step 1: Write the failing tests**
  - `test_control_coverage_matched`.
  - `test_null_random_walk_lifts_near_one`: a 6,000-candle seeded GBM with 500 draws; the median lift is in [0.9, 1.1],
    and the share with p < 0.05 is at most 0.10.
  - `test_planted_reversals_detected`: sharp V reversals injected at 90-candle cycle centres give a reversal lift above 1.5
    and p < 0.01.
  - `test_reaction_same_candle_counts_reaction`.
  - `test_coverage_rule_marks_not_testable`.
  - `test_planted_level_reaction_detected`.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(exp7): timing track with coverage-matched controls`.

### Task 9: Filter track (B–I)

**Files:**
- Create: `backend/app/gold_research/exp7/filters.py`
- Test: `backend/tests/test_exp7_filters.py`

**Interfaces — Consumes:**
- Experiment 6's `_trades` (Experiment 5 baseline trades) and `_verdicts` (VSA and trend PASS)
- Experiment 6's `evaluate_arm`, `null_means`, `cluster_ci`, `cost_scenarios`
- `state.levels_at` and `panel`

**Interfaces — Produces:**
- `filters.gann_at_signals(symbol: str, tf: str, upto: str, trades: pl.DataFrame) -> pl.DataFrame`. Per trade:
  - the family flags at the entry price and candle;
  - `t_cycle_bars`, `balance_swing`, `balance_atr`, `side_swing`, `side_atr`, `families`.
- `filters.ARMS = ("B","C","D-swing","D-atr","E-swing","E-atr","F","G","H","I")`.
- `filters.arm_keep(t: pl.DataFrame) -> dict[str, np.ndarray]`. The rules follow spec §4.4. For C and F, "supporting side"
  means a level at or below the entry for longs, and at or above it for shorts.
- `filters.run(segment: str, draws: int) -> list[dict]`: one row per `F|sym|arm`, with Experiment 6's metrics and the six
  development conditions evaluated.

- [ ] **Step 1: Write the failing tests**
  - `test_arm_definitions`: a synthetic frame; each arm keeps exactly the expected rows.
  - `test_E_side_rule`: longs are kept only when `side == +1`, shorts only when `side == −1`.
  - `test_planted_filter_edge`: R is +1 where F is set and −0.2 elsewhere; the arm's p < 0.01 against the random filter.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(exp7): Gann filter arms over Experiment 5 trades`.

### Task 10: Gann-only rules (J1–J6)

**Files:**
- Create: `backend/app/gold_research/exp7/rules.py`
- Test: `backend/tests/test_exp7_rules.py`

**Interfaces — Consumes:**
- `sim.Series`, `sim.Orders`, `sim.simulate`
- Experiment 5's `with_controls`, `metrics`, `HOLD`, `GRID`
- the existing CHoCH and liquidity-sweep detectors
- `state.panel` and `levels_at`

**Interfaces — Produces:**
- `rules.signals(b: Bars, atr: np.ndarray, panel: pl.DataFrame, p: GannParams) -> dict[str, pl.DataFrame]`.
  - Per rule: `idx`, `d`, `stop`, `tp1`, `tp3`, and `trigger_px`.
  - J1–J6 exactly as in spec §4.5.
- `rules.to_orders(sig: pl.DataFrame, atr: np.ndarray) -> sim.Orders`.
  - Entry: the next candle's open.
  - Stop: beyond the trigger extreme, with a risk floor of 0.25 × ATR.
- `rules.run(segment: str) -> list[dict]`: one row per `J|sym|tf|rule`.
  - Primary R: 2R, the stop, or `HOLD`, whichever comes first.
  - TP1 and TP3 are descriptive.
  - Includes the direction-matched random-entry control.

- [ ] **Step 1: Write the failing tests**
  - `test_each_rule_fires_on_constructed_case` (6 cases).
  - `test_rules_prefix_equality`: signals before j are identical when the bars are cut at j + 1.
  - `test_stop_beyond_trigger_and_min_risk`.
  - `test_tp1_at_least_1R`.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(exp7): Gann-only rules J1-J6`.

### Task 11: Runtime check, pre-registration and development run

- [ ] **Step 1: Measure the runtime.**
  - Run the timing track on XAUUSD H1 for the year 2005 only, from training data, with 200 draws.
  - Extrapolate the full development runtime.
  - Set `controls.draws` to 20,000, or to the pre-declared fallback of 4,000 draws with a Gaussian tail fit.

  This measures runtime only; no outcome is read for any decision.
- [ ] **Step 2: Freeze the settings.**
  - Generate `docs/research/EXP7_parameters.json` and `docs/gann/GANN_PARAMETER_REGISTER.md`, and commit them.
  - Run `python -m app.gold_research.exp7 prereg`, then commit `EXP7_preregistration.json`.
- [ ] **Step 3: Run development.**
  - Run `python -m app.gold_research.exp7 develop` in the background, logging to `data/historical/exp7_develop.log`.
  - Expected: `docs/research/EXP7_development.json` with every test row and the candidate list.
- [ ] **Step 4:** Commit: `research(exp7): pre-registration and development results`.

### Task 12: Confirmation run and reports

- [ ] **Step 1: Run confirmation once.** Run `python -m app.gold_research.exp7 confirm` on the development candidates only.
  Expected: `docs/research/EXP7_confirmation.json`. A second call raises an error.
- [ ] **Step 2: Generate the reports.** Run `python -m app.gold_research.exp7 report`, which writes
  `docs/gann/GANN_BACKTEST_REPORT.md` and `docs/gann/GANN_LIMITATIONS.md`. Together they contain:
  - every test, including failures;
  - the coverage-rule removals;
  - the descriptive levels;
  - the astro family;
  - cost sensitivity;
  - the trial count, updated from 2,115;
  - the disclosure that Experiment 6 used the confirmation period;
  - the Phase 20 answers.
- [ ] **Step 3: Update the trial count.** Update it where the Experiment 5 report reads it (`exp5/report._trial_correction`
  source), and in `docs/handover/KNOWN_LIMITATIONS.md`. Regenerate any report that depends on it.
- [ ] **Step 4:** Commit: `research(exp7): confirmation and Gann backtest report`.
