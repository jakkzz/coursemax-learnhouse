# Unattended roster refresh — implementation and evidence

## Current release — deployed 2026-11-03 19:42 UTC

Live source `d58e4899b45ce999caef5e2bed4d55ad9492f0e8`, image
`d85f488bdd6ac9123c3ab239fedba8c905c413d726775d9f96b367280485e91e`, healthy at
`https://learn.route66.click`; current release `roster-d58e4899-20261103`.
Approved GitHub Actions run **41685386822** built and typechecked `fa815717`.
Successful run/head, downloaded SHA256 and embedded BUILD_ID were verified.
The candidate's only later code change fixes empty disposable FK teardown in a
provider migration test; its frontend Git tree is identical
(`5407a7686fd35d849fca35b588e9fc8f92a2cda5`). No frontend check was waived.

- **147 baked** PostgreSQL/parser/HTTP/auth/lifecycle/regression checks pass for
  the unchanged runtime payload; see the image recovery note below.
- **Eight packaged native-auth/DB browser workflows** pass: teacher/student × EN/TH
  × 1440/390, actual Redis-led worker against a synthetic internal HTTPS registrar,
  saved background changes, retained focus/drafts, explicit manual acceptance,
  persisted pause/resume and student denial. Screenshots reviewed; no page errors,
  horizontal overflow or collapsed status text. Existing 28 component scenarios
  remain separate, broader fixture coverage.
- **1,262 API files / 5,527 web entries** verified, with **2,630** old hashed assets
  retained. Parent layers and runtime configuration are unchanged. Packaging
  verification caught and rejected restrictive extraction modes and a nested-public
  copy; corrected extraction preserves modes and merges directory contents.
- A fresh full database restore applies `e6bc47a4da35` twice and runs native
  bootstrap: every existing row in **82 tables**, including **48 academic events**,
  remains unchanged; no Alembic stamp.
- The **actual retained `3f19ea47` image** boots against restored synthetic scheduled
  history. Native teacher/student login, manager roster/history reading and student
  denial pass; academic/identity fingerprints are unchanged. The fixture waits for
  API health as well as the web entry before browser checks.

**Deployed after the owner's “deploy it anyway” instruction.** This permitted a
one-time restart-gate exception, not weaker build/runtime limits. Actual admission
was RAM3.00GiB/disk39.82GiB; minimum observed RAM2.90GiB. Global policy is unchanged.

The previously verified `003d5dd9` image and builder state were no longer in the local
Docker store. After unchanged build gates passed, the same retained artifacts were
repackaged without compiling Next again. Image `d85f488b` reverified every API/web
file/link/mode, old static asset and parent configuration/layer prefix, and was saved/
checksummed. The 147 baked/eight persisted workflow results above precede this
identical-payload repackage; they were not rerun as a new complete matrix.

Fresh quiesced DB/schema/content snapshots are protected. The named live migration
preserved every existing row in 82 tables, including 48 academic events, with no
stamp. Only app replaced/gateway reloaded; environment, limits, mounts and DB/Redis/
gateway identities remain unchanged. Live verifies 1,262 API hashes, frontend BUILD_ID,
schema/index/immutable guard and Redis worker leadership. Four live EN/TH 1440/390
entry checks pass: Google/LINE/password controls, private-route denial, no page errors
or horizontal overflow. No real account session was copied or teacher impersonated.

One eligible roster was registered, unpaused, due 2026-11-03 19:58 UTC (04 Nov 02:58
Bangkok); the actual registrar result was still pending at initial verification.
Keep the compatible `3f19ea47` parent/archive and current data for code-only rollback.
Never downgrade or restore older academic data.

Private evidence/helpers: `~/.local/state/learnhouse-roster-gha-20261103/`, especially
`candidate-verification.json`, `baked.log`, `browser-results.json`,
`restore-rehearsal.log`, `parent-image-browser.json`, `persisted-*-parent.json`
and `activation-result.json`, `live-entry-results.json`, `candidate.image.tar.sha256`.
The active release holds `live-verification.json`, `migration.log`, protected backup
checksums and the one-time owner override record. Synthetic/live-entry checks do not
establish real provider/device, institutional migration or broad CourseMax parity
acceptance.

## Historical planning and source checkpoints

