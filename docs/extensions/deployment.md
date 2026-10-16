# Internal extension deployment records

## Latest: class workspace color hierarchy — deployed 2026-10-16

Live source `255e6d75c1c4febbbd3446192b88c1e2e50c0494`, image
`coursemax-learnhouse:classes-color-20261016`, ID
`sha256:f8a7078282ed3245814cb749bc89dbee193e0ecf5a29e6293901cabd6c8b5a68`.
[Scoped color roles](classes-color.md): existing blue for actions/selection, green
for connected classes/access, amber for pending matches/repair and red for failures.
Roster account labels retain text and gain semantic color/icons; unmatched accounts
stay neutral. Native shell, weekday colors, copy and workflows are unchanged.

51 web tests, production build and separate route/types pass. Four compiled EN/TH
1440/390 task journeys cover class list, pending/direct/connected/conflicting states,
source retry and roster handoff. 104 computed foreground/surface checks pass, minimum
4.84:1; text-pair tests also simulate common color-vision deficiencies. Selected tasks
retain a visible underline. Native CSS transitions are allowed to settle before exact
color assertions. One batched desktop/mobile visual inspection; no polish/rebuild loop.
Four live native-bootstrap navigation/reload smokes verify the actual primary action
is blue with white text, without opening real student rosters.

All 1,010 API/config/migration hashes are parent-identical; 5,300 web entries match.
Fresh protected backups, exact seven-archive compatible 7acb parent image/load
round-trip and isolated restore pass. No schema operation. App-only restart/gateway
reload; identity/grants/progress/academic snapshots, runtime/env and non-app IDs
preserved, apart from four native role startup timestamps. Footer unchanged; source
menu updated to exact source revision. No native hook, permission, academic-data or
global theme change. Protected evidence: `classes-color-20261016/`,
`classes-color-web-20261016/`, `releases/classes-color-20261016/`.

## Previous: usable section setup and durable status — deployed 2026-10-16

Live source `7acb67a5b68515cb11ca18b9729c89b56f4c6e5c`, image
`coursemax-learnhouse:class-workspace-20261016`, ID
`sha256:81f6b6d8467c95599efd24b3f6c91c0d023ca59ed359354ea1b5d63f0aa74fa4`.
[Section workflow](class-section-setup.md): already-assigned teachers can set up a
section of an explicitly mapped course and import its initial roster directly.
New mapping/access decisions retain the existing review. Request status survives
reload, pending requests are not repeated, and the open workspace discovers a
completed connection. Overview, Timetable and Roster replace unfinished tabs;
connected sections offer real roster/session/native-content handoffs.

53 focused disposable-PostgreSQL/native-session tests and 48 web tests pass, as do
the production build and separate route/types check. Four compiled EN/TH 1440/390
journeys complete request/reload/status refresh, direct setup, source failure/retry
and roster handoff. They exposed and now cover an aborted-response bug that could
replace valid connection data with `{}`. Four live native-bootstrap navigation and
reload smokes pass against the actual authorized class list; they do not open real
student rosters or impersonate an institutional teacher.

1,010 API/config/migration hashes, 95 owned API files and 5,297 web entries verified.
No new native hook/boundary exception. Exact compatible d96f parent retained and
six-archive image/load round-trip verified. Fresh DB/content/runtime backups and
isolated restore passed; an interrupted final restore-verification attempt was
retained and the verifier rerun to completion before application. No schema or
migration operation. App only recreated and gateway reloaded; identity/grants,
progress, existing academic rows, runtime/env and all non-app container IDs match.
Only four native role startup timestamps changed. Native settings now say
“Development” instead of “Preview only”; the source menu points to the exact source
revision. Other organization configuration was verified unchanged.

Protected evidence: `class-workspace-20261016/`,
`class-workspace-web-release-20261016/`, `releases/class-workspace-20261016/`.
No real roster/history migration, syllabus/plan editor, unattended roster refresh,
calendar generation or cutover is claimed.

## Previous: automatic NRRU acquisition — deployed 2026-10-16

Live source `d96f2c6cb2f7916574f6f1ffb97a62ef355f5e9c`, image
`coursemax-learnhouse:nrru-auto-20261016`, ID
`sha256:75effee94fd16093ed5982158f362def37ed39b56739c8a104c5733d53a83a11`.
[Workflow and authority contract](nrru-automatic-acquisition.md). Select term/section,
review the matching native course and automatically retrieved section count, then
connect with initial roster import in the same transaction. No roster URL/internal
ID input. Existing timetable acquisition is reused; no fabricated class identifiers.

