# Attendance corrections, history and CSV — rehearsed plan

2026-11-04. **Historical planning/rehearsal checkpoint.**
Follow-up: [implementation source and delivery status](attendance-corrections-reporting.md).
The slice is now implemented, pushed and deployed; the evidence below records
what was known at planning time, not the latest implementation results.
Baseline: fork `4782e92b`, live source `e142f6e3`, image `310ed40a`.
Audit scope: **B05/B06/B07 → LH-04**, chiefly B07. These IDs remain in progress.
Continue the existing [attendance-loop design](attendance-loop.md), not a replacement.

## Smallest complete slice

An assigned teacher opens Attendance, corrects one saved member's session result,
sees the attributable history, and exports a class summary. The student sees their
own effective result/history and the same totals. Original scans/receipts never change.

1. **Teacher:** My classes → Attendance → session → member → **Correct attendance**.
   Show current result and original arrival separately. Select Present, Late, Absent,
   Excused, or **Use recorded evidence** (reset); enter a meaningful reason; Save.
   The class/member are selected from authorized records, not typed internal IDs.
2. **Student:** same session shows the current outcome, original receipt if any and
   the reason/time of their correction. Class **My attendance** shows dated own
   history, totals and coverage. No roster list, other people's notes or staff raw journal.
3. **Teacher:** class **History and summary** shows per-student counts and coverage;
   select a member to see dated history. **Download CSV** exports the same summary
   for the chosen session-date range, all matching members—not the current page only.

No new account/enrollment writer, attendance table, scheduler, flag or service.
Leave requests/approval are the following slice and must use this same decision writer;
no leave attachments, scoring/gradebook, bulk corrections, risk configuration,
location/exit requirements, notification sends or institutional import here.

## Authorities and decisions

| Fact | Existing authority / implementation |
| --- | --- |
| Staff and class scope | `academic_rosters.can_manage`, `class_attendance.session_scope/staff`, native org/session checks; retain matched and unmatched saved classes |
| Stable member | `AcademicRosterEntry.id` in that exact class + `SchoolStudent`; no name/email matching, ownership transfer or reenrollment |
| Immutable receipt | `AttendanceScan`, `own_receipt`; never change `computed_status`, arrival or actor |
| Correction | Append typed `attendance_decided` to existing `AttendanceEvent` under `academic_rosters.serialize`, commit once |
| Effective result | One extended `class_attendance.scan_projection` and shared batched data loader, used by every reader and scan retry response |
| Summary arithmetic | Existing `attendance_policy.summarize_attendance`; no React/CSV-specific calculation |
| Live update | Existing `attendance_head`/SSE cursor includes decision event IDs; no new transport or outbox |

### Append-only decision contract

Proposed `POST /api/v1/attendance/sessions/{session_id}/decisions`:
`roster_entry_id`, `status=present|late|absent|excused|reset`, trimmed `reason` (5–500),
`expected_token` and a client UUID `request_id` retained for retries of that intent.
Strict DTO, same-origin write, current native manager authority and exact class/member
validation on every call, including a retry. A withdrawn member can be corrected
historically without being reactivated. Future and currently no-class sessions reject
new decisions; existing decisions survive no-class/restore.

The evidence token binds session version, class/roster version, this member's latest
decision ID and scan evidence. Under the existing academic transaction lock:

- Same actor/request ID and exact normalized intent returns the committed decision,
  even after a lost acknowledgement. Changed intent/key collision returns409.
- A different request with stale evidence returns409; two reviewers must not silently
  overwrite each other. Preserve the editor draft and show current evidence on reload.
- Append actor/time/status/reason/roster ID/request ID and previous decision reference;
  reset is another decision, never delete/update an earlier one. Do not increment the
  session version for a correction (that would unnecessarily invalidate open QR codes).
- Flush/commit once; errors roll back the whole decision. Later leave approval must
  append here in its request-decision transaction, not call a separate attendance writer.

No schema change is expected. Existing session event index suffices initially; profile
real query plans before proposing any additional index/migration.

### One projection and honest historical coverage

Order: **no-class → latest non-reset teacher decision → earliest scan → known
membership + collected session missing status → unknown/not-recorded/not-eligible**.
Every receipt DTO keeps `computed_status` and reports the current `effective_status`.
New scans, same-challenge retries and receipt reloads must not bypass corrections.

- QR-open journal evidence means that the class session was collected. Scan evidence
  also establishes collection; do not infer collection from session creation or a
  correction alone. A personal retrospective correction counts only for its reviewed
  member/session; everyone else remains not recorded/unknown. No mandatory collection toggle.
- Build observed membership intervals from `AcademicClassEvent`, keyed by stable
  class/student/entry ownership. Handle `registry_member_added/seen/reactivated`,
  `registry_member_missing` with its recorded status, `manual_member_added` and
  `manual_membership_changed`. Registrar confirmation of a manually controlled member
  must not override manual withdrawal. Use deterministic event ordering; ambiguous or
  incomplete history stays unknown, not active by default.
