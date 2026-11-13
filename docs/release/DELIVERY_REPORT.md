# Delivery report: release v2 (2026-11-13)

## A. Deployment

| | |
|---|---|
| Frontend | https://trading-agent-frontend-sigma.vercel.app (Vercel, production) |
| Backend | https://backend-production-dd47.up.railway.app (Railway, service `backend`, SQLite on volume `/data`) |
| Production branch | `main` |
| Release commit | _filled at deploy_ |
| Deployed at | _filled at deploy_ |
| Database | Alembic `0006` applied at start (additive: new table `signal_records`); recovery point: API export of all customer data taken before the deploy (outside the repository) |
| Status | _filled after verification_ |

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

_filled after the final runs_

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

_filled after production verification_
