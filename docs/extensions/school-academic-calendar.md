# Shared school academic calendar

Status: deployed to LearnHouse staging, 2026-10-17; not institutional acceptance.
Live source `91a2c629c797dd352ba554f2c2a06a9e2a5afcbe`, image
`coursemax-learnhouse:calendar-upload-repair-20261017`. Assignment work remains excluded.
Claude Code's Opus 5.5 completed backend work in the separate `school-calendar`
Herdr session; Impeccable-guided upload/review corrections and desktop/mobile task
confirmation are complete.

Use **My classes → School calendars** to upload/review/publish an official PDF
(existing platform-superadmin permission). **Read PDF and review dates** reads it
automatically; opening an existing empty draft also reads its retained source, with
no re-upload. Then open your own NRRU class's **Schedule**, select its published
calendar and teaching mode, preview and apply. A native course match is not required.
No calendar facts are seeded; the official PDF and human review remain necessary.

## Automatic reading correction — 2026-10-17

The first release exposed an empty calendar builder while staging had organization
AI disabled and no native provider key. Readable NRRU teaching-calendar announcements
now use a deterministic text reader before any AI fallback. It recognizes the school
and primary semester/year, explicit odd/even week-table labels, teaching boundaries,
closures and make-ups. It never infers rotation from week parity, imports a next-term
opening reference as another complete semester, or treats an exam label as no-class.
A closed teaching week still carries its explicit closure/makeup sessions, without
ordinary scheduled teaching. Original PDF bytes/page evidence remain untouched.

Conflicting announcement/appendix dates become a concise review question; detailed
comparisons remain available. Uncertain fields have direct inspector actions.
Publication stays disabled until questions/uncertainty are resolved and edits saved.
The default is upload → automatic reading → focused review, not manual construction.
Manual regeneration/full week lists are disclosed only when needed. Reading failure
keeps the PDF/draft and retries reading; a newer saved version is loaded rather than
overwritten. Empty AI output fails/refunds instead of saving an empty success.

The local reader makes no AI call or credit reservation. Unknown layouts still use
native AI feature/usage/rate/model/MFA rules and need a configured provider; no AI
flags, secrets, permission gates or security headers were changed. Scanned-PDF OCR
is not included. The retained real-source text yielded 15 weeks and 11 closure/makeup
pairs, with source conflict and midterm questions; this is parser proof, not a human
institutional publication, provider trial or broad PDF-format acceptance.

Correction proof: 69 frontend checks, full isolated bundle/types, 195 PostgreSQL
harness checks and 20 final pure reader/planner checks (overlapping counts). Nine
compiled EN1440/TH390 tasks cover automatic upload, retained-draft failure/retry,
review/publication/class apply, student read-only attendance links, and source-based
review without publication. Two live fresh-native-login read-only calendar smokes
pass. Code-only app replacement: fresh protected DB backup, retained exact parent,
1,022 API and 5,311 desired web entries verified, in-flight assets kept; no migration.
Schema/source/draft, identity, roster, progress, environment/mounts and unrelated
service IDs remain unchanged. Only source-menu URL and native role startup timestamps
change. Evidence: `calendar-upload-repair-20261017/` and its matching release directory.

## Product outcome

Upload the school's academic-calendar PDF once, review it, and publish a reusable
school/year calendar. Each authorized class selects a term/calendar, combines it
with its official meeting times, and reviews a dated schedule. Table, month calendar,
class-session detail and attendance consume the same sessions. Assignment links,
deadlines, submissions and grading integration are outside this delivery.
A school class must not need a native course match just to construct its schedule.

## Research findings

### Keep from CourseMax

- Separate term/teaching weeks, recurring offering facts, holiday exceptions and
  dated sessions. Calendar rotation is explicit, not week-number parity: its seeded
  week 8 is midterm and week 9 resumes as **even**.
- Upload → extract → human review/edit → save, with a nullable make-up date rather
  than a guessed replacement. Apply a closure only to meetings it actually affects.
- Preserve the original academic-week identity when a meeting is moved. A Thursday
  closure may be made up on a Wednesday much later without becoming that later week.
- Show the reason for a missing meeting, the make-up relationship and any remaining gap.

