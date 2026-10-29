# SentinelNepal — Implementation Plan

> Status: **Phase 0 draft — awaiting approval.** See [`architecture.md`](architecture.md) for
> the design and [`threat-model.md`](threat-model.md) for security analysis.

## 1. Starting point

Repository inspection (2026-10-28): the Git repository `amantiwaricr/SentinelNepal` had
**no commits and no files**. There is no existing code to preserve, so Phase 1 creates the
skeleton described in `architecture.md` §5.

## 2. Team roles (three students)

Roles are "owners", not silos — every merge needs a review from one other member.

| Student | Primary ownership | Secondary |
|---|---|---|
| **A — ML & data** | `ml/` package, dataset preparation, evaluation reports, feature-mapping table, collector feature window | Live compatibility gate |
| **B — Backend & security** | FastAPI, DB schema/migrations, auth, audit, incidents, firewall helper, nftables lab | Recommendation engine, security tests |
| **C — Frontend & QA** | React dashboard, typed API client, E2E tests, user manual, diagrams | Docker Compose, CI, test report |

All three: weekly status update in `docs/PROJECT_STATUS.md`, final report chapters, viva prep.

## 3. Twelve-week schedule

| Week | Phase | Main outputs | Owner(s) |
|---|---|---|---|
| 1 | 0 → 1 | Approved plan; repo skeleton, Compose, health endpoint, CI running lint + tests | All |
| 2 | 1 → 2 | Alembic baseline, frontend shell + routing; dataset downloaded & profiled (`ml/reports/data_profile.md`) | B, C / A |
| 3 | 2 | Preprocessing pipeline + tests; LR and RF trained; validation-set comparison | A |
| 4 | 2 / 3 | Test-set evaluation report, artifact manifest, `Predictor` API; DB models + auth | A / B |
| 5 | 3 | Alerts, incidents, notes, audit, dataset-analysis runs, dashboard summary API | B (A integrates ML service) |
| 6 | 4 | Login, dashboard, alerts explorer, alert details, IP investigation pages | C |
| 7 | 4 / 5 | Incidents, audit, model pages; recommendation engine; security review pass #1 | C / B |
| 8 | 6 | Collector (Zeek JSON tailer + replay), ingest API, bounded queue, WebSocket, feature-mapping doc | A, B |
| 9 | 6 / 7 | Compatibility gate + live_compatible model; firewall helper with fake adapter + unit tests | A / B |
| 10 | 7 | Approval workflow UI, nftables lab integration, expiry/reconcile, recovery guide | B, C |
| 11 | 8 | End-to-end workflows A–D, performance measurements, bug fixing, security review pass #2 | All |
| 12 | 8 | Documentation set, diagrams, final report, demo rehearsal, viva Q&A | All |

Buffer: weeks 11–12 absorb slippage. If a phase overruns by more than one week, cut from
the **stretch** list (§6) before cutting tests or documentation.

## 4. Phase-by-phase tasks and acceptance criteria

### Phase 1 — Repository foundation (week 1–2)

Tasks: directory structure; Vite React-TS + Tailwind + Router app with `AppLayout`;
FastAPI app factory with structured logging, request-ID middleware and the error envelope;
settings via `pydantic-settings` from env; SQLAlchemy engine/session; Alembic configured
with an initial empty-ish migration (e.g. `users` table only); Docker Compose (`db`,
`backend`, `frontend`) with health checks; `.env.example`; `.gitignore`; `README.md`
setup guide; GitHub Actions workflow running backend + frontend tests; first tests.

Acceptance:
- [ ] `docker compose up` starts db, backend, frontend; all report healthy.
- [ ] `GET /api/v1/health/live` → 200; `/health/ready` reports DB + migration state truthfully.
- [ ] `alembic upgrade head` works on an empty database; `alembic downgrade base` too.
- [ ] `pytest` (backend) and `npm test` (frontend) pass locally and in CI.
- [ ] A team member who did not write the README can set up from it.

