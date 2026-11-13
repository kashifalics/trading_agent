# Delivery report: release v2 (2026-11-13)

## A. Deployment

| | |
|---|---|
| Frontend | https://trading-agent-frontend-sigma.vercel.app (Vercel, production) |
| Backend | https://backend-production-dd47.up.railway.app (Railway, service `backend`, SQLite on volume `/data`) |
| Production branch | `main` |
| Release commit | `496f49e` on `main` (merge of `feature/strategy-engine-v2`, no force push); post-deploy fixes `06b2fb2` (frontend only) |
| Deployed at | 2026-11-13: backend 16:50 UTC (Railway deployment `923f0a27`, SUCCESS); frontend 16:51 UTC, redeployed with the fixes at 17:41 UTC (Vercel production) |
| Database | Alembic `0005 -> 0006` applied at start at 16:51 UTC (additive: new table `signal_records`). Recovery point: API export of all customer data taken before the deploy (outside the repository). After the deploy: 438 paper trades and 11 predictions, the same as the export |
| Status | **Live and verified** (see C) |

## B. Research (Experiment 5, owner-approved)

- **Completed for XAUUSD.**
  - 84 pre-registered cells: 6 strategies × 2 directions × 7 timeframes. 51 had at least 100 development signals and were tested.
  - 65,103 simulated trades on the training segment (2003-05 to 2020-02-07). Real Dukascopy bid/ask, 1-minute resolution, matched
    random-entry controls.
  - Trade-weighted mean −0.150R per trade.
- **0 candidates passed development.** The best deflated Sharpe probability was 0.51 against the 0.95 needed, with 2,032 trials
  counted across experiments 1-5. CSCV probability of overfitting: 0.17.
- **Validation was not run:** it is only for cells that pass development. **The sealed final test (from 2023-06-24) was never
  read.**
- **EURUSD/GBPUSD not tested:** the free Dukascopy download was refused or throttled most of the time (about 1,800 of about
  12,000 EURUSD files). The FX part can run unchanged when the download completes.
- **Product status:** five strategies are NOT VALIDATED; range mean reversion is INSUFFICIENT EVIDENCE (never enough signals to
  test).
- Report: `docs/reports/XAUUSD_EXPERIMENT5.md`; frozen files in `docs/research/`.

## C. Testing

**Before the release (on the merged code):**

| Suite | Result |
|---|---|
| Backend (pytest) | 434 passed, 30 skipped (the skips need optional local data); engine tests re-run after the research-status change |
| Frontend unit and page tests (vitest) | 80 passed, including a new check that the Overview's server render has no clock-dependent text |
| End-to-end (Playwright, production build) | 8 of 8 passed |
| Typecheck, lint, production build | clean |

**Production checks (2026-11-13):**
- **Backend:**
  - Health responds; requests without the key get 401.
  - `/engine` serves all six instruments with fresh data and the research statuses.
  - `/engine/signals` works: migration 0006 is live, and lifecycle records were being created and stepped within minutes.
  - Logs show no errors.
- **Every page, desktop (1440 px) and phone (390 px), 30 checks:** 0 page errors, 0 console errors, 0 failed API calls, 0
  horizontal overflow, no `NaN` / `undefined` text, and 0 accessibility violations (axe).
- **The first sweep found three defects.** They were fixed, tested and redeployed (`06b2fb2`) before the second sweep above:
  - a hydration error on the Overview (React #418);
  - a table that could not be scrolled with the keyboard;
  - outdated wording on Settings.
- **Speed:**
  - The server answers in about 0.25 s; pages show their heading in 0.2-0.9 s and finish loading in 3-10 s.
  - During the checks, this machine's connection to Railway's Singapore edge was unreliable: TLS handshakes of 1-12 s and DNS
    failures. These inflated some single measurements to tens of seconds; the server timings above exclude them.
  - Details: `docs/handover/KNOWN_LIMITATIONS.md` item 11.

**Minor items left:** small tap targets on some pages (most on Data Sources: 44 small links and badges), below the 24 px
recommendation. They work, but are tight on a phone.

## D. Security

**Findings and fixes:**
- No secrets in tracked files or git history.
- No raw SQL built from strings.
- Every API route except `/health` needs the key (the new `/engine` routes included).
- Production refuses to start without a secret key and authentication.
- CORS is limited to the frontend address.
- The rate limit applies per client.
- Content-Security-Policy is in place.
- `backend/dev.db-wal/-shm` were untracked.

**Remaining risks:**
- **npm advisories:** `zod` (client-side form validation) and `postcss` inside Next.js (build time) have advisories whose fixes are
  breaking major upgrades. Neither is reachable from outside.
- **Public API docs:** `/docs` lists the endpoints (no data).
- **Key storage:** the API key is stored in the browser (localStorage), mitigated by the CSP.
- **Rotate the Twelve Data key** that was pasted in an earlier chat.

## E. Customer handover

- **Index:** `docs/handover/README.md` (12 documents). Screenshots of the deployed application are in `docs/release/screenshots/`.
- **Access:** open the frontend address, then enter the platform API key in **Settings → Save & verify**. The operator issues the
  key; it is not written in any document.
- **Limitations:** `docs/handover/KNOWN_LIMITATIONS.md`.

## F. Final assessment

**Released as an analysis-only platform, as the brief allows when no strategy passes validation.**

- **What works in production:**
  - Every instrument gets one clear action (BUY, SELL, WAIT FOR BUY, WAIT FOR SELL, EXIT or NO TRADE) with an exact entry,
    stop-loss and TP1-TP3.
  - Every signal is recorded once and followed to its outcome.
  - Paper trades are kept apart from new signals.
  - Every page agrees with the strategy engine.
  - The disclosures are on every signal page.
- **What is not proven:**
  - No strategy has an edge: Experiment 5 found none on 17 years of gold, after experiments 1-4 found none.
  - The plans are labelled **UNVALIDATED — HYPOTHETICAL TRADE PLAN**, and no win probability is shown.
  - The paper forward test of the older v1 rules stands at −53.2R over 305 closed trades (net of the spread). The product shows
    this figure on its Overview.
- **Not done in this release:**
  - The EURUSD/GBPUSD research: the free download was refused. It continues by itself, and the experiment can run later.
  - A forward test of the v2 strategies: it should start only if one passes research.
- **Recommendation:**
  - Use the platform for analysis and study, not to place money on its plans.
  - Watch backend memory (item 11 of the known limitations).
  - Run the FX part of Experiment 5 when the data is complete; no product change is needed for it.