- An observation is known **from observation time**, not an invented official enrollment
  date. Do not apply today's active/withdrawn state backwards. Preserve inclusive
  withdrawal-at-session-start behavior and gaps between withdrawal/reactivation.
- A valid scan or an explicit teacher-reviewed correction is evidence for that pair
  despite incomplete roster history. The latter is an attributable academic decision,
  not an inferred registrar fact or a membership/role change. Reset removes only the
  override; without other evidence the pair returns to unknown/not recorded.
- A completed session counts only when its effective result is Present/Late/Absent/
  Excused and participation/collection or explicit pair evidence supports it. Exclude
  no-class, future/in-progress, uncollected and unknown-membership pairs. Calendar
  replacement sessions already marked no-class do not double-count their successor.
- Use the existing arithmetic: Present + Late + Excused count as attended; round to
  two decimals before the strict below-80% default risk comparison. Empty denominator
  is **no percentage**, not0%. No new threshold settings. Clearly label partial coverage;
  do not present a definitive risk badge for incomplete coverage or withdrawn members.
  Percentage is explicitly over recorded/known eligible completed sessions, not the
  entire official term. Carry excluded/unknown counts in JSON and CSV.

### Read and export contracts

Proposed class paths under `/api/v1/attendance/classes/{class_id}`:

- `GET /summary?from=YYYY-MM-DD&to=YYYY-MM-DD` — manager-only class summary.
- `GET /history?roster_entry_id=…&before=…` — manager-selected member, keyset-paged
  sessions and decisions; includes original scans separately from current result.
- `GET /own?from=…&to=…&before=…` — server-selected own saved identity, summary and
  paged history. Read historical own records using `member(require_active=False)`
  while retaining existing identity-conflict and organization checks. No new scan right.
- `GET /summary.csv?from=…&to=…` — manager-only, same aggregate and date rules.

Use explicit class-local session-date boundaries (inclusive selected dates converted
server-side to UTC), `as_of` time and coverage description. No silent 200-session
limit from the current session picker may cap totals/history. Pagination limits
presentation, not aggregation. Read a coherent snapshot for each report/export
(e.g. one read-only repeatable-read transaction set before queries), release it when
finished, and recheck authority per new request. JSON and CSV use the same aggregate;
independent requests after a correction may truthfully have different `as_of` values.
Batch-load scans, decisions and membership history; no per-member SQL query loop.

CSV: UTF-8 BOM, standard quoting/CRLF, student number as text, name, membership,
known denominator, Present/Late/Absent/Excused, two-decimal percentage or blank,
coverage/exclusion counts, risk/unknown indicator, range and `as_of`. No provider
email/subject, raw journal, QR secrets or correction reasons in a class summary CSV.
Neutralize spreadsheet formula-leading text after leading whitespace/control
characters; CSV quoting alone does not prevent evaluation. Excel may still coerce
numeric student numbers on import: retain raw digits, do not use `="…"` formulas.

## Existing callers and files that must change together

Backend (`apps/api/src/route66_ext/`):

- `services/class_attendance.py`: shared decision writer, projection/data loading;
  **both branches of `accept_scan`** return the canonical effective result.
- `routers/class_attendance.py`: `session_snapshot` teacher and own branches, `/receipts`,
  new decision/history/summary/export endpoints. Existing SSE uses that snapshot.
- Small owned `services/attendance_reporting.py` only if needed to keep batched history/
  membership/aggregate loading separate; reuse existing pure `attendance_policy.py`.
- `tests/services/test_class_attendance.py`, `test_attendance_arrival.py` plus focused
  correction/reporting tests. No new native hook/model/bootstrap registration expected.

Frontend (`apps/web/extensions/route66/`):

- `AttendanceWorkspace.tsx`, `attendance-client.ts`, `attendance-copy.ts`: typed decision,
  summary/coverage/history DTOs, Excused/reset labels, class report/own-history entry.
- `AttendanceCheckin.tsx`, receipt route/component and `useAttendanceStream.ts` consumers:
  distinguish immutable arrival from effective correction; same DTO everywhere.
- Add small `AttendanceHistory`/`AttendanceSummary` components only where useful;
  consume existing native tabs/Interior Button/Input/select controls, no visual redesign.
- Extend real-component fixtures/browser checks, not source-regex assertions alone.

## Interaction rehearsal brief (not browser proof)

Operate mode in the existing Interior/native attendance shell. Keep the QR/teacher
live roster, selected class/session, filters, scroll and inline correction draft stable.
Place **Correct attendance** on each row; focus its inline reason/status editor and
restore that row action on Close. On mobile use stacked labeled history rows, not a
mandatory horizontally scrolled matrix. Expose Excused as text, not color alone.

Live events update the displayed result, not the user's draft or reviewed token.
After a stale409 show what changed with **Reload and review**, retaining reason/status;
explicitly review the refreshed result before another Save. After a failed response
retry the same request ID/intent. A changed draft uses a new ID only after resolving
an uncertain previous save. Success focus goes to the persisted result/status message.

