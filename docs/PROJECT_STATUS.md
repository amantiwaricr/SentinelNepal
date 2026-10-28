# SentinelNepal — Project Status

_Last updated: 2026-10-28_

## Current phase

**Phase 2 — Dataset processing and ML engine: complete.** Three models trained and evaluated
once on the official UNSW-NB15 files; results in [`model-evaluation.md`](model-evaluation.md).
Next: Phase 3 (backend APIs, database, authentication, incidents).

## Phase tracker

| Phase | Title | Status |
|---|---|---|
| 0 | Planning and architecture | Approved as written (2026-10-28) |
| 1 | Repository foundation | Complete (see acceptance below) |
| 2 | Dataset processing and ML engine | Complete (real results; limitations documented) |
| 3 | Backend APIs, DB, auth, incidents | Not started |
| 4 | Frontend SOC dashboard | Not started |
| 5 | Recommendations and hardening | Not started |
| 6 | Live network monitoring | Not started |
| 7 | nftables approved blocking | Not started |
| 8 | Integration, testing, documentation | Not started |

Phase 0 decisions recorded at approval: a different admin must approve each block
(configurable for solo demos); only admins request blocks; server-side sessions in an
HttpOnly cookie; team roles as in `implementation-plan.md` §2. Lab VM availability and
written supervisor authorisation are still to be confirmed before Phase 6.

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

- Login page is a placeholder; there is no authentication until Phase 3, so the API currently
  exposes only health endpoints.
- Rate limiting, sessions, CSP header, and refusal of placeholder secrets outside development
  are Phase 3 items.
- The frontend container runs the Vite dev server; a production static build is Phase 8.
- Version choices: TypeScript is held at 6.0 because `typescript-eslint` 8.72 supports
  `<6.1`; React Router is held at 7.x (maintained) rather than 8.x to use a well-documented API.

- ML: scores are uncalibrated (no calibration study yet); UNSW-NB15 has no brute-force class;
  live feature mapping is preliminary until Phase 6.

## Next steps

1. Phase 3: backend models, auth, incidents, audit; integrate `Predictor` via an
   `ml_service` that stores model hashes in `model_versions`.
2. Phase 3: choose an alert threshold on the attack score from the **validation** split and
   store it with the model version; re-measure single-threaded latency without re-scoring
   the test set.
3. Phase 4/5: label low-reliability predicted categories in the UI and recommendations.
