# SentinelNepal — Project Status

_Last updated: 2026-10-29_

## Current phase

**Phase 6 — Live network monitoring: complete** (TShark in an isolated Docker lab; see
the limitations below). Next: Phase 7 (nftables blocking with approval). That phase needs a
disposable Linux VM: real nftables tests must never run on a primary machine.

The team asked to start Phase 6 but has not yet recorded the supervisor's **written
authorisation** in this repository. The lab is a closed Docker network, but the
authorisation must still be filed before the lab is demonstrated.

## Phase tracker

| Phase | Title | Status |
|---|---|---|
| 0 | Planning and architecture | Approved as written (2026-10-28) |
| 1 | Repository foundation | Complete (see acceptance below) |
| 2 | Dataset processing and ML engine | Complete (real results; limitations documented) |
| 3 | Backend APIs, DB, auth, incidents | Complete |
| 4 | Frontend SOC dashboard | Complete |
| 5 | Recommendations and hardening | Complete |
| 6 | Live network monitoring | Complete (TShark/Docker lab; real-model lab run pending) |
| 7 | nftables approved blocking | Not started |
| 8 | Integration, testing, documentation | Not started |

Phase 0 decisions recorded at approval: a different admin must approve each block
(configurable for solo demos); only admins request blocks; server-side sessions in an
HttpOnly cookie; team roles as in `implementation-plan.md` §2.

Phase 6 decisions (team, 2026-10-29):

- **TShark instead of Zeek.** TShark does the protocol dissection; SentinelNepal only
  groups its fields into flows.
- **A Docker lab instead of a VirtualBox/WSL VM**, so that it runs on Docker Desktop for
  Windows.

## Phase 6 — completed work

- **`sentinel_ml.live`** (feature engineering stays in `ml/`):
  - runs `tshark -T fields` with a fixed argument list and no shell, and parses its packet
    lines (malformed lines are counted, not guessed);
  - builds bidirectional flows: they end on FIN/RST + 2 s, 30 s idle, or 300 s active, with
    a 50,000-flow memory bound;
  - computes UNSW-NB15 features with the dataset's units, plus the 100-connection `ct_*`
    window;
  - `TSHARK_FEATURE_MAP` and `check_compatibility()`.
- **Feature mapping:** `ct_state_ttl` cannot be obtained from TShark. The live profile is
  therefore `full_no_ttl` (36 features), of which 15 are documented approximations
  (`docs/feature-mapping.md`, generated tables). `sentinel-ml pcap-features` exports flows
  from a capture to CSV.
- **Backend:**
  - collectors with hashed bearer tokens (`create-collector`, `rotate-collector-token`);
  - `POST /ingest/flows` validates each record (bad records are counted, the rest of the
    batch is kept), with a 2 MiB / 500-record limit and a bounded queue (overflow is
    counted as dropped);
  - `POST /ingest/heartbeat`;
  - a `LiveWorker` thread scores batches; duplicate alerts are prevented by `dedup_key`;
  - the **live gate**: an active `full_no_ttl` model, compatible features, admin approval
    (audited), and the collector in `inference` mode (audited; refused while the gate is
    closed);
  - `/live/status`, `/live/flows`, `/collectors`, `/models/{id}/live-approval`;
  - the `/events` WebSocket (session cookie, Origin check, session re-checked every 60 s);
  - collector health on System & Settings: offline 30 s after the last heartbeat, or at
    once after a clean stop. Migration `0004`.
- **Collector** (`collector/`, see its README):
  - reads finished dumpcap ring-buffer files, ordered by their start time;
  - batching sender with a bounded buffer and backoff; heartbeat every 10 s;
  - `replay` sends a UNSW-NB15 CSV as `source: replay`.
- **Docker lab** (`docker compose --profile lab`):
  - `lab-server` (nginx + sshd) and `lab-client` on an `internal` network;
  - `capture` (dumpcap as an unprivileged user with only `CAP_NET_RAW`, in `lab-server`'s
    network namespace);
  - `collector` (unprivileged, read-only filesystem, no capabilities);
  - traffic scripts `normal.sh`, `scan.sh`, `ssh-guess.sh`, `http-burst.sh`, which can only
    target `lab-server`.
- **Frontend:**
  - Live Monitoring page: gate status and reason, approximated features, collector
    online/offline, mode, counters and last problem, recent flows tagged Live/Replay;
  - admin mode switch; live approval on the Model page;
  - a WebSocket provider with reconnect/backoff. The dashboard, alerts list and Live page
    refetch on notifications without a reload.
- **Docs:** `docs/lab-runbook.md` (Windows/Docker Desktop steps), architecture §10.1/§11.1,
  threat model (collector, dissector), `collector/README.md`, README.
- **CI:**
  - new `collector` job (ruff, mypy, pytest with TShark installed);
  - the ML job installs TShark, so the real-capture test runs;
  - the audit job includes the collector;
  - the compose job builds the `lab` profile.

## Phase 6 — test results (actually run on 2026-10-29)

| Check | Result |
|---|---|
| Backend `ruff format --check`, `ruff check`, `mypy` | clean |
| Backend tests with PostgreSQL | **232 passed** (11 live/ingest/WebSocket integration tests; authorisation matrix extended to the new routes) |
| ML `ruff`, `mypy`, `pytest` | clean; **171 passed** (22 live tests, one runs real TShark 4.2.2 on a synthetic pcap) |
| Collector `ruff`, `mypy`, `pytest` | clean; **14 passed** (synthetic packets and CSV rows; TShark 4.2.2 installed) |
| Frontend generated types, format, lint, typecheck | clean |
| Frontend tests | **83 passed** (14 files) |
| Frontend build | built |
| `docker compose --profile lab config` | valid |
| `pip-audit` for the collector | not run locally (tool not installed in the sandbox); the CI audit job runs it |

