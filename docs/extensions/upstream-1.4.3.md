# Upstream 1.4.3 source integration — 2026-10-29

Owner requested an upstream update while preserving our customizations. Integrated
pinned upstream `2d75337273ac496c523db34541707f4268d4d644` (1.4.3) into the fork from
`92df5b89`, rehearsed in the separate `coursemax/upstream-1.4.3` worktree before
advancing staging source. Upstream main `3b13dae5` has the same tree. This is a
source update, **not a live deployment**. Live remains the retained `88fea34b` image.

## Resolution

- Eight textual conflicts resolved: native MFA/session/users, web auth proxy,
  Google callback, login, org layout and tenancy proxy. No ours/theirs whole-tree
  merge. All 395 pre-existing added fork files remain; no custom module deleted.
- Native auth/security/RBAC/dependency fixes are accepted. Retain provider subject
  ownership, retired email-only Google (410), LINE, profile cancellation/locks,
  owner-email DTO, course-history veto, syllabus exception, native UserGroup bridge,
  attendance continuation and shared Interior controls.
- MFA rotation preserves immutable provider claims, original auth time and native
  custom-domain provenance. Session issuance accepts both sets of arguments.
- Native MFA challenges use upstream SQL spending. Provider challenges deliberately
  keep the existing 43-character JTI and Redis spending ledger: switching stores
  during an update could admit an already-consumed in-flight challenge. A read-only
  precheck now rejects spent provider challenges before consuming backup codes.
  This preserves the established provider flow rather than claiming all challenge
  types now share one ledger.
- Auth proxy unions provider and native MFA token paths, retains provider Origin
  forwarding/strict logout, adopts upstream origin checks, browser-host propagation
  and refresh-token redaction. Browser session state no longer stores refresh tokens.
- Keep our opaque server-verified Google callback unchanged; native cross-origin
  callback implementation does not replace that flow. Native login MFA and owned
  attendance continuation exceptions coexist. Stored provider MFA also sets the
  arrival ref before login's redirect effect runs.
- Native command-palette/shortcut providers coexist with our in-flow attribution
  and chromeless guards. New search entries for custom workspaces are not added here.
- Merge revision `d5ab36f3c924` joins `c4fa25e2b813` and `e8f9a0b1c2d3` without DDL.
  From `apps/api`, `python -m src.route66_ext.migrations heads` uses both native and
  owned discovery. This is NOT permission to stamp/upgrade a bootstrap live schema.
- Actual dependency regression found and fixed: pypdf 6.21 moved `Font` from
  `pypdf._font` to `pypdf.generic._font`; our positional Thai table reader now uses
  that location. It still depends on a private library interface, covered by generated
  PDF tests. Do not deploy this source on the old dependency layer.

## Boundary review

The historical `upstream_baseline` and `snapshot` remain unchanged. The gate now
recognizes only exact bytes from the explicitly pinned `accepted_upstream_revision`
for upstream-changed paths. Neither retained legacy paths nor exact custom exceptions
can use that exemption; those must match their separately reviewed hashes. No native
prefix was opened. Tests verify subsequent working/staged/committed drift is rejected.

Exact native exceptions record the resolved auth/session/profile/retention/UI files,
including files that Git auto-merged. Existing syllabus/proxy/mobile-menu hashes were
reviewed against the upstream delta; the left menu's only new delta is its Discord URL.
The upstream combined Google/magic-link test now expects 410 for the retired legacy
Google endpoint while retaining magic-link domain-binding assertions. Owned Google
completion remains covered by PostgreSQL tests; no test was changed to re-enable it.

## Validation observed

Using a new isolated Python environment installed from the updated frozen `uv.lock`,
and web dependencies installed with pinned Bun 1.4.4/frozen lockfile:

- 199 native auth/MFA/RBAC/privacy plus owned session/discovery regressions pass.
- 114 isolated PostgreSQL Google/LINE/roster tests pass.
- 54 isolated PostgreSQL learning-access/policy tests pass.
- Calendar/syllabus suite: 21 pass, one opt-in private-source proof skipped. Includes
  generated Thai PDFs, native syllabus create/edit/save and existing named migrations.
- 83 custom frontend source/contract checks pass.
- 55 Bun behavior checks pass: native/provider auth proxy, cookies/origin/logout,
  attendance continuation, native search, keyboard shortcuts and relay credential stripping.
- Generated Next routes and full TypeScript no-emit pass at a 2048 MiB JS heap.
- Extension placement gate and tooling suite pass (28 tests).

Upstream's SQLite fixture cannot compile our PostgreSQL regex CHECKs once all models
are discovered. An explicit **test-only** plugin omits only those owned CHECKs on
SQLite; real extension constraints remain exercised on isolated PostgreSQL. No runtime
constraint or production dependency override was changed. The discovery test's stale
19-table count was replaced with the exact 20 already-existing owned table names.
The syllabus fixture now includes the native Assignment table because upstream's
activity update synchronizes its publication state.

A low-memory TypeScript attempt failed before the successful bounded retry. A combined
large backend test process ended without a summary; it is not counted as passing.
The bounded split suites above are the accepted results. Fixture repairs add the
explicit test-venv/config/deployment mounts and reuse the attendance runner's bounded
WAL/tmpfs settings. No shared DB/network/service was used by those tests.

Example commands (from the fork, synthetic fixtures only):

```sh
python3 -B scripts/extensions/check_boundary.py
python3 -B -m unittest discover -s scripts/extensions -p 'test_*.py' -q
# In the isolated API environment:
python -m pytest -p src.route66_ext.tests.sqlite_native_tests \
  src/tests/routers/test_mfa_router.py \
  src/tests/security/test_auth_flow_hardening.py \
  src/tests/security/test_hardening_round7b_auth.py \
  src/tests/security/test_hardening_round7_rbac.py \
  src/tests/routers/test_users_router.py \
  src/route66_ext/tests/services/test_upstream_143_sessions.py \
  src/route66_ext/tests/services/test_extension_boundary.py
# PostgreSQL runner supports LEARNHOUSE_API_TEST_IMAGE and
# LEARNHOUSE_API_TEST_VENV for an isolated runtime with the updated lockfile.
```

## Remaining before deploying this version

1. Recover recorded private runtime/Compose/release files: their named paths are
   missing even though existing containers retain their configuration. Do not replace
   credentials or recreate the app from guessed settings.
2. Build a fresh matching API/web/collab runtime and full production web bundle;
   historical same-base overlays cannot deploy this dependency/runtime upgrade.
3. Rehearse the actual bootstrap-schema upgrade. Graph discovery and named-migration
   tests do not prove a complete fresh/existing Alembic chain or live schema readiness.
4. Verify/fix new upstream chapter deletion against bound syllabus retention before
   enabling this version for real content. The existing course-level guard survives,
   but does not cover this new deletion path. No new deletion policy was invented here.
5. Review existing background-backfill settings/resources, then exercise the compiled
   EN/TH login/QR/teacher/student workflows and real provider/device acceptance as needed.

Custom-page search metadata/new upstream Thai labels are follow-up UI integration,
not proof that custom modules were removed. No app build/image replacement, migration,
secret change, real institutional write, historical import or live deployment occurred.