216 isolated PostgreSQL/native-session/auth/access/roster/attendance/migration tests,
19 pure parser tests, 46 owned web tests and 25 boundary/source-tool tests pass.
Fresh full production bundle and separate generated-route/types pass. Sixteen
compiled EN/TH desktop/mobile journeys include URL-free connection, automatic
initial roster, source-failure retry without partial writes, persisted roster,
student native-content handoff and preserved manual access/work. Six live native
auth/account/workspace smoke journeys pass. The actual deployed acquisition
function also read the official export and validated exactly 45 P7 students without
saving/printing student records or accessing the database. These are distinct from
genuine institutional provider/session acceptance, which is not claimed.

1,010 API/config/migration hashes and 5,297 web entries verified. All non-owned API,
configuration and native migration bytes are parent-identical; no native hook or
boundary exception was added. API source retains native root ownership; web entries
retain exact parent ownership when unchanged and UID/GID1000 when overlaid. Image
configuration except revision labels and the parent RootFS prefix are preserved.

Protected fresh DB/content/runtime backups, exact saved3019 image archive/load
round-trip and isolated socket restore passed before applying owned revision
`f47eb52fa044`. The exact candidate migration entrypoint was exercised against the
restored database. Full schema comparison permits only nullable `registry_class_id`
and the named unique official course/term/section constraint; all other schema,
identity/provider keys, grants, progress and academic rows match. The existing
native-bootstrap database remains unversioned; no inferred Alembic head was stamped.
All role fields match except four native-startup timestamps. Only app was recreated;
gateway reloaded. All non-app container IDs and runtime/environment match this
release's own before snapshot. The previous release's unrelated-container failure
remains recorded below, not erased or excluded.

No real roster/history/content migration, cutover, host cleanup or unrelated service
mutation occurred. The saved3019 app rollback refuses if any NULL-ID source class
has since been created; preserve evidence and forward-repair instead. Never restore
historical live DB/content for app rollback. Unattended periodic refresh, dated
calendar planning, persisted identity cases and wider academic parity remain open.
Protected evidence: `releases/nrru-auto-20261016/`, `nrru-auto-20261016/`.

## Previous: production preview and menu retirement — deployed 2026-10-16

Live source `3019c79e8a2abfe2ebd78e8f464c578caf092126`, image
`coursemax-learnhouse:retire-menus-3019c79e`, ID
`sha256:741c3ebf51c013efc32141d7ff18efdf54a5e87e6e9a006aa6832e9cef0ec240`.
First deployed `2066d2f7` removes the production synthetic renderer and redirects the
legacy manager route to `/classes`; then the two explicitly approved native menu
entries were removed. Native dashboard denials remain authoritative for non-managers.
Both menu files, ordinary task links and security/plan controls remain intact.

Full production bundles, separate generated-route/types, sixteen compiled journeys
and ten live smoke journeys pass for the final release. Desktop/mobile EN/TH menu
and legacy-role-query tasks are covered. All 1,001 backend/config/migration hashes
match exact parent `2066d2f7`; 5,296 required web entries match bytes/links/modes and
ownership (unchanged parent ownership retained, changed entries UID/GID1000).
Fresh protected backups, isolated socket restore and exact-parent image archive
round-trip pass. API/schema/runtime/identity/grant/progress/academic snapshots match;
only four native default-role startup timestamps differ after full-field comparison.

Only the staging app was recreated by this deployment; gateway was reloaded. The
original global non-app-ID assertion failed because an unrelated container vanished
concurrently; the exact discrepancy and unchanged remaining IDs are recorded, not
ignored. CourseMax and LearnHouse stores/gateway IDs match. No cleanup or unrelated
mutation was performed. Full details: [demo-retirement.md](demo-retirement.md).
Protected releases: `retire-demo-2066d2f7-20261016` and
`retire-menus-3019c79e-20261016`; the latter was current at that checkpoint. App-only rollback to the
API-identical exact parent preserves all live evidence; never restore historical DB
or files. Real identity resolution, syllabus, dated plans and academic parity remain
unfinished. No real migration or cutover occurred.

## Previous: class connections and access recovery — deployed 2026-10-15