### Lab run (sandbox, 2026-10-29, real containers and real captured packets)

**Setup.** This was the Docker lab on the verification sandbox, not the team's machine.

- Docker Hub and the Debian mirror were unreachable there. The images were built from a
  locally bootstrapped Ubuntu 24.04 base, with the same packages and steps as the committed
  Dockerfiles. Those Dockerfiles (`python:3.13-slim`, `debian:bookworm-slim`) are built by
  the CI compose job.
- **The model was trained on synthetic data** (`sentinel_ml.testing`, `full_no_ttl`
  profile, threshold set by hand to 0.2), because the UNSW-NB15 files are not in the
  sandbox. Its predicted categories and scores are therefore **meaningless**. The run shows
  that the pipeline works; it says nothing about detection quality. A run with the real
  `full_no_ttl` model is still to be recorded on the team machine.
- Times are UTC. Screenshots were taken with Playwright/Chromium and not committed.

**Flows:**

- After the fixes below, an offline rebuild of 12 capture files gave 98 flows, all `FIN`,
  none single-packet.
- The Live page showed real lab flows: `lab-client:<port> → lab-server:80`, tcp/http,
  `FIN`, 6/4 packets, about 400/470 bytes.
- Heartbeat counters after the run: 35 capture files, 8,406 packets, 0 malformed lines,
  0 unreadable files, 0 send failures, 0 dropped.
- 26 records were rejected. All were sent before the `feature_source` fix below.

**Gate:**

- In observation mode, flows were shown with **Not scored**, and the gate showed "not
  approved for live inference".
- Through the browser, an admin approved the model and switched `lab-sensor` to
  inference. The gate then read: "approved for live use. All features obtainable from
  TShark; 15 are approximations not validated against UNSW-NB15 ground truth."

**Exercises** (synthetic model, so the labels mean nothing):

| Exercise (time) | Observed |
|---|---|
| `scan.sh` (16:19:49) | Dashboard total went from 9 to 1,041 with **0 page navigations**. WebSocket messages: 1 `hello`, 6 `flows.observed`, 6 `alerts.created`. One alert per probed port (1,024 "Exploits", plus 17 "Fuzzers" from browsing) |
| ordinary `normal.sh` browsing | Also raised alerts with the synthetic model (false positives on known-benign traffic) |
| `ssh-guess.sh` (16:29:15–16:30:10) | 15 alerts on port 22 ("Fuzzers", scores 0.600–0.680) |
| `http-burst.sh` (finished 16:30:11) | Last burst alert stored at 16:30:45, about 34 s later. 329 port-80 alerts in that window (the burst plus browsing) |
| collector `docker stop` (16:20:48–51) | Health showed `collectors: unavailable` at the 16:21:25 poll (5 s polling), 30 s after the last heartbeat. Then a change was made: a clean stop shows offline at once. Retest: stopped 16:24:07, `unavailable` at 16:24:10 |
| collector restart (16:23:54) | Online at 16:24:00. It read the capture files written while it was down (164 more alerts) and created **no duplicates**: 1,215 alerts, 1,215 distinct flows |
| `ssh-guess.sh` on a quiet network (background browsing stopped; after the closed-flow change below), 16:33:02–16:33:42 | All 15 port-22 alerts were stored by 16:33:44, 2 s after the script ended. dumpcap rotated its file at 16:33:44 even without traffic |
| replay of a 300-row synthetic CSV | `rows_read=300, rows_rejected_locally=0, accepted_by_api=300`; 195 `replay` alerts |
| replay of a 200-row synthetic CSV, browser open | Dashboard total went from 1,427 to 1,554 with 0 page navigations |

### Phase 6 acceptance

- [x] The collector processes supported records: TShark flows and CSV replay (lab run;
  `test_live.py`, `test_collector.py`).
- [x] Invalid records are rejected or handled safely, and counted. The integration test
  sends bad IPs, non-finite values, unknown features, negative times and missing fields.
  In the lab run, 26 records were rejected without stopping the collector.
- [x] The dashboard updates without manual CSV upload: WebSocket notifications plus a REST
  refetch, with no reload (lab run, frontend tests).
- [x] Collection failures are visible: offline status, health component, unreadable
  capture files, send failures, drops and last error are shown on the Live page.
- [x] Live inference is enabled only for validated compatible features. The gate requires
  compatibility and an admin approval; the `full` model is refused (`ct_state_ttl`).
  "Validated" here means the mapping was checked and approved by a person. The 15
  approximated features have not been validated against ground truth (see limitations).
- [x] CSV replay remains as a fallback (`sentinel-collector replay`).
- [ ] A lab run with the real `full_no_ttl` model, recorded on the team machine. Supervisor
  authorisation to be filed.

### Defects found and fixed during Phase 6

- Flow records lacked `feature_source`, so the API rejected them (the 26 rejected records).
- dumpcap restarts reset its file sequence numbers, so name order interleaved two runs.
  The flow builder's clock jumped ahead, which split almost every flow (170 of 189 flows
  had a single packet). Files are now ordered by their start time, and idle flows are
  ended 60 s behind real time (the file being written may still contain packets).
