# LearnHouse fork: extension-first instructions

Start with the current task, this guide and relevant parts of
`docs/extensions/development.md`. In the private handoff workspace, use the newest
`../STATUS.md` and `../PLAN.md` when current implementation state matters. Read
framework, identity, boundary and historical evidence only as needed for the change;
do not turn every small edit into a full handoff/release audit.

## Current owner directive: development speed, KISS and DRY

This is the development phase, not production acceptance. This instruction supersedes
older process-heavy wording below and in historical handoffs:

- Implement the smallest usable change. Reuse existing code; avoid speculative
  abstractions, extra services, flags, approval flows and duplicated authorities.
- Do not add unsolicited security hardening, compliance requirements, legal claims,
  threat-model exercises or new prohibitions. Keep existing working authentication
  and permissions as-is unless the task actually concerns them.
- Routine development, fixes, tests and owner-fork commits/pushes need no repeated
  approval. Ask only for an actual unresolved product choice or a concrete operation
  outside the agreed scope—not routine engineering work.
- Use focused tests and short feedback loops. Documentation does not require an app
  build; a small change does not automatically require every suite, four browser
  sizes, a backup/restore rehearsal or deployment. Match checks to affected behavior.
- Isolated synthetic fixtures, test fakes and local prototypes are normal development
  tools. Do not mistake them for real institutional acceptance or copy real sessions.
- Architecture documents describe current implementation, not a mandate to add more
  controls. Broader security/production-readiness work is a separate requested task.
- Preserve existing data, secrets and shared services. Actual database changes or
  shared-host deployment still need the relevant practical recovery checks; those
  checks are not prerequisites for unrelated coding or documentation.

Keep the existing extension boundary as the simple default; do not start an unrelated
core refactor or policy expansion. No runtime security or infrastructure change is
requested by this development-process directive.

## Custom frontend standard — Interior (owner instruction, 2026-10-17)

Use https://www.interior.dev/docs across all our custom LearnHouse frontend modules,
existing and new. Share reviewed source/adapted headless interactions under
`apps/web/extensions/route66/components/interior/`; consume them through existing
extension adapters where appropriate. Do not implement another bespoke button,
copy/loading control or choice rail in each feature, or call cosmetic CSS alone a
complete component migration. Review the relevant upstream implementation first.

Interior is copy-source, not a package/framework replacement. Pin the reviewed
commit and retain its MIT notice/provenance in `docs/extensions/interior-ui.md`.
Reuse native LearnHouse/Radix behavior when already adequate (auth, shell, forms,
dialogs, tabs, dates and disclosures); record the reason for adaptations. Preserve
EN/TH, keyboard/focus/pointer cancellation, stable loading layouts, reduced motion,
forced colors and private projector content. Keep academic/network state in its
existing owner; a UI animation must never infer successful persistence. No global
native-shell restyle or auth/backend rewrite is implied.

## Earlier demo-retirement directive (completed; historical context)

Remove production demos and dry-run the full-goal plan through sequential, bounded
GPT-5.6 jobs. Retain synthetic test fixtures only; do not ship fake institution data,
fabricate milestones, or treat a source-contract audit as runtime/user-task acceptance.
This earlier directive does not require workers, full-goal audits or production-style
release gates for every subsequent development task.

## Current owner requirement: automatic school-data acquisition (2026-10-16)

Do not ask teachers or administrators to paste roster URLs or transcribe internal
school IDs. LearnHouse must acquire NRRU rosters and schedules internally, following
CourseMax's synchronization and calendar semantics. Users select a term/class and
review actual course equivalence, permissions or ambiguous source matches—not
engineering lookup gaps. Preserve exact verified student matching, manual members,
history, two accepted missing snapshots, and reviewed calendar/rotation/exceptions.
School data never grants native roles, authorship or enrollment. No portal credentials,
fabricated keys, per-course hardcoded shortcuts or runtime dependency on CourseMax.