Do not copy seeded course/term keys or historical migrations as a runtime planner.
CourseMax's PDF parser only extracts closures/makeups; full term boundaries and
teaching weeks were seeded separately. Selecting its holiday schedule does not
regenerate existing sessions. Its current upload does not retain the original PDF.
Its exception lookup matches make-up sessions by course/date rather than exact
section/session; that shortcut must not be ported.

### Existing LearnHouse capabilities and constraints

- Native assignment behavior was researched but is not part of this feature.
  Calendar operations must not mutate assignments, deadlines, submissions or grades.
- Native AI already provides provider-neutral `generate(output_type=...)`, model
  selection and existing organization feature/usage rules. `pypdf` and numbered-page
  text extraction are installed. Reuse these through a typed adapter instead of
  importing CourseMax's provider/secret infrastructure. Empty/truncated text must be
  surfaced; scans need a supported PDF-vision/OCR path or manual completion.
- Generic organization uploads are public through native content-file routing. Do
  not assume that an ordinary org upload path protects source evidence. Choose a
  bounded private PDF store/read adapter, or evaluate database storage for these
  small, infrequent annual documents; retain original bytes and checksum either way.
- Existing `AcademicClass.course_id` is mandatory; org and staff authorization derive
  through that course. Unmatched official classes currently have no persisted class
  record. Persisted schedules/attendance before native matching need an explicit fix.
- Existing `AttendanceSession` timestamps/title/class/policy are **always immutable**
  through PostgreSQL guards. Re-generation cannot simply update their times, even
  before scans. Existing immutable receipts/challenges/events and no-class audit remain.

## Proposed backend shape

1. **Calendar library:** organization-scoped school key, academic year and calendar
   group/track (regular/weekend/etc.). A year can contain several terms; do not
   silently apply a regular-program calendar to every institutional class.
2. **Source documents:** private original PDF bytes, checksum and page evidence.
   Uploading another PDF for the same school/year/group creates another draft and
   preserves earlier sources; identical bytes reuse the stored source. Draft clones
   retain their source. Multiple-source announcement merging is not claimed.
3. **Calendar revisions:** editable draft → reviewed published revision. A typed
   revision payload can hold terms, explicit week ranges/rotation, exam periods and
   dated closures/makeup mappings without a table per PDF field. Unknown fields stay
   visibly unresolved; registration/payment dates are not automatically no-class days.
4. **Class selection:** pin a published revision and its term to the exact school
   course/section/year/semester. Snapshot the selected recurring meeting facts. Support
   multiple weekly slots. Publishing a new school revision never silently rewrites
   existing classes; show an affected-class diff and an explicit update action.
5. **Planner:** deterministic preview → reviewed apply. Produce real local dates and
   timezone-aware session instants, original academic-week/slot identity, closure
   reasons and replacement links. Explicit make-up dates may lie outside teaching
   weeks; flag out-of-term dates and overlaps for decisions rather than discarding or
   merging them. Exam windows alone do not establish an exact class exam appointment.
6. **Session authority:** use the existing attendance session identity for confirmed
   dated meetings, with additive calendar-origin/nominal-slot/replacement metadata.
   Preview is not another authoritative session table. An affected holiday meeting
   is excluded from attendance; the replacement meeting has its own normal attendance.
   Later changes preserve originals, mark explicitly replaced future sessions no-class
   through the audited path, and create replacements. Past/evidence-bearing sessions
   are protected from automatic regeneration. Repeat apply must not duplicate sessions.
### Agreed structural direction

Extend `AcademicClass` with explicit organization ownership and an optional native
course match. Preserve IDs when matching later, including roster/session history.
The first reviewed schedule save creates an unmatched school class; GET and preview
must not create records. Existing assigned-teacher authority remains valid; new
unmatched classes require the confirmed identity's exact official section evidence.
No second class, roster or attendance-session authority is introduced.

A missing native match never grants content access. Existing manually authorized
staff/classes must retain their current authority; do not force them through a new
school identity ceremony as a side effect of this feature.

### Explicitly excluded

No assignment links, class-specific assignment deadlines, independent attempts,
submission/grading changes, or migration of historical institutional data.

## Impeccable surface proposal — Operate mode

