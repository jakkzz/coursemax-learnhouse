#!/usr/bin/env bash
# Offline optional-profile / native-filesystem dry run; no live volumes or APIs.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
API_IMAGE=${API_IMAGE:-coursemax-learnhouse:80bdc5b7}
python3 "$ROOT/deploy/staging/preflight.py"
docker image inspect "$API_IMAGE" >/dev/null

docker run --rm --pull=never --network none --read-only \
  --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges \
  --memory 384m --cpus 0.5 --pids-limit 64 --tmpfs /tmp:rw,size=16m \
  -v "$ROOT/apps/api/src:/app/api/src:ro" \
  -e TESTING=true -e LEARNHOUSE_DISABLE_EE=1 \
  -e LEARNHOUSE_AUTH_JWT_SECRET_KEY=synthetic-profile-regression-key-32-chars \
  -w /app/api --entrypoint /app/api/.venv/bin/python "$API_IMAGE" \
  -B -m unittest src.tests.services.test_provider_profile -v
