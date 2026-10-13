#!/usr/bin/env bash
# Isolated, pinned web build: no live secrets, networks, volumes or service restarts.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
python3 -B "$ROOT/deploy/staging/preflight.py"
OUT=${1:?Provide a new private evidence directory}
[[ ! -e "$OUT" ]] || { echo 'Evidence directory must be new' >&2; exit 1; }
mkdir -m 700 -p "$OUT"
mkdir -m 700 "$OUT/dependencies"
IMAGE=ghcr.io/learnhouse/app@sha256:0aca30cd7b772bebfb75c8e4e54613ab4391adb2d4e05403992867388169514f
NAME="lh-native-web-build-$$"
cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  # Only temporary dependencies created by THIS invocation, never host caches.
  docker run --rm --pull=never --network none --read-only --memory 64m --cpus 0.25 \
    -v "$OUT/dependencies:/generated:rw" --entrypoint /app/api/.venv/bin/python "$IMAGE" \
    -B -c 'from pathlib import Path; import shutil; root=Path("/generated"); [shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink() for p in root.iterdir()]' >/dev/null 2>&1 || true
}
trap cleanup EXIT
# Large generated dependency packages use <=600MiB of disk, freeing memory for
# compilation. Only this new build directory is written; no cache is pruned.
docker run -d --pull=never --name "$NAME" --memory 3328m --cpus 1 --read-only --ulimit core=0 --oom-score-adj 500 \
  --tmpfs /scratch:rw,exec,size=2048m --tmpfs /tmp:rw,size=64m \
  -v "$ROOT/apps/web:/source:ro" \
  -v "$OUT/dependencies:/scratch/web/.build-deps:rw" \
  -v "$ROOT/deploy/staging/native_web_dependency_budget.py:/budget.py:ro" \
  -e NEXT_TELEMETRY_DISABLED=1 -e BUN_INSTALL_CACHE_DIR=/scratch/cache \
  -e NODE_OPTIONS=--max-old-space-size=1536 -e LEARNHOUSE_DISABLE_EE=1 -e LEARNHOUSE_BUILD_CPUS=1 -e LEARNHOUSE_BUILD_LOW_MEMORY=true \
  --entrypoint sh "$IMAGE" -c '
    mkdir -p /scratch/web
    cp -a /source/. /scratch/web/
    cd /scratch/web
    timeout 180 bun install --frozen-lockfile --ignore-scripts --network-concurrency 2 &&
    /app/api/.venv/bin/python -B /budget.py &&
    timeout 480 bun run build --webpack && touch /scratch/build-success
    echo BUILD_FINISHED
    sleep 600
  ' > "$OUT/container-id"
for iteration in $(seq 1 150); do
  if docker exec "$NAME" test -f /scratch/build-success >/dev/null 2>&1; then
    docker logs "$NAME" > "$OUT/build.log" 2>&1
    docker exec "$NAME" sh -c 'cd /scratch/web; tar czf /scratch/web-runtime.tar.gz -C .next/standalone .; tar czf /scratch/web-static.tar.gz -C .next static; tar czf /scratch/web-public.tar.gz public'
    for file in web-runtime web-static web-public; do
      docker cp "$NAME:/scratch/$file.tar.gz" "$OUT/$file.tar.gz" >/dev/null
    done
    (cd "$OUT"; sha256sum web-*.tar.gz > artifact.sha256)
    echo "Validated build artifacts: $OUT"
    exit 0
  fi
  if ! docker inspect "$NAME" --format '{{.State.Running}}' 2>/dev/null | grep -q true; then break; fi
  if docker logs "$NAME" 2>&1 | grep -q BUILD_FINISHED; then break; fi
  if (( iteration % 3 == 0 )); then
    docker stats "$NAME" --no-stream --format '{{.MemUsage}}' >> "$OUT/memory.log" 2>/dev/null || true
  fi
  sleep 5
done
docker logs "$NAME" > "$OUT/build.log" 2>&1
 tail -35 "$OUT/build.log"
exit 1