Original planning/rehearsal: 2026-11-03, baseline `46fa0d97` (runtime
`85a18e87` / `3f19ea47`). The owner subsequently requested implementation of the
revised plan. The historical rehearsal below remains distinct from runtime proof.

Historical source checkpoint `14b84adf`: owned worker, shared acceptance, system attribution,
manager controls and shared EN/TH roster UI are written. **66 source-mounted
PostgreSQL/HTTP/lifecycle/discovery regressions and 28 tooling tests pass.** The
1,000-student fixture retained 1,002 scheduled events; initial plus scheduled history
occupied 876,544 bytes, with both observations completing in about 20 seconds at
0.5 CPU. No evidence pruning/hash-only skipping was added. The full frontend build,
rendered workflows, compatible rollback and deployment are still pending. Live
remains unchanged; do not treat this source checkpoint as activation.

### Earlier implementation follow-up — validated source, local build blocked

The owner-approved implementation is wired through the owned router lifecycle and
all three interactive import callers. It uses the existing engine/writer/access
repair, SQL fencing, deployment Redis leadership, six-hour cadence, pause/check
controls and exactly one matching large-drop continuation. A recent-run partial
index avoids scanning per-student history during status polling. No native hook,
new pool/service, deployment flag or alternate roster/account writer was added.

Observed source/component checkpoint (2026-11-03; superseded by packaged evidence above):

- **77** isolated PostgreSQL/parser/HTTP/metadata/lifecycle/regression checks pass,
  including concurrent claims, expired/changed leases, one-connection fetching,
  crash/lost acknowledgement, real fixture-connection loss, manual/background races,
  old-term unmatched/NULL-ID sources, authority loss and native access failure.
- Named migration `e6bc47a4da35` follows `d5ab36f3c924`. It preserves human events,
  adds constrained system attribution and operational state/history index, and
  refuses downgrade over retained history/state. The exact `85a18e87` **source**
  reader successfully reads new NULL-actor scheduled history and the manager roster
  in the disposable database; this is not a new image/whole-backup restore claim.
- **28** rendered component/browser flows pass at EN/TH 1440/390, including students,
  official-only viewing, unmatched saved-roster navigation, 0/1/40/1,000 rows,
  queued/failure/review/pause states, drafts/focus, intended withdrawal, wrong-class
  responses and stopped polling. A mobile status-column collapse was caught and
  fixed with an explicit width regression. Shared Interior controls are reused.
- **28** tooling tests and the boundary gate pass. The design detector found no
  mechanical issues. The 1,000-student fixture retains 1,002 scheduled events;
  initial plus scheduled history, including indexes, occupies 892,928 bytes and
  both observations take about 18 seconds at 0.5 CPU. Evidence is not pruned.

Browser checks use actual roster components and synthetic HTTP responses, substituting
unrelated shell/calendar owners and using the recorded native CSS artifact. They do
**not** prove a new full Next bundle, native-shell typography, real UI-to-DB workflows,
provider/device acceptance or owner usability approval. The visual review is inline.

**Resource blocker:** the `vps-limited` full bundle was cancelled when host available
RAM fell below 1.5 GiB. Separate generated-route checks succeeded, but full TypeScript
checks exhausted 1,024/1,536 MiB heaps; the 2,048 MiB-heap attempt was stopped at the
same host headroom limit. No successful full bundle/types or deployable artifact is
claimed. The shared 4 GiB builder ceiling and admission floors were not weakened;
only our build/test was stopped. No live service/schema/records changed.

Live remains `85a18e87` / `3f19ea47`. Next: wait for adequate build headroom, archive
the **latest** source (the failed private build snapshot is only `14b84adf`), complete
bundle/types and compiled persisted workflows, then verified packaging, fresh
protected recovery checks, named migration, bounded app-only deployment and live
verification. Do not deploy the failed artifacts or restore older academic data.

### Approved off-host build continuation

After a fresh `42838c21` local retry also stopped at 1.46 GiB available RAM, the
owner approved trying GitHub Actions. `.github/workflows/route66-web-artifact.yaml`
is the one exact reviewed discovery exception; snapshot/prefix policy is unchanged.
The existing upstream community workflow was not reused because it also builds
other services/architectures and publishes to the upstream registry namespace.

