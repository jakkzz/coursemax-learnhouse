#!/usr/bin/env bash
# Generated-route TypeScript only. This does NOT replace the full bundle gate.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
python3 -B "$ROOT/deploy/staging/preflight.py"
IMAGE=${LEARNHOUSE_WEB_BUILD_IMAGE:-ghcr.io/learnhouse/app@sha256:0aca30cd7b772bebfb75c8e4e54613ab4391adb2d4e05403992867388169514f}
docker image inspect "$IMAGE" >/dev/null
docker run --rm --pull never --read-only --memory 3584m --oom-score-adj 500 --cpus 1 --pids-limit 256 \
  --cap-drop ALL --security-opt no-new-privileges --ulimit core=0 \
  --tmpfs /scratch:rw,exec,size=1800m --tmpfs /tmp:rw,size=32m \
  -v "$ROOT/apps/web:/source:ro" \
  -e NEXT_TELEMETRY_DISABLED=1 -e BUN_INSTALL_CACHE_DIR=/scratch/cache \
  -e NODE_OPTIONS=--max-old-space-size=2048 -e LEARNHOUSE_DISABLE_EE=1 \
  -e LEARNHOUSE_BUILD_NO_TELEMETRY=true -e LEARNHOUSE_BUILD_CPUS=1 \
  --entrypoint sh "$IMAGE" -c '
    mkdir -p /scratch/web; tar -cf - -C /source . | tar -xf - --no-same-owner -C /scratch/web; cd /scratch/web
    timeout 180 bun install --frozen-lockfile --ignore-scripts --network-concurrency 2 &&
    rm -rf /scratch/cache &&
    timeout 90 node node_modules/next/dist/bin/next typegen &&
    # Only THIS disposable tmpfs installation: types do not need binary assets
    # or source maps. No artifact is produced or eligible for release here.
    find node_modules -type f \( -name "*.map" -o -name "*.node" -o -name "*.wasm" \
      -o -name "*.woff" -o -name "*.woff2" -o -name "*.ttf" -o -name "*.md" \) -delete &&
    timeout 240 node node_modules/typescript/bin/tsc --noEmit &&
    echo ROUTE_TYPES_AND_TSC_PASSED
  '