### Phase 2 — Dataset processing and ML engine (weeks 2–4)

Tasks: `ml/data/README.md` download guide; profiling script producing real column list,
dtypes, missing values, label distribution, duplicates, IP availability; canonical schema
(`schema.py`) with aliases for both file families; label normalisation; preprocessing
`ColumnTransformer`; training CLI for LR and RF with seed; validation-based selection;
one-shot test evaluation; latency benchmark; `Predictor` class (load + hash check +
validate + predict + explain); manifest + versioning; `full` and `live_compatible`
profiles; ablation with/without TTL features; synthetic fixtures for unit tests.

Acceptance:
- [ ] `sentinel-ml train --profile full` and `sentinel-ml train --profile live_compatible` reproduce the artifact (same metrics with same seed and data hash).
- [ ] Reports in `ml/reports/` contain precision/recall/F1, confusion matrix, FPR, per-class metrics, latency, and environment details — generated from real runs.
- [ ] Synthetic-fixture tests are labelled `synthetic` and never quoted as model performance.
- [ ] Tests cover missing columns, extra columns, wrong types, NaN/inf, unknown categories, empty input.
- [ ] Training and inference share `schema.py` and the saved `Pipeline`; no feature logic copied into the backend.
- [ ] Leakage check documented (id, labels, IPs, ports, timestamps excluded; split before fitting).

### Phase 3 — Backend APIs, DB, auth, incidents (weeks 4–5)

Tasks: ORM models + migrations for all tables in `architecture.md` §7; Argon2 hashing;
session login/logout; role dependencies; login rate limiting + account lockout; CLI to
create the first admin (`python -m app.cli create-user --role admin`); all REST endpoints in §8 except
ingest/WS; dataset analysis runner (background thread, one run at a time); `ml_service`
wrapper; audit service + DB trigger; seed script for demo users (dev only).

Acceptance:
- [ ] Migrations apply on a clean DB and downgrade cleanly.
- [ ] Authorisation matrix test: every endpoint × {anonymous, analyst, admin} returns the expected status.
- [ ] Alert → incident → notes → status change persists and is audited with actor + action.
- [ ] Audit records cannot be modified through any endpoint, and the DB trigger rejects UPDATE/DELETE (tested).
- [ ] No model alert ever creates an incident with status `confirmed`.

### Phase 4 — Frontend SOC dashboard (weeks 6–7)

Tasks: typed API client (generated from OpenAPI or hand-written types checked in CI);
auth context + protected routes; the 11 pages; shared components (DataTable, Pagination,
SeverityBadge, StatusBadge, ConfirmDialog, EmptyState, ErrorState, LoadingState,
SourceTag "LIVE"/"DATASET"); Recharts charts; WebSocket hook with reconnect (moved to
Phase 6, when the backend gains a WebSocket endpoint).

Acceptance (met 2026-10-29; evidence in `PROJECT_STATUS.md`):
- [x] Login → dashboard (real API data) → alert details → create incident → add note → change status → see audit entry.
- [x] Firewall approvals page shows status, expiry, result, reversal; approve requires typed confirmation.
- [x] No hard-coded statistics (review); empty states shown on a fresh DB.
- [x] Component tests for tables, filters, confirm dialog, route guard; keyboard-accessible forms.

### Phase 5 — Recommendations and hardening (week 7)

Tasks: rule catalogue (§5 below); evidence checks; cautious fallback; security review
checklist from `threat-model.md`; dependency audit (`pip-audit`, `npm audit`); security
tests (SQLi strings, XSS payloads stored and rendered as text, CSRF header, CORS, upload
limits, path traversal in filenames, oversized fields).

Acceptance: as in the phase prompt — every recommendation lists evidence + limitations;
unknown categories get "investigate further"; sensitive actions role-checked; security tests pass.
Met 2026-10-29 (evidence in `PROJECT_STATUS.md`, `security-review.md`, `recommendations.md`).

