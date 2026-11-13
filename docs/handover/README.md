# Handover documents (release v2)

| # | Document | File |
|---|---|---|
| 1 | Customer user guide | [docs/USER_GUIDE.md](../USER_GUIDE.md) |
| 2 | Technical architecture | [docs/ARCHITECTURE.md](../ARCHITECTURE.md), [TECHNICAL_HANDOVER.md §2](../TECHNICAL_HANDOVER.md), strategy engine: [engine_v2/DESIGN.md §1](../engine_v2/DESIGN.md) |
| 3 | Installation and configuration | [docs/LOCAL_SETUP.md](../LOCAL_SETUP.md), [TECHNICAL_HANDOVER.md §4-5](../TECHNICAL_HANDOVER.md) |
| 4 | API documentation | [docs/API_SPECIFICATION.md](../API_SPECIFICATION.md); live OpenAPI at `<backend>/docs` |
| 5 | Database and migrations | [docs/DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md), [TECHNICAL_HANDOVER.md §6](../TECHNICAL_HANDOVER.md) |
| 6 | Trading strategies | [STRATEGIES.md](STRATEGIES.md) (customer), [engine_v2/DESIGN.md](../engine_v2/DESIGN.md) (exact rules) |
| 7 | Research and validation | [reports/XAUUSD_EXPERIMENT5.md](../reports/XAUUSD_EXPERIMENT5.md), [engine_v2/EXPERIMENT_PLAN.md](../engine_v2/EXPERIMENT_PLAN.md), earlier experiments in [docs/reports/](../reports/) |
| 8 | Risk management | [RISK_MANAGEMENT.md](RISK_MANAGEMENT.md) |
| 9 | Known limitations | [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) |
| 10 | Troubleshooting | [TECHNICAL_HANDOVER.md §11](../TECHNICAL_HANDOVER.md) |
| 11 | Maintenance | [TECHNICAL_HANDOVER.md §13](../TECHNICAL_HANDOVER.md) |
| 12 | Deployment and rollback | [TECHNICAL_HANDOVER.md §12](../TECHNICAL_HANDOVER.md) |

The release record is in [docs/release/](../release/): the checklist, the delivery report and screenshots of the deployed
application.

**Customer access:**
- **Address and key:** open the frontend address from the delivery report, then enter the platform API key in **Settings → Save &
  verify**. The key is issued by the operator and is never shown in these documents.
- **Analysis only:** the platform never places orders.