- Capture files were root-owned with mode 0600, so the collector could not read them.
  Capture and collector now share an unprivileged user, and dumpcap gets `CAP_NET_RAW`
  as a file capability.
- nginx failed on the IPv6 listen line in a container without IPv6; the lab server now
  listens on IPv4 only.
- A WebSocket refresh could be lost when a reconnect changed the context value; the
  subscription is now stable.
- A collector's clean shutdown waited 30 s before showing offline; it now shows at once.
- With the 60 s lag above, TCP flows that had already closed also waited for it on a quiet
  network. Closed flows now end without the lag (test
  `test_closed_flows_end_promptly_on_a_quiet_network`).

## Phase 5 — completed work

- **Recommendation engine** (`backend/app/services/recommendations/`, explained in
  `docs/recommendations.md`): 11 versioned rules in code, grouped as DoS, reconnaissance,
  exploit-like (Exploits, Shellcode, Backdoor, Worms), fuzzing/analysis, Generic, a labelled
  brute-force-like heuristic, unknown categories, and a fallback. Each rule states its kind
  (investigate, harden, contain), required evidence, priority, limitations and whether a
  human must approve. Evidence comes only from stored data: addresses, port/service, score,
  the model's top class, the model's recorded per-class precision, and counts of related
  stored alerts. When evidence is missing, the stronger action is withheld and a
  `fallback.investigate` recommendation names what is missing. Containment always needs a
  recorded source, a strong score and a category with at least 50% recorded precision.
- Recommendations are generated when an alert is first opened and stored once per rule
  (migration `0003`, unique `alert_id` + `rule_id`), with the rule version and the evidence as
  observed. `GET /recommendations/rules` publishes the catalogue; model listings include
  `low_precision_categories`, used by the UI and the rules (one definition, in the backend).
- **Frontend:** recommendation cards on the alert page (priority, approval need, rule and
  version, action, reason, evidence checked with met/missing, limitations); the
  Recommendations page lists the rule catalogue; the model page takes "unreliable label"
  from the API.
- **Hardening** (details and evidence in `docs/security-review.md`):
  - request body limit: 64 KiB for JSON, the upload limit for uploads, checked from
    `Content-Length` and while streaming (oversized uploads are no longer spooled to disk);
  - API responses add `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`,
    `Cache-Control: no-store`, `Cross-Origin-Resource-Policy: same-origin`;
  - partitioned CSV uploads parse only known UNSW-NB15 columns;
  - security tests for injection strings in every filter and at login, stored script
    payloads, oversized fields and streamed uploads;
  - dependency audit job in CI (`pip-audit`, `npm audit`); threat-model checklist updated.

## Phase 5 — test results (actually run on 2026-10-29)

| Check | Result |
|---|---|
| Backend `ruff format --check`, `ruff check`, `mypy` | clean |
| Backend tests with PostgreSQL | **214 passed** (17 rule unit tests, 6 recommendation integration tests, 20 security integration tests, 4 new middleware tests) |
| Backend tests without a database | 68 passed, 146 skipped |
| `alembic check`; downgrade 0003 → 0002 → upgrade | no new operations; both directions ran |
| ML `ruff`, `mypy`, `pytest` | clean; **140 passed** (new wide-file test) |
| Frontend generated types, format, lint, typecheck | clean |
| Frontend tests | **74 passed** (13 files) |
| Frontend build | built |
| `pip-audit 2.10.1` (backend and ml requirements, runtime and dev) | no known vulnerabilities |
| `npm audit` (frontend) | 0 vulnerabilities |

**Browser check** (real backend and PostgreSQL, Vite dev server, Playwright/Chromium;
synthetic model and synthetic CSV with RFC 5737 documentation addresses; deleted
afterwards):

- The 300-row synthetic upload completed (300 valid, 204 alerts).
- API responses in the browser carried the CSP, `no-store` and CORP headers; a 100 KB JSON
  body sent from the signed-in page was refused with `413 payload_too_large`.
- From source `192.0.2.10`:
  - an Exploits alert got `exploit.inspect_target` and `exploit.contain` (needs approval),
    plus `bruteforce_like.review_auth`, because the synthetic record's service was `ftp`;
  - a DoS alert got `dos.review_load` and `dos.rate_limit`;
  - a Generic alert got `generic.investigate`;
  - a Reconnaissance alert got `recon.review_exposure` and a fallback stating that
    `recon.watch_source` was withheld (the source had alerts to only 1 port).
- The synthetic model's validation precision is about 100%, so containment appeared where
  all other evidence was present. With the real `full` model, DoS, Shellcode, Fuzzers,
  Backdoor and Analysis are below 50% on the testing file and never get containment.
- The Recommendations page listed all 11 rules. No page errors.

### Phase 5 acceptance

- [x] Recommendations are tied to supported evidence: every recommendation stores its
  required evidence and what was observed; unmet evidence withholds the action
  (`test_recommendation_rules.py`, `test_recommendations.py`).
- [x] Unknown categories receive cautious guidance (`unknown.investigate`, no blocking).
- [x] No recommendation is presented as proof of an attack: every rule's limitations say so,
  and a test rejects overclaiming words in rule text.
- [x] Sensitive actions require appropriate permissions: harden and contain rules are
  flagged for human approval; blocks still need an admin-approved firewall request;
  authorisation matrix covers the new endpoint.
- [x] Security tests cover common weaknesses (see `docs/security-review.md`).

### Defects found and fixed during Phase 5

- A body-size error raised inside the request stream was turned into a generic 400 by
  FastAPI's body parsing; the middleware now sends the 413 itself.
