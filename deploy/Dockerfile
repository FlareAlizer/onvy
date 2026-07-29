# syntax=docker/dockerfile:1
#
# Onvy API — production image.
# Build context is the REPO ROOT (needs both app/ and frontend/):
#   docker build -f deploy/Dockerfile -t onvy-api:latest .
#
# 3 stages:
#   1) frontend-builder — builds the Vite/React SPA -> frontend/dist
#   2) python-builder    — resolves & installs prod deps into a venv via uv (uses uv.lock)
#   3) runtime           — slim, non-root, only the venv + app code + built SPA

# ---------------------------------------------------------------------------
# Stage 1: frontend
# ---------------------------------------------------------------------------
FROM node:22.23.1-alpine@sha256:b74031e546d7f4faf561d797ac1b76beccac856a042815ca77db4fd047581605 AS frontend-builder

WORKDIR /frontend

# Install with lockfile only first — better layer caching on source-only changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: python deps (resolved from uv.lock, no dev group, project itself
# is NOT installed as a package — app/ is copied and run directly via uvicorn)
# ---------------------------------------------------------------------------
FROM python:3.12.13-slim-bookworm@sha256:72d3d75f2639ab82b34b29390ad3d6e0827c775befee94edda8e9976818f488d AS python-builder

# Pin uv to the exact version this project was developed/verified with.
RUN pip install --no-cache-dir uv==0.11.26

WORKDIR /build

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
# --no-install-project: pyproject.toml has no [build-system] (it's not meant to
# be pip-installed as a package) — we only want the resolved dependency set.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---------------------------------------------------------------------------
# Stage 3: runtime
# ---------------------------------------------------------------------------
FROM python:3.12.13-slim-bookworm@sha256:72d3d75f2639ab82b34b29390ad3d6e0827c775befee94edda8e9976818f488d AS runtime

# Non-root user with fixed uid/gid so bind-mounted volumes have stable ownership.
RUN groupadd --gid 10001 onvy && \
    useradd --uid 10001 --gid onvy --no-create-home --shell /usr/sbin/nologin onvy

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY --from=python-builder /opt/venv /opt/venv
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini
# Скрипты подготовки точки и шаблон конфига: их запускают внутри контейнера
# (docs/runbook-pilot-setup.md), значит они обязаны быть в образе — иначе
# завести смену на боевом сервере нечем.
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY --from=frontend-builder /frontend/dist ./frontend/dist

RUN chown -R onvy:onvy /app
USER onvy

EXPOSE 8000

# No curl/wget in slim image — probe the health endpoint with the stdlib instead.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else sys.exit(1)"]

# 1 worker per container; scale by running more containers/replicas, not
# uvicorn's --workers (keeps one Alembic-migrated schema, avoids in-process
# state duplication surprises). Migrations are run as a separate deploy step,
# never at worker startup — see scripts/deploy.sh.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
