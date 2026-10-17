# School academic calendars

## Assigned-teacher syllabi and automatic hybrid weeks

The reported resource-owner CREATE error came from native **syllabus preparation**,
not attendance-schedule saving. An active, explicitly assigned course teacher who
remains a native organization member can now prepare and edit that course's syllabus
without becoming an organization admin or general native course author. One exact
six-line native RBAC delegate runs only after the native decision and MFA checks.
Its extension-owned policy permits READ/CREATE/UPDATE at the class syllabus factory
and READ/UPDATE at the particular native activity/editor/version routes. Existing
native author/admin grants remain unchanged; unrelated activities/courses, general
course editing and deletion remain denied. Immutable `class_syllabus_prepared`
evidence binds the activity and course; mutable activity metadata cannot grant access
or make reuse return an unbound draft. Assignment or membership revocation is checked
fresh. No native roles, resource-author rows, enrollments or progress are added.

Hybrid is available for date-only course plans **and** reviewed school-week calendars.
The teacher chooses on-campus-first or online-first once. Course dates alternate in
seven-day blocks; reviewed school rotation takes precedence where available, including
an exam pause whose week 9 resumes as even. School rotation labels and source JSON
never change. Missing/filtered/cancelled meetings do not restart the cycle; make-ups
retain their original week's mode. Dated previews and existing past/attendance
protections remain authoritative. Syllabus drafts can be prepared before this mode
choice or attendance saving and existing authored content is never rewritten.

The compatible wire pattern remains `even_onsite`; optional
`hybrid_start: 'onsite' | 'online'` supplies the reviewed first mode. Missing values
retain the previous explicitly reviewed rotation behavior. The choice participates
in preview fingerprints and idempotency, is stored in the existing append-only
schedule-applied event, and reloads through the schedule DTO. No migration, school
publication change, implicit holiday or universal exam closure is introduced.

Validation covers 19 calendar/PostgreSQL cases (plus one opt-in real-PDF skip),
including two strengthened cases, 54 native-access/policy regressions, 20 pure planner
cases plus one static scope case, 81 web checks, 25 tooling/four overlay checks and
the production bundle/generated-route TypeScript. Five compiled native-shell journeys
cover non-admin teacher EN/TH desktop and Thai mobile, independent native draft
editing/save/reload, both first modes, date review/save/reload/cancel and read-only
student online/on-campus make-ups. No page errors or horizontal overflow. These are
synthetic checks, not institutional/provider or owner-browser acceptance. Native
rich-text editing remains desktop-only. Finish review is inline, not independent.

### Direction contract

**THESIS** Choose the first hybrid mode once; review actual dates rather than calculate
odd/even week numbers or acquire an admin role to write a syllabus.
**OWN-WORLD** Preserve native LearnHouse and the pinned Interior material layer;
existing select/button behavior, typography and restrained neutral surfaces.
**STORY** Select the accepted calendar/program, choose hybrid and its first mode,
review dated sessions and save; prepare the syllabus independently in the native editor.
**FIRST VIEWPORT** Retain the existing class task rail and calendar/mode fields;
reveal one first-mode select for hybrid, not a week-by-week configuration wall.
**FORM** Ordinary Operate extension of the incumbent surface, not a new visual world;
no concept roll, dependency, font, animation or shipping raster.
**FINISH** unreviewed and undocumented is unfinished; this build ends with the finish
review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
Existing DESIGN.md/Interior rules remain unchanged.

## Course planning from a published semester calendar

Deployed to LearnHouse staging, 2026-10-17, source `df75ce08`, image
`coursemax-learnhouse:course-calendar-planning-20261017`. The earlier date-only exclusion
was a workflow discrepancy: a published academic-date calendar must remain selectable.
The picker now scopes accepted calendars by academic year **and semester**, including
date-only programs. A teacher chooses the program, reviews suggested first/last
teaching dates and adds course-specific no-class/make-up exceptions before preview.
The proposed end precedes that program's first final-exam/closing date; it is not a
new official calendar fact. Missing boundaries stay empty. Teacher-confirmed seven-day
course weeks are distinct from institution-authored weeks. No inferred odd/even
rotation; at that release alternating mode still required explicit reviewed rotation
(superseded by the course-specific hybrid choice above).

Preview/apply reuse the existing attendance planner, fingerprint/version check and
past/evidence protections. Source bytes, school payload/publication and other classes
are unchanged. Course planning input is retained in the existing append-only
`class_schedule_applied` event and reloaded with its schedule version; no schema change.