- Evidence text said "1 ports"; counts are now pluralised correctly.
- Test setup: the streamed-upload test first ran without the analyst user it signs in as.

## Phase 4 — completed work

- **Typed API client generated from the backend schema.** `python -m app.cli export-openapi`
  writes `frontend/openapi.json`. A backend unit test fails when that file is stale.
  `npm run gen:api` (`frontend/scripts/gen-api-types.mjs`, a small purpose-built generator,
  because `openapi-typescript` pins TypeScript 5) writes `src/types/api.gen.ts`, and CI runs
  `npm run gen:api:check`. Response fields with fixed value sets (alert source, status,
  severity and category; incident and firewall status; audit outcome) are now `Literal`
  types in the API schema; a unit test keeps them equal to the database CHECK values.
- **Backend additions:** `GET /api/v1/users/directory` (any signed-in user: id, username,
  role, active flag) for assignment pickers and requester names; added to the
  authorisation matrix.
- **Authentication in the UI:** sign-in form; `/auth/me` on start-up; route guard
  (`RequireAuth`) with a post-login redirect restricted to same-app paths; any 401 returns
  to sign-in with "session ended"; sign-out. The session stays in the HttpOnly cookie:
  nothing is stored in web storage (ESLint rule). Navigation hides the admin-only audit
  page from analysts; the API enforces every rule regardless.
- **Pages:** dashboard (stat cards, Recharts activity and category charts loaded lazily,
  severity/status breakdowns, frequent source IPs, incidents, analysis runs, component
  health, All / Dataset / Live source switch); alerts explorer (IP, CIDR, category,
  severity, status, source, time filters in the URL; sorting; pagination); alert details
  (connection, model assessment with threshold, top class scores, stored feature values,
  related alerts, review status, incidents, recommendations); IP and subnet investigation;
  incidents list and detail (create, edit, assign, status workflow limited to allowed
  transitions with confirmation, notes, audit-based history); firewall approvals (list,
  detail, new request prefilled from an alert, approve with typed target, reject with
  reason, revoke; requester, status, expiry, execution result and reversal shown); audit
  logs (admin); model evaluation (recorded validation/test metrics, threshold, per-class
  precision with "unreliable label" below 50%, admin activation); dataset analysis (upload,
  run list polled while a run is in progress); system & settings (readiness, components,
  admin user management); recommendations (states that the engine is Phase 5).
- **Honesty in the UI:** every alert shows a DATASET / REPLAY / LIVE tag; scores are labelled
  uncalibrated and never shown as percentages; alert pages state "prediction, not proof";
  no geolocation, ownership or threat intelligence anywhere; firewall pages state that
  nothing is applied before Phase 7 and show "Applied" only when the API's `applied` is true.
- **Accessibility:** labelled form controls, captioned tables, a modal dialog with focus
  trap and Escape, keyboard-operable source switch, skip link, text alternatives for charts.

## Phase 4 — test results (actually run on 2026-10-29)

| Check | Command | Result |
|---|---|---|
| Generated types current | `npm run gen:api:check` | up to date |
| Frontend format / lint / types | `npm run format:check && npm run lint && npm run typecheck` | clean |
| Frontend tests | `npm test` | **73 passed** (12 files) |
| Frontend build | `npm run build` | built; main chunk 379 kB (115 kB gzip), charts chunk 356 kB loaded only on the dashboard |
| Backend lint / types | `ruff format --check . && ruff check . && mypy` | clean |
| Backend tests (with PostgreSQL) | `TEST_DATABASE_URL=… pytest` | **166 passed** |
| Backend tests (no database) | `pytest` | 47 passed, 119 skipped |
| Migrations vs models | `alembic check` | no new upgrade operations |
| ML | `ruff …; mypy; pytest` | 139 passed |

Frontend tests use a route-based fake of the API (`src/test/mockApi.ts`) with hand-written,
synthetic fixtures. They cover the route guard, sign-in failure and success, open-redirect
refusal, session expiry, sign-out, role-based navigation, tables, pagination, the
confirmation dialog (typed text, focus, Escape), alert filters in the URL, alert
acknowledgement, incident creation from an alert, incident status change, assignment and
notes (markup rendered as text), firewall approval with typed target, self-approval
refusal, rejection reason, analyst view, request creation, dashboard figures and empty
states, the source switch, upload as multipart, model activation, user creation and audit
filters.

**Browser walkthrough (real backend, PostgreSQL and Vite dev server; Playwright/Chromium;
synthetic model and synthetic CSV using RFC 5737 documentation addresses).** Observed:

1. A signed-out visit to `/alerts` showed the sign-in page; a wrong password showed
   "Invalid username or password" with a request ID.
2. After sign-in the browser held an `HttpOnly`, `SameSite=Strict` cookie on `/api`;
   `localStorage`, `sessionStorage` and `document.cookie` were all empty.
3. The fresh database showed empty states. Uploading the 300-row synthetic CSV completed
   with 300 valid rows, 0 rejected and 204 alerts (synthetic model threshold 0.200); the
   dashboard's total-alerts card showed 204; the Live view showed no live alerts.
4. Filtering alerts by source `192.0.2.10` returned 41, equal to a direct database count.
5. Alert → IP investigation → new incident → note (`<b>` shown as text) → assignment →
   "Under investigation"; the incident history listed all four actions.
6. The analyst's block request was refused ("Only administrators may request blocks");
   `/audit` showed "Not available for your role".
