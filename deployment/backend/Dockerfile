# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM python:3.12-slim-bookworm@sha256:8a7e7cc04fd3e2bd787f7f24e22d5d119aa590d429b50c95dfe12b3abe52f48b AS wheels

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.lock ./
RUN python -m pip wheel --wheel-dir /wheels --requirement requirements.lock

FROM python:3.12-slim-bookworm@sha256:8a7e7cc04fd3e2bd787f7f24e22d5d119aa590d429b50c95dfe12b3abe52f48b AS runtime

ARG SOURCE_COMMIT_SHA=unknown

LABEL org.opencontainers.image.source="https://github.com/swiftaihub/CareerSignals" \
      org.opencontainers.image.revision="${SOURCE_COMMIT_SHA}"

ENV CAREERSIGNAL_SOURCE_COMMIT_SHA="${SOURCE_COMMIT_SHA}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/careersignals \
    DBT_PROJECT_DIR=/app/dbt \
    DBT_PROFILES_DIR=/app/dbt

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl libgomp1 tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 careersignals \
    && useradd --uid 10001 --gid careersignals --create-home --shell /usr/sbin/nologin careersignals

COPY --from=wheels /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels

WORKDIR /app
COPY --chown=careersignals:careersignals apps/api apps/api
COPY --chown=careersignals:careersignals apps/worker apps/worker
COPY --chown=careersignals:careersignals apps/scheduler apps/scheduler
COPY --chown=careersignals:careersignals packages packages
COPY --chown=careersignals:careersignals src src
COPY --chown=careersignals:careersignals config config
COPY --chown=careersignals:careersignals dbt dbt
COPY --chown=careersignals:careersignals scripts scripts
COPY --chown=careersignals:careersignals supabase supabase
COPY --chown=careersignals:careersignals data/demo data/demo
COPY --chown=careersignals:careersignals data/sample data/sample

RUN mkdir -p /run/careersignals /home/careersignals/.duckdb /app/dbt/logs /app/dbt/target \
    && chown -R careersignals:careersignals /run/careersignals /home/careersignals /app/dbt/logs /app/dbt/target

USER careersignals

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