### Phase 6 — Live monitoring (weeks 8–9)

Tasks: collector package (Zeek JSON log tailer handling rotation, validators, UTC
normalisation, http/ftp join by `uid` with short wait window, 100-connection window
aggregator, batching sender with retry/backoff, heartbeat); `replay` command for CSV;
ingest endpoint + bounded queue + inference worker; WebSocket broadcast; compatibility gate;
`docs/feature-mapping.md` with the verified table; lab runbook.

As built (2026-10-29): TShark instead of Zeek, in a Docker lab instead of a VM (team
decision; see `architecture.md` §10.1). The Zeek-specific tasks (log tailer, `uid` joins)
became a capture-file reader and a flow builder over TShark fields; the lab runbook is
`docs/lab-runbook.md`.

Acceptance (met 2026-10-29 in the sandbox lab; evidence in `PROJECT_STATUS.md`):
- [x] Replay of a CSV creates alerts that appear on the dashboard without page reload.
- [x] Invalid records are rejected and counted; collector offline is visible within 30 s
  (30 s after the last heartbeat; at once after a clean stop).
- [x] Live inference stays disabled until the gate passes; the reason is shown.
- [x] Lab run documented with real observations (screenshots/logs), no fabricated
  detections. The sandbox run used a model trained on synthetic data; a run with the real
  `full_no_ttl` model on the team machine is still to be recorded.

### Phase 7 — nftables and approved blocking (weeks 9–10)

Tasks: helper daemon (`firewall/sentinel_fw`) with request schema, validator, protected
ranges, `NftAdapter` and `FakeNftAdapter`, dry-run, idempotent unblock, list/verify;
systemd unit with `CapabilityBoundingSet=CAP_NET_ADMIN`, socket group permissions;
backend client + workflow state machine + reconcile task; UI wiring;
`docs/firewall-safety.md` with emergency recovery (`nft delete table inet sentinelnepal`).

Acceptance:
- [ ] Unit tests (no root) cover invalid IP/CIDR, protected targets, unauthorised users, self-approval refusal, duplicates, expiry, revoke idempotency, helper failure/timeout, DB failure, audit entries, interrupted action recovery.
- [ ] VM integration script shows: unrelated pre-existing tables/rules unchanged (ruleset diff before/after), block effective (ping/curl from client VM fails), expiry removes it, revoke removes it.
- [ ] No UI or API path reports "blocked" without helper confirmation + verify.

### Phase 8 — Integration, testing, documentation (weeks 11–12)

Tasks: workflows A–D end to end; full test run with recorded commands and outputs;
performance measurements (inference latency, throughput, API p95, live alert latency);
documentation set listed in the phase prompt; final review checklist.

Acceptance: as in the phase prompt; `docs/test-report.md` contains only real results.

## 5. Recommendation rule catalogue (draft for Phase 5)

Model categories are grouped so recommendations match what the model can actually predict:

| Rule group | Model categories | Example action | Requires approval |
|---|---|---|---|
| `dos` | DoS | Review traffic rates for the target service; consider rate limiting; consider upstream/ISP DDoS mitigation | Yes for any block |
| `recon` | Reconnaissance | Review exposed services on the destination; close unnecessary ports; watch for follow-up activity from the same source | Yes for any block |
| `exploit` | Exploits, Shellcode, Backdoor, Worms | Inspect the destination service; verify patch level; check for indicators of compromise on the host | Yes |
| `fuzzing_analysis` | Fuzzers, Analysis | Review application/input-validation logs for the destination service | Yes |
| `generic` | Generic | Category is broad in UNSW-NB15 → investigate further before acting | Yes |
| `bruteforce_like` | *None in UNSW-NB15* | Only produced by an explicit heuristic (many short failed connections to an auth service such as port 22, from Zeek evidence) and labelled "heuristic, not model" | Yes |
| `unknown` | Score below threshold, gate disabled, or unsupported category | "Further investigation recommended"; no blocking suggestion | — |

