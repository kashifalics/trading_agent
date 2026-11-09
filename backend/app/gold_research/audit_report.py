"""Markdown rendering of the research audit (audit.py). Every number comes from audit.json."""
import numpy as np


def _f(x, d=2, sign=True) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    return f"{x:+.{d}f}" if sign else f"{x:.{d}f}"


def _p(x, d=1) -> str:
    return "-" if x is None else f"{100 * x:.{d}f}%"


def render(a: dict) -> str:
    mt, pbo = a["multiple_testing"], a["pbo"]
    L = [f"# {a['symbol']} independent research audit", "",
         f"_Generated {a['generated']} by `python -m app.gold_research audit` from the stored training-period files. Scope: {a['scope']}. "
         "Nothing here changes the frozen split, reads the sealed final-test period or promotes anything. Analysis only._", ""]
    L += ["## Summary", ""]
    c = a["candidates"]
    L += [f"* **Multiple testing.** {mt['tests']:,} pre-registered training tests. BH keeps {mt['bh_q_lt_0_10']} at q < 0.10 and "
          f"{mt['bh_q_lt_0_05']} at q < 0.05; only {mt['bonferroni_0_05']} survive Bonferroni and {mt['holm_0_05']} survive Holm. "
          f"Storey's estimate says about {100 * mt['storey_pi0']:.0f}% of all tests are pure noise and the estimated false-discovery rate among the "
          f"{mt['bh_q_lt_0_10']} candidates is {_p(mt['estimated_fdr_at_candidate_threshold'], 0)} (about {mt['expected_false_candidates']:.1f} expected false ones).",
          f"* **Profitability is the weak point.** Tests are about beating matched random trades; on raw profit after the spread only "
          f"{mt['profit_tests_nominal_p_lt_0_05']} of {mt['tests']:,} tests reach nominal p < 0.05 (about {mt['expected_nominal_profit_hits_under_null']:.0f} would by chance) "
          f"and {mt['profit_tests_bh_q_lt_0_10']} survive BH.",
          f"* **Backtest overfitting.** Choosing the best of these tests in one half of the training years and checking it in the other half "
          f"(CSCV, {pbo['edge']['splits']:,} splits of {pbo['edge']['blocks']} year blocks): probability of overfitting {_p(pbo['edge']['pbo'], 0)} on edge "
          f"and {_p(pbo['mean_r']['pbo'], 0)} on mean R; the selected test's out-of-sample result is below zero in "
          f"{_p(pbo['mean_r']['prob_selected_oos_below_zero'], 0)} of splits (mean R).", ""]
    L += ["## 1. Multiple testing and overfitting", "",
          "| Measure | Value |", "|---|---|",
          f"| Tests (pattern / combination / multi-timeframe x timeframe x direction, >= 100 trades) | {mt['tests']:,} |",
          f"| Benjamini-Hochberg q < 0.10 (the frozen candidates) / q < 0.05 | {mt['bh_q_lt_0_10']} / {mt['bh_q_lt_0_05']} |",
          f"| Bonferroni p < 0.05/{mt['tests']} | {mt['bonferroni_0_05']} |", f"| Holm (alpha 0.05) | {mt['holm_0_05']} |",
          f"| Storey pi0 (share of true nulls, lambda 0.5) | {mt['storey_pi0']:.3f} |",
          f"| Estimated FDR at the candidate threshold | {_p(mt['estimated_fdr_at_candidate_threshold'], 1)} |",
          f"| Tests with a positive edge (any size) | {_p(mt['share_positive_edge'], 1)} |",
          f"| Profit tests (mean R > 0): nominal p < 0.05 / BH q < 0.10 | {mt['profit_tests_nominal_p_lt_0_05']} / {mt['profit_tests_bh_q_lt_0_10']} |", "",
          "Tests are correlated (the same trades feed a pattern, its combinations and its multi-timeframe variants), so the effective number "
          "of independent tests is smaller than the count; BH stays valid under the positive dependence this creates, Bonferroni and Holm are "
          "conservative.", "",
          "**Probability of backtest overfitting (CSCV).** Per-year totals for every test; all ways of splitting the 16 year blocks "
          f"({', '.join(a['pbo_blocks'])}) into two halves; in each, the best test in one half is ranked in the other.", "",
          "| Selection metric | Strategies | Splits | PBO | Median logit | Selected: in-sample mean | Selected: out-of-sample mean | P(out-of-sample < 0) |",
          "|---|---|---|---|---|---|---|---|"]
    for k, v in pbo.items():
        L.append(f"| {k} | {v['strategies']:,} | {v['splits']:,} | {_p(v['pbo'], 1)} | {v['median_logit']:+.2f} | {_f(v['selected_is_mean'], 3)} | "
                 f"{_f(v['selected_oos_mean'], 3)} | {_p(v['prob_selected_oos_below_zero'], 0)} |")
    L += ["", "**Reproducibility.** The 52 frozen candidates recomputed from the current training files:", ""]
    rp = a["reproducibility"]
    same = sum(1 for r in rp if r["n_then"] == r["n_now"] and abs((r["edge_then"] or 0) - (r["edge_now"] or 0)) < 1e-9)
    L.append(f"{same} of {len(rp)} reproduce exactly (same trade count and edge)." + ("" if same == len(rp) else
             " Differences: " + "; ".join(f"{r['key']} n {r['n_then']}->{r['n_now']}, edge {_f(r['edge_then'], 4)}->{_f(r['edge_now'], 4)}"
                                          for r in rp if r["n_then"] != r["n_now"] or abs((r['edge_then'] or 0) - (r['edge_now'] or 0)) >= 1e-9)))
    L.append("")
    for e in c:
        L += [f"## Candidate: {e['candidate']}", ""]
        t = e["training"]
        L += [f"Training: {t['n']:,} trades, win rate {_p(t['win_rate'], 0)}, mean R {_f(t['mean_r'], 3)} +/- {_f(t['mean_r_se'], 3, False)} (p = "
              f"{t['p_profit']:.3f} for mean R > 0), matched long controls {_f(t['ctrl_mean_r'], 3)}, edge {_f(t['edge'], 3)} +/- {_f(t['edge_se'], 3, False)}, "
              f"profit factor {_f(t.get('profit_factor'), 2, False)}, {t['clusters']} independent time clusters.", ""]
        for lab, dsr in (("per trade", e["deflated_sharpe_per_trade_obs"]), ("per time cluster", e["deflated_sharpe_cluster_obs"])):
            L.append(f"* Deflated Sharpe ratio ({lab}, {dsr['observations']:,} observations): Sharpe per trade {dsr['sharpe_per_trade']:.4f} versus "
                     f"{dsr['expected_max_sharpe_of_trials']:.4f}, the best a no-edge test would show by luck among {dsr['trials']:,}; probability the "
                     f"true Sharpe is above that: {_p(dsr['deflated_sharpe_probability'], 1)}.")
        L += ["", "**2. Cost stress (training trades).** Spread multiplied on every trade; slippage charged on entry and exit.", "",
              "| Spread | Slippage / side | Mean R | 95% CI | Win % | Profit factor | p (mean > 0) |", "|---|---|---|---|---|---|---|"]
        be = None
        for s in e["stress"]:
            if "spread_x" not in s:
                be = s
                continue
            L.append(f"| x{s['spread_x']:g} | ${s['slippage_per_side']:.2f} | {_f(s['mean_r'], 3)} | {_f(s['ci_low'], 3)} to {_f(s['ci_high'], 3)} | "
                     f"{_p(s['win_rate'], 0)} | {_f(s['profit_factor'], 2, False)} | {s['p_positive']:.3f} |")
        if be:
            L += ["", f"Break-even: the mean turns to zero with about ${be['breakeven_extra_cost_usd_round_trip']:.2f} of extra cost per round trip "
                      f"(median spread ${be['median_spread_usd']:.2f}, median risk ${be['median_risk_usd']:.2f})."]
        d = e["drift"]
        L += ["", "**4. Long-term drift.**", "",
              f"* Matched random LONG trades (same entry type, stop size, session, volatility, year): {_f(d['matched_long_control_mean_r'], 3)}R; "
              f"the candidate's edge over them: {_f(d['edge_over_matched_long_controls'], 3)}R.",
              f"* The same signals traded SHORT (mirror stop, 2R, 48 candles): {d['same_signals_traded_short']['n']:,} trades, mean R "
              f"{_f(d['same_signals_traded_short']['mean_r'], 3)} +/- {_f(d['same_signals_traded_short']['se'], 3, False)}.",
              ("* The bearish version of the pattern: " + (f"{d['opposite_direction_pattern']['n']:,} trades, mean R {_f(d['opposite_direction_pattern']['mean_r'], 3)}, "
                                                           f"edge {_f(d['opposite_direction_pattern']['edge'], 3)}" if d['opposite_direction_pattern'] else "not tested (too few trades)")),
              f"* In the {len(d['down_years'])} training years when gold fell: " + (", ".join(
                  f"{y['year']} ({_p(y['gold_year_return'], 0)}): n={y['n']}, mean R {_f(y['mean_r'], 2)}" for y in d["down_years"]) or "none") + ".", "",
              "Random market entries at the candidate's typical stop size, long versus short, by year (training):", "",
              "| Year | Random long mean R | Random short mean R |", "|---|---|---|"]
        L += [f"| {r['year']} | {_f(r.get('random_long'), 3)} | {_f(r.get('random_short'), 3)} |" for r in d["random_long_vs_short_by_year"]]
        st = e["stability"]
        L += ["", f"**5. Stability.** Positive mean R in {st['years_positive']} of {st['years']} training years.", "",
              "| Year | Trades | Win % | Mean R | Edge | Gold that year |", "|---|---|---|---|---|---|"]
        L += [f"| {y['year']} | {y['n']} | {_p(y['win_rate'], 0)} | {_f(y['mean_r'], 2)} | {_f(y['edge'], 2)} | {_p(y.get('gold_year_return'), 0)} |"
              for y in st["year"]]
        for col in ("session", "vol_level", "trend_regime", "structural_regime"):
            L += ["", f"| {col.replace('_', ' ')} | Trades | Mean R | Edge |", "|---|---|---|---|"]
            L += [f"| {r[col]} | {r['n']} | {_f(r['mean_r'], 2)} | {_f(r['edge'], 2)} |" for r in st[col]]
        rl = e["realism"]
        L += ["", "**7. Execution realism.**", "",
              f"* Entry: {rl['entry']}.", f"* Stop: {rl['stop']}. Target: {rl['target']}.",
              f"* Risk per trade: median ${rl['risk_usd_median']:.2f} ({rl['risk_atr_median']:.2f} ATR), 5th percentile ${rl['risk_usd_p5']:.2f}; "
              f"{_p(rl['share_risk_below_0_50_usd'])} of trades risk under $0.50 and {_p(rl['share_risk_below_1_usd'])} under $1.00 (stops that "
              "close can be below a broker's minimum stop distance).",
              f"* Spread as a share of risk: median {_p(rl['spread_over_risk_median'])}, 95th percentile {_p(rl['spread_over_risk_p95'])}.",
              f"* Stops filled beyond the stop price (gaps): {_p(rl['share_gap_through_stop'])}; worst {rl['worst_stop_r']:.2f}R.",
              f"* Intrabar assumption (stop counted first inside a minute): flipping it changes {_p(rl['intrabar_optimistic_share_changed'], 2)} of results.",
              f"* Entries during the 17:00-19:00 New York rollover (wide spreads): {_p(rl['share_entries_in_rollover'])}"
              + (f", mean R {_f(rl['rollover_mean_r'], 2)}" if rl['rollover_mean_r'] is not None else "") + ".",
              f"* Overlapping positions if every signal were taken: median {rl['median_concurrent_positions']:.0f}, maximum {rl['max_concurrent_positions']}.",
              "* Stopped out within " + " / ".join(str(k) for k in rl["stopped_within"]) + " candles: "
              + " / ".join(_p(v, 0) for v in rl["stopped_within"].values() if v is not None) + ".", ""]
    md = a["missing_data"]
    L += ["## 3. Missing scheduled data", "", f"Period: {md['period']}. Scheduled-open minutes {md['scheduled_minutes']:,}; missing "
          f"{md['missing_minutes']:,} ({_p(md['missing_share'], 2)}), of which {md['material_missing_minutes']:,} in material gaps (30+ minutes, excluded "
          f"from research) and {md['holiday_missing_minutes']:,} on 24-26 Dec / 1-2 Jan.", ""]
    for col in ("year", "session", "weekday", "vol_level", "trend_regime"):
        L += [f"| {col.replace('_', ' ')} | Scheduled minutes | Missing | Share missing |", "|---|---|---|---|"]
        L += [f"| {r[col]} | {r['scheduled']:,} | {r['missing']:,} | {_p(r['share'], 2)} |" for r in md[f"by_{col}"]]
        L.append("")
    lk = a["leakage"]
    L += ["## 6. Look-ahead and leakage checks", "", f"Training ends {lk['train_end']}.", "",
          "| TF | Trades | Last entry | Last outcome window end | Inside training | Segments in file |", "|---|---|---|---|---|---|"]
    L += [f"| {tf} | {v['trades']:,} | {v['last_entry'][:16]} | {v['last_outcome_window_end'][:16]} | {'yes' if v['outcome_windows_inside_training'] else 'NO'} | "
          f"{', '.join(v['segments_in_file'])} |" for tf, v in lk["timeframes"].items()]
    L += ["", f"* Validation or final-test outputs present in the research folder: {', '.join(lk['validation_or_test_outputs_present']) or 'none'}.",
          f"* Final-test seal log exists (any read of the sealed period would be recorded): {'yes' if lk['seal_log_exists'] else 'no: the sealed period has never been read'}.",
          f"* Stage-1 discovery generated {lk['stage1_generated']}; it is tied to the frozen split (hash matches: {lk['stage1_split_sha256_matches']}).",
          f"* Model training outputs present: {'yes' if lk['ml_training_present'] else 'not yet (models are trained by stage 2 after validation trades are simulated, on training rows only)'}.",
          "* Every data read in the research code goes through the sealed loader; call sites and the segment they request:", ""]
    for f_, lines in lk["loader_call_sites"].items():
        L += [f"  * `{f_}`: " + "; ".join(f"`{x}`" for x in lines)]
    L += ["", "* Design guarantees, each covered by a test: detectors are causal (prefix versus full history); higher-timeframe candles are used "
          "only after they close; regime thresholds are fixed in ATR units or trailing percentiles (nothing fitted on later data); controls are "
          "drawn from the same segment; models use purged walk-forward folds with nested parameter choice and cross-fitted calibration inside "
          "training; the unnamed-pattern model is fitted on training candles only.",
          "* Researcher-side disclosures: earlier exploratory studies on Twelve Data candles (2024-2026) touched the final-test period. The "
          "chart, Wyckoff and harmonic families were commissioned before stage-1 results existed. The unnamed-pattern stage (phase 6) was written "
          "after the stage-1 training results had been seen; its design is generic (no parameters tuned to those results) but it is not blind.", "",
          "## Limitations of this audit", "",
          "* Training data only: validation had not run when this audit was produced; its results are reported separately and decide the candidates.",
          "* PBO uses year blocks of unequal size and treats every test as a strategy, including correlated variants.",
          "* The deflated Sharpe ratio assumes independent observations; the cluster version is the conservative reading.",
          "* Slippage is a flat dollar assumption; real slippage grows in fast markets and at the rollover.",
          "* One data source (Dukascopy); broker spreads, minimum stop distances and swap differ."]
    return "\n".join(L) + "\n"
