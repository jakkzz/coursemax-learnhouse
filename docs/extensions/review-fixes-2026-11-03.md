# Review fixes — 2026-11-03

Owner requested: plan all three fixes, rehearse, revise the plan, implement,
commit/push and deploy. Starting source `5975d917`; live image `4cbc54da`.
This is a backend-only repair: no schema, frontend, account, roster import,
provider configuration or shared-infrastructure changes.

## Initial plan (before rehearsal)

1. Bind roster previews to the class version/configuration used for fetching.
   Reject concurrent corrections instead of stamping old rows with new facts.
2. Remove the retention guard's nested database-pool dependency. Evaluate a
   separate guard pool against mixed guard/academic traffic, not only deletes.
3. Make native chapter/activity reordering one transaction: replace its first
   commit with a flush, leaving the final commit after all activity validation.
4. Add permanent synthetic regressions for each failure and existing retention,
   permissions, ordinary deletion, shared activities and successful reordering.
5. Package only changed API files over the verified current image; test the baked
   result against disposable PostgreSQL. Preserve the parent image, back up the
   relevant live state, replace only the app and verify public/private endpoints.
   Roll back code only if necessary; never restore old academic data.

## Native integration decision to rehearse

The current HTTP guard keeps a separate transaction alive around native services.
A larger pool is not a fix. If a dedicated pool still deadlocks against ordinary
academic writers, move the existing owned retention check into the native deletion
transaction with exact delegates in `services/courses/chapters.py` and
`services/courses/activities/activities.py`; serialize reordering in that same
request transaction. Keep every policy/query in the existing owned extension.
This also protects direct native service calls without route replacement,
monkeypatches, dependency overrides or a second content writer.

The owner explicitly requested fixing the three reported defects, including the
native reorder service. Record only these exact reviewed native bytes in the
existing boundary exception mechanism; do not widen prefixes, move the snapshot
or relax upstream acceptance. Rehearse permission/retention/concurrency and atomic
failure before selecting the final integration.

## Rehearsal and revised plan

The initial review reproduced all three failures with checked-in functions and
synthetic dependencies. A further bounded scheduling rehearsal rejected a separate
guard pool: ordinary academic writers can fill the main pool while waiting for the
guard's lock, so its native handler still cannot acquire a connection. The revised
single-transaction design completed 30 mixed writers using two connection slots.
These are offline scheduling checks, not PostgreSQL acceptance.

Revised implementation:

- Snapshot the roster class version before fetching; after refresh, reject a changed
  version before constructing or storing the preview. Do not lock during HTTP fetch.
- Replace the ASGI retention transaction with the same owned guard called by native
  chapter/activity deletion, using the caller's session before file deletion. Take
  the advisory lock after native permission checks; re-read deletion links under it.
- Lock native reordering after authorization and before reading/mutating links.
  Replace the intermediate commit with flush; final commit releases the shared lock.
  The lock need not span post-commit search indexing or HTTP response transmission.
- Keep the launcher and native CORS/CSRF behavior. No second pool, middleware session,
  route replacement, session override, schema change or permission redesign.
- The only native edits are these exact delegates and commit-to-flush in the two
  identified course service files. Existing boundary snapshot/allowlists stay pinned.
- Add real isolated PostgreSQL cases for stale preview rejection, failed-reorder
  rollback, successful reorder and pool-size-one HTTP completion; retain protected
  syllabus/files/versions and concurrent-preparation checks through mutation commit.
- API-only image overlay, focused baked regressions, app-only deployment and code-only
  parent rollback. Frontend bytes and dependencies must remain identical to parent.

## Implementation validation

The three new PostgreSQL regressions failed against the original implementation:
wrong-section preview was accepted, failed reorder persisted changed chapter links,
and a one-connection HTTP fixture hit QueuePool timeout. They now pass, with an
additional unchanged-preview/stale-apply check. Eight focused checks pass including
launcher composition; 85 identity/permission regressions pass, and the protected
syllabus/files/versions/concurrent-commit case passes separately. Native trailing
slashes now use their ordinary redirect before the guarded handler (the HTTP test
follows it instead of expecting a middleware-generated response).

All 46 affected native chapter/activity unit tests pass. Their opt-in SQLite plugin
emulates only PostgreSQL advisory-lock SQL; real locking and rollback were tested
on PostgreSQL, not inferred from SQLite. The guard uses portable JSON string
extraction without changing its bound-activity predicate. Boundary and 28 tooling
checks pass; exact exceptions cover only the two reviewed native service files.

The final source rerun passes 10 focused PostgreSQL/HTTP/launcher checks, including
explicit denial before lock acquisition. Private evidence:
`~/.local/state/learnhouse-review-20261103/`. No live changes yet.

A packaging preflight refused 2.90 GiB available RAM; work waited until recovery.
With 3.49 GiB available, the current image was archived and all 60 OCI blobs verified
against its exact configuration `4cbc54da`. `Dockerfile.review-fixes` uses that local
verified OCI context through the shared limited builder: no registry pull, dependency
installation or frontend rebuild. Preserve this parent archive for code-only recovery.
Baked acceptance and activation are pending.