Extend the existing native Classes world; no rebrand or global shell changes.
Inspected current Classes source and compiled synthetic EN desktop/TH mobile index
and weekly-schedule captures. The captures' fixture footer is not live org config.
Root PRODUCT/DESIGN contain historical prototype wording; report it, do not repair
that unrelated drift in this feature.

### Placement and primary tasks

- **Classes → School calendars:** one shared library, not an account-profile field
  or a PDF embedded in each LearnHouse course. Show school/year/calendar group,
  available terms, source and published/draft state. Authorized publisher gets one
  primary action: **Upload academic calendar**. Reuse existing bounded native admin
  authority for shared publishing; a staff email domain is not publishing authority.
- **Upload/review:** term dates, a focused teaching-week editor, and holidays/makeups.
  Prioritize unresolved dates and show retained page text beside editing. The private
  original PDF opens in a new tab: native DENY/frame-ancestors headers remain intact,
  so an embedded viewer is not offered. Original PDF, not extracted text, is authoritative.
  Source pages and uncertainty can be corrected explicitly. Parsing failure preserves
  the PDF and draft for retry/manual completion; it never clears a published calendar.
- **Class → Schedule:** replace the weekly-only destination with **Table / Calendar**
  views plus a compact recurring-times summary. First use: choose the published
  calendar/term → inspect resulting meetings and exceptions → **Create schedule**.
  Native matching stays separate. Later: **Review calendar changes**, not an
  unexplained automatic rewrite.
- **Session detail:** actual date/time, original teaching week, room/mode, any
  "make-up for …" relationship and **Open attendance**.
  Keep check-in/attendance controls here rather than a disconnected calendar copy.

### Layout and behavior

Desktop table: date/time, academic week, meeting/room, status/reason and next action. Calendar: month controls and selected-day agenda; both select the same
session and retain the viewed period. Mobile defaults to compact chronological
records; calendar month cells stay short and the chosen day's agenda carries detail.
A month view is not an unreadable seven-column schedule table squeezed into a phone.

Blue marks actions/selection, neutral/struck-through text identifies cancelled
meetings, and make-up links explicitly name their original date. Do not rely on color
alone. Preserve natural Thai/English, keyboard controls, 44px actions and native type.
Switching view never writes a schedule. Saving a draft is distinct from publishing;
publishing a shared calendar is distinct from applying it to any class.

## Focused implementation proof

- PDF upload/source retention and parse failure → repair → review → publish → reload.
- Exact school/year/track/term selection and no native-match requirement.
- Multiple recurring slots, explicit odd/even sequence, exam ambiguity, holiday with
  and without make-up, cross-week/weekend make-up, collisions and out-of-range dates.
- Preview has no session/attendance/grant writes; repeated apply is idempotent;
  concurrent/stale apply fails without partial changes.
- Confirmed schedule reloads identically in table/calendar/attendance. No-class
  meetings reject check-in; the replacement accepts it under existing roster rules.
- Revised calendar preserves past/evidence-bearing sessions and original receipts;
  reviewed future replacements do not duplicate or erase history.
- No assignment mutation or link. No implicit native role, enrollment, progress or
  grading mutation. An unmatched class cannot obtain native learning grants.
- Register owned models/router/migration through existing bootstrap/composed graph;
  isolated existing/fresh schema tests before any shared-data operation.
- Desktop/mobile teacher and student tasks in Thai/English, bounded visual review.

## Implemented API and ownership

All routes are composed through `src.route66_ext.bootstrap`, under
`/api/v1/school-calendars`; native files are unchanged.

- `GET ''`: published library (plus drafts for platform superadmins), `can_edit`.
- Multipart `POST ''`: `name`, Buddhist `academic_year`, natural-language `track`,
  `file`; retain a valid PDF up to 10 MB before any optional AI call.
- `GET /revisions/{id}` and private `GET /revisions/{id}/source`.
- `PUT /revisions/{id}`: `{expected_version,payload}`; editable drafts only.
- `POST /revisions/{id}/parse`: `{expected_version}`; existing admin/org/MFA gates.
  Recognized NRRU text uses the local reader without AI; unknown layouts retain native
  AI feature/plan/credit/rate/model gates. Failure leaves source/draft intact.
- `POST /revisions/{id}/publish`: `{expected_version,reviewed:true}`; unresolved or
  uncertain facts prevent publication. Published JSON and source bytes are immutable.