Live source **7bf6ed1fde349f9a580ff92ad610e742cf389b09**, image
`coursemax-learnhouse:class-connections-7bf6ed1f`, ID
`sha256:dbd796717b14505016aa02801f8353566b094e383aac811f5f38b3465b565d11`.
Eight owned backend overlays and a rebuilt frontend on exact **396d1a01**. All
1,001 API/config/migration hashes and 5,291 required web bytes/links/modes/owners
verified; native runtime image configuration and parent rootfs prefix preserved.
No new native hook, dependency, schema migration or activation environment change.

209 full isolated PostgreSQL/native HTTP/auth/roster/attendance tests pass. A
52-test focused recheck additionally exercises the actual native course-page metadata
handler: released private content is readable after delegation, while unpublished
content remains denied. 42 web and 13 boundary-tool tests, corrected full production
bundle/types, separate generated-route types, and 12 compiled EN/TH desktop/mobile
journeys pass. Four stateful journeys complete teacher request → explicit admin
review/connect → reviewed roster apply/reload → native student course page → access
repair, preserving manual readers/work. These use synthetic fixture APIs; native
session/authorization/transactions are checked separately in PostgreSQL integration.
Two live native-auth and four live bilingual desktop/mobile workspace flows pass.
Approved owner Chrome verifies the real own section and usable request action without
submitting it; the existing settings tab remains untouched. No real academic writes.

Fresh protected DB/content/runtime backups and isolated socket-only restoration pass.
Exact compatible **396d1a01** image is recoverable from a protected full saved bf4 OCI
base plus verified 396d delta/config; the reconstructed archive was round-trip loaded.
Only staging app recreated and gateway reloaded. Schema, account/provider ownership,
profiles, audited grants, role permissions, academic evidence, groups, native learning
progress, runtime/env and every other container ID preserved. Only four default-role
`update_date` fields refresh through unchanged native startup; all other role fields
individually verified. Source disclosure points to exact published owner-fork source.

Protected release: `class-connections-7bf6ed1f-20261015`. App-only rollback to 396d
refuses access-evidence-bearing recovery; use a compatible forward app fix instead.
Never restore historical live DB/files/grants/evidence. Generated UI scratch was
recoverably archived with full manifests and process/mount checks; no source, live
data, images or protected backups pruned. CourseMax remains live and untouched.
Actual course/roster review stays in the product; real migration, native enrollment
automation, provider/device and full academic parity are not claimed.

### Implementation contract

The owned extension now includes teacher section requests, an administrator course/
teaching/access review, quota-checked group provisioning, recoverable reading access,
private-course handoff and explicit successor-group repair. No extra activation flag
is required. The retired flag-only Compose/env files and six-file historical build
recipe were removed; use `deploy/staging/Dockerfile.class-connections` with an isolated
backend-plus-validated-web context. Its parent is exact **396d1a01**, not bf4f2908.
See [learning-access.md](learning-access.md) for the current authorization/recovery
contract. The entry below records the previous live behavior, not the new policy.

The validation and protected deployment above supersede the previous inactive
release below. They do not authorize inferred course equivalence, unreviewed real
roster import, historical migration, data deletion or platform cutover.

## Previous: inactive learning-access backend — 2026-10-15

Live source **396d1a012c55198c2798a8cde3c5cfe0f4c45e88**, image
`coursemax-learnhouse:learning-access-396d1a01`, image ID
`sha256:48c51641cfd838005075f6c8063311a4be29ecd534d57269e27cdee9d1ccde3f`.
Six owned backend files overlay exact healthy **bf4f2908**; all 5,304 accepted web
entries remain byte/link/mode-identical. No frontend rebuild or new UI acceptance
claimed. 999 API/config/migration hashes verified; runtime image configuration and
parent rootfs prefix preserved. No new core hook, dependency or schema migration.
See [learning-access.md](learning-access.md) for separate enrollment and recovery gates.

**Configuration remains locked off by default.** The optional configuration Compose
layer is NOT applied; production environment/runtime unchanged. Preview is read-only;
new configuration apply requires the explicit owned gate in addition to all native
authorization/plan/origin checks. Existing delegations would still reconcile if new
configuration were frozen; deployment verified zero delegations/events and seven
empty academic tables before and after. No mapping, class, roster, group, enrollment
or grant was created. Real activation remains separately prohibited pending recovery/
setup/authority acceptance. CourseMax untouched; no cleanup or image pruning.