7. admin2 created the request; admin2's own approval was refused ("A different
   administrator must approve this request"); admin1's approve button stayed disabled with
   a wrong target and succeeded with the exact one. The list then showed "Approved (not
   applied)", "No expiry (not applied)", "Not executed: no firewall helper (added in
   Phase 7)", "Not revoked".
8. The audit log listed every step, including the denied self-approval.
9. At 390 px width there was no horizontal overflow.

The browser console showed only the expected 401/403 responses (signed-out check, wrong
password, refused requests). The synthetic model, CSV and database were deleted afterwards.

### Phase 4 acceptance

- [x] Login → dashboard (real API data) → alert details → create incident → add note →
  change status → see audit entry (walkthrough steps 1–5 and 8; component tests).
- [x] Firewall approvals page shows status, expiry, result and reversal; approval requires
  typed confirmation (walkthrough step 7; tests).
- [x] No hard-coded statistics: every figure comes from an API response (review; dashboard
  test checks values from a synthetic response); empty states shown on a fresh database.
- [x] Component tests for tables, filters, confirmation dialog and route guard;
  keyboard-accessible forms (labels, focus trap, Escape).
- Deferred: the WebSocket hook in the plan's Phase 4 task list moves to Phase 6, because the
  backend has no WebSocket endpoint until live ingest exists. Dataset runs are polled over
  REST while in progress.

### Defects found and fixed during Phase 4

- Two `banner` landmarks: page headers used `<header>` inside `main`; changed to `<div>`.
- Helper functions exported from component files broke React fast refresh; moved to `lib/`.
- The Recharts bundle made the main chunk 736 kB; charts are now loaded lazily.
- Bottom dashboard row stretched panels to equal height; aligned to the top.
- The first walkthrough read the result count before the filtered response arrived (a
  script race, not an app bug); the script now waits for the response.

## Phase 3 — completed work

- **Schema** (migration `0002`): sessions, model versions, analysis runs, collectors, alerts
  (`INET` columns, GiST indexes), incidents, incident–alert links, notes, recommendations,
  firewall requests and results, audit logs. CHECK constraints from shared enums; partial
  unique indexes (one active model per profile; one open firewall request per target); a
  trigger rejecting UPDATE, DELETE and TRUNCATE on `audit_logs`.
- **Authentication**: Argon2id; password policy; timing-equalised failures; opaque session
  token (SHA-256 stored) in an HttpOnly, SameSite=Strict cookie; idle (30 min) and absolute
  (12 h) expiry; lockout after 5 failures; per-IP login rate limit; one generic login error
  with the real reason in the audit log; CSRF header required on state-changing requests;
  production refuses placeholder database passwords.
- **Authorisation**: `admin` and `analyst` roles enforced server-side on every route; an
  authorisation-matrix test covers every API route (enumerated from OpenAPI).
- **Users**: admin API (create, change role, deactivate, reset password — revokes sessions)
  with guards against locking out the last admin; `python -m app.cli create-user`.
- **Models**: CLI-only registration from `MODEL_ARTIFACTS_DIR` with the trusted SHA-256,
  metrics and validation-chosen alert threshold; synthetic models refused unless explicitly
  allowed; audited activation; models load only through the hash-checked `Predictor`.
- **Dataset analysis**: streamed uploads (size, type and content checks; server-generated
  names), background worker (one run at a time, per-chunk progress, interrupted runs marked
  failed, starts even if the database is down), alerts via the attack-score threshold.
- **Alerts and investigation**: filters (IP, CIDR, category, severity, status, source, time),
  sorting, pagination, detail with evidence, audited status changes; IP and subnet summaries
  from stored data only; dashboard summary; detailed component health.
- **Incidents**: always created as `new`; fixed transition map; assignment; idempotent alert
  linking; append-only notes; per-incident history.
- **Firewall requests** (no execution until Phase 7): target validation, protected networks,
  limits, two-person approval with typed confirmation, reject, idempotent revoke,
  `applied=false` in every response.
- **Audit log**: admin-only, read-only API with filters.
- `sentinel-ml threshold` (validation-only threshold and single-threaded latency); ML files
  written as UTF-8 (the Windows-written reports were re-encoded); `sentinel_ml.testing`
  shared by both test suites.
- Docker image installs `sentinel_ml`; Compose mounts `ml/artifacts` read-only; CI installs
  the ML package for the backend.

## Phase 3 — test results (actually run on 2026-10-28)

| Check | Command / method | Result |
|---|---|---|
| Backend tests (unit + PostgreSQL integration) | `TEST_DATABASE_URL=… pytest` | **155 passed** |
| Backend without a test database | `pytest` | 38 passed, 117 skipped (integration needs PostgreSQL) |
| Backend lint / format / types | `ruff check`, `ruff format --check`, `mypy` (strict) | Passed; 62 files |
| Migrations | upgrade → `alembic check` → downgrade → upgrade | Clean; no drift |
| Audit immutability | UPDATE / DELETE / TRUNCATE as the app's DB user, and via the ORM in tests | All rejected by the trigger |
| ML tests | `cd ml && pytest` | **139 passed** |
| Frontend | `npm test`, typecheck, lint, build | 22 passed; clean |
| GitHub CI run on `d7c4b9c` | backend, ml, frontend, compose | All succeeded |
| Docker stack, end to end | real images; CLI user creation and model registration; API calls | See below |

