# Upstream 1.4.3 deployment — 2026-10-29

## Current release

- Source: `7f2f997ce678a385b22c3b57920c1847f90289d3` (upstream merge plus extension-only review fixes and packaging).
- Image: `coursemax-learnhouse:upstream143-7f2f997c-20261029`, ID `sha256:4cbc54da5c0602e4a2432d28066e3a89fb570a9a4c69ea789112110ba503c07a`.
- App-only release: `~/.local/state/learnhouse-launch/releases/upstream143-7f2f997c-20261029`.
- The private `current-release-path` points there. Original missing configuration was recovered from running-container inspection, not guessed or replaced.
- The API runs through `sh /app/api/src/route66_ext/start.sh`. Native `app.py` alone does **not** install the syllabus deletion guard.

Only the app was replaced; the existing gateway was reloaded for upstream DNS.
PostgreSQL, Redis and gateway container IDs, networks, content mount, resource limits,
credentials and existing auth settings were preserved. Google/public registration
and linked LINE/LIFF remain enabled. The only environment changes set
`LEARNHOUSE_BACKFILL_INTERVAL_HOURS=0` and `LEARNHOUSE_RAG_BACKFILL_HOURS=0`, retaining
the current AI/HLS-off behavior without starting historical processing.

## Database and recovery

A network-isolated restore rehearsed the actual unversioned 81-table bootstrap DB.
Named upstream revisions `d7e8f9a0b1c2` and `e8f9a0b1c2d3` were idempotent; metadata
bootstrap added nothing further. During activation the app was quiesced, fresh
DB/schema/content backups were taken and archive listings verified, then the same
runner applied the revisions. It added only `used_link_token`, verified every
existing row unchanged inside the transaction, and did not stamp Alembic or backfill
accounts. No academic/content/student migration was performed.

Retained rollback image: `sha256:85065604eb84fc303fafd920f481cd2abee34a1d1ffdcfd488c2a3db16ebc50d`
(source `88fea34b`). Its complete 698 MiB archive was verified against the image
configuration and 254 blob hashes. The earlier truncated archive was discarded only
after that verification. Original environment and app-only rollback Compose inputs
are saved in the release directory; private evidence remains under
`~/.local/state/learnhouse-upgrade-20261029/`.

Rollback is **code-only**: never restore an older database or erase new evidence.
The parent predates native SQL single-use spending; if unexpired rows exist in
`used_link_token`, retain them and repair forward or wait for their expiration rather
than weaken replay protection. The additive table stays in place. Keep current
credentials if they are subsequently rotated; do not blindly replay stale env files.

## Observed validation

- Full production Next bundle and separate, non-waived TypeScript check.
- 27 collab socket/behavior tests using its Node/tsx package test command.
- 11 baked-runtime PostgreSQL/auth/retention/factory/PDF checks, without source or
  venv overlays; 8,593 API/web/retained-static file checks, no mismatches.
- Eight compiled EN/TH teacher/student workflows at 1440/390: real native password
  sessions, class/calendar navigation, deletion denials, scheduled attendance,
  no-class/restore and QR check-in. Isolated PostgreSQL confirms the final session
  at version 2, one student receipt, and retained syllabus/binding evidence.
- Four live EN/TH 1440/390 login-entry checks: Google, LINE and password controls,
  correct provider ordering, no page errors or horizontal overflow. Anonymous
  school/class/attendance requests return 401; existing admin grant remains intact.
- Live health is HTTP 200 and Docker health is healthy. Final recorded capacity:
  14.05 GiB disk free / 4.71 GiB available RAM.

Real Google/LINE consent, MFA devices and physical QR trials were not repeated.
Synthetic proof is not institutional acceptance or full feature parity. Earlier
source-suite evidence remains in [the integration record](upstream-1.4.3.md).

## Build notes

The owned `deploy/staging/Dockerfile.upstream-143` supports a `web-artifact` target.
After successful bundle/types, export and hash that artifact; the final `runner`
can consume it with `--build-context frontend-builder=/path/to/web-artifact`.
This avoids rebuilding the frontend when assembling the matching API/collab image.
Keep prior static chunks via `old-static/` for in-flight clients.

Normalize read/executable modes of the **clean public source archive only** before
COPY; private archive permissions initially prevented unprivileged baked tests from
reading modules. Do not chmod the enclosing private state, runtime files or backups.
The temporary test-mount workaround was reverted; `84059227` has the same source tree
as the released `7f2f997c`.

Shared-host builds repeatedly exhausted capacity. Only this task's bounded builder
was stopped/retried; only its disposable cache was reclaimed. No other workload or
existing application image was stopped/deleted. The accepted synthetic containers
were removed after their DB dump and results were retained. No broader cleanup
permission is implied.
