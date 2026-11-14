# Confirmation Layer (VSA + Indicators) and Experiment 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a VSA and indicator confirmation matrix to the strategy engine, shown on every signal and gating nothing until
Experiment 6 proves it. Then run Experiment 6 on XAUUSD and BTCUSDT.

**Architecture:**
- **Pipeline.** New causal indicators feed three new modules in `app/strategy_engine/`: `volume.py` (volume type, reliability,
  relative volume), `vsa.py` (bar measures and events) and `confirm.py` (the ten-component matrix).
- **Strategies** tag their checks with components and return their key candles (`anchors`). The selector scores the chosen plan
  and applies `config.GATES`, which stays empty until Experiment 6 fills it.
- **Experiment 6:**
  - BTCUSDT history comes from Binance's archive, written in the historical store's format, so Experiment 5's pipeline gives
    the BTC baseline unchanged.
  - The harness (`app/gold_research/exp6/`) re-scores every baseline trade at its signal candle and runs the registered
    statistics.

**Tech Stack:** Python 3.12, numpy, polars, FastAPI, SQLAlchemy, pytest; Next.js 15, React 19, TanStack Query, vitest.

**Spec:** `docs/engine_v2/CONFIRMATION_DESIGN.md` (product) and `docs/engine_v2/EXPERIMENT_6_PLAN.md` (pre-registered
experiment). Both were approved by the owner on 2026-11-13. Executors read both; section numbers below refer to them.

## Global Constraints

- **No look-ahead.** Every value at candle *i* uses candles ≤ *i*; a VSA confirmation uses only completed candles after its event.
- **UNAVAILABLE never counts as a pass**, in the matrix, in gates and in experiment arms.
- **Mandatory components decide exactly as today.** With `GATES` empty, every engine decision on existing fixtures is unchanged.
- **Gates:**
  - `config.GATES` is empty in code; only a commit citing `docs/reports/EXPERIMENT6_CONFIRMATIONS.md` may fill it;
  - `("XAUUSD", "vsa")`, or any XAUUSD combination containing `vsa`, is rejected at import.
- **Fixed values.** Thresholds are exactly design §5 and §7; they live in `config.CONFIRM` and `config.VSA_T` and are never tuned.
- **Volume labels** (customer copy, verbatim):
  - `base` → "Exchange volume (Binance only)"
  - `tick` → "Tick volume (broker)"
  - `venue` → "Venue volume (Dukascopy)"
  - `none` → "No volume"
- **Sealed data.** XAUUSD from 2023-06-24 and the BTCUSDT final 15% are never read. `store.load_tf` refuses them; no task passes
  `final_test=True`.
- **Commit order.** The Experiment 6 pre-registration JSON is committed before any filtered outcome is computed. The BTCUSDT split
  is committed before any BTCUSDT event is generated.
- **Disclosures.** No win probability anywhere. Spot FX, gold, US30 and oil volume is never called market-wide volume.
- **Approval.** No push, merge or deploy without the owner's approval. Work stays on `feature/confirmation-engine`.
- **Checks** run from `backend/` with `.venv/Scripts/python.exe`:
  - tests: `-m pytest -q`
  - lint: `-m ruff check app tests --select E,F,W,I --ignore E501`
  - frontend: `npx vitest run`, `npx tsc --noEmit`, `npm run lint`

## Review Focus

1. **Mixed or zero volume.** A live series where some candles have tick volume and others none or 0 (provider fallback, a
   feed outage) → VSA, VWAP and RVOL must be UNAVAILABLE with the reason, never computed from the mixture. Test in Task 4.
2. **Short history.** H8, 1W and 1M, a new instrument, fewer than 200 candles or fewer than 4 weeks of hour-of-week samples →
   the affected categories are UNAVAILABLE and the card still renders. Tests in Tasks 4 and 9.
3. **Clock changes and the weekly reopen.** Hour-of-week baselines and VWAP anchors across the New York and Europe DST switches
   and the Sunday 17:00 reopen → a London-open candle is compared with London opens; the VWAP resets at 17:00 New York in both
   seasons. Test in Task 4.
4. **Zero-range candles or ATR ≤ 0 / NaN** (flat filler candles, thin markets) → that candle's VSA measures are NaN and produce no
   event; never a division by zero, never "effort without result" from a flat candle. Test in Task 6.
5. **API results without the new fields** (a cached result from before the deploy, NO TRADE timeframes, the classic page) → the
   card renders without the confirmation row and shows no error. Test in Task 10.

---

## File structure

| File | Responsibility |
|---|---|
| `backend/app/historical/binance_archive.py` (new) | Download Binance monthly 1m klines with checksum checks; write clean M1 in the store's format |
| `backend/app/historical/config.py`, `split.py`, `build.py`, `quality.py` (modify) | `continuous` calendar: every minute scheduled open, split snapped to Monday 00:00 UTC |
| `backend/app/market_data/bars.py`, `binance/provider.py` (modify) | `Bars.vtype`, `Bars.tb` (taker-buy); live Binance keeps `taker_buy_base` |
| `backend/app/feature_engineering/indicators.py` (modify) | MACD, Stochastic RSI, ROC, Keltner, historical volatility, session VWAP, SMA, OBV, MFI |
| `backend/app/strategy_engine/volume.py` (new) | Volume type, reliability, hour-of-week, session ids, RVOL |
| `backend/app/strategy_engine/vsa.py` (new) | Bar measures, events, confirmation state at a view candle |
| `backend/app/strategy_engine/confirm.py` (new) | The ten components and the category rules per strategy; gate checks |
| `backend/app/strategy_engine/config.py` (modify) | `CONFIRM`, `VSA_T`, `COMBOS`, `GATES`, `VOLUME_LABELS`, gate validation |
| `backend/app/strategy_engine/strategies/*.py`, `base.py` (modify) | `Candidate.checks`, `Candidate.anchors` |
| `backend/app/strategy_engine/context.py`, `selector.py`, `service.py` (modify) | New arrays in `TFData`; the matrix on the chosen plan; gates; API fields |
| `backend/app/gold_research/events.py` (modify) | `bars_from_frame`: `v = bid_volume + ask_volume`, `tb` when present |
| `backend/app/gold_research/exp5/run.py` (modify) | `PRECISION["BTCUSDT"] = 2`; calendar-aware where it assumes FX |
| `backend/app/gold_research/exp6/` (new: `__init__.py`, `__main__.py`, `rescore.py`, `stats.py`, `run.py`, `report.py`) | Re-score, pre-register, develop, confirm, report |
| `frontend/src/lib/engine-types.ts`, `components/domain/confirmations.tsx` (new), `components/domain/engine.tsx` (modify) | Chips, evidence panel, VSA states |
| Tests: `backend/tests/test_binance_archive.py`, `test_confirm_indicators.py`, `test_volume_vsa.py`, `test_confirm.py`, `test_exp6.py` (new); `test_strategy_engine.py`, `test_engine_api.py` (extend); `frontend/src/__tests__/engine.test.tsx` (extend) | |

