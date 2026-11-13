# Strategy engine v2: work plan and status

Working notes for the two briefs of 2026-11-13: "clear BUY/SELL signal system" and "strategy-driven signal engine". They are
updated as work proceeds.

Constraints (owner's rules):
- No new profitability experiment before the owner approves `EXPERIMENT_PLAN.md`, and the sealed XAUUSD final-test period is never
  read.
- No unvalidated strategy is promoted. No live broker execution, no paid APIs, no credentials in output.
- No push, merge or deploy without approval. Existing research reports stay as they are.
- The running paper forward test keeps its frozen v1 rules: v2 runs beside it, not instead of it.

| # | Step | Status |
|---|---|---|
| 1 | Audit of the existing system and data quality (`AUDIT.md`) | done |
| 2 | Design: architecture, regime classifier, six strategy specs, plan (entry/SL/TP) rules, risk, sessions/news (`DESIGN.md`) | done |
| 3 | Experiment plan for approval (`EXPERIMENT_PLAN.md`); nothing is run | done |
| 4 | Indicators (ADX/DMI, Bollinger width, efficiency ratio) + regime classifier + tests | done |
| 5 | Trade-plan builder: tick rounding, side checks, TP1-3, costs, expiry + tests | done |
| 6 | Six strategy modules + tests | done |
| 7 | Multi-timeframe profiles, selector, conflict resolution, service + API + tests | done |
| 8 | Sessions (DST-correct) and central risk module + tests; news filter reported unavailable unless a free reliable source exists | done |
| 9 | Signal lifecycle record (DB + tracker + API) + tests | done |
| 10 | Decision vocabulary BUY / SELL / WAIT FOR BUY / WAIT FOR SELL / EXIT / NO TRADE; paper-trade management separate | done |
| 11 | Signals page redesign (best first, prices visible), all pages consistent; frontend + e2e tests | done |
| 12 | Local run on real stored candles: worked BUY and SELL examples, screenshots, implementation report, blockers | done |

All steps are done (local). See `IMPLEMENTATION_REPORT.md`. Next steps need the owner: approve `EXPERIMENT_PLAN.md`, approve the deploy.
