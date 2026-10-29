# SentinelNepal

Machine-learning-based network intrusion detection and incident response system —
Tribhuvan University BSc CSIT final-year project.

SentinelNepal scores network flow records with a model trained on the public UNSW-NB15
dataset, raises alerts for analyst review, suggests defensive measures, and lets an
administrator approve temporary, reversible IP blocks in an isolated Ubuntu lab using
nftables. Model output is treated as evidence for investigation, never as proof of an attack.

> **Status:** Phases 1–6 complete.
>
> - SOC dashboard on a backend API, with authentication, alerts, incidents,
>   evidence-based recommendations, an audit log and the firewall *request* workflow.
> - ML pipeline trained and evaluated on UNSW-NB15; security review done.
> - Live monitoring of an isolated Docker lab with TShark, behind an admin-approved
>   scoring gate.
>
> Firewall execution (Phase 7) comes later. See
> [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Implementation plan](docs/implementation-plan.md)
- [Threat model](docs/threat-model.md)
- [Security review](docs/security-review.md)
- [Defensive recommendations](docs/recommendations.md)
- [Model evaluation](docs/model-evaluation.md)
- [Feature mapping (dataset → TShark / Zeek)](docs/feature-mapping.md)
- [Lab runbook: live monitoring](docs/lab-runbook.md)
- [Project status](docs/PROJECT_STATUS.md)
- [Contributor and agent rules](AGENTS.md) — read before contributing

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI API, SQLAlchemy models, Alembic migrations, pytest suite |
| `frontend/` | React + TypeScript + Vite + Tailwind dashboard, Vitest suite |
| `ml/` | `sentinel_ml` package: preprocessing, training, evaluation, inference (Phase 2) |
| `collector/` | TShark capture collector and CSV replay (Phase 6) |
| `lab/` | Isolated Docker lab: server, client and traffic scripts (Phase 6) |
| `firewall/` | Restricted nftables helper (Phase 7) |
| `docs/` | Design, plan, threat model, status |

## Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Git | any recent | everything |
| Docker Engine + Compose v2 | Docker 24+ | Option A, and the database in Option B |
| Python | 3.12 or newer (CI and the image use 3.13) | Option B, running backend tests |
| Node.js | 22 LTS | Option B, running frontend tests |

Windows users: use WSL 2 (Ubuntu) for the commands below.

## Option A — run everything with Docker Compose

```bash
git clone https://github.com/amantiwaricr/SentinelNepal.git
cd SentinelNepal
cp .env.example .env
```

Edit `.env` and replace `POSTGRES_PASSWORD=change-me` with a long random value, for example
the output of `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`. Then:

```bash
docker compose up --build
```

Compose starts four services in order: `db` (PostgreSQL 16) → `migrate` (runs
`alembic upgrade head` once, then exits) → `backend` (FastAPI on port 8000) → `frontend`
(Vite dev server on port 5173). All ports are published on `127.0.0.1` only.

| URL | What |
|---|---|
| http://localhost:5173 | Dashboard (System Health page shows live backend status) |
| http://localhost:8000/api/docs | Interactive API documentation (disabled when `ENVIRONMENT=production`) |
| http://localhost:8000/api/v1/health/live | Liveness: the process is up |
| http://localhost:8000/api/v1/health/ready | Readiness: database reachable and schema at the latest migration (503 otherwise) |

Stop with `Ctrl+C`, or `docker compose down`. `docker compose down -v` also **deletes the
database volume**.

### Live monitoring lab (optional)

The `lab` profile adds an isolated lab network, packet capture of its server, and the
collector. Set it up first: train a `full_no_ttl` model, register a collector, and put its
token in `.env`. Then run:

```bash
docker compose --profile lab up -d --build
```

Every step, including test traffic, failure tests and CSV replay, is in
[docs/lab-runbook.md](docs/lab-runbook.md).

## Option B — native development (faster edit/reload)

Run only PostgreSQL in Docker and the backend/frontend directly on your machine.

```bash
cp .env.example .env              # then set POSTGRES_PASSWORD as above
docker compose up -d db           # PostgreSQL on 127.0.0.1:5433
```

