"""The Experiment 7 register: every setting and every test, fixed before any outcome (spec sections 4.2-4.7).

register() is hashed into the pre-registration; test_ids() enumerates every test of every family. Changing anything here after
an outcome has been seen is a new trial and must be recorded as one.
"""
import hashlib
import json

from app.gann.params import GannParams

SYMBOLS = ("XAUUSD", "BTCUSDT")
TIMING_TFS = ("H1", "H4", "D1")
INFO_TFS = ("M15", "W1")  # reported for information only
RULE_TFS = ("H1", "H4", "D1")
OUTCOMES = ("reversal", "vol", "expansion", "dchange")
# time method -> (panel column, timeframes tested)
TIME_METHODS = {
    "cycle_bars": ("t_cycle_bars", ("H1", "H4", "D1")),
    "cycle_days": ("t_cycle_days", ("D1",)),
    "fraction": ("t_fraction", ("H1", "H4", "D1")),
    "anniversary": ("t_anniversary", ("D1",)),
    "seasonal": ("t_seasonal", ("D1",)),
    "balance_swing": ("t_balance_swing", ("H1", "H4", "D1")),
    "balance_atr": ("t_balance_atr", ("H1", "H4", "D1")),
    "balance_fixed": ("t_balance_fixed", ("D1",)),
    "sq9_time": ("t_sq9_time", ("H1", "H4", "D1")),
}
LEVEL_METHODS = ("division", "square9", "angle_swing", "angle_atr")
DESCRIPTIVE_LEVELS = ("sq4", "twelfth")
ARMS = ("B", "C", "D-swing", "D-atr", "E-swing", "E-atr", "F", "G", "H", "I")
RULES = ("J1", "J2", "J3", "J4", "J5", "J6")
ASTRO_EVENTS = ("moon_phase", "mercury_station", "mars_jupiter", "mars_saturn")
ASTRO_OUTCOMES = ("reversal", "vol")

DRAWS = 20_000  # Task 11 may switch to the pre-declared fallback (4,000 draws + Gaussian tail) after timing one year
ALPHA = 0.05

OUTCOME_DEF = {
    "reversal": {"rule": "candle is a 10-left/10-right fractal high or low (hindsight outcome)", "fractal": 10,
                 "tested": "inside > outside"},
    "vol": {"rule": "true range / ATR(14) of the previous candle", "tested": "inside > outside"},
    "expansion": {"rule": "true range > 1.5 x ATR(14) of the previous candle", "threshold_atr": 1.5,
                  "tested": "inside > outside"},
    "dchange": {"rule": "sign(C[t+10]-C[t]) != sign(C[t]-C[t-10])", "n": 10, "tested": "two-sided |log lift|"},
}
REACTION = {"touch_tol": "max(0.1 x ATR, tick)", "move_atr": 1.0, "beyond_close_atr": 1.0, "horizon": 20,
            "tie": "the reaction wins when one candle does both (the close is the candle's last price)"}
LEVEL_DRAWS = 4_000  # measured: 20,000 level draws would take ~30 h (square9 ~1.1 s per draw at H1); the pre-declared fallback
CONTROLS = {"draws": DRAWS, "tail": "empirical", "level_draws": LEVEL_DRAWS, "level_tail": "gaussian",
            "fallback": {"draws": 4_000, "tail": "gaussian fit to the null distribution"},
            "runtime_basis": "timed on a synthetic random walk of the real XAUUSD H1 size (102,671 candles), no real outcome read",
            "time": "random cycle lengths uniform on [7, 366], excluding every Gann count +- its tolerance, same anchors, "
                    "spans and tolerance rule; coverage within 1 percentage point (up to 50 redraws, else the closest)",
            "levels": "every level shifted by a random fraction of the local level spacing, excluding shifts within the "
                      "tolerance", "filters": "Experiment 6 random filter, same keep rate per timeframe x direction x year",
            "rules": "Experiment 5 direction-matched random entries in the same timeframe and session",
            "coverage_rule": 0.90, "seed": 7}
FLOORS = {"timing_inside_candles": 200, "timing_inside_events": 30, "filters_kept": 300, "rules_trades": 100,
          "year_share": 0.60, "min_year_trades": 20}
RULE_PARAMS = {"entry": "next candle open", "stop": "beyond the trigger extreme", "min_risk_atr": 0.25,
               "rejection_close_atr": 0.25, "retest_window": 10, "primary_exit": "2R, stop or Experiment 5 HOLD",
               "tp1": "nearest Gann level >= 1R, else 1R", "tp2_r": 2.0, "tp3": "next Gann level, else 3R"}
COSTS = {"XAUUSD": {"real": "Dukascopy bid/ask", "slippage_scenarios": [0.10, 0.30]},
         "BTCUSDT": {"real": "Binance price +- $1 (archive convention)", "taker_fee_per_side": 0.001},
         "doubled": "every pass also needs a positive result at doubled costs",
         "swap": "scenario for holds past 17:00 New York (no free history)"}
ASTRO = {"ephemeris": "JPL DE421 via Skyfield 1.55", "frame": "geocentric apparent ecliptic longitude",
         "events": {"moon_phase": "new and full moon", "mercury_station": "retrograde and direct stations",
                    "mars_jupiter": "conjunction, square, opposition", "mars_saturn": "conjunction, square, opposition"},
         "window_days": 2, "timeframe": "D1",
         "excluded": "Sun ingresses into cardinal signs (identical to the seasonal cardinal dates)"}


def test_ids() -> dict[str, list[str]]:
    timing = [f"T|{s}|{tf}|{m}|{o}" for s in SYMBOLS for m, (_, tfs) in TIME_METHODS.items() for tf in tfs for o in OUTCOMES]
    timing += [f"L|{s}|{tf}|{m}" for s in SYMBOLS for tf in TIMING_TFS for m in LEVEL_METHODS]
    trading = [f"F|{s}|{a}" for s in SYMBOLS for a in ARMS]
    trading += [f"J|{s}|{tf}|{r}" for s in SYMBOLS for tf in RULE_TFS for r in RULES]
    astro = [f"A|{s}|{e}|{o}" for s in SYMBOLS for e in ASTRO_EVENTS for o in ASTRO_OUTCOMES]
    desc = [f"D|{s}|{tf}|{m}" for s in SYMBOLS for tf in TIMING_TFS for m in DESCRIPTIVE_LEVELS]
    return {"timing": timing, "trading": trading, "astro": astro, "descriptive": desc}


def register() -> dict:
    g = GannParams()
    doc = {"experiment": 7, "symbols": list(SYMBOLS), "gann": g.to_dict(), "gann_sha": g.sha(),
           "timing": {"tfs": list(TIMING_TFS), "info_tfs": list(INFO_TFS),
                      "methods": {m: {"column": c, "tfs": list(t)} for m, (c, t) in TIME_METHODS.items()},
                      "levels": list(LEVEL_METHODS), "descriptive_levels": list(DESCRIPTIVE_LEVELS)},
           "outcomes": OUTCOME_DEF, "reaction": REACTION, "filters": {"arms": list(ARMS)},
           "rules": {"rules": list(RULES), "tfs": list(RULE_TFS), **RULE_PARAMS}, "astro": ASTRO, "controls": CONTROLS,
           "floors": FLOORS, "alpha": ALPHA, "costs": COSTS, "families": {k: len(v) for k, v in test_ids().items()}}
    doc["sha"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    return doc
