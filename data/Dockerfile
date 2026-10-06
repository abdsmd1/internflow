# syntax=docker/dockerfile:1.7
# Image des traitements de données (seed + pipeline PySpark).
# Multi-stage : uv et les caches de build ne finissent pas dans l'image finale.

ARG PYTHON_VERSION=3.12

# ------------------------------------------------------------------ build
FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
# 1) Dépendances seules (couche en cache tant que le lock ne change pas).
COPY uv.lock pyproject.toml ./
COPY services/api/pyproject.toml services/api/README.md services/api/
COPY data/pyproject.toml data/README.md data/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package internflow-data

# 2) Code : le pipeline réutilise le domaine et la persistance de l'API (seed).
COPY services/api/ services/api/
COPY data/ data/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package internflow-data

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime

# Spark 4 tourne sur Java 17 ou 21 : Debian fournit OpenJDK 21.
# `procps` fournit `ps`, utilisé par les scripts de lancement de Spark.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends openjdk-21-jre-headless procps \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app \
 && mkdir -p /lake && chown app:app /lake

# Pilote JDBC PostgreSQL : version épinglée ET empreinte vérifiée au build.
ARG PGJDBC_VERSION=42.7.13
ADD --chmod=644 \
    --checksum=sha256:6e0e4cc2d8cae902084f8a2b18728b073a6fd9d1f87c9d8bff8f298c18185b93 \
    https://github.com/pgjdbc/pgjdbc/releases/download/REL${PGJDBC_VERSION}/postgresql-${PGJDBC_VERSION}.jar \
    /opt/jars/postgresql.jar

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INTERNFLOW_DATA_JDBC_DRIVER_JAR=/opt/jars/postgresql.jar \
    INTERNFLOW_DATA_LAKE_PATH=/lake

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv

USER app
VOLUME ["/lake"]

ENTRYPOINT ["internflow-data"]
CMD ["--help"]
