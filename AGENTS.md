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
Unattended refresh and dated-calendar semantics remain unfinished; weekly timetable
facts alone do not create dated sessions. Historical migration stays last.

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

## Current upstream source — 2026-10-29

Upstream 1.4.3 (`2d753372`) is integrated with our customizations; this is not a
live upgrade. See `docs/extensions/upstream-1.4.3.md` for conflict resolutions,
updated dependency tests and remaining deployment work. Live remains `88fea34b`.
The historical boundary snapshot stays pinned; exact upstream-byte acceptance
cannot overwrite retained custom hooks. Use the composed migration entrypoint,
not an assumed native-only `upgrade head`. Recorded private runtime/release files
are missing: recover them before any recreation; do not generate new secrets.

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
