# SentinelNepal — Project Status

_Last updated: 2026-10-28_

## Current phase

**Phase 1 — Repository foundation: complete.** Next: Phase 2 (dataset processing and ML engine).

## Phase tracker

| Phase | Title | Status |
|---|---|---|
| 0 | Planning and architecture | Approved as written (2026-10-28) |
| 1 | Repository foundation | Complete (see acceptance below) |
| 2 | Dataset processing and ML engine | Not started |
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
  job builds the committed images without that workaround; it has not run yet.
- GitHub Actions versions (`actions/*@v7`) were chosen from the actions' published tags; the
  workflow has not yet run on GitHub at the time of writing.

## Known issues / limitations

- Login page is a placeholder; there is no authentication until Phase 3, so the API currently
  exposes only health endpoints.
- Rate limiting, sessions, CSP header, and refusal of placeholder secrets outside development
  are Phase 3 items.
- The frontend container runs the Vite dev server; a production static build is Phase 8.
- Version choices: TypeScript is held at 6.0 because `typescript-eslint` 8.72 supports
  `<6.1`; React Router is held at 7.x (maintained) rather than 8.x to use a well-documented API.

## Next steps (Phase 2)

1. Download UNSW-NB15 partitioned CSVs (and full-record CSVs for IP-aware demos) into `ml/data/`.
2. Profile the real files (columns, types, missing values, labels, duplicates) and record the results.
3. Build the `sentinel_ml` package: schema, preprocessing pipeline, LR/RF training, validation
   selection, test evaluation, latency, `Predictor`, artifact manifest.
