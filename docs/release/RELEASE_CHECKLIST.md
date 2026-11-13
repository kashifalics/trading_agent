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
| 2 | FX history: Dukascopy EURUSD/GBPUSD M1 download (detached process, `data/historical/fx_download.log`), then build and freeze the 70/15/15 split before any look | running, Dukascopy refusing connections (EURUSD about 1,800 of about 12,000 files, GBPUSD not started): FX part cannot finish today, reported as a limitation |
| 3 | Engine made evaluable at any past candle (window view) with causal zone lifetimes (no status look-ahead); live behaviour unchanged | done (replay equals a run on the prefix: tested; 11x faster sweep levels) |
| 4 | Experiment 5 harness: pre-registration (counts only, committed before outcomes), simulation, statistics, report | done; pre-registration committed 6ddce9d before outcomes (51 of 84 cells testable) |
| 5 | Run Experiment 5 on XAUUSD development and validation; FX when the data is ready | done for XAUUSD: 51 cells tested, 0 passed development (best deflated Sharpe 0.51 vs 0.95), so validation was not run and the sealed final test was never read; FX waits for its data |
| 6 | Research statuses in the product follow the result (failed = NOT VALIDATED) | done (51352c4): five NOT VALIDATED, range mean reversion INSUFFICIENT EVIDENCE; live API serves them |
| 7 | Consistency across pages (Chart Analysis, Trade Opportunities, Paper Trading) and disclosures (five categories) | done: engine strip on Chart Analysis and Trade Opportunities, category legend on Signals, Overview redesign (dark violet theme after the owner's Dribbble reference) |
| 8 | Risk, data and provider checks; news reported unavailable | done: stale data -> NO TRADE (new), weekend/rollover blocks, spread filter, news unavailable |
| 9 | Security: env, secrets, CORS, auth, dependencies, logging, rate limit; untrack `dev.db-wal/-shm` | done: no secrets in files or history, no raw SQL, routes protected, prod config enforced; npm zod/postcss advisories accepted (client/build only); dev.db-wal untracked |
| 10 | Full tests: backend, frontend, typecheck, lint, build, end-to-end | done: backend 434 passed / 30 skipped, frontend 79 passed, end-to-end 8/8, typecheck + lint + production build clean |
| 11 | Production database: migration 0006 is additive (CREATE TABLE only); recovery point (export) before deploy | done: export in `backups/2026-11-13-pre-v2/` (outside the repo); 0005 -> 0006 ran at start; 438 paper trades and 11 predictions before and after |
| 12 | Merge to `main` (no force push), push, deploy Railway + Vercel, verify migration, smoke test, desktop and phone | done: `496f49e` deployed 16:50-16:51 UTC; migration 0006 live; first sweep found 3 defects (Overview hydration error, keyboard-unscrollable table, outdated Settings text), fixed in `06b2fb2` and redeployed 17:41 UTC; second sweep: 15 pages x 2 widths with 0 errors, 0 failed calls, 0 overflow, 0 axe violations |
| 13 | Handover documents (12) with screenshots of the deployed application | done: `docs/handover/README.md` indexes the 12 documents and 11 screenshots of the final build (`docs/release/screenshots/`) |
| 14 | Final delivery report | done: `docs/release/DELIVERY_REPORT.md` (sections A-F) |
