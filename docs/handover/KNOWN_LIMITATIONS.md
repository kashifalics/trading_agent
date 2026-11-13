# Known limitations (release v2, 2026-11-13)

**Strategy evidence**
1. **No validated strategy.** Experiment 5 tested the six strategies on 17 years of gold. None passed the pre-registered criteria
   ([report](../reports/XAUUSD_EXPERIMENT5.md)). Experiments 1-4 (1,981 earlier trials) found none either. Every plan is
   therefore an **UNVALIDATED — HYPOTHETICAL TRADE PLAN**. The platform shows no win probability.
2. **The paper forward test runs the older v1 rules.** It is a measurement of those rules (negative so far), not of the six v2
   strategies. A v2 forward test should start only after a strategy passes research.

**Data**

3. **The FX cross-check is not done.** Dukascopy refused or throttled most download requests for EURUSD/GBPUSD history during the
   release. The download resumes by itself, and the FX part of Experiment 5 can be run when it completes.
4. **Live history is short.** The free providers give weeks of intraday candles. H8, W1 and MN1 often have fewer than the 120
   candles the regime classifier needs, and then honestly report NO TRADE (insufficient data). BiQuote has no monthly series.
5. **News is not filtered.** No free, reliable economic calendar exists. The product says so on every signal page.
6. **No real volume.** Spot FX and gold have no exchange volume, so no strategy uses volume.
7. **Quotes can be delayed.** When the provider's quote is stale, prices are labelled delayed and the last close is used.

**Product scope**

8. **Several analysis engines coexist.**
   - The Signals, Overview and Scanner pages use the strategy engine (v2).
   - Chart Analysis, Predictions and Trade Opportunities use older engines. They show the v2 action beside their own analysis.
9. **The lower-timeframe trigger is reported, not required** by the v2 rules.
10. **Simulation assumptions.**
    - The research measures TP1 with a full exit at a 96-candle horizon.
    - The paper test holds trades until the stop or TP1, with no time limit.
    - Slippage and swap are scenarios, not measurements.
11. **Single server, single database file.** The backend runs as one process with SQLite on a persistent volume. Horizontal
    scaling would need PostgreSQL (supported) and moving the minute cycle to a single worker. Measured after the release
    (2026-11-13):
    - **The minute cycle takes 17-21 s.** It runs the v1 and v2 engines for six instruments. Requests share the process's
      Python interpreter with it, so a response can take a few seconds longer while it runs. Server time is otherwise about
      0.25 s; large responses are gzip-compressed (Gold Research: 843 KB sent as 174 KB).
    - **Memory: 0.78 GB of the plan's 1 GB** 30 minutes after the start, and still rising. The previous release ran at about
      0.9 GB for hours without a restart. Watch `railway metrics --service backend --memory`. If it nears 1 GB, analyse fewer
      instruments (`SIGNAL_SYMBOLS`) or raise the limit; raising it is a paid plan change and the owner's decision.
12. **Dependency advisories.** `zod` (client-side form validation) and `postcss` inside Next.js (build time) have advisories whose
    fixes are breaking major upgrades. Neither is reachable from outside, so they are scheduled for a later release.
13. **The Railway config file format** (`railway.json`) is deprecated after 2026-12-01. Run `railway config migrate` before then.