The new fork-only workflow runs on the standard hosted Ubuntu runner, keeps the
4 GiB/no-added-swap/2-CPU/single-step builder limits, and calls the existing owned
`Dockerfile.upstream-143` web-artifact target. Full bundling and non-waived types must
both succeed. It uploads a tar archive preserving links/modes, its SHA256 and source
revision. Only read access to public source is requested; no production credentials,
server access, registry publication or automatic deployment. Existing unrelated
workflows are unchanged. Verify the successful run/head SHA, downloaded checksum
and embedded BUILD_ID before local packaging. Off-host success is not deployment
or database acceptance; normal candidate/recovery/live checks still follow.

Private evidence: `~/.local/state/learnhouse-roster-refresh-20261103/`, especially
`backend-final.log`, `rollback-reader.log`, `ui-3.log`, `ui-results.json`,
`web-build.log`, `web-min-memory` and `types-{1,2,3,4}.log`.
For the parent-reader check, place `git archive 85a18e87 apps/api` under
`parent/` in `LEARNHOUSE_TEST_PRIVATE_SOURCE`; the reader itself is checked in at
`apps/api/src/route66_ext/tests/services/roster_refresh_parent_reader.py`.
Browser reproduction uses `apps/web/extensions/route66/tests/build-roster-refresh.mjs`
with pinned dependencies in a bounded container, then `roster-refresh.browser.cjs`
with `LEARNHOUSE_UI_EVIDENCE`, `LEARNHOUSE_NATIVE_WEB`, `PLAYWRIGHT_MODULE_PATH` and
`CHROME_BIN`. No dependency install, real credentials or live registrar is needed.

Audit scope: B02 roster/history, O02 periodic work and O05 official-source handling;
regressions touch A05/B01 native eligibility. Identity-case resolution, attendance
corrections, broad authoring and historical migration remain separate roadmap items.

## Product brief

**Job / mode:** Operate. A teacher should trust the saved class roster without
repeatedly visiting the registrar, and see a precise next action only when something
needs attention. Students get the resulting own-class access; they never operate a
sync control or see their classmates' private roster.

**Direction:** Keep the existing My classes → saved roster workspace, native shell,
shared Interior controls and English/Thai layout. Official NRRU source viewing is
not saved membership. Do not turn its read-only refresh icon into an import action.
One quiet status line, one check/retry action and inline exceptional review; no
new dashboard, tab hierarchy, setup wizard, timer picker or default-off deployment
flag. Preserve selection, filters, manual-member drafts, focus and readable rows.

**Outcome:** A valid scheduled snapshot reaches the existing roster writer and
native access-repair path once; the teacher can tell last attempted/accepted state,
see changes, pause/resume and recover failures without internal IDs or pasted URLs.

## Sources inspected

- Current `services/academic_rosters.py`, `routers/academic_classes.py` and
  `routers/class_connections.py`: fixed-origin HTML/RTF parsing, first acquisition,
  preview/apply, 30-minute identical-snapshot cooldown, manual member protection,
  two accepted missing snapshots, version checks and one shared academic lock.
- `db/academic_classes.py`: retained class/roster/event authority; every event
  currently requires a real `actor_user_id`. There is no refresh scheduler/state.
- `services/learning_access{,_recovery}.py`: optional native access repair is isolated
  with savepoints; manually granted access/progress are not a second roster writer.
- `ClassesWorkspace.tsx`, `real-teaching/OfficialRoster.tsx`, `ClassConnections.tsx`:
  saved roster, separate official-only view and existing access-repair action.
- Owned `adapters/application.py` / `bootstrap.py`: lifecycle and metadata seams;
  no native startup/router hook is needed for the proposed integration.
- Pinned CourseMax `9647db65d4b37b0b3a569bc1e61042997663d179`:
  `backend/scripts/sync_nrru_rosters.py`, `backend/app/services/nrru_roster.py`,
  `offering_policy.py` and `docker-compose.yml`. Its configured registrar offerings
  run every 21,600 seconds, two seconds apart, including older terms; scheduled
  runs have no human actor. It rejects a drop below half when at least ten registry
  members are active. This is source evidence, not a runtime dependency or permission
  to copy its whole implementation. LearnHouse also supports reviewed NULL-class-ID
  RTF sources; do not copy the old non-NULL-ID eligibility predicate.

