# Shared school academic calendar — research and proposed implementation

Status: proposal, 2026-10-16. No schema, API, UI or runtime changes implemented by
this research. Requested independent Claude brainstorming is pending its workspace
trust prompt in the separate `school-calendar` Herdr session; it has not reviewed
this proposal. The requested `claude-opus-5-5` model is not yet verified.

## Product outcome

Upload the school's academic-calendar PDF once, review it, and publish a reusable
school/year calendar. Each authorized class selects a term/calendar, combines it
with its official meeting times, and reviews a dated schedule. Table, month calendar,
class-session detail and attendance consume the same sessions. Native LearnHouse
assignments can be explicitly linked without transferring content or grading ownership.
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

- Native `src/db/courses/assignments.py`: an assignment belongs to one organization,
  course, chapter and activity. It has one `due_date`, not a section-specific deadline.
  Submission uniqueness is `(user_id, assignment_id)` and task submission uniqueness
  is `(user_id, assignment_task_id)`. Reusing the same assignment across years does
  not give a returning student a fresh independent submission.
- Native assignment service `authorize_assignment_access(..., activity_id=...)`
  applies course access plus activity publication/paywall/lock gates. Retain it.
  Native create/update commit internally: do not invoke them mid-way through an
  extension transaction and assume rollback is still atomic.
- Native deadline parsing accepts date-only/naive/offset strings with existing
  server-time semantics. A calendar must not invent an independent Bangkok deadline
  or claim a timezone fix that the submission endpoint does not enforce.
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
2. **Source documents:** original PDFs, checksum, extraction method and page evidence.
   Support a supplementary announcement without replacing the earlier source.
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
7. **Native assignment link:** explicit session ↔ native assignment/activity references,
   checked against the matched native course and the reader's current access. Core
   owns instructions, publication, submission, grading, solutions and the actual
   deadline. A session move must not move an assignment's deadline automatically.
   Restricted/deleted assignment references must not leak cached instructions/answers.

### Structural decision to settle with the backend reviewer

Prefer extending the existing school-class aggregate rather than building a second
roster/session authority, but compare these concrete options before migration:

- Give `AcademicClass` explicit organization ownership and an optional native-course
  match, preserving existing rows/IDs and auditing every affected authorization,
  connection, roster and learning-access path.
- Persist only an official-tuple schedule association until matching, then attach it
  to the existing class. This is less invasive initially but must not turn planning
  and attendance into two competing class/session models or quietly gate attendance
  on a content match.

A missing native match never grants content access. Existing manually authorized
staff/classes must retain their current authority; do not force them through a new
school identity ceremony as a side effect of this feature.

### Assignment scope decision

The smallest useful integration is a link to an existing native assignment, with its
actual native deadline and submission behavior clearly preserved. This satisfies
"connect to the core assignment object" but **not independent section/year attempts**.
If independent class deadlines/submissions are required now, design that explicitly:
core occurrence/context support, or genuinely isolated native assignment instances
with enforceable visibility. Merely duplicating activities inside one shared course
would still expose them to other course members. Do not introduce a shadow extension
deadline or second grading/submission engine to hide this gap.

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
- **Upload/review:** source PDF beside four concise sections: term dates, teaching
  weeks, holidays/makeups, other dated events. Prioritize missing/ambiguous dates.
  Each extracted fact can reveal its page/quote. Parsing failure preserves the PDF
  and draft for retry/manual completion; it does not clear the current calendar.
- **Class → Schedule:** replace the weekly-only destination with **Table / Calendar**
  views plus a compact recurring-times summary. First use: choose the published
  calendar/term → inspect resulting meetings and exceptions → **Create schedule**.
  Native matching stays separate. Later: **Review calendar changes**, not an
  unexplained automatic rewrite.
- **Session detail:** actual date/time, original teaching week, room/mode, any
  "make-up for …" relationship, linked native assignments and **Open attendance**.
  Keep check-in/attendance controls here rather than a disconnected calendar copy.

### Layout and behavior

Desktop table: date/time, academic week, meeting/room, status/reason, linked work,
next action. Calendar: month controls and selected-day agenda; both select the same
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
- Native assignment link respects course/activity gates, independent READ/UPDATE,
  answer hiding, deletion and current deadline. No implicit native role, enrollment,
  progress or grading mutation.
- Register owned models/router/migration through existing bootstrap/composed graph;
  isolated existing/fresh schema tests before any shared-data operation.
- Desktop/mobile teacher and student tasks in Thai/English, bounded visual review.

## Open confirmation

Confirm the proposed shared-library / class-schedule placement, and whether native
assignment links are sufficient initially or independent per-class deadlines and
submission attempts are required in this delivery. Claude's recommendation remains
pending; this document is not an accepted backend design or a completed feature.
