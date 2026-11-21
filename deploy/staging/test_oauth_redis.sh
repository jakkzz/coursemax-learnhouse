#!/usr/bin/env bash
# Disposable, cached-image tests. No TCP networking, host ports or app volumes.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
python3 -B "$ROOT/deploy/staging/preflight.py"
API_IMAGE=${LEARNHOUSE_API_TEST_IMAGE:-ghcr.io/learnhouse/app@sha256:0aca30cd7b772bebfb75c8e4e54613ab4391adb2d4e05403992867388169514f}
REDIS_IMAGE=redis@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499
# Never pull automatically; missing images require the separate pre-pull gate.
docker image inspect "$API_IMAGE" >/dev/null
docker image inspect "$REDIS_IMAGE" >/dev/null
SCRATCH=$(mktemp -d /tmp/lh-oauth-redis.XXXXXXXX)
NAME=lh-oauth-redis-$(basename "$SCRATCH" | tr '[:upper:]' '[:lower:]')
STARTED=0
cleanup() {
  if [[ $STARTED == 1 ]]; then docker stop --time 5 "$NAME" >/dev/null 2>&1 || true; fi
  # Only this harness's disposable socket/directory; never application files.
  rm -f -- "$SCRATCH/redis.sock"
  rmdir -- "$SCRATCH" 2>/dev/null || true
}
trap cleanup EXIT

docker run -d --rm --pull=never --name "$NAME" --network none --read-only \
  --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges \
  --memory 64m --cpus 0.25 --pids-limit 64 --tmpfs /data:rw,size=16m \
  -v "$SCRATCH:/scratch" --entrypoint redis-server "$REDIS_IMAGE" \
  --port 0 --unixsocket /scratch/redis.sock --unixsocketperm 700 --dir /scratch \
  --save '' --appendonly no --maxmemory 16mb --maxmemory-policy noeviction >/dev/null
STARTED=1
for _ in $(seq 1 30); do
  if docker exec "$NAME" redis-cli -s /scratch/redis.sock ping >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$NAME" redis-cli -s /scratch/redis.sock ping >/dev/null

docker run --rm --pull=never --network none --read-only \
  --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges \
  --memory 192m --cpus 0.5 --pids-limit 64 --tmpfs /tmp:rw,size=16m \
  -v "$SCRATCH:/scratch" \
  -v "$ROOT/apps/api/src:/app/api/src:ro" \
  -e RUN_OAUTH_REDIS_TESTS=1 -e OAUTH_TEST_REDIS_SOCKET=/scratch/redis.sock \
  -w /app/api --entrypoint /app/api/.venv/bin/python "$API_IMAGE" \
  -B -m unittest src.tests.services.test_provider_proof \
  src.tests.services.test_oauth_transactions \
  src.tests.services.test_oauth_transactions_redis \
  src.tests.services.test_google_handoff \
  src.route66_ext.tests.services.test_attendance_handoff -v