The product/design context still contains prototype-era notes. The deployed source,
current instructions and `interior-ui.md` are authoritative for this incremental
surface. No new visual world, assets, dependencies or native shell edits are planned.

## Initial candidate, before rehearsal

1. Start one extension-owned periodic task after native startup, checking saved
   registrar classes every six hours and preserving initial interactive review.
   Reuse the existing fetch/parser/apply/access-repair path.
2. Evaluate a changed-hash-only shortcut against the two-missing-snapshot rule;
   verify whether the cooldown currently lives in the shared writer or only HTTP.
3. Evaluate in-process scheduling against two instances, a retry after commit and a
   manual review racing a background fetch. Never hold the academic lock for HTTP.
4. Determine truthful scheduled attribution: do not replay a teacher session or
   silently label a system job as the last teacher who clicked Apply.
5. Rehearse empty/wrong-section/partial replies, a large drop, manual withdrawals,
   identity conflicts, revoked management authority and optional native access failure.
6. Rehearse teacher desktop/mobile and student tasks on a state/interaction model:
   fresh, checking, failed with saved rows, missing-once, review-needed, paused,
   stale preview and roster-saved/access-repair-pending. Preserve drafts and focus.

## Rehearsal results and revisions

Observed, not an implementation claim:

- **32 existing baked API checks passed** in disposable, network-isolated PostgreSQL:
  both arrival orders for Google/roster matching, stable IDs, manual membership,
  missing/reactivation, conflicts, authorization, stale/one-use previews, native
  access/progress preservation and access-repair isolation; four RTF parser cases
  are included. No live PostgreSQL or registrar was accessed.
- **32 offline model/parser/UX checks passed** in
  `scripts/extensions/rehearse_roster_refresh.py`. The proposed timing, lease and UI
  states are a synthetic specification, not a real worker or SQL concurrency test.
  HTML source-selection/parser checks execute selected unchanged current functions.
- **Two real packaged FastAPI lifecycle checks passed:** a public
  `APIRouter(lifespan=...)` composes after native startup, cancels its task before
  native shutdown, preserves native lifespan state, and never starts on failed
  native startup. No runtime monkeypatch or native-file hook is needed.
- A real red/green model case exposed repeated large-drop approval: after the first
  approved missing snapshot, the next identical observation was still held forever.
  The revised one-confirmation authorization passes; changed digest, source or class
  version does not reuse it.

| Candidate assumption / observed gap | Revised decision |
| --- | --- |
| Skip any unchanged source hash | Re-fetch and accept eligible observations even when identical: a later successful observation must be able to confirm an existing missing member. Reusing a cached result/retrying one job is not another snapshot. |
| Direct `apply_roster()` carries all HTTP checks | It does not carry the HTTP cooldown/preview authorization. Factor shared acceptance checks and use them from both paths; do not call an HTTP endpoint as a worker. |
| One in-memory task/lock is enough | Persist a per-class claim/fencing token and completed result, plus deployment-scoped leader coordination. Restart/overlap cannot apply a job twice. |
| Borrow the last teacher's user ID | Scheduled events need a real system origin with no human actor. Make the owned event schema support it, keeping interactive actors unchanged. |
| A structurally valid short page is safe to apply repeatedly | Carry the pinned source's large-drop rule into automated acceptance. Empty/invalid pages remain failures, never empty rosters. |
| “Review changes” alone solves a held large drop | Bind explicit review to a fresh snapshot, then allow exactly one matching later observation to finish the two-snapshot decision. Otherwise the teacher is trapped in repeated approvals. |
| Refresh success and native access success are one state | Save the accepted roster independently; show the existing access-repair action separately. Never tell a teacher to import the same roster again to fix native access. |
| Poll by incrementing the existing global refresh counter | That effect clears previews, member drafts and reasons. Poll status independently; invalidate stale confirmation, not the user's work. |
| NULL official class ID means manual/unconfigured | LearnHouse's reviewed course/term/section RTF source is valid. Use persisted source selection, not the old CourseMax non-NULL-ID predicate. |
| Official-source screen can host the new import button | It is read-only source viewing. Put membership refresh in the saved roster and provide a clearly labelled handoff from the official view. |

