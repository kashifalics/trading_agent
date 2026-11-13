# Release checklist: v2 production release (started 2026-11-13)

Owner's authorisation (2026-11-13): run Experiment 5 (`docs/engine_v2/EXPERIMENT_PLAN.md`), download free EURUSD/GBPUSD history,
finish the product, test, merge, push, apply safe migrations, deploy, verify, hand over.

Still forbidden:
- reading the sealed XAUUSD final test (from 2023-06-24), or the FX final 15% once frozen;
- invented performance;
- promoting a strategy that fails;
- live broker execution;
- exposed secrets;
- paid services;
- destructive database operations without a recovery path.

| # | Item | Status |
|---|---|---|
| 1 | Baseline: branch `feature/strategy-engine-v2` @ d1dc661, clean apart from `backend/dev.db-wal/-shm` (tracked by mistake: see 9) | done |
| 2 | FX history: Dukascopy EURUSD/GBPUSD M1 download (detached process, `data/historical/fx_download.log`), then build and freeze the 70/15/15 split before any look | running |
| 3 | Engine made evaluable at any past candle (window view) with causal zone lifetimes (no status look-ahead); live behaviour unchanged | todo |
| 4 | Experiment 5 harness: pre-registration (counts only, committed before outcomes), simulation, statistics, report | todo |
| 5 | Run Experiment 5 on XAUUSD development and validation; FX when the data is ready | todo |
| 6 | Research statuses in the product follow the result (failed = NOT VALIDATED) | todo |
| 7 | Consistency across pages (Chart Analysis, Trade Opportunities, Paper Trading) and disclosures (five categories) | todo |
| 8 | Risk, data and provider checks; news reported unavailable | todo |
| 9 | Security: env, secrets, CORS, auth, dependencies, logging, rate limit; untrack `dev.db-wal/-shm` | todo |
| 10 | Full tests: backend, frontend, typecheck, lint, build, end-to-end | todo |
| 11 | Production database: migration 0006 is additive (CREATE TABLE only); recovery point (export) before deploy | todo |
| 12 | Merge to `main` (no force push), push, deploy Railway + Vercel, verify migration, smoke test, desktop and phone | todo |
| 13 | Handover documents (12) with screenshots of the deployed application | todo |
| 14 | Final delivery report | todo |