`POST /schedules/by-class/{id}/syllabus` accepts `{expected_version,language?,revision_id?,planning?}`.
It prepares an ordinary **unpublished native course activity**, using the chosen
semester/program, calendar pin and weekly outline. A saved attendance schedule is
not required when an accepted revision is selected. Outcomes/topics/grading remain
explicit instructor-completion placeholders, not invented course facts. Existing
course/semester/program syllabi are opened without overwriting edits or publication;
other programs keep separate, clearly named drafts. Native
READ/CREATE/UPDATE permissions apply independently of school-class management; an
unmatched section must first use the existing course connection flow. The adapter
uses native chapter/activity services under savepoints so their commits remain inside
one caller transaction/roster lock. Failure rolls back partial chapters; concurrent
retries reuse one draft. Editing/publication/student reading stay native-owned.
The public editor URL follows the native `/course/{id}/activity/{id}/edit` rewrite,
not its internal `/editor` route. Draft creation and scheduling work on mobile;
LearnHouse's existing rich-text editor requires desktop, stated on the handoff link.

Checks: 19 passing calendar/PostgreSQL cases (one additional opt-in real-PDF case
skipped), 17 pure planner/template cases, 80 web checks, full production bundle and
generated-route TypeScript. Five compiled native-shell teacher/student journeys cover
EN/TH desktop and Thai mobile: date-only selection, course exceptions, independent
syllabus creation, native desktop editing/save/reload, mobile desktop-editor handoff,
schedule review/apply/reload and student read-only make-ups. No page errors or
horizontal overflow. Native PostgreSQL tests cover authoring denial, draft reader
404s, explicit publication, atomic failure, concurrent reuse, program separation and
preserved edits. Synthetic checks are not institutional/provider acceptance.

The live read-only check confirms the existing published school calendar now exposes
three semester/program planning choices. Two fresh-native-login EN/TH navigation
checks and syllabus origin/nonexistent-class denials pass. No live syllabus or
attendance schedule was created. App-only replacement/gateway reload, no migration;
exact schema, protected calendar/source/native-content/academic rows, environment,
mounts and peer IDs preserved. 1,030 API files and 5,491 web entries/permissions verified.
Fresh protected backup and exact preceding private-calendar image retained for code
recovery; never restore old academic data. Finish review was inline, not independent.

### Direction contract

**THESIS** Select the accepted semester calendar and complete the course task, without
sending teachers back to administrators to manufacture school-wide teaching weeks.
**OWN-WORLD** Existing LearnHouse controls and pinned Interior material; no new styling
system, dependency or standalone prose editor.
**STORY** Choose calendar/program, check proposed dates/exceptions, preview and save
sessions; prepare a syllabus independently and complete/publish it in the native editor.
**FIRST VIEWPORT** Retain one class task rail and calendar/mode choices; reveal only
course dates for date-only sources. Syllabus is a separate secondary action.
**FORM** Narrow extension of the existing Operate surface, no new visual identity.
**FINISH** unreviewed and undocumented is unfinished; this build ends with the finish
review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
Shared DESIGN.md/Interior remain unchanged; screenshots are private evidence only.

## Teacher-private calendars and proposal evidence

Deployed to LearnHouse staging, 2026-10-17, source `256bc802`, image
`coursemax-learnhouse:private-calendars-20261017`. Migration `c4fa25e2b813`
follows `b3e9c4d1a702` in the existing composed graph. Synthetic dry runs and
an exact-candidate protected restore rehearsal passed before live application.
Existing rows/source bytes and class pins were preserved; no native Alembic stamp.

- Existing calendars retain their IDs and become organization-scoped. Shared
  year/program uniqueness remains; each private upload gets its own calendar.
- Confirmed teachers upload PDFs or HTTPS PDF URLs privately. Only the owner and
  authorized platform reviewers in the same organization can read their drafts,
  accepted dates and retained originals. A domain hint alone is not sufficient.
- Acceptance freezes a private revision; it does not publish it to the school.
  Teachers attach accepted own/private or published shared revisions to the existing
  course-connection request. Attachments are append-only, idempotent per revision,
  visible to the requester/reviewers and included in connection review fingerprints.
  A completed proposal cannot acquire new attachments.
- Administrators explicitly prepare a school-wide **copy**, then review and publish
  it through the existing acceptance screen. Originals never change ownership or
  visibility. Copied source bytes, provenance and revision lineage remain intact.