- `POST /{calendar_id}/draft`: `{from_revision_id}`; source-retaining draft clone.
- `GET /schedules`: exact `registry_course_id,academic_year,semester,section` query.
- `GET /schedules/by-class/{class_id}`: organization-bound teacher or active member.
- `POST /schedules/preview`: `{section,revision_id,pattern,expected_version?}`.
- `POST /schedules/apply`: same plus `{expected_version,fingerprint,reviewed:true}`.

Shared writes use the existing platform-superadmin check. An unmatched class's
first reviewed apply requires the teacher's confirmed identity and exact own official
section. It creates the existing `AcademicClass` aggregate, not another class system.
Matching later retains its class/roster/session IDs; unmatched classes cannot acquire
native learning grants. Students can read their own schedule both before and after
native matching, without gaining native content access.

Payload: `timezone:'Asia/Bangkok'`, up to three terms, explicit numbered week ranges,
rotation and `teaching` boolean, dated closures with nullable make-ups, optional page/
uncertainty and `unresolved` questions. Unknown keys are rejected. Teaching ranges
longer than seven days must be split. Exam labels alone never suppress meetings.
Patterns: `onsite`, `online`, `even_onsite`; no inferred parity. Recognized official
`W:(start-end)` restrictions apply to original academic weeks, including make-ups;
unsupported syntax is not silently treated as unrestricted.

Revision DTO also returns source-page count/text, truncation and validation issues.
Preview includes errors, warnings, action labels and added/replaced/cancelled/
unchanged/skipped-past counts. Protected rows show their actual unchanged result.
Superseded saved sessions remain visible in retained history. Attendance links use
`/attendance?class=X&session=Y`; the class-list request forwards the selected ID so
an authorized older session is still reachable outside its recent-200 list.

## Validation and deployment boundary

Implementation uses four new owned tables (19 total), organization ownership and an
optional course on `AcademicClass`, and additive attendance provenance. Named migration
`b3e9c4d1a702` extends `f47eb52fa044`. The checked runner is
`deploy/staging/apply_school_calendar_migration.py`; it refuses versioned databases
and never guesses or stamps an Alembic head. Run it from a verified candidate **before**
starting the new app, after the relevant backup/restore checks. Startup table creation
alone cannot add the necessary class/session columns.

Initial-release proof: 113 affected PostgreSQL/native/boundary tests passed after correcting
two legacy-fixture assertions from an earlier 235-test run; frozen historical SQL and
migrations were not rewritten. Eight calendar PostgreSQL tests include mocked typed-AI
success/failure and preserved source/draft state; 13 final pure planner cases include
strict official week ranges. No real provider/model call or institutional PDF acceptance
is claimed. Two final focused PG tests verify warnings for overlapping manual meetings
without modifying them and preserve unmatched apply. Counts overlap; do not add them.
Initial frontend proof: 67 checks passed; full isolated Next bundle/TypeScript passed at
`school-calendar-web-release-20261016`. Five compiled teacher/student EN1440/TH390
journeys cover PDF/manual repair/publication, unmatched apply, identical table/calendar/
attendance IDs, matched/unmatched student reading, and publish-return refresh without
reload. No page errors, horizontal overflow, assignment writes or student academic
writes were observed in these fixtures. Boundary, diff and 25 tooling checks pass.
Deployment then passed fresh protected backup/restore, the named migration and
nullable-course class/session reads in the compatible fallback. Standalone migration
explicitly imports native FK targets through existing adapters. Two live native-login
EN1440/TH390 calendar navigation/return/reload tasks pass with private reads, correct
upload visibility, denied foreign/anonymous access and no academic writes. Existing
identity, roster, progress, grants, runtime/environment and unrelated service IDs are
preserved. The intended class-org backfill and four native role startup timestamp
changes are recorded separately. No real provider/device acceptance is claimed.

Known limits: first apply skips past dates rather than manufacturing historical
absences; an unmatched class has one owning teacher. Official `W:` numbers must be
confirmed against the reviewed academic week numbering on real NRRU material.
Never roll back academic evidence to an older dump. The pre-calendar app is not a
safe runtime fallback once unmatched classes exist: retain exact parent artifacts,
but verify a calendar-compatible code rollback against new records before release.
Synthetic fixtures and isolated tests are not institutional acceptance.
