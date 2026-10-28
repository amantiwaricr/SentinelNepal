# SentinelNepal — Project Status

_Last updated: 2026-10-28_

## Current phase

**Phase 0 — Planning and architecture: drafts complete, awaiting approval.**
Phase 1 must not start until the plan is approved (see questions in
[`implementation-plan.md`](implementation-plan.md) §10).

## Phase tracker

| Phase | Title | Status |
|---|---|---|
| 0 | Planning and architecture | Draft complete — awaiting approval |
| 1 | Repository foundation | Not started |
| 2 | Dataset processing and ML engine | Not started |
| 3 | Backend APIs, DB, auth, incidents | Not started |
| 4 | Frontend SOC dashboard | Not started |
| 5 | Recommendations and hardening | Not started |
| 6 | Live network monitoring | Not started |
| 7 | nftables approved blocking | Not started |
| 8 | Integration, testing, documentation | Not started |

## Completed in Phase 0

- Inspected the repository: it had no commits and no files, so there was no existing code to preserve.
- Wrote `docs/architecture.md`: components, repository layout, data model, API, ML pipeline,
  feature mapping (preliminary), live processing, firewall design, security boundaries,
  failure handling.
- Wrote `docs/implementation-plan.md`: roles, 12-week schedule, per-phase tasks and
  acceptance criteria, recommendation catalogue draft, scope control, risks.
- Wrote `docs/threat-model.md`: assets, trust boundaries, STRIDE mitigations, residual risks,
  security test checklist.
- Wrote `AGENTS.md`: persistent conventions and rules.

## Test results

None — no code exists yet. No tests have been run.

## Model metrics

None. The UNSW-NB15 dataset has not been downloaded or inspected yet. Any dataset facts in
the docs (row counts, column names, categories) are taken from the dataset's published
description and are marked "to verify in Phase 2".

## Environment observed (planning container only)

Recorded so that Phase 1 pins versions that actually install. These are from the cloud
container used for planning, not from the team's machines:
Python 3.13, Node.js 22, Docker 29, PostgreSQL client 16, `nft` present; Zeek not installed.

## Known issues / open questions

1. Approval needed for: two-person firewall approval rule, who may request blocks,
   session-cookie auth, lab VM availability and written authorisation, team role allocation.
2. Live feature compatibility is expected to be partial (TTL, jitter, loss, TCP window and
   handshake-timing features are not in default Zeek `conn.log`). This is a design input,
   not yet verified.

## Next steps

1. Team reviews and approves (or amends) the Phase 0 documents.
2. Phase 1: repository skeleton, Docker Compose, health endpoint, Alembic, CI, first tests.
