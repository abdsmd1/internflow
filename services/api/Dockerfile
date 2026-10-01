# syntax=docker/dockerfile:1.7
# Image multi-stage : les outils de build ne finissent pas dans l'image finale.

ARG PYTHON_VERSION=3.12

# ------------------------------------------------------------------ build
FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
# 1) Dépendances seules : couche mise en cache tant que le lock ne change pas.
COPY uv.lock pyproject.toml ./
COPY services/api/pyproject.toml services/api/README.md services/api/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package internflow-api

# 2) Code applicatif.
COPY services/api/ services/api/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package internflow-api

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime

# Utilisateur non-root : limite l'impact d'une éventuelle compromission.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
# Migrations embarquées pour pouvoir lancer `alembic upgrade head` depuis l'image.
COPY --chown=app:app services/api/alembic.ini ./alembic.ini
COPY --chown=app:app services/api/migrations ./migrations

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]

CMD ["uvicorn", "internflow_api.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header", "--no-access-log"]
