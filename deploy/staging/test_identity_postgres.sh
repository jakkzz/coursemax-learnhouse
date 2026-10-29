#!/usr/bin/env bash
# Disposable PostgreSQL over a private Unix socket; no live DB or network access.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
python3 -B "$ROOT/deploy/staging/preflight.py"
API_IMAGE=${LEARNHOUSE_API_TEST_IMAGE:-ghcr.io/learnhouse/app@sha256:0aca30cd7b772bebfb75c8e4e54613ab4391adb2d4e05403992867388169514f}
DB_IMAGE=pgvector/pgvector@sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a
docker image inspect "$API_IMAGE" >/dev/null
docker image inspect "$DB_IMAGE" >/dev/null
SCRATCH=$(mktemp -d /tmp/lh-identity-pg.XXXXXXXX)
NAME=lh-identity-pg-$(basename "$SCRATCH" | tr '[:upper:]' '[:lower:]')
STARTED=0
cleanup() {
  if [[ $STARTED == 1 ]]; then docker stop --time 5 "$NAME" >/dev/null 2>&1 || true; fi
  rm -f -- "$SCRATCH/.s.PGSQL.5432" "$SCRATCH/.s.PGSQL.5432.lock" "$SCRATCH/passwd"
  rmdir -- "$SCRATCH" 2>/dev/null || true
}
trap cleanup EXIT
# A synthetic passwd entry lets initdb run as the host fixture-directory owner.
# Never expose the host's real passwd file or run the database as host root.
if [[ $(id -u) == 0 ]]; then echo 'Run this fixture as an unprivileged user' >&2; exit 1; fi
printf 'fixture:x:%s:%s:Synthetic fixture:/tmp:/bin/sh\n' "$(id -u)" "$(id -g)" > "$SCRATCH/passwd"
docker run -d --rm --pull=never --name "$NAME" --network none --read-only \
  --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges \
  --memory 512m --cpus 0.5 --pids-limit 96 \
  --tmpfs "/var/lib/postgresql/data:rw,size=320m,uid=$(id -u),gid=$(id -g)" \
  --tmpfs "/var/run/postgresql:rw,size=4m,uid=$(id -u),gid=$(id -g)" \
  --tmpfs /tmp:rw,size=16m -v "$SCRATCH:/scratch" -v "$SCRATCH/passwd:/etc/passwd:ro" \
  -e POSTGRES_USER=fixture -e POSTGRES_DB=fixture -e POSTGRES_PASSWORD=synthetic-fixture-only \
  "$DB_IMAGE" -c listen_addresses='' -c unix_socket_directories=/scratch,/var/run/postgresql \
  -c unix_socket_permissions=0700 -c shared_buffers=16MB -c max_connections=20 \
  -c min_wal_size=32MB -c max_wal_size=64MB -c checkpoint_timeout=30s >/dev/null
STARTED=1
READY=0
for _ in $(seq 1 60); do
  # PID 1 must be the final postgres process, not initdb's temporary server.
  if docker exec "$NAME" sh -c 'read -r process < /proc/1/comm; test "$process" = postgres' >/dev/null 2>&1 \
    && docker exec "$NAME" psql -h /scratch -U fixture -d fixture -tAc 'SELECT 1' >/dev/null 2>&1; then
    READY=1; break
  fi
  sleep 1
done
if [[ $READY != 1 ]]; then
  echo 'Disposable PostgreSQL did not become ready' >&2
  docker logs "$NAME" >&2
  exit 1
fi

VENV=()
if [[ -n ${LEARNHOUSE_API_TEST_VENV:-} ]]; then
  VENV=(-v "$LEARNHOUSE_API_TEST_VENV:/app/api/.venv:ro")
fi
docker run --rm --pull=never --network none --read-only "${VENV[@]}" \
  --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges \
  --memory 384m --cpus 0.5 --pids-limit 64 --tmpfs /tmp:rw,size=16m \
  -v "$SCRATCH:/scratch" \
  -v "$ROOT/apps/api/src:/app/api/src:ro" \
  -v "$ROOT/apps/api/config:/app/api/config:ro" \
  -v "$ROOT/apps/api/migrations:/app/api/migrations:ro" \
  -v "$ROOT/deploy/staging:/deployment:ro" \
  -e TESTING=true -e LEARNHOUSE_AUTH_JWT_SECRET_KEY=synthetic-fixture-jwt-secret-32-chars \
  -e LEARNHOUSE_DOMAIN=learn.example.com -e LEARNHOUSE_SSL=true -e LEARNHOUSE_DISABLE_EE=1 \
  -e RUN_IDENTITY_POSTGRES_TESTS=1 -e IDENTITY_TEST_PG_SOCKET=/scratch \
  -w /app/api --entrypoint /app/api/.venv/bin/python "$API_IMAGE" \
  -B -c 'import unittest; from src.tests.services import test_academic_rosters as a; loader=unittest.defaultTestLoader; suite=loader.loadTestsFromNames(["src.tests.services.test_native_google_sessions", "src.tests.services.test_native_line_sessions"]); suite.addTests(a.AcademicRosterTests(name) for name in a.AcademicRosterTests.__dict__ if name.startswith("test_")); suite.addTests(loader.loadTestsFromTestCase(a.ParserTests)); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())'
