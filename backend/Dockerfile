# Backend API image. Build context is the repository root (see docker-compose.yml) so that
# later phases can install the shared ml/ package alongside the backend.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Unprivileged runtime user: the API never needs root (AGENTS.md).
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin sentinel

COPY backend/requirements.txt ./
# Retries/timeouts help on slow connections; the cache mount keeps downloaded wheels between
# build attempts without storing them in the image.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 10 --timeout 60 -r requirements.txt

COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app

USER sentinel
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2)"]

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