---

## Phase A: BTCUSDT history (start first: the download runs in the background while Phase B is built)

### Task 1: Binance archive and the continuous calendar

**Files:**
- Create: `backend/app/historical/binance_archive.py`, `backend/tests/test_binance_archive.py`
- Modify: `backend/app/historical/config.py` (`Instrument` gains `source: str = "dukascopy"`; add `Instrument("BTCUSDT", 0.01, calendar="continuous", source="binance")`), `split.py`, `build.py`, `quality.py`

**Interfaces:**
- Produces:
  - `binance_archive.month_url(symbol: str, ym: str) -> str` →
    `https://data.binance.vision/data/spot/monthly/klines/{symbol}/1m/{symbol}-1m-{ym}.zip`
  - `binance_archive.download(symbol: str, start: str = "2017-08", end: str | None = None, log=print) -> dict`: resumable.
    Raw zips go to `RAW.parent / "binance" / symbol`. Each zip is verified against its `.CHECKSUM` (sha256); a mismatch is
    deleted and retried.
  - `binance_archive.parse_month(zip_bytes: bytes) -> pl.DataFrame`: columns `ts` (UTC datetime, candle open), `open, high, low,
    close, volume, taker_buy_base`. Open times above 1e14 are microseconds, otherwise milliseconds.
  - `binance_archive.write_clean_m1(symbol: str, half_spread: float = 1.0, log=print) -> int`. It writes
    `CLEAN/symbol/M1/{year}.parquet` with the gold schema:
    - `bid_* = price − half_spread`, `ask_* = price + half_spread` (the owner's $2 round-trip cost model);
    - `bid_volume = volume`, `ask_volume = 0.0`, plus `taker_buy_base`.
  - `split.next_boundary(ts: datetime, calendar: str) -> datetime`: Saturday 00:00 UTC for `fx_weekly`, Monday 00:00 UTC for
    `continuous`. `compute_split` uses it.
  - The gap mapping in `build.py` and `quality.py` treats every minute of a `continuous` instrument as scheduled open; runs of
    ≥ 30 missing minutes are still material gaps.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_month_normalises_ms_and_us_open_times():  # two rows: 1704067200000 (ms) and 1735689600000000 (us)
    df = parse_month(_zip([[1704067200000, ...], [1735689600000000, ...]]))
    assert df["ts"].to_list() == [datetime(2024,1,1,tzinfo=UTC), datetime(2025,1,1,tzinfo=UTC)]
    assert df.columns == ["ts", "open", "high", "low", "close", "volume", "taker_buy_base"]

def test_checksum_mismatch_is_rejected_and_file_removed(tmp_path, monkeypatch): ...  # fake fetch returns bad bytes once
def test_clean_m1_uses_the_store_schema_with_the_cost_model(tmp_path):
    # bid_close == close - 1.0, ask_close == close + 1.0, bid_volume == volume, ask_volume == 0.0, taker_buy_base kept
def test_continuous_split_snaps_to_monday():
    assert next_boundary(datetime(2024,5,8,13,tzinfo=UTC), "continuous") == datetime(2024,5,13,tzinfo=UTC)
    assert next_boundary(datetime(2024,5,8,13,tzinfo=UTC), "fx_weekly") == datetime(2024,5,11,tzinfo=UTC)
def test_continuous_calendar_counts_weekend_minutes_as_open():
    # a missing Saturday 40-minute run is a material gap for BTCUSDT; the same run is a scheduled closure for XAUUSD
```

- [ ] **Step 2: Run them and confirm they fail.** `.venv/Scripts/python.exe -m pytest tests/test_binance_archive.py -q`
  should fail with an ImportError.
- [ ] **Step 3: Implement** the functions above. Use `httpx` (already a dependency) with the existing download backoff style
  from `historical/download.py`.
- [ ] **Step 4: Run them; they should pass.** Also run `tests/test_historical.py`, which must stay green (gold behaviour unchanged).
- [ ] **Step 5: Commit.** `git commit -m "Binance archive downloader and continuous-calendar support in the historical store"`

### Task 2: Download BTCUSDT, build timeframes, freeze the split (operational)

**Interfaces:**
- Consumes: Task 1.
- Produces: `CLEAN/BTCUSDT/{M1..MN1}`, `docs/research/BTCUSDT_split.json` (committed), `data/historical/reports/BTCUSDT_*`.

- [ ] **Step 1: Download.** Run `python -m app.historical download-binance --symbol BTCUSDT` (add this subcommand to
  `app/historical/__main__.py`) as a detached process, logging to `data/historical/btc_download.log`. Expected:
  - one zip per month from 2017-08 to 2026-10;
  - every checksum OK;
  - the summary line gives the month count and the row count.
- [ ] **Step 2: Build.** `python -m app.historical build --symbol BTCUSDT`. It writes clean M1 through `write_clean_m1`, rebuilds
  M5 to MN1 with the existing rebuild, and runs `verify_timeframes`. Expected: "all timeframes identical to direct M1".
- [ ] **Step 3: Freeze the split.** `python -m app.historical split --symbol BTCUSDT --freeze`. Expected: the JSON shows
  70/15/15 boundaries on Mondays 00:00 UTC.
- [ ] **Step 4: Check the seal.** `load_tf("BTCUSDT", "H1", upto="test")` without `final_test` raises `SealError`. Add this as a
  test in `test_binance_archive.py`; it is skipped when the data is absent.
- [ ] **Step 5: Commit** the split JSON before generating any event:
  `git commit -m "BTCUSDT split frozen (70/15/15, Monday boundaries), final 15% sealed"`

### Task 3: BTCUSDT baseline events and cell gate (Experiment 5 pipeline, counts only)

**Files:** Modify `backend/app/gold_research/exp5/run.py` (`PRECISION["BTCUSDT"] = 2`) and `backend/app/gold_research/events.py`
(`bars_from_frame` → `v = bid_volume + ask_volume`, `tb = taker_buy_base` when the column exists).

**Interfaces:**
- Consumes: Task 2.
- Produces: `data/historical/exp5/BTCUSDT/events_{tf}.parquet` and `docs/research/BTCUSDT_exp5_preregistration.json` (cells with
  ≥ 100 compatible development signals; counts only).

- [ ] **Step 1: Write the failing test.** `test_bars_from_frame_sums_both_sides_and_keeps_taker_buy`: for a frame with
  `bid_volume = [2, 3]`, `ask_volume = [1, 1]` and `taker_buy_base = [1, 2]`, expect `v == [3, 4]` and `tb == [1, 2]`. Without
  the column, `tb is None`.
- [ ] **Step 2: Implement it, and run** `tests/test_exp3.py tests/test_gold_sim.py` plus the new test. All must pass: gold
  events do not use volume, so nothing else changes.
- [ ] **Step 3: Run events, then the gate.** `python -m app.gold_research.exp5 events --symbol BTCUSDT`, detached, as for gold,
  then `... gate --symbol BTCUSDT`. Expected: a cell table with counts and no outcomes.
- [ ] **Step 4: Commit** the BTCUSDT pre-registration: `git commit -m "BTCUSDT baseline cells pre-registered (counts only)"`

The BTCUSDT `develop` step (outcomes) waits for Task 12.

---

## Phase B: the confirmation layer

### Task 4: Volume metadata and volume quality

**Files:**
- Modify: `backend/app/market_data/bars.py` (add `vtype: str = "none"` and `tb: np.ndarray | None = None` after `step`;
  `from_candles` sets `vtype` to the most common `volume_type` and `tb` from `meta["taker_buy_base"]` when every row has it;
  `slice` and `upto` carry both), `backend/app/market_data/binance/provider.py` (`meta["taker_buy_base"] = r[9]`).
- Create: `backend/app/strategy_engine/volume.py`, `backend/tests/test_volume_vsa.py`.

**Interfaces:**
- Produces:
  - `VOLUME_LABELS` (in `config.py`), verbatim from Global Constraints.
  - `@dataclass VolumeQuality(type: str, label: str, reliable: bool, reason: str)`.
  - `quality(v: np.ndarray, vtype: str, i: int, rv_n: np.ndarray, window: int = 2000) -> VolumeQuality`. Reliable only if:
    - `vtype != "none"`;
    - at least 95% of `v[max(0, i-window+1):i+1]` is finite and > 0;
    - no run of ≥ 10 identical values;
    - `rv_n[i] ≥ 4` (baseline samples, from `rvol`).
  - `hour_of_week(t: np.ndarray, calendar: str) -> np.ndarray[int]`: New York local time for any calendar other than
    `continuous`; UTC for `continuous`.
  - `session_ids(t: np.ndarray, calendar: str) -> np.ndarray[int]`: a new id at 17:00 New York (DST-aware) for non-continuous
    calendars; at 00:00 UTC for `continuous`.
  - `rvol(v: np.ndarray, t: np.ndarray, step: int, calendar: str) -> tuple[np.ndarray, np.ndarray]` returns (RVOL, baseline
    sample count):
    - for `step ≤ 14400`, the median of earlier candles with the same hour of week within the last 20 weeks;
    - fewer than 4 → the same hour of day over the last 20 weekdays;
    - for `step ≥ 28800`, the median of the previous 20 candles.

    Uses only earlier candles.

- [ ] **Step 1: Write the failing tests**

```python
def test_rvol_compares_a_candle_with_the_same_hour_of_week_only(): ...  # London 08:00 candles at 3x, others 1x -> rvol 1.0 at 08:00
def test_rvol_is_causal():  # rvol(v[:k]) == rvol(v)[:k] for every k in a 30-week hourly series
def test_hour_of_week_follows_new_york_dst_for_fx_and_utc_for_continuous():
    # 2024-03-08 21:00 UTC (Fri 16:00 NY EST) and 2024-03-15 20:00 UTC (Fri 16:00 NY EDT) -> same fx hour-of-week; differ for continuous
def test_session_ids_reset_at_17_new_york_in_both_seasons(): ...
def test_quality_unavailable_for_mixed_zero_constant_or_missing_volume():
    # 10% zeros -> reliable False, reason mentions "zero"; 12 identical values -> False "constant"; vtype "none" -> False "no volume"
def test_quality_unavailable_when_history_is_shorter_than_four_samples(): ...
def test_binance_candles_keep_taker_buy_and_bars_carry_it(): ...  # from_candles -> tb array; slice keeps tb and vtype
```

- [ ] **Step 2: Run them; they should fail.** `-m pytest tests/test_volume_vsa.py -q`
- [ ] **Step 3: Implement** with numpy and `zoneinfo("America/New_York")`. Write `rvol` as a per-hour-bucket rolling median over
  the previous 20 occurrences.
- [ ] **Step 4: Run them; they should pass,** together with `tests/test_providers_ingestion.py` (the Binance meta change).
- [ ] **Step 5: Commit.** `git commit -m "Volume type, reliability and session-normalised relative volume"`

### Task 5: Indicators

**Files:**
- Modify: `backend/app/feature_engineering/indicators.py`
- Create: `backend/tests/test_confirm_indicators.py`

**Interfaces:**
- Produces (all causal; NaN before the "valid from" index in design §4):
  - `macd(c, fast=12, slow=26, signal=9) -> tuple[line, signal, hist]`, valid from index 34.
  - `stoch_rsi(c, rsi_n=14, stoch_n=14, k=3, d=3) -> tuple[k_line, d_line]` on 0-100, valid from 33.
  - `roc(c, n=10) -> np.ndarray`: `c[i]/c[i-n] - 1`.
  - `keltner(h, l, c, n_ema=20, n_atr=10, mult=2.0) -> tuple[mid, upper, lower]`.
  - `hist_vol(c, n=20) -> np.ndarray`: the standard deviation of log returns.
  - `sma(x, n) -> np.ndarray`.
  - `session_vwap(h, l, c, v, session_id) -> np.ndarray`: typical price weighted by volume, reset when `session_id` changes; NaN
    where the cumulative volume is 0 or `v` is not finite.
  - `obv(c, v) -> np.ndarray`.
  - `mfi(h, l, c, v, n=14) -> np.ndarray`.
  - `valid_from(x, k) -> np.ndarray`: copies `x` with `[:k] = NaN` (used for EMA 200 with k = 199).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("fn", [macd_hist, stoch_k, roc10, kelt_up, hv20, vwap_sess, obv_, mfi14])
def test_indicator_is_causal(fn):  # fn(series[:k]) == fn(series)[:k] (NaN-equal) for k in 40..400 step 37
def test_warm_up_is_nan_until_valid_from(): ...  # macd hist[:34] all NaN, hist[34] finite; stoch_rsi[:33] NaN
def test_macd_matches_hand_example(): ...  # 40-candle series with values checked against a pandas reference computed once and pinned
def test_vwap_resets_at_each_session_and_is_nan_without_volume(): ...
def test_mfi_is_100_when_every_candle_rises(): ...
```

- [ ] **Step 2: Run them; they should fail.**
- [ ] **Step 3: Implement** in numpy, using the existing `ema`, `atr` and `rsi`.
- [ ] **Step 4: Run them; they should pass,** together with `tests/test_strategy_engine.py::test_indicators_measure_trend_noise_and_compression`.
- [ ] **Step 5: Commit.** `git commit -m "Indicators for the confirmation layer (MACD, Stoch RSI, ROC, Keltner, HV, VWAP, OBV, MFI)"`

### Task 6: VSA measures and events

**Files:**
- Create: `backend/app/strategy_engine/vsa.py`
- Test: `backend/tests/test_volume_vsa.py`
- Modify: `config.py` (`VSA_T = {"wide": 1.2, "narrow": 0.6, "top": 0.67, "bottom": 0.33, "low": 0.7, "high": 1.5, "ultra": 2.5,
  "prior_n": 8, "prior_atr": 2.0, "confirm_n": 3, "test_n": 10, "test_atr": 0.3, "absorb_n": 5, "absorb_atr": 1.0,
  "level_n": 50}`)

**Interfaces:**
- Produces:
  - `@dataclass Measures(spread, close_pos, rvol, prior_move)`, each an ndarray.
  - `measures(b: Bars, atr: np.ndarray, rv: np.ndarray) -> Measures`: NaN where ATR ≤ 0 or NaN, or where `h == l` (no
    close position).
  - `@dataclass VsaEvent(kind: str, idx: int, direction: int, confirm_n: int, text: str)`. `kind` is one of `climactic`,
    `stopping`, `no_demand`, `no_supply`, `upthrust`, `spring`, `test`, `effort_no_result`, `result_no_effort`, `absorption`,
    `accumulation`, `distribution`.
  - `levels(b: Bars, n: int = 50) -> tuple[np.ndarray, np.ndarray]`: the highest high and lowest low of candles i-n..i-1
    (the "meaningful level"; the window holds the recent swings and, on 1H and above, the previous day's extremes). It is
    causal, so a replay equals live.
  - `detect(b: Bars, m: Measures, level_hi: np.ndarray, level_lo: np.ndarray) -> list[VsaEvent]`. Each event is decided
    from candles ≤ its `idx`. Accumulation and distribution are not detected here.
  - `context_label(events: list[VsaEvent], rng: tuple[float, float, int] | None, b: Bars, i: int) -> str | None`. Given a range
    (low, high, start candle), it returns "potential accumulation" or "potential distribution" when the range holds a confirmed
    spring or stopping volume (or the bearish mirrors) plus a test candle. Display only.
  - `pressure(b: Bars, i: int) -> dict`. It returns `{"source": "taker-buy share (Binance)" | "inferred from price", "value":
    float, "side": "buying" | "selling" | "balanced"}`. The value is the taker-buy share when `b.tb` exists (≥ 0.55 buying,
    ≤ 0.45 selling), otherwise the close position. Evidence only.
  - `state(e: VsaEvent, b: Bars, i: int) -> str`:
    - `"n/a"` when the event needs no confirmation;
    - `"unconfirmed"` while `i < e.idx + e.confirm_n`;
    - `"confirmed"` or `"failed"` by the rule in design §5, using candles `e.idx+1 .. e.idx+confirm_n` only.
  - `until(events: list[VsaEvent], i: int) -> list[VsaEvent]`: the events with `idx ≤ i`.

- [ ] **Step 1: Write the failing tests.** One hand-built series per event, with a PASS and a "context missing" twin:

```python
def test_high_volume_alone_is_never_an_event():  # ultra rvol, mid close, no prior move, no level -> no event at all
def test_stopping_volume_needs_a_prior_decline_and_a_close_off_the_low(): ...
def test_stopping_volume_is_unconfirmed_until_three_candles_then_confirmed_or_failed(): ...
def test_spring_needs_a_meaningful_level_undercut_and_a_close_back_above(): ...
def test_test_bar_must_follow_a_spring_within_ten_candles_on_low_volume(): ...
def test_absorption_requires_effort_without_result_at_a_level_and_a_move_away(): ...
def test_zero_range_or_zero_atr_candle_produces_no_measure_and_no_event(): ...
def test_detect_is_causal():  # events of series[:k] == [e for e in detect(series) if e.idx < k] (states differ only by window)
def test_pressure_uses_taker_share_on_binance_and_says_inferred_elsewhere(): ...
def test_accumulation_label_needs_a_range_spring_and_test(): ...
```

- [ ] **Step 2: Run them; they should fail.**
- [ ] **Step 3: Implement** with vectorised measures and a single pass over candles for the events.
- [ ] **Step 4: Run them; they should pass.**
- [ ] **Step 5: Commit.** `git commit -m "VSA bar measures and events with context and causal confirmation"`

### Task 7: Strategies report component-tagged checks and key candles

**Files:**
- Modify: `backend/app/strategy_engine/strategies/base.py` and all six strategy files.
- Test: `backend/tests/test_strategy_engine.py`.

**Interfaces:**
- Produces:
  - `Candidate.checks: list[tuple[str, bool, str]]`: (component, met, text), where component is one of `regime`, `htf`,
    `entry`, `structure`.
  - `Candidate.anchors: dict[str, int | float | list[int]]`. Keys:

    | Strategy | Anchor keys |
    |---|---|
    | trend_pullback | `pullback` (list of candle indices), `trigger` |
    | breakout_retest | `breakout`, `retest` (list), `level` |
    | momentum_continuation | `displacement`, `pullback` (list) |
    | range_reversion | `touch` (list of the last boundary candles), `boundary` (float) |
    | sweep_reversal | `sweep`, `level` (float) |
    | volatility_expansion | `expansion`, `box_hi`, `box_lo` |

  - `reasons` and `missing` keep their current text exactly. `checks` is added beside them.
  - `range_reversion.find_range(t: TFData, i: int) -> tuple[float, float, int] | None`: the strategy's existing range test,
    extracted unchanged. It is reused by Task 9 for `vsa.context_label`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("fixture", [_pullback_ready, _box_then_break, _momentum_ready, _range_touch, _sweep_series_shift, _expansion])
def test_ready_candidates_carry_anchors_inside_the_view(fixture):
    c = ...  # evaluate at the fixture's last candle
    assert c.status == "ready" and set(c.anchors) == EXPECTED_KEYS[c.strategy]
    assert all(0 <= k <= t.last for k in _indices(c.anchors))
def test_checks_tag_every_reason_with_a_component(): ...  # every reason text appears in checks with met=True
```

Reuse the existing helpers `bars`, `from_closes`, `td`, `_box_then_break` and `_sweep_series`; add fixtures for the other four
from the existing tests' series.

- [ ] **Step 2: Run them; they should fail.**
- [ ] **Step 3: Implement.** Record the anchors where each strategy already computes those indices. Do not change a condition.
- [ ] **Step 4: Run the whole of `tests/test_strategy_engine.py`. It must pass with every existing assertion unchanged.**
- [ ] **Step 5: Commit.** `git commit -m "Strategies tag their checks by component and report their key candles"`

### Task 8: TFData fields and the confirmation matrix

**Files:**
- Create: `backend/app/strategy_engine/confirm.py`, `backend/tests/test_confirm.py`
- Modify: `config.py`, `backend/app/strategy_engine/context.py`

**Interfaces:**
- Consumes: Tasks 4-7.
- Produces:
  - **`TFData.build(tf, bars, pa=None, levels=None, calendar: str = "fx_weekly")` adds:** `ema200`, `macd_hist`, `stoch_k`,
    `stoch_d`, `roc10`, `kc_mid`, `kc_up`, `kc_lo`, `hv20`, `hv_pct`, `vwap` (TF ≤ 1H only, else all NaN), `rv`, `rv_n`, `vsa_m`
    (Measures), `vsa_events` (list), `vtype` (from `bars.vtype`), `calendar`.
    - A `volume` property returns `quality(bars.v, vtype, last, rv_n)`.
    - `at(i)` keeps all of them; consumers read index `t.last` and `vsa.until(t.vsa_events, t.last)`.
    - `TFData.build(..., vtype=...)` overrides `bars.vtype`; research passes `"venue"` or `"base"`.
  - In `config.py`:
    - `CONFIRM = {"di_for": 5.0, "atr_pct_pass": (20, 90), "atr_pct_fail": (10, 95), "roc_dead_atr": 0.25, "stoch_lo": 20,
      "stoch_hi": 80, "pullback_rvol_pass": 0.8, "pullback_rvol_fail": 1.3, "breakout_rvol": 1.5, "retest_rvol": 1.0,
      "weak_rvol": 1.0, "disp_rvol": 1.5, "disp_pullback_ratio": 0.6, "sweep_rvol": 1.2, "expansion_rvol": 1.5}`;
    - `COMBOS = {"trend_pullback": ("trend", "momentum", "vsa"), "breakout_retest": ("vsa", "trend"), "momentum_continuation":
      ("trend", "momentum", "volatility"), "range_reversion": ("momentum", "vsa"), "sweep_reversal": ("momentum", "vsa"),
      "volatility_expansion": ("volatility", "vsa")}`;
    - `GATES: dict[str, dict[str, tuple[str, ...]]] = {}`;
    - `CONFIRM_STATUS: dict[str, dict[str, str]] = {}`, keyed by symbol → category, with values "not passed" or "gate".
      Missing means "evidence only — not tested". Task 12 fills it from the report;
    - `validate_gates(g) -> None`, called at import: it raises `ValueError` for an unknown symbol, strategy or category, and for
      XAUUSD with `vsa`.
  - `@dataclass Component(key, label, verdict, reason, evidence: dict, mandatory: bool, gating: bool = False, promoted_by: str | None = None, note: str = "")`.
    `note` holds the customer text for evidence categories: "evidence only — not tested", "did not pass Experiment 6" or
    "gate: Experiment 6", from `CONFIRM_STATUS`.
    The keys and labels are:

    | key | label |
    |---|---|
    | `regime` | Market regime |
    | `htf` | Higher timeframe |
    | `entry` | Entry |
    | `structure` | Market structure |
    | `vsa` | VSA |
    | `momentum` | Momentum |
    | `trend` | Trend |
    | `volatility` | Volatility |
    | `execution` | Spread & execution |
    | `rr` | Risk/reward |

  - `trend_verdict(t: TFData, d: int) -> tuple[str, str, dict]`
  - `momentum_verdict(strategy: str, t: TFData, d: int) -> tuple[str, str, dict]`
  - `volatility_verdict(strategy: str, t: TFData, d: int, anchors: dict) -> tuple[str, str, dict]`
  - `vsa_verdict(strategy: str, t: TFData, d: int, anchors: dict) -> tuple[str, str, dict]`: UNAVAILABLE when `t.volume.reliable`
    is false; events must be confirmed (or need no confirmation) to make a PASS.
  - `score(c: Candidate, t: TFData, regime: Regime, context: Regime | None, plan: dict | None, *, blocked: list[str],
    stale: bool, symbol: str) -> list[Component]`: ten components in the order of design §6.
  - `combo_pass(components, strategy) -> bool`
  - `gate_failures(components: list[Component], symbol: str, strategy: str) -> list[Component]`: promoted categories whose
    verdict is not PASS.

- [ ] **Step 1: Write the failing tests.** One worked example per rule in design §7 for PASS, FAIL, NEUTRAL and UNAVAILABLE,
  with the expected reason text checked, plus:

```python
def test_unavailable_never_passes_a_combination(): ...  # vsa UNAVAILABLE + others PASS -> combo_pass False
def test_momentum_uses_one_primary_indicator_and_agreement_adds_nothing():
    # trend_pullback: MACD hist rising 2 candles -> PASS whether RSI/Stoch/ROC agree or not; evidence lists all four
def test_trend_ignores_signals_the_regime_already_uses(): ...  # EMA20/50/ADX level changes alone never change the trend verdict
def test_vsa_unavailable_with_tick_reason_when_volume_unreliable(): ...
def test_unconfirmed_vsa_event_cannot_make_a_pass(): ...
def test_gates_reject_gold_vsa_and_unknown_names():
    with pytest.raises(ValueError): validate_gates({"XAUUSD": {"trend_pullback": ("vsa",)}})
    with pytest.raises(ValueError): validate_gates({"XAUUSD": {"trend_pullback": ("momentum", "vsa")}})
    with pytest.raises(ValueError): validate_gates({"BTCUSDT": {"nope": ("trend",)}})
def test_gate_failures_only_for_promoted_categories(): ...
```

- [ ] **Step 2: Run them; they should fail.**
- [ ] **Step 3: Implement.** Every threshold is read from `CONFIRM` and `VSA_T`; there are no literals in `confirm.py`.
- [ ] **Step 4: Run them; they should pass.**
- [ ] **Step 5: Commit.** `git commit -m "Confirmation matrix: ten components, one verdict per category, gates validated"`

### Task 9: Engine integration (selector, service, API)

**Files:**
- Modify: `backend/app/strategy_engine/selector.py`, `service.py`
- Test: `backend/tests/test_strategy_engine.py`, `backend/tests/test_engine_api.py`

**Interfaces:**
- Consumes: Task 8 (`TFData` fields, `score`, `gate_failures`), Task 6 (`context_label`, `pressure`), Task 7 (`find_range`).
- Produces:
  - **`evaluate_timeframe(..., symbol: str = "")`.** On the chosen plan it sets `confirmations` (a list of `Component` as dicts),
    `volume` (`VolumeQuality` as a dict) and `vsa`. `vsa` is `{"events": [the last 10 up to t.last, each with kind, time,
    direction, state, text], "pressure": pressure(...), "context": context_label(...)}`. A gate failure turns BUY/SELL into `WAIT FOR …` and appends
    `missing confirmation: <label lower> (<reason>)` to `missing`.
  - **NO TRADE results carry** `confirmations: []` and `volume`.
  - **`service.analyze` passes** `symbol` and the instrument's calendar to `TFData.build`.

- [ ] **Step 1: Write the failing tests**

```python
def test_decisions_unchanged_with_empty_gates():  # every existing fixture in this file: action/plan identical to the stored expectation
def test_replay_view_equals_live_matrix():  # evaluate_timeframe on TFData.build(bars[:k]) == on TFData.build(bars).at(k-1), confirmations equal
def test_promoted_gate_turns_buy_into_wait_and_names_the_missing_confirmation(monkeypatch):
    monkeypatch.setitem(GATES, "BTCUSDT", {"trend_pullback": ("momentum",)})  # momentum FAIL fixture
    r = evaluate_timeframe(..., symbol="BTCUSDT")
    assert r["action"] == "WAIT FOR BUY" and any(m.startswith("missing confirmation: momentum") for m in r["missing"])
def test_short_history_reports_unavailable_not_errors(): ...  # 150 candles -> trend UNAVAILABLE (EMA200), card fields present
# test_engine_api.py
def test_engine_detail_exposes_confirmations_volume_and_vsa(client, seeded_btc): ...  # 10 components, volume.label exact copy
```

- [ ] **Step 2: Run them; they should fail.**
- [ ] **Step 3: Implement.** The matrix is computed only for the chosen plan, so a dozen evaluations per timeframe stay as cheap as
  today.
- [ ] **Step 4: Run `tests/test_strategy_engine.py`, `tests/test_engine_api.py` and `tests/test_paper_api.py`; all should
  pass.** Then run the whole suite: `-m pytest -q`.
- [ ] **Step 5: Commit.** `git commit -m "Engine scores the chosen plan with the confirmation matrix; gates applied when promoted"`

### Task 10: Signal card confirmations (frontend)

**Files:**
- Create: `frontend/src/components/domain/confirmations.tsx`
- Modify: `frontend/src/lib/engine-types.ts`, `frontend/src/components/domain/engine.tsx` (SignalCard, EngineDetailPanel),
  `frontend/src/test/engine.ts` (fixtures)
- Test: `frontend/src/__tests__/engine.test.tsx`

**Interfaces:**
- Consumes: the API fields from Task 9.
- Produces:
  - Types: `Verdict = "PASS" | "FAIL" | "NEUTRAL" | "UNAVAILABLE"`; `Confirmation`; `VolumeInfo`; `VsaEventOut`.
    `EngineTimeframe` gains optional `confirmations`, `volume` and `vsa`.
  - `ConfirmationChips({ items }: { items?: Confirmation[] })`: renders nothing when `items` is missing or empty. Its chips, in
    order:

    | Chip | Component |
    |---|---|
    | Trend | trend |
    | Structure | structure |
    | VSA | vsa |
    | Momentum | momentum |
    | Volatility | volatility |
    | Spread | execution |
    | R:R | rr |

    Each chip shows its verdict with `data-testid="chip-<key>"` and is coloured by verdict. An evidence category shows its
    `note` from the API ("evidence only — not tested", "did not pass Experiment 6", "gate: Experiment 6").
  - `ConfirmationDetail({ items, volume, vsa })`: every component's verdict and reason, the indicator evidence, the VSA events with
    their state, and the volume label. The VSA state text is:

    | Verdict | Text |
    |---|---|
    | PASS | "VSA confirming" |
    | NEUTRAL | "VSA neutral" |
    | FAIL | "VSA contradictory" |
    | UNAVAILABLE | "VSA unavailable: <reason>" |

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows the seven confirmation chips with their verdicts on a BUY card", ...)   // GOLD_BUY fixture with confirmations
it("marks evidence-only categories and a gate differently", ...)
it("says VSA unavailable with its reason and names tick volume as broker volume", ...) // volume.label "Tick volume (broker)"
it("WAIT card names the missing confirmation", ...)
it("renders a card without confirmations (older cached result) with no error", ...)   // Review Focus 5
```

- [ ] **Step 2: Run them; they should fail.** `npx vitest run src/__tests__/engine.test.tsx`
- [ ] **Step 3: Implement** with the existing `Badge` and `cn`, and the dark-theme tokens `text-bull`, `text-bear`, `text-warn`
  and `text-muted-foreground`.
- [ ] **Step 4: Run them; they should pass.** Then `npx vitest run`, `npx tsc --noEmit` and `npm run lint`, all clean.
- [ ] **Step 5: Commit.** `git commit -m "Signal cards show the confirmation matrix, VSA states and volume type"`

---

## Phase C: Experiment 6

### Task 11: Experiment 6 harness

**Files:**
- Create: `backend/app/gold_research/exp6/{__init__,__main__,rescore,stats,run,report}.py`, `backend/tests/test_exp6.py`

**Interfaces:**
- Consumes:
  - Experiment 5's `events_{tf}.parquet` (`idx`, `strategy`, `direction`, `entry_mode`, `limit`, `stop`, `signal_ts`,
    `compatible`) and trades (`r_of`, `spread_entry`, `risk_px`, `entry_ts`, `signal_ts`);
  - `HIST`, `load_split`, `load_tf`, `bars_from_frame`, `_levels` and `_context` from exp5;
  - Task 9's `TFData.build` and `confirm.score`.
- Produces:
  - **`rescore.verdicts(symbol: str, tf: str, upto: str, log=print) -> pl.DataFrame`.** One row per event, with `idx`,
    `strategy`, `direction` and the verdicts for `vsa`, `momentum`, `trend`, `volatility` and `combo`. It rebuilds `TFData` with
    `vtype="venue"` for XAUUSD or `"base"` for BTCUSDT, re-evaluates the strategy at `t.at(idx, levels=…)`, and raises
    `RescoreMismatch` when direction, entry or stop differ from the event. The output is written to `out_dir/verdicts_{tf}.parquet`.
  - **`stats.random_filter_p(r: np.ndarray, keep: np.ndarray, strata: np.ndarray, draws: int = 20_000, seed: int = 6) -> float`.**
    Per stratum it draws, without replacement, as many trades as were kept there, then returns `(1 + #(null_mean ≥
    kept_mean)) / (draws + 1)`.
  - **`stats.holm(ps: dict[str, float]) -> dict[str, float]`** gives adjusted p-values.
  - **`stats.cluster_ci(diff_r_kept, diff_r_dropped, week) -> tuple[float, float]`.**
  - **`run.prereg(log=print) -> dict`.**
    - Writes `docs/research/EXP6_preregistration.json`; refuses to overwrite.
    - For both instruments × 6 strategies × 5 arms it records kept and dropped development **signal** counts, and the
      family (≥ 300 kept, ≥ 10% dropped).
    - It also records the code commit, the sha256 of `CONFIRM` + `VSA_T` + `COMBOS`, the split hashes, the plan commit, the
      prior trials (2,032) and the new trial count.
  - **`run.develop(log=print) -> dict`** writes `EXP6_development.json`. It refuses to run without a committed pre-registration
    (`git ls-files --error-unmatch`). It computes the metrics of plan §5 and applies criteria 1-6 of plan §6.
    - Doubled costs: `r_2x = r − spread_entry/risk_px`.
    - The BTC fee scenario: `r_fee = r − 2·0.001·entry/risk_px`.
  - **`run.confirm(log=print) -> dict`** writes `EXP6_confirmation.json`.
    - It runs once and refuses to run again.
    - It simulates the confirmation-segment baseline trades with exp5's `simulate(symbol, tf, "validation", ev)`, and only for
      the strategies with carried arms.
    - It applies the confirmation criteria.
  - **`report.write() -> str`** writes `docs/reports/EXPERIMENT6_CONFIRMATIONS.md`.
  - **`__main__`** commands: `rescore --symbol S`, `prereg`, `develop`, `confirm`, `report`.

- [ ] **Step 1: Write the failing tests** (synthetic data only)

```python
def test_random_filter_p_finds_a_planted_edge_and_rejects_noise():
    # kept = trades with planted +0.3R -> p < 0.001 ; kept = random half -> p > 0.05 in 19 of 20 seeds
def test_random_filter_respects_strata(): ...  # null draws match kept counts per stratum exactly
def test_holm_matches_reference(): ...  # [0.01, 0.04, 0.03] -> [0.03, 0.06, 0.06]
def test_prereg_counts_signals_only_and_refuses_overwrite(tmp_path): ...  # no r column read (assert via a frame without outcomes)
def test_develop_refuses_without_committed_prereg(tmp_path): ...
def test_confirm_runs_once(tmp_path): ...
def test_rescore_raises_on_signal_mismatch(): ...
def test_double_cost_and_fee_adjustments(): ...  # r=1.0, spread_entry=0.3, risk_px=3 -> r_2x=0.9; entry=50_000, risk=500 -> r_fee=0.8
```

- [ ] **Step 2: Run them; they should fail.** `-m pytest tests/test_exp6.py -q`
- [ ] **Step 3: Implement.** Reuse exp5's `metrics` for the reported measures. Strata = `tf × direction × year(signal_ts)`.
- [ ] **Step 4: Run them; they should pass.** Then run the full backend suite and ruff.
- [ ] **Step 5: Commit.** `git commit -m "Experiment 6 harness: re-score, pre-register, develop, confirm, report"`

### Task 12: Run Experiment 6 (operational; each numbered output committed before the next starts)

- [ ] **Step 1: Re-score.** Run `python -m app.gold_research.exp6 rescore --symbol XAUUSD`, then `--symbol BTCUSDT`, detached,
  with logs in `data/historical/exp6_*.log`. Expected: no `RescoreMismatch`, and one verdict file per timeframe.
- [ ] **Step 2: Pre-register.** `python -m app.gold_research.exp6 prereg`. Commit `docs/research/EXP6_preregistration.json`:
  `git commit -m "Experiment 6 pre-registration (counts only, before outcomes)"`
- [ ] **Step 3: BTCUSDT baseline outcomes.** `python -m app.gold_research.exp5 develop --symbol BTCUSDT`, then
  `... report --symbol BTCUSDT`. Commit the BTCUSDT Experiment 5 results and report.
- [ ] **Step 4: Development.** `python -m app.gold_research.exp6 develop`, then commit `EXP6_development.json`.
- [ ] **Step 5: Confirmation, once.** `python -m app.gold_research.exp6 confirm`, only when an arm passed development; otherwise
  the JSON records "not run: no arm passed development". Commit `EXP6_confirmation.json`.
- [ ] **Step 6: Report.** `python -m app.gold_research.exp6 report`. Commit `docs/reports/EXPERIMENT6_CONFIRMATIONS.md`.
- [ ] **Step 7: Gates.**
  - Only for arms that passed both stages: set `config.GATES` in a commit whose message cites the report.
  - Run `-m pytest -q`; `validate_gates` must accept it.
  - Fill `config.CONFIRM_STATUS` for both instruments from the report: "gate" for promoted arms, "not passed" for tested arms
    that failed. If no arm passed, `GATES` stays empty and the cards say "did not pass Experiment 6".

### Task 13: Documentation and final verification

**Files:**
- Modify: `docs/USER_GUIDE.md` (the confirmation row and the VSA states), `docs/handover/STRATEGIES.md` (a confirmations
  section), `docs/handover/KNOWN_LIMITATIONS.md` (the volume types; gold VSA never gated), `docs/API_SPECIFICATION.md` (the new
  fields), `docs/engine_v2/IMPLEMENTATION_REPORT.md` (an Experiment 6 section with results, linked)

- [ ] **Step 1: Write the documents** from the committed results only, every number with its sample size, period and cost level.
- [ ] **Step 2: Run the full checks.**
  - Backend: `-m pytest -q` and ruff.
  - Frontend: `npx vitest run`, `npx tsc --noEmit`, `npm run lint`, `npm run build`, `npm run e2e`.
  - Expected: everything green; the counts are recorded in the report.
- [ ] **Step 3: Commit.** `git commit -m "Docs: confirmation layer and Experiment 6 results"`
- [ ] **Step 4: Report to the owner.** Say whether each confirmation improved performance, what is gated, and what is not. Ask
  for approval before merging or deploying.
