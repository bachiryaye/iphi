#!/usr/bin/env bash
# Disposable deployment check using image entrypoints without Compose (ADR 0028).
set -euo pipefail

image="${IPHI_COMPACT_IMAGE:-iphi-compact:validation}"
state_dir="$(mktemp -d /tmp/iphi-compact-check.XXXXXXXX)"
resource="$(basename "$state_dir" | tr '.' '-')"
created_network=false
keep="${IPHI_COMPACT_KEEP:-0}"

cleanup() {
    if [[ "$keep" == 1 ]]; then
        echo "Validation resources retained: $resource; private state: $state_dir"
        return
    fi
    if [[ "$created_network" == true ]]; then
        docker rm -f -v "$resource-api" "$resource-worker" "$resource-db" >/dev/null 2>&1 || true
        docker network rm "$resource" >/dev/null 2>&1 || true
    fi
    python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1])' "$state_dir"
}
trap cleanup EXIT

python3 - "$state_dir" "$resource" <<'PY'
import secrets
import sys
from pathlib import Path

directory, name = Path(sys.argv[1]), sys.argv[2]
password = secrets.token_hex(24)
backend = {
    'IPHI_DATABASE_URL': f'postgresql+psycopg://iphi:{password}@{name}-db:5432/iphi',
    'IPHI_DEPLOYMENT_MODE': 'local',
    'IPHI_BIND_HOST': '127.0.0.1',
    'IPHI_ALLOWED_HOSTS': '127.0.0.1,localhost',
    'IPHI_LLM_PROVIDER': 'none',
    'IPHI_RETENTION_DAYS': '7',
    'IPHI_CYCLE_INTERVAL_S': '5',
    **{f'IPHI_DEMO_{role}_PASSWORD': secrets.token_hex(24)
       for role in ('VIEWER', 'ENGINEER', 'ADMIN')},
}
for filename, values in (
    ('runtime.env', backend),
    ('database.env', {'POSTGRES_USER': 'iphi', 'POSTGRES_PASSWORD': password, 'POSTGRES_DB': 'iphi'}),
):
    path = directory / filename
    path.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
    path.chmod(0o600)
PY

docker network create "$resource" >/dev/null
created_network=true
docker run -d --name "$resource-db" --network "$resource" \
    --memory 256m --shm-size 64m --env-file "$state_dir/database.env" \
    postgres:16-alpine >/dev/null
docker run --rm --network "$resource" --env-file "$state_dir/runtime.env" \
    --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
    "$image" migrate >"$state_dir/migrate.log" 2>&1
docker run -d --name "$resource-worker" --network "$resource" \
    --env-file "$state_dir/runtime.env" --memory 256m \
    --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
    "$image" worker >/dev/null
docker run -d --name "$resource-api" --network "$resource" \
    --env-file "$state_dir/runtime.env" --memory 256m -p 127.0.0.1::8000 \
    --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
    "$image" >/dev/null
port="$(docker port "$resource-api" 8000/tcp | cut -d: -f2)"
base_url="http://127.0.0.1:$port"
printf '%s\n' "$base_url" >"$state_dir/url"
printf '%s\n' "$resource" >"$state_dir/resource"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf 'url=%s\nresource=%s\nstate_dir=%s\n' "$base_url" "$resource" "$state_dir" >>"$GITHUB_OUTPUT"
fi

ready=false
for _ in $(seq 1 90); do
    if curl --silent --fail --max-time 3 "$base_url/ready" >"$state_dir/ready.json"; then
        ready=true
        break
    fi
    sleep 2
done
if [[ "$ready" != true ]]; then
    docker logs --tail 30 "$resource-api"
    docker logs --tail 30 "$resource-worker"
    exit 1
fi
curl --silent --show-error --fail --max-time 10 -H 'Accept: text/html' \
    "$base_url/help" -o "$state_dir/help.html"
curl --silent --show-error --fail --max-time 10 "$base_url/theme-init.js" -o /dev/null
docker exec "$resource-api" python -m scripts.demo --no-live-incident
docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}' \
    "$resource-api" "$resource-worker" "$resource-db"
echo "Compact image entrypoints and deterministic demo passed: $base_url"