Private logs: `~/.local/state/learnhouse-roster-refresh-plan-20261103/`:
`baseline.log`, `rehearsal.log`, `lifespan.log`, `review-dead-end-red.log`.
The flow review is inline, not an independent worker or a human usability study.

## Revised implementation contract

### 1. Scope, cadence and eligibility

- Default **every six hours**, with one outbound roster request at a time and at
  least two seconds between source requests, matching the pinned source's cadence.
  Do not add an interval picker or new service dependency.
- Only an already saved class with an accepted initial roster and valid server-owned
  source binding is eligible. Opening an official roster, viewing a timetable or
  creating a calendar-only class never opts it into an initial roster import.
- Include the reviewed HTML and NULL-ID RTF sources, matched and unmatched saved
  classes. Revalidate organization, mapping and management authority: active assigned
  org teachers for matched classes; the existing verified-owner rule for unmatched
  classes. Do not impersonate either actor or reuse a browser/provider session.
- Older terms are not assumed closed from the current date. Like the reference,
  refresh configured classes until paused or their authority becomes invalid. Show
  **Pause automatic refresh / Resume** in normal class controls; no invented term
  dates or destructive automatic term closure. Revoked authority stops application.
- Initial connect/initial reviewed apply schedules the next check six hours later.
  Existing accepted classes get operational state lazily with staggered first due
  times; do not replay missed six-hour slots after downtime or backfill membership.
- On source failure or review hold, keep the roster and retry at the ordinary next
  six-hour check. **Check now** can request an earlier check using existing native
  context/origin/throttle controls; requests coalesce. Lock/version contention can
  retry after one minute without being shown as a registrar failure.
- Preserve the existing 30-minute recently-applied identical-source guard across
  callers. A duplicate check can update “last checked” but not missing counters,
  class version or “last applied.” It does not schedule an artificial catch-up run.

### 2. One durable coordinator, one existing roster writer

Use the existing API process, native database engine and deployment-scoped Redis.
Register an owned lifecycle on `bootstrap.build_router()` using public
`APIRouter(lifespan=...)`; preserve native startup/shutdown and the API launcher.
No cron host change, new container/queue, extra SQL pool or native core patch.

One small owned `AcademicRosterRefresh` table is proposed, keyed by `class_id`:
paused/control-version, next-check time, last-attempt time/result-event pointer,
lease UUID/expiry, and an optional one-confirmation large-drop approval. Existing
`AcademicClass.last_synced_at`, version and source hash stay authoritative for
accepted snapshots; do not duplicate memberships, identity ownership or history.
A completed `roster_refresh_finished` event holds the run ID, source provenance,
outcome/counts and safe failure code. Do not save failed raw registrar bodies.

Execution order:

1. Acquire/renew a short deployment Redis leadership lease. Claim one due class in
   a short SQL transaction using row locking/skip-locked and a 120-second fencing
   lease. Snapshot class version, control version and full source/organization/course
   binding. Commit and **release the SQL connection before fetching**.
2. Call the existing bounded `fetch_roster()` with its ten-second outer timeout.
   No academic lock, database transaction or connection is held over network waits.
3. Open one writer session. Try the existing academic advisory lock without queuing
   a background connection behind interactive work; then lock/re-read the state row.
   Recheck fencing token, control version, class/source binding and authority.
   An expired/replaced worker cannot commit. Pause then resume also invalidates the
   old fetch. Source/class drift discards that result and schedules a fresh check.
4. Apply shared snapshot acceptance. On acceptance call the existing `apply_roster()`
   and existing optional native access-repair path, not a new account/enrollment or
   roster writer. Save result and next-due time **in the same transaction**. On data
   failure roll back before recording a failed attempt in a short new transaction.
5. Redis loss prevents new claims. SQL fencing/atomic completion—not the Redis lease
   alone—protects commits and retry after lost acknowledgements. Shutdown cancels and
   awaits this task before native shutdown; no detached job outlives the app.

All code paths which change refresh controls follow academic-lock → state-row-lock
order. Claim-only transactions never wait for the academic lock. Interactive manual
apply can win a race; the worker then discards its stale fetch. A completed worker
can stale a manual preview; the UI must request a new review, never replay approval.

