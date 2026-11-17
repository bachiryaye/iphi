#!/bin/sh
# One image, one role per container (ADR 0001, ADR 0020).
set -eu

migrate_if_requested() {
    if [ "${IPHI_MIGRATE_ON_START:-false}" = "true" ]; then
        python -m app.bootstrap
    fi
}

role="${1:-api}"
[ "$#" -gt 0 ] && shift

case "$role" in
    api)
        migrate_if_requested
        exec uvicorn app.main:build --factory --host 0.0.0.0 --port "${IPHI_PORT:-8000}" \
            --no-server-header "$@"
        ;;
    worker)
        migrate_if_requested
        exec python -m app.worker "$@"
        ;;
    migrate)
        exec python -m app.bootstrap "$@"
        ;;
    healthcheck)
        exec python -m app.healthcheck
        ;;
    *)
        exec "$role" "$@"
        ;;
esac
