# SentinelNepal — Project Status

_Last updated: 2026-10-29_

## Current phase

**Phase 4 — Frontend SOC dashboard: complete.** Next: Phase 5 (recommendation engine and
security hardening). Registering the real `full` model in a running backend is a
per-installation step (see Next steps).

## Phase tracker

| Phase | Title | Status |
|---|---|---|
| 0 | Planning and architecture | Approved as written (2026-10-28) |
| 1 | Repository foundation | Complete (see acceptance below) |
| 2 | Dataset processing and ML engine | Complete (real results; limitations documented) |
| 3 | Backend APIs, DB, auth, incidents | Complete |
| 4 | Frontend SOC dashboard | Complete |
| 5 | Recommendations and hardening | Not started |
| 6 | Live network monitoring | Not started |
| 7 | nftables approved blocking | Not started |
| 8 | Integration, testing, documentation | Not started |

Phase 0 decisions recorded at approval: a different admin must approve each block
(configurable for solo demos); only admins request blocks; server-side sessions in an
HttpOnly cookie; team roles as in `implementation-plan.md` §2. Lab VM availability and
written supervisor authorisation are still to be confirmed before Phase 6.

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
- Dataset runs are refreshed by polling every 3 s while in progress; WebSocket notifications
  arrive with live ingest in Phase 6.
- The incident "add to incident" picker lists at most 100 incidents (API page size).
- Rate limiting is in-memory and per process; it resets on restart (documented residual risk).
- The application's database user owns the tables, so it could disable the audit trigger;
  production hardening (a separate non-owner role) is planned for Phase 8.
- Multipart parsing may spool an oversized upload to a temporary file before the streamed
  size check rejects it; a `Content-Length` pre-check limits honest clients only.
- The analysis worker is single-process; running several API worker processes is unsupported.
- Recommendation rules (Phase 5), live ingest and WebSocket events (Phase 6), and firewall
  execution (Phase 7) are not implemented; their endpoints and tables exist where planned.
- The plan's "demo seed script" was replaced by `python -m app.cli create-user`.
- A CSP header is not set yet (Phase 5 security review).
- The frontend container runs the Vite dev server; a production static build is Phase 8.
- Version choices: TypeScript is held at 6.0 because `typescript-eslint` 8.72 supports
  `<6.1`; React Router is held at 7.x (maintained) rather than 8.x to use a well-documented API.

- ML: scores are uncalibrated (no calibration study yet); UNSW-NB15 has no brute-force class;
  live feature mapping is preliminary until Phase 6.

## Next steps

1. On each installation that has the real artifacts: register the `full` model with
   `python -m app.cli register-model ../ml/artifacts/random_forest-full-20261028T135634Z
   --reports-dir ../ml/reports --activate` (Docker: `/models/…` and
   `--reports-dir /model-reports`). Thresholds: done 2026-10-28, threshold 0.815,
   validation FPR 4.92%, attack recall 90.25%.
2. Phase 5: recommendation rule engine (evidence and limitations per rule, "investigate
   further" for unreliable categories), security review against `threat-model.md`, CSP,
   dependency audits, security tests.