The existing writer emits per-member evidence on accepted snapshots. At the current
1,000-student cap and six-hour cadence this can mean about 4,000 member events per
class/day, not four. Keep this visible in the bounded implementation fixture and
storage estimate; do not silently prune evidence or add a hash-only shortcut. Any
later no-op optimization must preserve missing confirmations and identity/access
repair, rather than become a prerequisite architecture project.

### 3. Acceptance, holds and honest audit attribution

- Keep existing exact section/course/term parsing, source bounds, duplicate checks,
  manual memberships/withdrawals, stable student/entry IDs and existing identity
  conflict handling. A failed/empty parse is not a successful zero-member snapshot.
  An identity conflict does not transfer an account or silently grant access; full
  identity-case resolution remains the next roadmap item.
- For at least ten active registry members, a parsed count below half is held before
  any member/missing-count change. Manual members are not the baseline. This exact
  threshold comes from the pinned source; do not invent extra percentage gates.
- **Review changes** re-fetches through the existing preview, showing affected names
  and counts, source/last-accepted times and the two-observation effect. The ordinary
  authorized teacher can approve; no new admin-only ceremony. Empty/malformed sources
  cannot be approved into withdrawals; existing manual member actions remain usable.
- An explicit large-drop approval records the selected-row semantic digest, full
  source binding, approving user/event and resulting class version. It permits only
  one separately fetched matching later observation, subject to cooldown, current
  authority and fencing. That observation consumes it. A different source/digest,
  intervening member/class edit or new approval scope needs fresh review. Retrying
  the same run never consumes another missing observation. A worker cannot approve
  its own large drop by echoing a digest.
- Do not overload `actor_user_id` with a fake account or last teacher. Add an owned
  migration making it nullable only for a tagged scheduled-refresh event with a
  valid run reference; retain the append-only trigger and existing human attribution.
  Use a small explicit scheduled-actor value through existing event-call parameters.
  Centralize the three direct access-recovery event writes through that factory so
  grants, releases, identity matches and the parent snapshot share honest provenance.
- The new migration follows owned merged head `d5ab36f3c924`, with explicit owned
  metadata registration for bootstrap and Alembic. No historical revision edits,
  broad boundary exception, inferred Alembic stamp or data ownership backfill.

### 4. Proposed HTTP and UI integration

Keep existing `/api/v1/academic-classes` routes and native authorization/origin rules:

| Proposed addition/change | Behavior |
| --- | --- |
| `GET /{class_id}/roster/refresh` | Manager-only operational status: due/attempt/accepted times, paused/control version, latest outcome and summary. No student roster disclosure. |
| `POST /{class_id}/roster/refresh/check` | Coalesce a check request; return 202 queued/already checking, never “roster updated” before commit. |
| `POST /{class_id}/roster/refresh/settings` | Pause/resume with expected control version; cancel stale in-flight authority, not existing memberships. |
| Existing preview/apply | Share acceptance checks, add usable changed-member details and explicit fresh large-drop confirmation. Keep existing one-use/version/permission semantics. |
| Existing learning-access status/retry | Remain the separate authority for access repair. Reuse its panel/actions; roster success is not a promise that native access succeeded. |

The refresh-status component is shared in the saved roster surface. Extend saved-class
navigation for manageable unmatched classes with an accepted roster: current
`linkedTeachingClass()` requires a native course UUID, so do **not** broaden that
native-content helper. A separate exact saved-school-class lookup opens the same
roster by class ID without claiming native course access. Calendar-only/unimported
classes remain ineligible; normal initial review still precedes automatic refresh.

### 5. Teacher/student UX, not a scheduler dashboard

Keep the real section/term heading visible. Desktop and mobile use the same reading
order; on mobile actions wrap below status, never force a horizontal toolbar.

```text
Desktop:  Course · section · semester
          Roster                       [Check now] [Refresh options ▾]
          Automatic · every 6 hours
          Last checked 09:10 · Next check 15:10
          Saved roster: 42 registry + 2 teacher-added
          [Only when needed: actionable exception + review/retry]
          Search / membership / account filters
          Existing roster rows
          Recent refreshes ▾

Mobile:   Course · section · semester
          Roster
          Automatic · every 6 hours
          Last checked … / Next check …
          [Check now] [Refresh options ▾]
          [Exception, if any]
          Search and wrapping filters
          Existing stacked member records
```