- Acquisition provenance is per revision (`source_url`, `resolved_url`, `fetched_at`),
  so PDF deduplication does not erase different retrievals. Existing unknown URLs
  remain null. Cloning and metadata regrouping preserve provenance and lineage.
- Publication, proposal approval and schedule application remain separate. Existing
  class pins, attendance, rosters, native roles/enrollment and progress are unchanged.
  Date-only sources do not define official teaching weeks; course planning now
  supports separate teacher-reviewed weeks as described above.

Bootstrap-created staging uses `deploy/staging/apply_private_calendar_migration.py`
only after protected backup and an isolated restore rehearsal. It checks existing
row hashes/counts, takes the existing transaction lock and never stamps native
Alembic. Versioned databases use the composed Alembic graph instead.

**Recovery must keep the new API.** A pre-ownership backend filters by organization
alone and is not safe once private documents exist. Retain a compatible image with
this API and the exact preceding web runtime; never restore academic data for a
code rollback.

Checks: 17 calendar/PostgreSQL cases, 54 native-access/policy checks, 80 web checks,
production bundle/generated-route TypeScript, and eight compiled native-account-shell
teacher/admin/student EN1060/TH390 tasks. File/URL intake, private acceptance,
proposal attachment/review and explicit school-copy publication complete without
schedule/course-approval writes, page errors or horizontal overflow. Synthetic
fixtures are not institutional/provider acceptance. Existing Interior materials and
native controls are reused; no dependency or replacement interaction was needed.
Two live fresh-native-login read-only navigation/calendar tasks, private capability/
mutation denial probes, native guards and health passed. No real calendar was parsed,
accepted, shared, attached or applied by this rollout.

## Earlier delivery history

Status: deployed to LearnHouse staging, 2026-10-17; not institutional acceptance.
Live source `bbad16c7807a353c24dd8ba1b6e97e29db29cabd`, image
`coursemax-learnhouse:calendar-pdf-dates-20261017`. Assignment work remains excluded.
Claude Code's Opus 5.5 completed backend work in the separate `school-calendar`
Herdr session; Impeccable-guided upload/review corrections and desktop/mobile task
confirmation are complete.

## NRRU classes subtabs — source ready, deployment pending

The class workspace now places **NRRU class list** and **School calendar** under
**NRRU classes**, instead of opening the library from a page-level button. Source
navigation remains visible in the calendar. Native LearnHouse/Radix tabs provide
keyboard and linked-panel behavior; no new Interior interaction implementation or
native source patch is needed. Calendar loading is lazy, visited panels stay mounted
so unsaved edits survive tab/source changes, and class Schedule links open this same
calendar tab. Existing revision-back confirmation and all API permissions remain.

75 web checks and four isolated real-component Playwright teacher/student flows
(EN 1440 / TH 390) pass, including keyboard switching, retry, retained search/edits,
read-only student controls and Schedule handoff. The fixture uses cached native
controls, not a production Next build or live deployment. No academic writes.
Evidence: `nrru-class-tabs-20261017/`. Full build/deployment is pending the existing
3 GiB available-memory reserve; preflight observed 2.29 GiB. No cleanup/restart,
backend/schema/data change or staging activation has occurred for this change.

## Current delivery: the same PDF reads from upload or URL

The retained uploaded MIX PDF and the supplied URL PDF are **byte-identical**:
111,914 bytes, two pages, SHA256
`6d0a74393bcbc6ed0a07c69aaf9f59ca31756317331a5a98531351243ba4d5d9`.
The source-only stop in the previous release was an implementation limitation, not
a reason to require a different PDF. It is removed.

Upload, URL import, and opening an empty retained draft now read the actual date
table into **75 dated entries across three separate programs**. Physical table rules
and positioned text/font decoding keep columns separate. Opening, conditional
midterm, all separately stated final-exam ranges, closing, grade deadlines and
registration/other dates retain their source page. The midterm qualifier applies
only to courses coordinated with the registrar; it is not a universal exam window.
This uses installed pypdf locally, with no AI/provider dependency or OCR.

The default preview shows key dates; program filtering and registration/other dates
are available without a questionnaire. Optional focused date editing and one-action
**Accept calendar** work for date-only calendars. File and URL imports produce equal
payloads; the private original PDF remains byte-identical. Existing saved empty
drafts can be opened without re-uploading. No teaching weeks, rotations, closures,
make-ups or attendance sessions are inferred into the school calendar. The original
release excluded date-only calendars from the timetable picker; this is superseded
by teacher-reviewed course planning above. Preview/apply without required course
dates returns `422 course_dates_required` without writes. Full teaching calendars
continue using their reviewed weeks.