The URL-free connection flow is deployed at d96f2c6c. CourseMax's historical setup
seeded class keys; new LearnHouse classes instead support an absent class ID and the
official course/term RTF export with exact section validation. Source failure/stale
review cannot partially connect/import. Do not reintroduce pasted links, fabricated
IDs or all-group imports. Owned migration discovery composes native wrappers with
new owned versions; unversioned bootstrap deployment uses the checked named runner,
never ad-hoc DDL or an inferred native-version stamp. See
`docs/extensions/nrru-automatic-acquisition.md` and newest deployment record.
Unattended refresh is deployed as recorded below. Wider calendar parity remains
separate; weekly timetable facts alone do not create dated sessions. Historical
migration stays last.

## End-to-end delivery (owner instruction, 2026-10-15)

Make the requested workflow work, not merely its backend. Complete ordinary wiring,
recovery, task UI, tests, builds, owner-fork commits/pushes and bounded app deployment
without repeatedly asking permission. Do not invent default-off activation barriers
or declare success with unusable/inactive code. Prefill verified source facts and
put necessary course/roster decisions in the product, not in a chat approval loop.
Optional academic-service failure must not prevent sign-in; isolate and recover it
without retaining provably stale bridge grants or deleting manual access/evidence.

Use the lightweight development directive above. Keep existing account/data ownership
and shared services intact; real historical migration and cutover remain separate
work. Prefer owned adapters/routes over native-core changes. Newest ../STATUS.md and
current release pointer are authoritative over historical deployment headings.

## Current runtime — student identity reviews, 2026-11-04

Live `53d3d248` / `b73530fb`, release `identity-53d3d248-20261104`. Student requests,
teacher receipts and existing-superadministrator decisions use the academic journal,
exact-match writer and native READ repair; no new table/role/account writer. Do not
treat unchanged closure as resolved ownership or allow merges/transfers. Private
reviewer evidence stays out of student/teacher DTOs and raw class history.

Full bundle/types, 56 baked checks, 40 component flows, two packaged EN/TH workflows
(six native-auth actor journeys),actual retained `d85f488b` compatibility and four
live entry checks pass. Normal admission passed; schema/runtime settings/peer IDs
are unchanged. Protected snapshots and saved current/parent images retained; code-
only rollback never restores old data. Fixtures must copy the actual owned launcher,
not fall back to native `app.py`. See `docs/extensions/identity-reviews.md` and newest
STATUS. Genuine provider/student and remaining staff identity parity remain open.
Existing roster worker remains active; two real source_failed results were observed.
Owner confirmed the roster file and moved on, not a successful acquisition claim.

## Previous runtime — unattended roster refresh, 2026-11-03

Live source `d58e4899`, image `d85f488b`, healthy; release `roster-d58e4899-20261103`.
Six-hour worker and EN/TH saved-roster controls are active. GitHub run `41685386822`
built/typechecked frontend `fa815717`, identical to this source's frontend tree.
The original verified image disappeared locally; identical payload was repackaged
under unchanged build gates and verified again, then saved/checksummed. Its existing
147 baked/eight persisted native-auth checks remain scoped evidence; four live entry
checks, API hashes, BUILD_ID, schema and worker leadership verify after deployment.

Named migration `e6bc47a4da35` preserved all rows in 82 existing tables/48 events,
without stamping. Only app replaced/gateway reloaded; runtime settings and peer IDs
preserved. Full isolated restore and actual retained `3f19ea47` auth/history reads
pass. Keep protected snapshots and code-only rollback; never restore older data.
Owner allowed a one-time restart-gate exception (admission3.00GiB, minimum2.90GiB);
global resource defaults are unchanged. See `docs/extensions/unattended-roster-refresh.md`
and newest root STATUS. Initial review, manual membership, native access repair and
append-only history remain; first actual scheduled result was pending at verification.

## Previous runtime — three review repairs, 2026-11-03