- Reuse shared Interior `Button`/loading behavior, native disclosure, inputs and
  existing roster rows/status vocabulary. No new tabs, oversized status cards,
  novelty controls, fonts, colors or shipping images. Pause is a secondary action;
  one principal next action owns each exceptional state.
- Keep the current 44px touch controls, native keyboard/visible focus and reduced
  motion. Use localized absolute times with a timezone, optional relative labels
  and `<time>` values. Do not announce a countdown every second.
- One polite live announcement for queued/completed/failed transitions; no background
  success-toast storm, forced modal or focus/scroll movement. Only the check button
  is busy/disabled; saved rows, filters and manual work remain usable.
- Poll the lightweight status only while the roster is visible; stop/abort on class
  switch/unmount. Do not call the existing global refresh setter on every poll.
  Ignore responses for a different class. A new version invalidates confirmation,
  shows **Roster changed — reload and review**, and retains search, selection,
  reason, focus and the intended member action. Never flip Withdraw into Restore.
- While a form/preview is open, do not silently replace its rows. The deliberate
  reload/review action obtains current data and asks the user to reconfirm the
  changed decision. A 409 follows the same recovery path without erasing drafts.
- **Official roster** remains a separate source-only view. If a saved manageable
  class exists, offer **Open saved roster**, not an auto-import side effect.
- Students keep own-membership/content/attendance views. No classmate list, job
  controls, source failure payload or internal identifiers. Waiting copy should not
  imply that a teacher must repeatedly click sync. Own native access is rechecked
  normally; no role or enrollment inference is added.
- Recent refresh history is a short human-readable run summary, not hundreds of
  `registry_member_seen` JSON blobs. Existing detailed evidence stays available to
  authorized managers. `matched` is a current count, **not** “new accounts linked.”

| State | Teacher sees / next action | Membership effect |
| --- | --- | --- |
| No initial accepted roster | **Review initial roster**; no claim that automation is already operating | None until existing review/apply |
| Ready / accepted | Last successful check, next due, concise outcome; **Check now** | Committed source state only |
| Queued / checking | **Check queued / Checking registrar…**, reserved label space | No optimistic success; saved rows remain |
| Failed / invalid / empty source | Last attempt failed, last accepted roster still shown; **Try again** or view official source | No missing-count increment or grants |
| Missing once | Affected row says **Not seen in one accepted check — still active** | Existing membership remains active |
| Large drop held | Explain count change and preserved roster; **Review roster changes** | None until explicit fresh review |
| Stale review | Specific changed-version notice; **Reload and review** | No automatic re-application |
| Roster accepted, access repair pending | Roster success plus separate **Review course access** / existing retry panel | Preserve evidence/manual access; existing owned-grant repair rules apply |
| Paused | **Automatic refresh paused**, saved rows and last accepted time; **Resume** | No withdrawal or unenrollment |
| Check overdue with no live claim | **Automatic check delayed**, truthful last accepted time; **Review manually** still works | Never label “automatic enabled” as successful work |
| Permission lost | Hide private cached rows and controls, use normal sign-in/assignment recovery | No stale worker apply |

Proposed core copy (to validate in actual UI, not claimed owner-approved):

| English | Thai |
| --- | --- |
| Automatic roster refresh · every 6 hours | อัปเดตรายชื่ออัตโนมัติทุก 6 ชั่วโมง |
| Check now | ตรวจสอบรายชื่อตอนนี้ |
| Could not check the registrar. Your saved roster is unchanged. | ตรวจสอบรายชื่อจากทะเบียนไม่ได้ รายชื่อที่บันทึกไว้ยังคงเดิม |
| Review roster changes | ตรวจสอบการเปลี่ยนแปลงรายชื่อ |
| Pause automatic refresh | พักการอัปเดตรายชื่ออัตโนมัติ |
| Resume automatic refresh | อัปเดตรายชื่ออัตโนมัติต่อ |
| Roster updated. Course access needs review. | อัปเดตรายชื่อแล้ว ต้องตรวจสอบสิทธิ์เข้าถึงรายวิชา |