Proof: 73 web tests, full bundle/generated-route TypeScript, 34 baked pure tests,
seven focused isolated PostgreSQL tests, and 13 compiled EN1440/TH390 journeys.
Actual bytes are tested through both upload/URL storage and date-only publication;
compiled flows cover both import methods, retained-draft retry, program filtering,
optional editing, publication, original-byte hash, full-calendar regressions, stale
recovery and read-only student schedules. A bounded desktop/mobile screenshot batch
was reviewed. Two live fresh-native-login read-only calendar smokes and native
security/connection checks pass. No agent live institutional parsing/publication/
class application; the live MIX draft stays version 0 and its source is unchanged.
Not institutional, owner-browser, provider, OCR or broad PDF-format acceptance.

Code-only app replacement/gateway reload, no migration: 1,027 API and 5,383 required
web entries, native Config/permissions and in-flight assets verified. Schema,
source/draft, identity/academic data, environment/mounts and peer IDs are preserved.
**Recovery uses the new backend with the exact previous web**, verified against the
new event payload. The exact previous image is retained but cannot read new `events`
JSON and is not a safe code rollback after new records are saved. Never restore old
academic evidence for code rollback. Evidence: `calendar-pdf-dates-20261017/`,
`calendar-pdf-dates-web-confirmed-20261017/`, and the matching release directory.

## Previous delivery: PDF URL alongside upload

Choose **Use PDF URL**, paste a public HTTPS PDF link, then **Read PDF**. It uses
exactly the same private source/draft storage as file upload; full teaching calendars
continue into the existing preview/accept/edit flow. Authentication, org boundary,
admin and MFA checks precede remote access. Native SSRF validation checks every hop
and connected peer; redirects, total time and streamed size are bounded, with no
forwarded credentials/cookies or environment proxies. Limit: 10 MB; URL: 2048 chars.

The supplied NRRU `MIX 1-69 (18-7-69).pdf` downloads successfully: 111,914 bytes,
two pages, semester 1/2569. It is an **abridged multi-program document**, not a full
teaching-week announcement. Its three columns remain together as a source preview,
not silently assigned to the first program. The year/title are detected, the original
bytes/page text retained, and no teaching weeks, holidays or make-ups invented.
There is no AI call or metadata questionnaire. The preview offers the original PDF,
a full-calendar upload or another URL; it does not offer publication of empty weeks.
Reopening this draft does not retry AI. No new schema or permission was introduced.
Extraction is still pypdf, not Docling/OCR.

Proof: 72 web tests, full bundle/generated-route TypeScript, 29 baked pure tests,
six focused PostgreSQL tests plus one overlapping final URL-route test; 13 compiled
EN1440/TH390 tasks including full-calendar URL preview, this actual source's read-only
preview/reopening/byte hash, and failed-link → file-upload recovery. Two live fresh
native-login read-only URL-entry smokes and native auth/security/connection checks
pass. The actual link was fetched read-only and its bytes exercised in isolated PG;
no live institutional source/draft was imported, parsed, published or applied by agent.
1,025 API/5,359 web entries verified; native Config and in-flight assets preserved.
App-only replacement/gateway reload, fresh backup, exact previous image retained,
no migration; schema, source/draft, identity, academic data, env/mounts and peer service
IDs preserved. Evidence: `calendar-pdf-url-20261017/` and matching web/release folders.
Not institutional, owner-browser, provider, OCR or broad PDF-format acceptance.

## Previous delivery: PDF-first preview and acceptance

Source `f8bf0e11728fc15f9e7fa7bbbbce686a4c7a5d70`, image
`coursemax-learnhouse:calendar-pdf-preview-20261017`.

Use **My classes → School calendars → Upload academic calendar**, then choose the
PDF. Its name, Buddhist academic year and program are filled from the document;
there is no upfront metadata form. A read-only preview shows the teaching weeks,
holidays and make-ups. Choose **Accept calendar** to publish the previewed proposals,
or **Edit calendar** to change the filled metadata/dates and preview again. Acceptance
saves edits and publishes atomically: no separate save or verification questionnaire.
Source disagreements remain available as notes and acceptance is recorded; structural
and date validation still applies. Existing superadmin/org/MFA/version gates remain.

