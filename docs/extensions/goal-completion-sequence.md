# Institutional workflow completion sequence

This is a **read-only source-contract audit and ordered plan**, not runtime, deployment,
parity, migration, or user-task acceptance. Source matches only mean “source contract
observed; runtime evidence required.” Synthetic fixtures stay test-only. Native account,
session, organization, course/content/progress, access, enrollment, and retention remain
authoritative; no parallel catalog, session, or enrollment system is authorized.

## Current source facts and gaps

The owned connection code is present: a reviewed official section can be connected to a
selected native course, with teaching/access effects routed through the native bridge.
The `/classes` workspace reads school identity and a teacher’s own registrar timetable,
and hands content reading to the native course route. Persisted attendance source and
check-in/no-class routes also exist. These are source observations, not completed audit
capabilities or live acceptance.

**Immediate priority — automatic NRRU acquisition, not pasted links.**
Users select a term/class; the server discovers and retrieves the school data. Port
CourseMax's scheduled roster reconciliation and calendar semantics, preserving native
authorization, verified student matching, manual members and history. CourseMax's
existing configured keys were seeded historically, not generically discovered.
NRRU also provides a course/term RTF roster export: absence of class IDs on the grid
is not justification for a manual-link task. Source parsing, exact section validation
and the existing class-key model/API contract still need implementation and tests.
Replace the flow end to end before continuing identity/syllabus/dated-plan work;
do not hide required inputs while leaving the server dependent on them. No portal
credentials, fabricated identifiers, runtime CourseMax dependency or historical migration.

The retired preview compatibility component and route redirect to `/classes` and ignore
legacy role/view/query state. Production code must neither statically nor dynamically
import or re-export its test fixtures. Retirement and the two explicitly approved
native menu-entry removals are deployed at `3019c79e`; see
[deployment evidence](demo-retirement.md). This rehearsal is not permission to
make further native edits or bypass the boundary.

Actual syllabus editing and persisted dated teaching plans are missing; the current
syllabus surface is a native reader handoff. Absence submission/review/overrides,
historical attendance reporting/CSV, and identity correction/admin-review handlers are
also missing. Students need a task hub, while native content and progress remain the
single authority. Parent review found all seven academic tables empty, and no historical
migration is authorized. Retirement does not establish academic feature parity.

## Next delivery queue — current execution override (2026-10-16)

The canonical LH phase groups remain audit/acceptance reference groups. They do not
require reimplementing accepted foundation or delay a usable basic syllabus/teaching
plan until every team tool or assessment migration is complete.

1. Production-demo and approved menu retirement are deployed. Next repair automatic
   NRRU class/roster/schedule acquisition so no teacher or administrator pastes a
   roster URL or transcribes school IDs. Validate exact source matches, scheduled
   refresh, preserved history and calendar-derived sessions end to end.
2. Run the connected-class integration exercise with isolated synthetic native
   sessions, explicit native authoring rights (READ alone is not edit), the real
   SchoolIdentity → Myclasses student path, and persisted identity-case resolution.
3. Let a teacher edit, save, reload, and publish a course-owned syllabus, reusing
   native content/authoring where equivalent; students see published content only.
4. Deliver a class-owned dated teaching plan/calendar with weeks, holidays, no-class
   days, and makeups without inventing timetable-derived dates; reuse actual
   attendance-session authority and test teacher/student.
5. Complete the attendance remainder.
6. Complete coursework/governance, student hub/classroom tools, and remaining 52-ID
   parity.
7. Close accepted parity, protected DR, and separately approved historical migration/
   cutover last.

No production mock, duplicate catalog/session/enrollment, or fake completion is allowed.
Retirement is live. Automatic NRRU acquisition remains an implementation gap;
source observations alone do not close it.

## Reviewed ordered phase manifest

Each phase has an explicit authority, audit IDs, dependencies, and concrete exit. The
machine-checked full 52-ID capability labels are in `scripts/extensions/rehearse_goal.py`;
this grouping follows `../PLAN.md` and `../feature-audit.md`.

1. **LH-00 — preservation** (no audit IDs; no dependency). Shared/native preservation.
   Exit: owner launch decisions, recoverable references, and approved preservation before
   any deletion.
2. **LH-01 — private usable base** (depends LH-00; A07, A08, C10, O04). Native base with
   extension adapters. Exit: private-file authorization, coordinated restore, compatible
   rollback, and mobile synthetic task evidence.
3. **LH-02 — identity and recovery** (depends LH-01; A01–A04). Native account/session with
   extension provider proofs. Exit: native lifecycle/routes, provider acceptance, and the
   revocation/recovery matrix.
4. **LH-03 — institutional class foundation** (depends LH-02; A05, A06, B01–B03). Native
   course/access plus extension class evidence. Exit: authorized synthetic class,
   official/manual roster reconciliation, and term/document review. Existing connection
   code must be validated here, not reimplemented as another authority.
5. **LH-04 — attendance and LINE classroom access** (depends LH-03; B05–B09). Extension
   attendance evidence under native roster/session authority. Exit: absence and override
   handlers, historical reports/CSV, and LINE/device/handoff/geofence acceptance.
6. **LH-05 — teams and classroom tools** (depends LH-03; E01–E06). Extension tools under
   native class authorization. Exit: cross-class denial, privacy thresholds, reconnect,
   and a distributed fan-out decision.
7. **LH-06 — coursework and governance** (depends LH-04 and LH-05; C07, C08, D01–D12,
   E08, O01, O03). Native content/access plus governed extension evidence. Exit:
   immutable submissions, governed grading/release/dispute, workers, exports,
   concurrency, and recovery.
8. **LH-07 — authoring and teaching UX** (depends LH-06; B04, C01–C06, C09, E07, O02,
   O05). Reuse native authoring/player only where equivalent. Exit: actual persisted
   syllabus and teaching plan, publication/recovery, and EN/TH mobile teacher/student
   walkthroughs.
9. **LH-08 — ledger closure** (depends LH-07). For **all 52 audit IDs**, record target
   owner, implementation/decision, tests, evidence treatment, and owner acceptance as
   accepted, approved deferred, or approved retired. Unfinished work remains pending or
   blocked. Exit also requires restore/provider/upgrade evidence and owner parity
   acceptance.
10. **LH-09 — migration and cutover last** (depends LH-08). Only after explicit approval,
    implement and rehearse real historical import, identity crosswalk, checksums,
    reconciliation, final delta, rollback, source retention, and then approved cutover.

## Rehearsal gates

Run owned web tests, extension script unit tests, the boundary checker, and existing pure
learning-access policy tests. The checker audits required source files, actual redirects,
fixture-import absence, school identity/timetable calls, bridge registration, attendance
routes/files, manifest completeness/order, and conditional legacy menu blockers. It does
not import the app or contact a network/database. Full web build, browser tasks, provider
checks, seven-table population, deployment, migration, and cutover evidence remain
outside this audit and must not be inferred from a green result.