Docker end-to-end check (synthetic model and data, registered with `--allow-synthetic`; the
artifact was deleted afterwards): upload without CSRF header refused; 400-row upload analysed
by the background worker → 395 valid, 5 rejected (`invalid_value:sbytes`), 261 alerts; alert
listing, dashboard and component health consistent; self-approval refused, second-admin
approval recorded with `applied=false`; analyst refused on the audit log; logout invalidated
the session; database refused `UPDATE audit_logs`. The alert count reflects the synthetic
model and says nothing about real detection performance.

### Phase 3 acceptance

- [x] Migrations apply on a clean database and downgrade cleanly.
- [x] Authorisation matrix over every endpoint × {anonymous, analyst, admin}.
- [x] Alert → incident → notes → status change persists and is audited with actor and action.
- [x] Audit records cannot be modified through any endpoint; the trigger rejects UPDATE/DELETE.
- [x] No model alert creates an incident (tested: analysis runs create none; incidents start
  `new` and the create schema has no status field).
- [x] The ML service is used without duplicating preprocessing (backend imports `sentinel_ml`).

### Defects found and fixed during Phase 3

1. Reports written on Windows were not valid UTF-8 (locale encoding); all ML file I/O now
   names UTF-8, an AST test enforces it, and the six reports were re-encoded.
2. A non-IP client address (e.g. a Unix socket) crashed login when stored in an `INET`
   column; client addresses are now validated.
3. Count queries whose filter referenced no table had no `FROM` clause and counted one phantom
   row on an empty database; every count names its table.
4. The analysis worker queried the database during startup, so a down database would stop
   the API starting; recovery now runs inside the worker thread with retries.
5. A deprecated SQLAlchemy call (`Row.tuple()`) was caught by the test warning filter.
6. JSONB columns had only Python-side defaults; database defaults added so plain SQL inserts
   are valid.

## Phase 2 — completed work

- **`sentinel_ml` package** (`ml/`), installable, imported by future backend/collector code:
  - `schema.py`: canonical columns for both UNSW-NB15 file families, 10 class labels,
    excluded columns with reasons, three feature profiles (`full` 39 features,
    `full_no_ttl` 36, `live_compatible` 27), and the dataset-to-Zeek availability table.
  - Shared validation (`clean_frame`): every value validated; invalid records rejected with
    reasons; only three legitimately-blank HTTP/FTP counters may be imputed.
  - Loading of partitioned and full-record files (chunked, header detection, column aliasing,
    hex ports, IPv4/IPv6 metadata, epoch timestamps → UTC), SHA-256 of every source file.
  - `sentinel-ml profile`: real column names, inferred types, blanks, raw and normalised
    label distributions, rejections, duplicates, train/test overlap, IP availability.
  - Training: duplicates removed, stratified 80/20 split of the official training file
    (seed 42), four candidates (Logistic Regression and Random Forest, each with/without
    balanced class weights), selection on validation macro-F1 (tie: lower FPR). The testing
    file is never read during training. Fit warnings recorded.
  - Evaluation (run once per artifact): per-class precision/recall/F1, confusion matrix,
    binary FPR/FNR, ROC-AUC/AP of the uncalibrated score, results on test rows not
    duplicating training rows, latency (single-record median/p95, batch throughput),
    environment and git commit. Markdown reports explain each metric's limitations.
  - `Predictor`: loads only if the model file's SHA-256 matches a trusted value, the
    feature-schema version matches, and scikit-learn is the training version; rejects
    malformed records individually with reasons; reports imputed features and unseen
    categories; global feature importance (labelled as non-causal).
  - Artifacts: `<kind>-<profile>-<UTC timestamp>/` with `model.joblib` and `manifest.json`
    (data hashes, seed, hyperparameters, all candidates' validation results, versions,
    git commit, model hash); never overwritten.
- `docs/feature-mapping.md`: generated from code; a test fails if it drifts.
- `ml/data/README.md` (official download and placement), `ml/README.md` (commands,
  decisions, versioning, metric limitations, known limitations).
- CI: new `ml` job (format, lint, strict mypy, tests).

## Phase 2 — test results (actually run on 2026-10-28)

| Check | Command | Result |
|---|---|---|
| ML tests (synthetic fixtures only) | `cd ml && pytest` | **90 passed** |
| ML lint / format | `ruff check .`, `ruff format --check .` | Passed |
| ML types | `mypy` (strict, with pandas-stubs) | No issues in 19 files |
| End-to-end on synthetic data | profile → train → evaluate | Reports generated with "SYNTHETIC DATA" banner (not committed, not quoted) |
| Scale check (synthetic, 175 341 train / 82 332 test rows, 4 cores) | train + evaluate | Train (4 candidates) ≈ 84 s; evaluate ≈ 41 s; peak memory ≈ 1 GB; RF model ≈ 64 MB. Timing only; real data will differ |

Tests cover: missing/extra columns, wrong types (strings, booleans, numbers as categories),
NaN/±inf, blank values, unknown categories, invalid/inconsistent labels, empty input,
oversized batches, header-only and empty files, file-family detection, chunked-vs-whole
loading equality, leakage guards, reproducibility with a fixed seed, duplicate removal,
training without the testing file, evaluation refusing changed training data or mixing
synthetic with real data, hash/tamper/schema/library-version checks on artifacts, and that
the predictor reproduces the saved pipeline's predictions.

### Defects found and fixed during Phase 2

1. IPs that failed to parse became `NaN` instead of `None` under pandas 3; now explicit object
   dtype keeps `None` (JSON `null`) for the API.
2. Header detection required `dur`, so a file missing that column was misreported as an
   unrecognised layout; detection now uses the label columns, and the missing column is named.

