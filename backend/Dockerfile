# Backend API image. Build context is the repository root (see docker-compose.yml) because the
# backend installs the shared ml/ package (sentinel_ml), which owns all feature handling.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Unprivileged runtime user: the API never needs root (AGENTS.md).
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin sentinel

# Same relative layout as the repository, so backend/requirements.txt can include
# ../ml/requirements.txt.
COPY ml/requirements.txt ml/requirements.txt
COPY backend/requirements.txt backend/requirements.txt
# Retries/timeouts help on slow connections; the cache mount keeps downloaded wheels between
# build attempts without storing them in the image.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 10 --timeout 60 -r backend/requirements.txt

COPY ml/pyproject.toml ml/pyproject.toml
COPY ml/sentinel_ml ml/sentinel_ml
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 10 --timeout 60 --no-deps ./ml

COPY backend/alembic.ini backend/alembic.ini
COPY backend/migrations backend/migrations
COPY backend/app backend/app

# Uploaded CSVs are written here (a named volume in Compose).
RUN mkdir -p /srv/backend/uploads && chown sentinel:sentinel /srv/backend/uploads

WORKDIR /srv/backend
USER sentinel
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2)"]

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
