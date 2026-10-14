# Internal extension extraction — 2026-10-14

This is an internal maintained package, not an upstream-supported plugin API.
The owner approved migration/rebuild/redeploy and resumed after bounded scratch
cleanup. Source extraction is validated; deployment evidence is recorded separately.

## What moved

- 28 backend feature modules and 13 added test modules under `src/route66_ext`.
- Six historical migration implementations moved into that package; discovered
  revision wrappers preserve IDs, ancestry and Alembic behavior.
- 25 added web files copied into `extensions/route66`; 23 TypeScript/component/page
  entry paths became delegates, while legacy styles remain unchanged for consumers.
- Three added frontend test modules moved with compatibility test loaders.
- Native dependencies are confined to 19 explicit backend facade modules (18 native
  `src` modules plus native config) and separate web UI/server adapters. Facades
  preserve signatures, native dependency identity, model objects, current native
  policy and transaction ownership. They do not monkeypatch native globals.
- Five router mounts replaced by one `route66_ext.bootstrap.build_router()` call.
  Native model-discovery paths remain minimal shims; metadata declarations/listeners
  load once. Existing table names/URLs/receipt IDs/session/provider namespaces stay.

[Exact migration map](extraction-map.json), [frozen boundary exceptions](boundary.json).
The extraction script is a one-shot offline codemod from a fixed source snapshot,
NOT a runtime/source-rewrite plugin loader. Do not replay it after completion.

## What deliberately did not move

Native account/session/MFA/refresh/logout, org policy, private owner DTO, profile edit
lock/cancellation and pre-file-deletion retention protections remain their existing
reviewed compatibility seams. With the exception of the reduced router integration,
all 42 other modified upstream files are byte-identical to the prior guide snapshot.
This preserves safety while avoiding another broad rewrite. We still have 43
modified original files relative to the upstream baseline; do not advertise zero
patches or automatic upgrade compatibility. Further seam minimization/upstream fixes
need separate review and native-contract regressions.

Typed facades reduce import churn, not semantic schema coupling: extension queries
still reference native models/fields. Upstream changes to native user/course/access,
config, session and lifecycle behavior still require tests and adapter adjustments.
Native enrollment/access bridge completion and unported feature parity are unchanged.

## Acceptance observed before packaging

- 157 isolated PostgreSQL/native-auth/class/attendance/discovery tests passed,
  including frozen SQL, native-model identity, 15 model tables, stable migration graph,
  unique resolved route operations and facade fail-closed behavior.
- 73 OAuth/proof/profile tests passed in a no-network read-only cached runtime with
  disposable tmpfs. No live DB, provider, registrar or old CourseMax dependency.
- 26 owned frontend tests and 13 source-boundary/tooling tests passed.
- Full production web bundle and generated-route TypeScript passed using retained
  current runtime; no image pull or dependency-version change. The first attempt
  couldn't start because the historical image digest wasn't cached, then succeeded
  with the retained current image.
- Eight compiled EN/TH teacher/student 1440/390 flows passed scheduling, QR display/
  privacy, filtering, no-class/restore, persisted private receipt/reload and expiry/
  heartbeat recovery without page errors/overflow. Initial harness ambiguity between
  the actual error alert and Next's route announcer was fixed by scoping the assertion
  to the check-in region, not weakening the consequence/state check.

No database migration, record rewrite, account grant, feature-flag change, message or
shared infrastructure mutation is required by this source-layout migration. Rebuild
recipes must include BOTH moved implementation files and all compatibility shims;
an old seven-file API overlay is not sufficient. Actual deployment still requires
protected backups/restore/retained parent, baked-byte checks, health/auth/privacy
checks and app-only replacement under resource gates. Never restore an old DB or
remove evidence to undo code changes.

The subsequent upstream rehearsal must pin the actual default branch/commit,
record textual conflicts and compatibility results separately, and never update
live staging merely because Git reports a clean merge.