### Real data profile (team machine, Windows, 2026-10-28)

The official partitioned files were downloaded on a team member's machine (the development
sandbox's network policy blocks the UNSW hosts) and profiled with `sentinel-ml profile`:

| | `UNSW_NB15_training-set.csv` | `UNSW_NB15_testing-set.csv` |
|---|---|---|
| SHA-256 | `bec7dd5e…0648fa` | `734fe664…c0a559` |
| Rows | 175 341 | 82 332 |
| Columns | 45, exactly as expected | 45, exactly as expected |
| Blank values / rejected rows | none / none | none / none |
| Duplicate rows (model features + label) | 67 601 (38.6%) | 26 387 (32.0%) |
| Normal / attack rows | 56 000 / 119 341 | 37 000 / 45 332 |
| IP addresses or timestamps | none | none |

Distinct test rows also present in the training file: 941. `proto` has 133 (train) / 131
(test) distinct values, `service` 13, `state` 9 / 7 (incl. rare values such as `no`, `PAR`).
Conclusion: the code's schema assumptions hold for these files; no schema change needed.
Full report: `ml/reports/data_profile.md` (to be committed from the team machine).

### Real training and evaluation (team machine, Windows 11, 2026-10-28, commit `d702fce`)

Selected model for every profile: `random_forest_balanced` (highest validation macro-F1).
Test file, evaluated once per model (details: [`model-evaluation.md`](model-evaluation.md)):

| Profile | Features | Test macro-F1 | Attack recall | False-positive rate (Normal flagged) | ROC-AUC |
|---|---|---|---|---|---|
| `full` | 39 | 50.3% | 99.8% | 39.7% | 0.979 |
| `full_no_ttl` | 36 | 49.1% | 99.6% | 39.8% | 0.977 |
| `live_compatible` | 27 | 49.9% | 99.7% | 39.2% | 0.975 |

Key findings: high attack recall but a high false-positive rate at the default decision
(validation showed ~17%, so the official test split is shifted); most false alerts are
predicted as Fuzzers; DoS/Analysis/Backdoor/Fuzzers/Shellcode labels are unreliable;
removing TTL features costs little; train/test overlap does not inflate results.

### Phase 2 acceptance

- [x] Preprocessing and inference share one feature definition and one saved pipeline.
- [x] Reproducible with documented commands (fixed seed and data hashes; reproducibility
  tested on synthetic data — the 1–1.5 h real runs were not repeated).
- [x] No obvious target leakage (identifiers, labels, IPs, ports, timestamps excluded; tested).
- [x] Tests cover missing columns, invalid data, incorrect types.
- [x] Valid predictions on supported inputs.
- [x] Reports distinguish real results from synthetic tests.

### Issues found during real runs

1. Training printed nothing for over an hour (Logistic Regression is slow on the real data);
   fixed by timestamped progress messages (`39c779c`).
2. On Windows, Random Forest evaluation printed hundreds of harmless scikit-learn
   `delayed`/`Parallel` warnings; inference now runs single-threaded and training no longer
   uses `warnings.catch_warnings` around threaded fits (`d4efd1a`). The committed latency
   figures predate this change.
3. A model's `+dirty` flag counted untracked report files; fixed (`d702fce`).

## Phase 1 — completed work

- Directory structure for `backend/`, `frontend/`, `ml/`, `collector/`, `firewall/` (the last
  three contain READMEs and placeholders only).
- **Backend** (FastAPI): app factory; settings from environment / root `.env`
  (`pydantic-settings`, secrets as `SecretStr`, `*` CORS origin rejected); JSON logging with
  per-request `X-Request-ID`; baseline security headers; consistent error envelope for
  404/405/422/`AppError`/500 (validation errors never echo input; 500s hide internals);
  `GET /api/v1/health/live` and `GET /api/v1/health/ready` (checks DB connectivity and
  Alembic revision, returns 503 with a component breakdown when not ready).
- **Database**: SQLAlchemy 2 with naming conventions; Alembic configured from app settings;
  migration `0001` creates `users` (role CHECK, lower-case username CHECK, unique username,
  `TIMESTAMPTZ` columns).
- **Frontend** (React 19, TypeScript 6, Vite 8, Tailwind 4, React Router 7, lucide-react):
  responsive dark-sidebar layout with skip link and mobile navigation; routes for all 11
  planned pages; System Health page wired to the real readiness endpoint with loading,
  error (incl. request id) and retry states; other pages are explicit "planned for Phase N"
  placeholders with no invented data; typed API client that parses the error envelope;
  ESLint rules banning `dangerouslySetInnerHTML` and `localStorage`/`sessionStorage`.
- **Docker Compose**: `db` → `migrate` (one-shot `alembic upgrade head`) → `backend` →
  `frontend`, with health checks, localhost-only ports, non-root containers.
- **CI** (`.github/workflows/ci.yml`): backend format/lint/type-check/`alembic check`/pytest
  with a PostgreSQL service; frontend format/lint/typecheck/test/build; Compose validation.
- `.env.example`, `.gitignore`, `.dockerignore`, `README.md` setup guide.

## Phase 1 — test results (actually run on 2026-10-28)