200 isolated PostgreSQL/native HTTP/auth/roster/attendance tests pass (43 new), plus
13 boundary tools and 41 existing web tests. Ten baked policy cases, baked disabled-
configuration 503, native OpenAPI routes and 999/5,304 artifact checks pass. Private
manifest verification runs as each artifact owner's UID without widening permissions;
failed owner/manifest-format attempts retained. Fresh DB/content/runtime backups,
exact saved bf4 image checksum/config-digest verification, and isolated socket-only
restore/identity checks pass. Additional pre-release restore confirms native org-role
assignments/definitions/provider/profile keys/course rows unchanged, excluding only
four default roles' `update_date`, refreshed by unchanged native startup code; each
other role field was independently compared before accepting that timestamp difference.
No historical evidence was restored or modified on live.

Only app recreated; gateway reloaded. Schema, identities/audited owner grants, native
groups/enrollment/progress, runtime/env, and all other container IDs preserved. Live
native auth/privacy/source disclosure and new-route anonymous/foreign-origin/nonexistent-
class denials pass. Two desktop/mobile native-auth and four EN/TH workspace journeys
pass with no academic writes/errors/overflow. No provider consent, actual institutional
student/device lifecycle or full parity acceptance claimed.

Protected release: `learning-access-396d1a01-20261015`. Rollback is app-only to the
exact saved **bf4f2908** parent; guard refuses rollback if learning-access events exist.
Never restore an old live DB/files/grants/evidence. Current live source link points to
the published owner fork at exact396d1a01. Full operational recovery/activation remains
separate; inactive code deployment is not approval to enable real grants.

## Previous: My classes native account layout — 2026-10-15

Live source/image **bf4f2908**, frontend-only on exact compatible **f9bc5b2a** parent.
See [classes-account-layout.md](classes-account-layout.md). My classes now uses the
same native account wrapper, breadcrumbs, sticky profile sidebar, mobile name/actions
and content framing as School identity. Duplicate class padding removed. Scoped
mobile footer allowance fixes fixed-action overlap without a native source edit.
Existing actual registrar facts, five tasks, strict linking and canonical handoffs
remain unchanged; no academic setup, permission, backend or schema change.

41 web / 13 boundary-tool tests, placement gate, corrected full production bundle /
post-bundle tsc and separate generated-route types pass. Eight compiled EN/TH
1440/1920/930/390 teacher+student journeys check matching framing, footer clearance,
task completion, reload/recovery/focus and zero academic writes/errors/overflow.
Inline finish/documenter review, not independent; disposition ship. DESIGN unchanged.
5,304 baked web entries verified by bytes/links/modes;995 measured backend/config /
migration files unchanged. Native production runtime regeneration and no fixture
endpoints verified. Initial fixture/packaging failures retained, not accepted.

Fresh protected backups, isolated socket DB restore/identity check and saved exact f9
parent checksum/config digest pass. Only staging app recreated/gateway reloaded;
schema, identity/provider/profile keys, audited grants, runtime/env and other running
container IDs preserved. Four live bilingual desktop/mobile native-bootstrap workspace
flows and two native-auth flows/private-origin-anonymous guards pass. Actual owner
English desktop Chrome separately checks both account frames, three real sections and
one actual section's Overview/Timetable. Tab released at My classes list; no session
copying or mutation. This is not institutional student/device lifecycle acceptance.

All seven checked academic tables remain zero; actual mappings, assignments, rosters
and approved plans/syllabi are still absent, not invented. CourseMax unchanged and
healthy. Protected release: `classes-layout-bf4f2908-20261015`. Rollback app only to
f9; never restore old live DB/files or undo evidence/grants. No old-folder cleanup or
image pruning. Final preflight 11.15GiB disk / 4.10GiB available RAM; recheck.

## Previous: actual registrar class workspace — 2026-10-15

Live source/image **f9bc5b2a**, frontend-only on exact compatible **4d9b24e0** parent.
See [real-teacher-workspace.md](real-teacher-workspace.md). Open each actual registrar
section into Overview/Timetable/Teaching plan/Roster/Syllabus;original meetings
preserved. Exact unambiguous authorized links hand off to canonical workspaces;
missing setup/content stays explicit. The simulator source/entry is deleted,not
relabeled. No new native hooks,API/schema,permissions,student import or generation.

