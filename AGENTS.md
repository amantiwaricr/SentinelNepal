# AGENTS.md — SentinelNepal working rules

These rules apply to every contributor, human or AI coding agent. Read this file,
`docs/implementation-plan.md`, and `docs/PROJECT_STATUS.md` before starting a phase.

## 1. Project in one paragraph

SentinelNepal is a TU BSc CSIT final-year project: an ML-assisted network intrusion
detection and incident response platform for an **isolated lab**. A scikit-learn model
trained on UNSW-NB15 scores flow records; analysts investigate alerts; admins may approve
temporary, reversible nftables blocks applied by a narrowly privileged helper. Design:
`docs/architecture.md`. Threats: `docs/threat-model.md`.

## 2. Non-negotiable rules

1. **Predictions are not proof.** Use "predicted", "suspected", "model score". Never write
   "attack detected/confirmed" for model output. Alerts never create `confirmed` incidents.
2. **Scores are uncalibrated** unless a calibration test in `ml/reports/` says otherwise.
3. **No automatic blocking.** No code path from prediction/recommendation to the firewall
   without an approved `firewall_request` by an admin (approver ≠ requester by default).
4. **No shell from the web app.** No `shell=True`, `os.system`, `eval`, or dynamic command
   strings anywhere in `backend/`. Only the firewall helper may invoke `nft`, with an
   argument list built from validated `ipaddress` objects.
5. **Firewall helper scope:** only `table inet sentinelnepal`; never `flush ruleset`; fixed
   ops `block`, `unblock`, `list`, `health`; deny by default; protected ranges enforced.
6. **Never fabricate** test output, metrics, alerts, collector events, or firewall results.
   If something was not run, say so. Synthetic fixtures are named/labelled `synthetic`.
7. **Never commit** secrets, `.env`, datasets, model artifacts, pcaps, Zeek logs, or real traffic.
8. **Live collection only** on authorised lab interfaces.
9. **Never invent** geolocation, attacker identity, or threat-intel data.

## 3. Architecture constraints

* Module boundaries: `frontend/`, `backend/`, `ml/` (`sentinel_ml` package), `collector/`, `firewall/`.
* Feature engineering exists **only** in `ml/sentinel_ml`. Backend and collector import it.
* Backend layering: `api/` (routing, auth deps, schemas) → `services/` (business logic, no
  FastAPI imports) → `models/` (ORM). Routes stay thin.
* Traffic collection, inference, DB writes, and firewall actions remain separate components.
* No new infrastructure (brokers, caches, extra services) without a written justification in
  `docs/architecture.md` and team agreement.
* REST is the source of truth; WebSocket messages are notifications only.

## 4. Coding conventions

### Python (backend, ml, collector, firewall)
* Python ≥ 3.12, type hints everywhere, `from __future__ import annotations` not required.
* Format/lint: `ruff format` + `ruff check`; type check: `mypy` on `backend/app` and `ml/sentinel_ml` (strict where practical).
* Pydantic v2 models for all external input; `extra="forbid"` on request schemas.
* SQLAlchemy 2.x typed ORM (`Mapped[...]`); no raw SQL strings except reviewed migrations.
* Timestamps: timezone-aware UTC (`datetime.now(timezone.utc)`), `TIMESTAMPTZ` columns.
* IPs: parse with `ipaddress`; store as PostgreSQL `INET`/`CIDR`.
* Logging: `logging` with structured (JSON) output; include `request_id`; never log
  passwords, tokens, cookies, or full uploaded rows.
* Errors: raise domain exceptions in services; map to the standard error envelope in `core/errors.py`.
* Names: `snake_case` functions/modules, `PascalCase` classes, `UPPER_CASE` constants.

### TypeScript (frontend)
* `strict: true`; no `any` without a comment explaining why.
* ESLint + Prettier. Functional components and hooks.
* All HTTP via `src/services/api/` typed client; base URL from `VITE_API_BASE_URL`.
* Reusable UI in `src/components/`, pages in `src/pages/`, shared types in `src/types/`.
* Never use `dangerouslySetInnerHTML`. Never store tokens in `localStorage`.
* Every data view has loading, empty, error states. No hard-coded statistics.
* Live data and dataset-analysis data are visibly labelled differently.

### Comments and docs
* Comment *why*, not *what*. Explain security-relevant decisions inline.
* Beginner-friendly explanations go in `docs/`, not in long code comments.

## 5. Testing requirements

* Every feature ships with tests in the same change.
* Backend: `pytest` with HTTPX/TestClient; PostgreSQL for integration tests (Compose service
  or testcontainers); authorisation-matrix test must be updated for each new endpoint.
* ML: unit tests on synthetic fixtures (missing/extra columns, wrong types, NaN/inf, unknown
  categories, empty input); reproducibility test with a fixed seed.
* Collector: parser/validator tests with sample Zeek JSON lines (hand-written, labelled synthetic).
* Firewall: unit tests use `FakeNftAdapter` and run without root; real nftables tests run only
  in a disposable VM via the documented script — **never on a developer's primary machine**.
* Frontend: Vitest + React Testing Library for components and key workflows.
* Do not skip, weaken, or delete tests to get a green build. Fix the cause or document the
  failure in `docs/PROJECT_STATUS.md`.
* Commands (run before every push; CI runs the same):
  * Backend: `cd backend && ruff format --check . && ruff check . && mypy && pytest`
    (set `TEST_DATABASE_URL` to a database whose name ends in `_test` to include the
    PostgreSQL integration tests; after model changes also run `alembic check`)
  * Frontend: `cd frontend && npm run format:check && npm run lint && npm run typecheck && npm test && npm run build`
  * `ml/`, `collector/`, `firewall/`: `pytest` in each directory once those phases add code.

## 6. Security rules

* Server-side authorisation on every endpoint; frontend guards are UX only.
* Roles: `admin`, `analyst`. Audit log readable by admin only; no update/delete endpoints.
* Passwords: Argon2id. Sessions: opaque token, hashed in DB, HttpOnly SameSite=Strict cookie.
* CORS: explicit origin allowlist; credentials allowed only for listed origins.
* Uploads: size/type limits, server-generated filenames, never used for training.
* Model artifacts: load only after SHA-256 matches the DB record; never load user-supplied files.
* Secrets come from environment variables; the app refuses placeholder secrets outside development.
* Audit every security-relevant action: auth events, role/user changes, incident status and
  assignment, firewall request/approve/reject/execute/verify/expire/revoke, model activation,
  live-inference gate changes.

## 7. Git workflow

* Small, coherent commits with descriptive messages; feature branches; PR review by another member.
* Update `docs/PROJECT_STATUS.md` at the end of every milestone with completed work, actual
  test results, known issues, and next steps.
* Do not move to the next phase until acceptance criteria are met or remaining gaps are documented.