Upstream 1.4.3 is deployed with backend repair source `85a18e87`, image `3f19ea47`.
See `docs/extensions/review-fixes-2026-11-03.md` for the rehearsed/revised plan,
93 baked checks, native unit regressions and verified app-only release. Stale roster
previews now conflict; reorder is atomic; deletion retention runs in the native
writer's transaction, not an HTTP middleware's second session. Preserve the exact
reviewed hooks in both native course-service files and the owned launcher/CORS/CSRF.

The historical boundary snapshot stays pinned; exact upstream-byte acceptance
cannot overwrite retained custom hooks. Use the composed migration entrypoint,
not an assumed native-only `upgrade head`. Private release configuration is recovered;
use the current release pointer, never guess configuration or generate new secrets.
The parent `4cbc54da` and verified archive are retained for code-only rollback;
never restore older academic data. Schema/frontend/dependencies/auth settings are
unchanged by this repair. See `docs/extensions/upstream-1.4.3-deployment.md` for the
preceding upgrade and its separate migration/older rollback constraints.

## Historical extraction baseline

Extraction source/image `fe1877c9`; read the newest `docs/extensions/deployment.md`
entry and private `../STATUS.md` for the actual live release and scope.
Owned feature code is extracted; 43 historical original-file patches remain, with
only the router registration changed further. No schema/data migration. Current
upstream default `dev` is still our original `45cf5d4f` baseline: isolated pull
reported zero incoming commits/conflicts, NOT future upgrade compatibility.

## Existing architecture and compatibility boundary

- Put our backend logic/tests in `apps/api/src/route66_ext/`, frontend logic/copy/
  tests in `apps/web/extensions/route66/`. Feature code has been extracted there;
  old feature paths are compatibility delegates, not places to add logic. Read
  `docs/extensions/extraction.md` and the exact extraction map before refactoring.
- Prefer existing adapters and minimal explicit hooks over scattered native edits.
  An actually new native hook is an exceptional integration decision under the
  existing exact boundary policy, not a reason for repeated approval or a design
  dossier for routine extension work.
- Do not auto-refresh the boundary snapshot, widen allowlists, modify checker policy
  to hide failures, monkeypatch native internals, shadow duplicate routes or silently
  restore unsafe native auth. Current auth/lifecycle/retention patches remain frozen
  until a tested replacement exists.
- Use `python3 -B scripts/extensions/check_boundary.py` for lightweight source
  placement checks. Run the `scripts/extensions` unittest suite when its contract
  is affected. Neither is a replacement for focused feature checks or runtime proof.
- One LearnHouse account/session/content/access authority. Our NRRU bridge/class
  metadata/academic evidence is an extension, not a parallel catalog/login or runtime
  dependency on old CourseMax. My classes is not an upstream-official feature.
- Preserve identity ownership, native org policy, private access, transactions and
  immutable evidence. Keep deployed URLs/table names/revision IDs stable during moves.
- Synthetic tests only; real data migration/provider credentials/retirement require
  specific approval. LINE login/LIFF does not imply Messaging webhook parity. No
  proactive sends by default; no real-session copying or fabricated student emails.
- No automatic upstream updater on the live fork. Pin and rehearse updates separately
  with adapter/auth/MFA/refresh/revocation/enrollment/lifecycle/migration/UI tests.
- Respect AGPL/Enterprise attribution/source obligations. Don't publish private
  institutional records, secrets or evidence with this public source fork.
- Communicate in English; retain natural Thai/English product copy and mobile tasks.

Report changes and relevant checks briefly; mention actual native-boundary or runtime
changes when present, not an exhaustive release checklist for every edit.
Existing untracked `.github/workflows/native-google-web.yaml`
and `.impeccable/` are unrelated: leave untouched/uncommitted.

Recovery/capacity gates below apply to actual deployment or heavy host work, not
ordinary edits, documentation or lightweight tests. On the
shared staging host retain >=10 GiB disk (>=12 GiB pre-pull) and >=3 GiB available
RAM; recheck before heavy operations. No broad cleanup or unrelated restarts.