5,295 baked web entries verified;995 measured backend/config/migration files unchanged.
38web/13boundary-tool tests,full bundle/post-bundle tsc,separate route-typegen/tsc,
6compiled EN/TH1440/1920/390 journeys pass,including ambiguous-link refusal and
canonical roster/released-course handoffs. No academic writes/page errors/overflow.
One detector[];inline finish/documenter verdict ship(not independent);DESIGN unchanged.
4live bootstrap workspace/2native-auth flows pass with private/origin/anonymous guards.
Actual owner Chrome separately opens all3real1/2569 sections,Overview/Timetable each,
and all5tasks for000204/P7;no fabricated proof/session copying. Tab released.

Fresh protected backups/isolated socket-only DB restore and saved exact4d parent
checksum/config digest passed. Only app recreated/gateway reloaded;schema,identity/
provider/profile keys,grants,runtime/env and other service IDs unchanged. Source menu
exactf9bc5b2a. App-only rollback retains new data/evidence,never restores old DB/files.
All7checked academic tables remain0;real class mapping/assignment/roster and actual
approved teaching plans/syllabi remain absent,not invented. No CourseMax changes.
Owner-authorized bounded cleanup archived/verified49,970entries before removing8old
rebuildable tmpfs UI copies(1.30876GiB);no app data/source/images/existing backups
removed. Headroom recovered;failed attempts retained. Final12.32GiB disk/4.33GiB RAM;
recheck before further heavy work. Protected release:real-teacher-f9bc5b2a-20261015.

## Previous recovery: remove live teaching demonstration — 2026-10-15

Owner rejected dummy roster/data. Live app recovered to the previously validated
exact **4d9b24e0** image;healthy,source menu/release pointer restored accordingly.
The fictional teaching workspace is no longer served;actual own registrar timetable
remains. Fresh protected backups and isolated DB identity restore/checksums passed;
only app replaced/gateway reloaded,identity/grants/runtime/other services preserved.
Seven checked academic tables had zero rows;no academic data purge or DB restore
performed on live. Actual signed-in owner Chrome confirms own1/2569three sections
and absence of fictional entry. Four simulation source files/retired test removed
from pending source;protected release/Git provenance retained.

At that recovery checkpoint,the real5-task UI was not yet deployed:38web tests/
boundary passed,but production build had timed out without accepted archives. Actual class mapping/assignment and roster
import are unconfigured;official teaching plan/syllabus sources still required.
Do not relabel fictional data or infer real content from timetable facts. See
[real-teacher-workspace.md](real-teacher-workspace.md). Private recovery evidence:
remove-dummy-teaching-20261015. No new cleanup/prune,privilege or student-data import.

## Retired: fictional teacher planning preview — 2026-10-15

Previously served source/image **c52f2e7b**, frontend-only on exact **4d9b24e0** parent.
See [teacher-planning-preview.md](teacher-planning-preview.md). Teacher discovery
entry in My classes; weekly timetable, dated plan, roster and shared syllabus use
fictional component-memory data only, discarded on exit/reload. No new native hook,
backend/schema writer, real academic generation, student setup or parity acceptance.
5,292 baked web entries verified;995 backend/config/migration files unchanged.
41 web/13 boundary tests,corrected full bundle/types,six compiled EN/TH1440/930/390
teacher flows,four live native-bootstrap workspace/two auth flows pass. Actual owner
teacher Chrome separately verifies all five views,review/acceptance,section-isolated
sample roster and reload reset. No fabricated institutional identity or session copy.
Protected backups/isolated restore/saved compatible4d9b24e0 parent retained. App only
replaced,gateway reloaded;schema,identity ownership/grants,runtime/environment and
other container IDs unchanged. Source menu exactc52f2e7b;owner-fork push only.
Brief2.91GiB post-workspace memory pause respected;remaining tests resumed above
floor and pass. Final checkpoint12.95GiB disk/3.19GiB RAM;recheck before heavy work.
Retained historical protected release:teacher-preview-c52f2e7b-20261015. This is not the current live release.

## Previous: registrar timetable color — 2026-10-15

Live source/image **4d9b24e0**, frontend-only overlay on teacher-workspace parent
**7fe104c9**. See [registrar-timetable-color.md](registrar-timetable-color.md).
5,286 baked web entries verified;995 measured backend/config/migration files unchanged.
33 web/13 boundary tests,full bundle/types,four compiled bilingual teacher flows,
four live workspace/two native-auth flows and actual owner teacher Chrome pass.
Labelled weekday categories,AA contrast,forced colors and color-vision simulations
checked. Protected backups/isolated DB restore/saved parent retained;schema/identity/
grants/runtime/other containers unchanged. App only replaced,gateway reloaded;
no migration/import/assignment/roster/student-account/message/security changes.