An empty retained draft still reads its saved PDF on opening, with no re-upload.
Publishing does not apply anything to a class. Open your own NRRU class's **Schedule**,
select the published calendar and teaching mode, then separately preview/apply.
A native course match is not required. No calendar facts are seeded. File-only upload
requires a recognizable year/program header; unsupported metadata is rejected rather
than invented. Explicit metadata remains supported by the existing API. Changing a
draft's year/program retains its old source/revision and copies into the correct
calendar scope; published bindings and class sessions are never reassigned.

Previous proof: 70 web tests, full bundle/generated-route TypeScript, 21 baked pure
reader/planner tests, five focused PostgreSQL tests plus two focused compatibility/
source-note checks (overlapping). Seven compiled EN1440/TH390 journeys cover file-only
preview/accept, optional edits without a separate save, retained-draft failure/retry,
stale-save recovery, and read-only student schedules/attendance. The protected source
text yields year 2569, ภาคปกติ, 15 weeks and 11 closures. Two live fresh-login read-only
calendar smokes pass; the agent did not parse/publish/apply the live institutional draft.
Code-only, no migration; 1,022 API and 5,336 web entries verified. Schema, source/draft,
identity, academic evidence, environment/mounts and non-app IDs preserved. Evidence:
`calendar-pdf-preview-20261017/`, its web artifact directory and matching release.

## Previous delivery: automatic reading correction — 2026-10-17

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
- Multipart `POST ''`: exactly one `file` (PDF up to 10 MB) or `url` (public HTTPS,
  up to 2048 chars). The same storage path handles both. Optional `name`, Buddhist
  `academic_year`, natural-language `track` override full-calendar metadata; a
  recognized abridged multi-program document always stays a combined source, never
  one program. Missing year/program is rejected without inventing facts. A valid
  source is retained before optional AI calls. Revision DTOs include `source_kind`
  and `source_programs`; recognized abridged sources have no generated term/week data.
- `GET /revisions/{id}` and private `GET /revisions/{id}/source`.
- `PUT /revisions/{id}`: `{expected_version,payload,metadata?}`; editable drafts only.
  Metadata supports `name`, `academic_year`, `track`; regrouping copies evidence into
  a new draft instead of reassigning guarded source/revision identities.
- `POST /revisions/{id}/parse`: `{expected_version}`; existing admin/org/MFA gates.
  Recognized NRRU text uses the local reader without AI; unknown layouts retain native
  AI feature/plan/credit/rate/model gates. Failure leaves source/draft intact.
- `POST /revisions/{id}/publish`: `{expected_version,reviewed:true,payload?,metadata?,
  accept_proposals?:true}`. Explicit proposal acceptance resolves review markers and
  records their acceptance with the source notes, validates and publishes atomically.
  Without it, unresolved/uncertain facts still prevent publication. Published JSON
  and source bytes remain immutable.
- `POST /{calendar_id}/draft`: `{from_revision_id}`; source-retaining draft clone.
- `GET /schedules`: exact `registry_course_id,academic_year,semester,section` query.
- `GET /schedules/by-class/{class_id}`: organization-bound teacher or active member.
- `POST /schedules/preview`: `{section,revision_id,pattern,expected_version?,planning?}`.
  `planning` for date-only semesters is `{program,starts_on,ends_on,closures?}`.
- `POST /schedules/apply`: same plus `{expected_version,fingerprint,reviewed:true}`.

Shared writes use the existing platform-superadmin check. An unmatched class's
first reviewed apply requires the teacher's confirmed identity and exact own official
section. It creates the existing `AcademicClass` aggregate, not another class system.
Matching later retains its class/roster/session IDs; unmatched classes cannot acquire
native learning grants. Students can read their own schedule both before and after
native matching, without gaining native content access.

Payload also supports up to 300 `events`: `{semester,program,kind,title,starts_on,
ends_on,page?,uncertain?,note?}`. Kinds are `opening|midterm|final|closing|grades|other`.
Each separately stated date/range remains separate. Events can publish without
terms/weeks. They do not themselves define meetings; separate teacher-reviewed
course planning may generate sessions. Summaries expose `has_teaching_weeks` and
semester/program-specific `planning_options`, with source events and proposed bounds.

Payload: `timezone:'Asia/Bangkok'`, up to three terms, explicit numbered week ranges,
rotation and `teaching` boolean, dated closures with nullable make-ups, optional page/
uncertainty and `unresolved` questions. Unknown keys are rejected. Teaching ranges
longer than seven days must be split. Exam labels alone never suppress meetings.
Patterns: `onsite`, `online`, `even_onsite`, with optional course-specific `hybrid_start`
as described above; no inferred school parity. Recognized official
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