Backend (in one terminal):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate         # Windows/WSL: same command inside WSL
pip install -r requirements-dev.txt
alembic upgrade head              # creates/updates the schema
uvicorn app.main:create_app --factory --reload --port 8000
```

The backend reads the repository-root `.env` (`POSTGRES_HOST=localhost`,
`POSTGRES_PORT=5433`). Real environment variables override values in `.env`.

Frontend (in another terminal):

```bash
cd frontend
npm ci
npm run dev                       # http://localhost:5173, proxies /api to localhost:8000
```

Set `API_PROXY_TARGET` if the backend runs elsewhere. `frontend/.env.example` documents
`VITE_API_BASE_URL` (default `/api/v1`).

## Operating the backend

Administrative commands run on the backend host (or inside the container) and are never
exposed over HTTP.

**1. Create the first administrator** (and more users the same way):

```bash
cd backend
python -m app.cli create-user --username admin1 --role admin
```

With Docker: `docker compose exec backend python -m app.cli create-user --username admin1 --role admin`.
Passwords need at least 12 characters and must not contain the username. Further users can
be managed by an admin through the API (`/api/v1/users`).

**2. Register a trained model** so uploads can be analysed. After training and evaluating it
(see [ml/README.md](ml/README.md)), choose its alert threshold on the validation split, then
register and activate it:

```bash
cd ml
sentinel-ml threshold artifacts/<artifact-dir> --target-fpr 0.05
cd ../backend
python -m app.cli register-model ../ml/artifacts/<artifact-dir> --reports-dir ../ml/reports --activate
```

With Docker, `ml/artifacts` is mounted read-only at `/models` and `ml/reports` at
`/model-reports`:
`docker compose exec backend python -m app.cli register-model /models/<artifact-dir> --reports-dir /model-reports --activate`
(without `--reports-dir`, alerts use the model's default decision instead of a threshold).
The model's SHA-256 is stored at registration; a model file that changes on disk afterwards
is never loaded.

**3. Use the dashboard** at http://localhost:5173 and sign in. A typical workflow:

- *Dataset Analysis*: upload a UNSW-NB15-format CSV; the run list updates while it is
  analysed. Its alerts are tagged **DATASET** everywhere.
- *Dashboard*: totals, activity, categories and frequent sources from stored data; switch
  between all, dataset and live/replay sources.
- *Alerts*: filter by IP, CIDR, category, severity, status, source and time; open an alert
  to see its evidence and rule-based recommendations, investigate its addresses, open an
  incident or request a block. *Recommendations* lists the rules
  ([docs/recommendations.md](docs/recommendations.md)).
- *Incidents*: assign, add notes, and move through the status workflow; the history comes
  from the audit log.
- *Firewall Approvals* (admins): approve a request by typing its target again. Until
  Phase 7 nothing is applied; the page says so.
- *Audit Logs* (admins), *Model Evaluation*, *System & Settings* (admins manage users here).

**4. Use the API directly** — interactive docs at http://localhost:8000/api/docs. Sign in with
`POST /api/v1/auth/login`; every state-changing request must send the header
`X-Requested-With: SentinelNepal`. Upload a UNSW-NB15-format CSV to
`POST /api/v1/datasets/analyses`; it is analysed in the background and its alerts appear
under `/api/v1/alerts`.

## Running the tests

### Backend

```bash
cd backend
source .venv/bin/activate
ruff format --check . && ruff check .     # formatting and lint
mypy                                      # strict type check of app/
pytest                                    # unit tests; DB tests are skipped without a test DB
```

The PostgreSQL integration tests (migrations, readiness, constraints) need a **dedicated test
database**. They drop and recreate its schema, so they refuse to run unless the database name
ends in `_test`:

```bash
docker compose exec db createdb -U sentinel sentinelnepal_test
TEST_DATABASE_URL=postgresql+psycopg://sentinel:<your-password>@localhost:5433/sentinelnepal_test pytest
```

To confirm the ORM models and migrations agree: `alembic check`.

### Frontend

```bash
cd frontend
npm run gen:api:check # src/types/api.gen.ts matches openapi.json
npm run format:check
npm run lint          # includes bans on dangerouslySetInnerHTML and localStorage
npm run typecheck
npm test
npm run build
```

When the API changes, regenerate the schema and the frontend types and commit both (a
backend test and the CI check fail otherwise):

```bash
cd backend && python -m app.cli export-openapi
cd ../frontend && npm run gen:api
```

### ML and collector

```bash
cd ml && ruff format --check . && ruff check . && mypy && pytest
```

```bash
cd collector && ruff format --check . && ruff check . && mypy && pytest
```

The collector needs `pip install -r requirements-dev.txt -e ../ml -e .`. Its capture tests,
and one ML test, need `tshark` on `PATH`; they are skipped without it.

### Continuous integration

`.github/workflows/ci.yml` runs all of the above on every push and pull request, with the
integration tests against a PostgreSQL service container and TShark installed. It also
validates and builds every Compose image, including the `lab` profile.

## Database migrations

```bash
cd backend
alembic upgrade head                                   # apply all migrations
alembic downgrade -1                                   # undo the latest migration
alembic revision --autogenerate -m "describe change"   # after editing app/models (review the file!)
```

## Configuration

All settings come from environment variables (see `.env.example`). Never commit `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `test`, or `production` (disables API docs) |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` | Database location (Compose overrides to `db:5432`) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | — | Database credentials |
| `DATABASE_URL` | unset | Full SQLAlchemy URL; overrides the `POSTGRES_*` parts |
| `POSTGRES_HOST_PORT` | `5433` | Host port Compose publishes PostgreSQL on |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed browser origins (`*` is rejected) |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `json` | `json` or `text` |
| `TEST_DATABASE_URL` | unset | Enables PostgreSQL integration tests (name must end in `_test`) |
| `COLLECTOR_TOKEN` | unset | The lab collector's token (from `create-collector`) |
| `LIVE_MODEL_PROFILE` | `full_no_ttl` | Feature profile of the model used for live and replayed flows |
| `COLLECTOR_OFFLINE_SECONDS` | `30` | A collector without a heartbeat for this long is shown offline |

## API conventions

- Base path `/api/v1`. Every response carries an `X-Request-ID` header.
- Errors always use one envelope, so the frontend can handle them uniformly:

  ```json
  {"error": {"code": "not_found", "message": "Not Found", "details": null, "request_id": "…"}}
  ```

  Validation errors list the failing fields but never echo submitted values. Unexpected
  errors return a generic 500 with the request id; details go to the server log only.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/health/ready` returns 503 with migrations `pending` | Run `alembic upgrade head` (Compose does this via the `migrate` service) |