Rehearsed walkthroughs: teacher returns without clicking refresh; temporary source
failure with saved rows; first missing observation then confirmation; one-time
large-drop review/recovery; teacher edits during refresh; access-repair partial
success; student cannot see classmates; official-only viewing performs no import.
The EN/TH state/action model was exercised; these wireframes were **not** rendered
or browser/device tested. Implementation must check actual EN/TH desktop/mobile
layouts, long Thai names, 0/1/40/1,000 students, filters, keyboard focus and motion.

## Implementation sequence and exact surfaces

1. **Owned schema and attribution.** New `db/roster_refresh.py`, owned migration and
   explicit metadata registration (`bootstrap.py` and the existing owned model
   discovery path). Update `db/academic_classes.py` and the event factory; route
   recovery receipts through it. Preserve old event rows/IDs and current native hooks.
2. **Shared acceptance and durable runner.** Extend `services/academic_rosters.py`
   rather than add another member writer. Add `services/roster_refresh.py` for claims,
   due work, limits and fenced transaction orchestration. Use the existing engine
   adapter and Redis resource configuration; no native security redesign.
3. **Lifecycle/API/callers.** Owned bootstrap lifecycle and a router included by
   `routers/academic_classes.py`. Cover both existing `class_connections.py` initial
   apply sites and manual preview/apply. Successful manual imports move the next
   due time in their transaction, so the worker cannot immediately count them again.
4. **Shared roster UX.** A small `RosterRefreshStatus.tsx` in the owned Classes layer;
   integrate `ClassesWorkspace.tsx`, the saved-school-class lookup and
   `RealTeachingWorkspace.tsx` handoff. Keep `OfficialRoster.tsx` source-only. Reuse
   `ClassConnections.tsx` access-repair UI and shared adapters/Interior components.
5. **Focused acceptance and bounded release, when implementation is requested.**
   Real PostgreSQL lease/duplicate/crash tests, migration on fresh/existing fixtures,
   preserved immutable events, one-connection-pool execution, native auth/permissions,
   delayed/lost HTTP responses, retry races, and 1,000-row transaction timing/storage.
   Test two live worker instances and loss of Redis/SQL, not just this model.
   Then actual component/compiled EN/TH teacher/student flows in one batched
   desktop/mobile inspection and at most one correction/confirmation pass.

No native-file edits or boundary policy widening are planned. Later implementation
must pass `check_boundary.py`; only affected backend/frontend artifacts need builds.
A combined API/UI/schema release needs the relevant named migration rehearsal,
protected backup and app-only deployment using the shared limited builder. Do not
start implementation/build/deployment from this planning task.

## Recovery and readiness

Pause stops future refreshes and invalidates in-flight claims; it never reverses an
accepted roster, clears missing evidence, restores revoked grants or deletes history.
Retain new system-attributed events and the operational table on code rollback.
Rehearse the current parent reading those additive records; if it cannot, prepare a
compatible reader without the scheduler before release. Do not promise blind rollback
to `85a18e87`, drop NULL-actor history or restore older academic data. Schema downgrade
must refuse while incompatible scheduled evidence exists.

**Ready for implementation planning handoff:** cadence, eligibility, source bounds,
transaction ownership, attribution, failure/review behavior, UI placement/copy,
recovery and targeted file/test sequence are resolved above. They are proposal choices
for this requested next item, not claims of runtime activation or owner usability
acceptance. The work intentionally excludes a new settings dashboard, custom scheduler
service, account/role/enrollment writer, proactive messages, full identity-case system,
attendance changes and real historical migration.

Reproduce the offline rehearsal from `platform/`:

```sh
python3 -B scripts/extensions/rehearse_roster_refresh.py PlanTests
```

`LifecycleTests` needs only FastAPI and can be run in the existing API image with
network disabled and a 128 MiB / 0.5 CPU limit. The baseline suite used
`deploy/staging/test_attendance_postgres.sh`, `LEARNHOUSE_TEST_BAKED=1` and the existing
`coursemax-learnhouse:review-85a18e87-20261103` image; exact test names/results are in
`baseline.log`. No package installation, build, live reads/imports, schema change,
provider exchange, messaging, source activation or deployment occurred.

