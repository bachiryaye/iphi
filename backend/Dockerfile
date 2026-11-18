# Pinned by digest: reproducible, and no registry lookup once cached. Bump tag and digest together.
FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS build
COPY --from=ghcr.io/astral-sh/uv:0.13@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS runtime
LABEL org.opencontainers.image.title="iphi-backend" \
      org.opencontainers.image.description="IPHI API, worker and migrations (simulated industrial data platform)" \
      org.opencontainers.image.source="https://github.com/bachiryaye/iphi"
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 iphi \
    && useradd --system --uid 10001 --gid iphi --no-create-home iphi
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY config ./config
# Tools of make demo and make perf.
COPY scripts ./scripts
COPY --chmod=0755 docker-entrypoint.sh /usr/local/bin/iphi-entrypoint
USER iphi
EXPOSE 8000
# Covers a migration on start (IPHI_MIGRATE_ON_START) before the first check counts.
HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=3 CMD ["iphi-entrypoint", "healthcheck"]
ENTRYPOINT ["iphi-entrypoint"]
CMD ["api"]