| `/health/ready` returns 503 with database `unavailable` | Check that `db` is running and `.env` credentials match; the API recovers automatically once the DB is back |
| `address already in use` for 5173, 8000, or 5433 | Stop the other process, or change the host port in `docker-compose.yml` / `POSTGRES_HOST_PORT` |
| `docker compose` says `Set POSTGRES_PASSWORD in .env` | Create `.env` from `.env.example` |
| Upload returns 503 `model_unavailable` | Register and activate a model (see "Operating the backend") |
| API returns 403 `csrf_check_failed` | Send `X-Requested-With: SentinelNepal` on POST/PATCH/DELETE requests |
| `npm error Exit handler never called!` or pip timeouts during `docker compose up --build` | A slow or unstable connection interrupted package downloads. Run the same command again: already-downloaded packages are cached, so each retry gets further. On very slow links, build one image at a time: `docker compose build backend`, then `docker compose build frontend`, then `docker compose up` |
| `pip`/`npm` SSL errors during `docker build` on a network with TLS inspection | The build container does not trust the network's proxy CA; build on a network without TLS interception or ask the network administrator for the CA |

## Safety

This project is for an isolated, authorised laboratory only. Do not run live collection on
networks you are not authorised to monitor, and never run firewall tests on your primary
machine or a shared network. See [docs/threat-model.md](docs/threat-model.md).