| Check | Command | Result |
|---|---|---|
| Backend tests (unit + PostgreSQL integration) | `TEST_DATABASE_URL=… pytest` | **28 passed** (22 unit + 6 PostgreSQL integration) |
| Backend lint/format | `ruff format --check . && ruff check .` | Passed |
| Backend types | `mypy` (strict) | No issues in 20 files |
| Migration drift | `alembic upgrade head && alembic check` | No new upgrade operations detected |
| Frontend tests | `npm test` | **22 passed** (4 files) |
| Frontend lint / types / format | `npm run lint`, `npm run typecheck`, `npm run format:check` | Passed |
| Frontend build | `npm run build` | Succeeded |
| Compose config | `docker compose config --quiet` | Valid |
| Compose stack | `docker compose up` | db, backend, frontend healthy; migrate exited 0; `/health/ready` 200 directly and via the frontend proxy |
| DB outage | stop `db`, query readiness, start `db` | 503 `unavailable` while down; 200 again after restart without restarting the API |
| Browser check | Playwright (Chromium) at 1366×800 and 390×844 | Pages render, readiness shown, no console errors, no horizontal overflow |
| README flow | Compose `db` + native `alembic upgrade head` + integration tests on port 5433 | Worked as documented |

Without `TEST_DATABASE_URL` the 6 integration tests are reported as skipped; CI always sets it.

### Defects found and fixed during Phase 1

1. Readiness check failed with a `ProgrammingError` on a fresh database: a `WHERE to_regclass(...)`
   guard does not stop PostgreSQL from rejecting a query on a missing table at parse time.
   Fixed by checking table existence in a separate query; covered by an integration test.
2. `CORS_ORIGINS=http://localhost:5173` from `.env`/environment crashed settings loading because
   `pydantic-settings` JSON-decodes list fields first. Fixed with `NoDecode`; regression tests
   now load settings from real environment variables and from an env file.
3. Unhandled 500 responses lacked the request id because Starlette's outermost error middleware
   runs outside the request-context middleware. Unhandled exceptions are now converted inside
   the request-context middleware; covered by a unit test.

### Environment notes (verification sandbox)

- Docker image builds in the verification sandbox needed its TLS-intercepting proxy's CA,
  which was mounted at build time from sandbox-only Dockerfile copies (not committed). The
  committed Dockerfiles were unchanged and need no CA on a normal network. The CI `compose`
  job builds the committed images without that workaround, and passed (see below).
- GitHub CI run #1 on commit `7b24229` (2026-10-28): `backend`, `frontend`, and `compose`
  (config validation + image build of the committed Dockerfiles) jobs all succeeded.

## Known issues / limitations

- The UI has no self-service password change; administrators reset passwords.
- Dataset runs are refreshed by polling every 3 s while in progress (WebSocket notifications
  cover live and replayed alerts only).
- The incident "add to incident" picker lists at most 100 incidents (API page size).
- Rate limiting is in-memory and per process; it resets on restart (documented residual risk).
- The application's database user owns the tables, so it could disable the audit trigger;
  production hardening (a separate non-owner role) is planned for Phase 8.
- The analysis worker is single-process; running several API worker processes is unsupported.
- Firewall execution (Phase 7) is not implemented; its endpoints and tables exist where
  planned.
- **Live monitoring (Phase 6):**
  - 15 of the live model's 36 features are TShark approximations of Argus/Bro values
    (window sizes, jitter, inter-packet times, loss, handshake times, load, state, `ct_*`
    windows). They have not been compared with UNSW-NB15 ground truth (that would need
    the published pcaps), so live scores carry an unmeasured domain shift.
  - Admin approval records acceptance of this, not validation.
  - Every flow is scored and alerted separately. A port scan produces about one alert per
    port; there is no alert grouping or rate limit on alert creation yet.
  - A live alert appears only after its 30 s capture file is finished. A TCP flow ends
    2 s after FIN/RST. Other flows end after 30 s idle, and on a quiet network up to 60 s
    later, because open flows are held back in case they continue in the file being
    written. Observed in the lab: 2–34 s after the traffic ended.
  - Recent flows are held in backend memory (last 200) and lost on restart. Collector
    read-state is in the container's tmpfs, so a restarted collector re-reads the ring
    buffer; deduplication prevents duplicate alerts.
  - The collector container shares the default Compose network with the database (it
    needs the backend). It has no database credentials.
  - UNSW-NB15 has no brute-force class; SSH guessing can only show up under other
    category names.
- The plan's "demo seed script" was replaced by `python -m app.cli create-user`.
- API responses have a strict CSP; the frontend page has none yet because the Vite dev
  server needs inline scripts. The Phase 8 production build must add one
  (`docs/security-review.md`).
- Recommendations are generated when an alert is first opened, using the related-alert
  counts at that moment; they are not regenerated when more alerts arrive later.
- The frontend container runs the Vite dev server; a production static build is Phase 8.
- Version choices: TypeScript is held at 6.0 because `typescript-eslint` 8.72 supports
  `<6.1`; React Router is held at 7.x (maintained) rather than 8.x to use a well-documented API.

- ML: scores are uncalibrated (no calibration study yet).

## Next steps

1. On the team machine (Windows, Docker Desktop), follow `docs/lab-runbook.md`:
   - pull, then `docker compose up -d --build` (applies migration `0004`);
   - train, threshold and register a `full_no_ttl` model;
   - create the collector and put its token in `.env`;
   - start the lab profile, approve the model and enable inference;
   - run the four scripts and a replay, and record the real observations (counts,
     categories, scores, screenshots) in this file.
2. File the supervisor's written authorisation for the lab.
3. Phase 7: the nftables helper. It needs a disposable Linux VM (VirtualBox Ubuntu is fine)
   for the real firewall tests; unit tests use `FakeNftAdapter` and need no root.