Every rule specifies `required_evidence`; if evidence is missing (e.g. no source IP in a
partitioned-dataset row) the recommendation downgrades to investigation-only and says why.

## 6. Scope control

**Must have (core):** everything in Phases 1–5; CSV replay through the ingest API; firewall
helper with fake adapter and VM-tested nftables adapter; documentation set.

**Should have:** Zeek live collection in the lab; `live_compatible` model with gate.

**Stretch (only if ahead of schedule):** Zeek over UNSW-NB15 PCAP slices for mapping
validation; probability calibration (`CalibratedClassifierCV`) with reliability diagram;
custom Zeek script for `tcprtt/synack/ackdat`; audit hash chain; Playwright E2E in CI;
CSV/PDF report export.

**Explicitly excluded:** automatic blocking, LLM features, paid APIs, geolocation/threat
intel, multi-tenant support, production hardening beyond lab needs.

## 7. Definition of done (every task)

1. Code follows `AGENTS.md`.
2. Tests written/updated and passing locally and in CI.
3. Docs updated (README/API/feature mapping as relevant).
4. `docs/PROJECT_STATUS.md` updated at milestone end with real test output summary.
5. Reviewed by another team member.

## 8. Key risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Live features don't match dataset features | High | High | Two feature profiles, compatibility gate, observation-only fallback, honest reporting |
| Over-optimistic metrics (shortcut features, duplicates) | High | Medium | Ablation without TTL features, de-duplicated test report, validation-only model selection |
| Firewall mistake locks out the lab VM | Medium | High | Dedicated table, protected ranges, kernel timeouts, dry-run default, console access, recovery guide |
| Zeek/VM setup consumes too much time | Medium | Medium | CSV replay path is fully functional without Zeek; Zeek is "should have" |
| Team member unavailable | Medium | Medium | Ownership + secondary owner per module; small PRs; docs updated weekly |
| Scope creep | Medium | High | Stretch list; phase gates; Phase 8 forbids new features |
| Dataset download blocked / large | Low | Medium | Partitioned CSVs are small (tens of MB); document mirrors only if official |
| Dependency incompatibility | Low | Low | Pin versions in Phase 1 after an actual install test; CI |
| Ethical/legal issue from monitoring | Low | High | Lab-only, written authorisation from supervisor, no third-party traffic captured or committed |

## 9. Overall acceptance criteria (project)

1. Uploading the official UNSW-NB15 test CSV produces a completed analysis run, alerts, and
   dashboard summaries; uploading a full-record CSV additionally enables IP investigation.
2. Reported model metrics are reproducible from documented commands and match the stored report.
3. Analysts can investigate alerts and manage incidents; every change is audited.
4. Replay (and, if achieved, Zeek) traffic produces dashboard updates without manual upload;
   live inference only runs when the compatibility gate passes.
5. In the isolated lab, an admin approves a temporary block requested by another admin; the
   helper applies and verifies it; it is visible in the UI and audit log; it expires or is
   revoked; unrelated firewall rules are provably unchanged.
6. No part of the UI or documentation presents a prediction as proof of an attack.
7. All tests in the test report were actually executed, with commands and results recorded.

## 10. Questions for approval

1. **Self-approval:** the plan requires a *different* admin to approve a block (two-person
   rule, enabled by default, configurable for a solo demo). Acceptable?
2. **Who may request blocks:** admins only by default; allow analysts to *request* (not approve)?
3. **Auth mechanism:** server-side sessions in an HttpOnly cookie (simpler logout/revocation
   than JWT). Acceptable?
4. **Lab resources:** can the team provide at least two Ubuntu VMs on an isolated network
   (VirtualBox/VMware host-only), and written supervisor authorisation for lab monitoring?
5. **Team allocation** in §2 — adjust names/roles as needed.