Teacher/private history distinguishes "Recorded arrival" / "เวลาเช็กชื่อเดิม" from
"Current result" / "ผลปัจจุบัน". Reset copy: "Use recorded evidence" /
"ใช้ผลจากหลักฐานที่บันทึกไว้". Empty history says not recorded, not absent. Own history
never renders manager-only controls. Filters with zero matches have Clear filters.
Projector stays aggregate-only with its existing scan-arrival meaning; an Excused
correction must not be celebrated or counted as a physical QR arrival.

## Rehearsal and implementation order

1. **This checkpoint:** inspect current sources and pinned CourseMax behavior; run
   actual pure policy + focused existing PostgreSQL/HTTP baselines and offline model.
2. **Implement authority/projection first:** append/retry/stale behavior, all three
   projection callers, observed membership coverage, one aggregate and CSV.
3. **Wire complete teacher/student UI:** correction, history, summary/download and
   existing live updates; no backend-only milestone.
4. **Focused acceptance before delivery:** actual disposable PostgreSQL concurrent
   reviewers/scan race/lost acknowledgement/rollback, student own-only and revoked
   manager denials, immutable scans/events, no-class/restore, withdraw/reactivate,
   unknown coverage, >200 sessions, 1000 members, and formula/Unicode CSV equality.
   Native-auth packaged EN1440/TH390 tasks must persist a correction, see it on the
   student's current/receipt/history surfaces, export matching totals and reset it.
   Verify immediate editor focus, stale draft retention, live updates, no overflow
   and reduced motion. One batched desktop/mobile inspection + one confirmation.
5. **Routine deployment when implementation is requested:** normal resource gates,
   approved off-host bundle/types if needed, verified image/bytes and fresh recovery
   snapshots; app-only replacement and live bounded verification. No real attendance
   mutation to manufacture acceptance; genuine class/provider/device trials separate.

## Rehearsal results and plan revisions

Commands from `platform/`:

```sh
PYTHONPATH=apps/api python3 -B -m unittest src.route66_ext.tests.services.test_attendance_policy -q
python3 -B scripts/extensions/rehearse_attendance_reporting.py -v
```

- **25 actual pure-policy checks pass.** Arithmetic, cutoffs, timezone, no-class,
  inclusive withdrawal and empty denominator behavior already exist.
- **20 offline specification checks pass.** Execute unmodified selected real
  `scan_projection`/receipt functions for baseline evidence; model proposed decisions,
  reset, no-class/restore, individual retrospective coverage, observed membership,
  stale/retry semantics, failure-before-commit, aggregate/CSV and formula handling.
- **Seven existing baked PostgreSQL/HTTP checks pass** in the current image with a
  disposable socket-only database: scan/receipt/reload, no-class/restore, immutable
  evidence, other-user receipt denial, revoked teacher, uncollected past date and
  committed own-state streaming/connection release. This validates the foundation,
  **not new correction endpoints or real-provider authentication** (test actors are synthetic).

Source inspection/rehearsal tightened the plan before implementation:

1. Updating only session snapshots would leave scan retries and receipt reloads wrong;
   all existing `scan_projection` callers are now explicitly inventoried/tested.
2. A personal decision cannot mark the class collected; retroactive reset must restore
   unknown/unrecorded instead of creating global absences.
3. Current roster state and the session picker's200-row cap cannot drive historical totals.
4. An explicit teacher correction can resolve one saved pair's missing historical outcome
   without backdating roster membership or requiring a new administrative workflow.
5. Retaining old code is **not semantic rollback proof**: existing old readers ignore
   `attendance_decided`. See the recovery constraint below.

CourseMax reference pin `9647db65d4b37b0b3a569bc1e61042997663d179`:
`backend/app/services/attendance.py::upsert_manual_override`,
`attendance_reporting.py`, `backend/app/api/attendance.py`. Preserve its shared override/
report arithmetic, not its mutable `AttendanceRecord` table or current-state historical
membership shortcuts. No runtime dependency on the old checkout.

Evidence: `~/.local/state/learnhouse-attendance-reporting-plan-20261104/`.
The in-memory authorization/serial-transaction model is not SQL concurrency, HTTP
permission or browser proof; CSV model is not a production export. No app code,
DB schema/data, environment, service, identity, enrollment or deployed image changed.

## Recovery and acceptance boundary

Before the first decision, the current parent remains a straightforward code rollback.
After any new decision, do **not** blindly revert to an older projection that would
hide corrections or report false attendance. Keep/produce a correction-aware rollback
image or forward-fix the owned projection; preserve all decision/scan history. Do not
restore an old DB, rewrite decisions or reset legitimate results for rollback.
Rehearse the actual chosen compatibility image against synthetic new history when
implementing; that compatibility is not established by this plan.

Owner acceptance is a teacher/student completing the corrected session → own history →
matching report/export workflow, with real device/provider participation where needed.
This checkpoint neither marks B05–B07 accepted nor changes scheduled-source-failure,
staff-identity, leave or wider CourseMax parity status. No unresolved product choice
blocks this scoped plan; historical coverage stays visibly partial rather than invented.