## Previous: teacher school workspace — 2026-10-15

Live `learn.route66.click`: source/image **7fe104c9**, frontend-only overlay on
attendance-capable **fe1877c9**. See [teacher-school-workspace.md](teacher-school-workspace.md).
5,283 baked web entries verified;995 measured backend/config/migration files unchanged.
Full build/types,30 web/13 boundary tests,four compiled bilingual teacher flows,
four live workspace/two native-auth flows and the owner's read-only teacher Chrome
term/search/reload tasks pass. Protected backups/isolated DB restore and saved parent
retained;schema/identity/grants/runtime/other containers unchanged. App only replaced,
gateway reloaded;no migration/import/assignment/roster/student-account/message change.
Native enrollment bridge and full institutional/private-file parity remain open.

## Historical extraction release — 2026-10-14

Extraction source/image **fe1877c9**. Source extraction details:
[extraction.md](extraction.md); agent contract: [development.md](development.md).
This is namespace isolation, not a new enrollment bridge or full CourseMax parity.

## Observed release

- 157 isolated PostgreSQL/auth/attendance/discovery tests, 73 proof/profile tests,
  26 frontend tests and 13 boundary-tool tests passed. Candidate image native app
  import/OpenAPI plus 35 facade/policy tests passed from baked files.
- Full production web bundle/types and eight compiled EN/TH teacher/student tasks
  passed at 1440/390 with persistent receipts, expiry recovery and no-class/restore.
- Eight live EN/TH attendance entry/private denial/class-return flows and two native
  auth flows passed without academic writes, errors or horizontal overflow. No
  real Google/LINE provider exchange or physical LIFF/device parity claimed.
- 989 tracked API Python files and 5,276 desired web entries verified against baked
  bytes/links/modes. Both implementations and compatibility discovery shims included.
- Protected DB/content/runtime backups and saved/checksummed attendance-capable
  a9a1c84b parent retained. DB restored on isolated socket and identity snapshots
  matched; content/runtime archive integrity passed. Not coordinated off-host DR.
- Only staging app replaced; gateway reloaded. All other container IDs unchanged;
  CourseMax healthy/untouched. Identity/profile/account-grant snapshots, runtime
  file bytes, feature flags and security policy preserved. Preflight environment
  comparison accounts for Compose's escaped `$$` versus actual regex `$` anchor;
  the deployed anchored origin policy itself is unchanged.
- Schema-only PostgreSQL dumps are byte-identical before/after (excluding pg_dump's
  random restrict markers). No migration, stamping, table rename, backfill, real
  class/roster import, grant, proactive message or shared-host mutation.
- Final observed resources:17.74 GiB free disk /5.71 GiB available RAM. Recheck
  before subsequent heavy operations; no cleanup beyond the separately approved
  exact scratch-directory batch.
- Scoped inline architecture/unchanged-UI task review, not an independent review.
  Existing institutional/privacy/device/parity gates remain unresolved.

The compatible parent supports the same attendance schema/receipts. Code rollback
retains the DB, files, identity grants and all new evidence; never restore an old DB.
Do not use an older pre-attendance image for evidence-bearing rollback.

## Requested upstream pull rehearsal

Migration source committed/pushed to `coursemax/staging`, then upstream fetched.
Remote default branch is **dev**, at **45cf5d4f78cf537064070dc8e315a64990d14966**;
remote main is **253cfb1cfc3eda1db7ca3b2d5617877420064fe4**.

An actual `git pull --no-rebase --no-tags upstream dev` ran in a detached isolated
worktree at fe1877c9. Result: **Already up to date; zero conflicts; zero incoming
commits**. Isolated boundary gate passed; primary/deployed source unchanged.

Important: upstream dev is still the same pin used for this fork. No newer upstream
change was exercised. This is NOT proof that future upgrades merge cleanly or remain
compatible. 43 historical original-file patches remain; only the router integration
changed further, while the other 42 were retained byte-identically. Rehearse a new
pinned upstream delta and all adapter/security/lifecycle/migration/task contracts
when one becomes available. Never run the automatic CLI updater on the live fork.
