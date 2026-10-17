# Attendance loop — CourseMax findings and next implementation

## Scope and delivery order

Owner brief, 2026-10-17: finish the pending calendar UI, then plan attendance from
CourseMax's useful behavior. Fix difficult scanning and LINE/ordinary-camera login,
make the phone experience enjoyable, and provide real-time feedback. Keep one data
owner and add no new routine gates, forms or approval steps.

This is source research and an implementation plan, not an attendance port or device
acceptance. Calendar API `746c8aa2` is live; calendar UI `9fc87afb` is still pending.
The deployment capacity check failed: 2.31 GiB free, subsequently below 1 GiB, then
3.17 GiB with 2.71 GiB available RAM; existing minima are 10 GiB disk / 3 GiB RAM.
No build/restart/prune was attempted in this task. Finish calendar bundle/types, focused desktop/mobile flows and the routine
app-only deployment once adequate headroom exists; do not package failed artifacts.

## Calendar deployment prerequisite completed — 2026-10-17

Pending calendar UI `9fc87afb` is now deployed and verified in
`calendar-ui-owner-20261017` / `e3914821…`, with the current API unchanged. See the
latest deployment record. The capacity-blocked dry-run checkpoint below is historical;
attendance arrival-loop application implementation is now next, not yet deployed.

## Dry run — implementation request, 2026-10-17

The follow-up request is deploy calendar first, then implement this plan. A fresh
capacity check still failed at 5.21 GiB disk / 2.38 GiB available RAM; no build or
restart was attempted. Offline checks passed 25 actual attendance-policy tests,
83 web source tests and 14 in-memory design assertions using the actual policy.
The rehearsal covers login after QR expiry, original arrival time, same/different
actor retries, revoked membership, deadline/version/no-class rejection and a failure
before receipt commit. It is not Redis/SQL/HTTP concurrency or real-device proof.

Two implementation details were clarified before coding: retain enough completed
handoff metadata to recover a committed receipt after a lost acknowledgement without
extending the deadline for a new scan; and handle SSE buffering at both nginx layers,
not just in FastAPI. Calendar deployment remains first; attendance application code
has not been started or represented as deployed.

## What is worth bringing from CourseMax

Reviewed CourseMax checkout `9da69c731e47d341d7e9d6c37e8aead5384aa466`.
Paths in this table are CourseMax source paths, not new runtime dependencies.

| Keep the useful behavior | Source evidence | Adaptation for LearnHouse |
| --- | --- | --- |
| Reserve a scan before login; preserve server arrival time through login delay | `backend/app/api/checkin.py` prepare/complete, `frontend/src/app/checkin/page.tsx`, `test_checkin_handoff_survives_login_delay_and_is_idempotent` in `backend/tests/test_attendance_integrity.py` | Resolve the rotating code immediately into a short-lived resumable handoff; finish through the existing native login and scan writer. Do not keep only an expiring raw code in browser storage. |
| One check-in writer for camera/browser and LIFF | `backend/app/api/{checkin,checkin_liff}.py`, `backend/app/services/attendance.py` | Both transports end in existing `class_attendance.accept_scan` semantics. Neither transport creates a different attendance ledger. |
| Server-verified LINE identity, linked accounts only | `backend/app/api/{checkin_liff,liff}.py`, `backend/tests/test_liff_identity_verification.py` | Reuse native LINE identity/session authorities; do not restore CourseMax auth or infer a user from a client-decoded token/name/email. |
| Stable QR while arrivals update independently | `frontend/src/components/session-checkin-control.tsx` | Fixed white high-contrast QR stage; renewal and roster updates must not move or blank it. |
| Useful live arrival feed | `frontend/src/components/session-checkin-roster.tsx` | Keep per-arrival highlights, held row order during edits and the new-arrivals pill. CourseMax polls every two seconds; it is NOT a server-pushed phone feedback system. |
| Retry-safe earliest arrival and original scan evidence | `backend/app/services/attendance.py`, `backend/tests/test_attendance_postgres.py` | Keep LearnHouse's stronger immutable scans/receipts and unique challenge/roster key; do not replace them with CourseMax's mutable record upsert. |
| Teacher corrections and excused leave share one attendance outcome | `backend/app/services/attendance.py::upsert_manual_override`, `backend/app/api/absence.py::decide_absence_request`, `backend/app/models/absence.py` | Append a correction through one decision path. Leave approval invokes that same path in the same transaction. The request records why, not another attendance status. |
| One reporting calculation for staff, student and export | `backend/app/services/attendance_reporting.py`, `backend/app/api/attendance.py`, integrity tests | One server projection/aggregate, including no-class exclusions and known membership boundaries. No separate frontend percentage or Gradebook count. |
| Task-first recovery and next class activity after arrival | `frontend/src/components/classroom-liff.tsx`, `frontend/src/app/checkin/liff/page.tsx` | Reuse an existing native session first. After a durable receipt offer My class, not another dashboard or compulsory activity. |

### Do not copy the friction or incomplete behavior

- CourseMax generates a 320px QR but renders it at 256px with a one-module margin;
  its QR points at ordinary `/checkin`, while the display encourages LINE scanning.
  Those are source-observed design risks, not a proven cause on the reported phones.
- Its browser handoff is good, but the direct LIFF check-in verifies identity before
  validating the raw QR. A slow sign-in can still outlive the code. Both entry paths
  need the same early reservation semantics.
- Its check-in success is a static screen. The teacher's two-second polling is not
  evidence of live phone updates after corrections/cancellation.
- Do not copy `line_qr_onsite` / `line_qr_online` as a model for transport. Provider,
  scan transport and the school's delivery mode are different facts; unknown school
  mode must not become online.
- Do not add location permission, LINE-app-only requirements, repeated confirmation,
  mandatory heartbeat/exit scans, profile questionnaires, new feature switches or
  medical-upload prerequisites to the normal arrival flow. Existing time/roster/
  identity rules stay; new attendance policy and attachments are not this first slice.

## Verified LearnHouse gaps

At source `1e4e7c69`, before this research (calendar UI changes are source-only):

1. `AttendanceCheckin.tsx` keeps a raw fragment token in `sessionStorage` for only
   120 seconds. Check-in needs another button press; login starts only after a failed
   submission. No server-reserved arrival survives a long login. Browser storage is
   not shared between LINE's webview and the phone's ordinary browser.
2. `/liff` does not receive a check-in destination. Its login redirect is `/liff`,
   and `line_subject_auth.py` LIFF start/session hard-code `/home`. Ordinary native
   OAuth already supports a validated return path; preserve that authority instead
   of adding an attendance login system.
3. `AttendanceWorkspace.tsx` opens one code with manual renewal. Its QR branch hides
   the roster; detail/receipt data refresh manually. There is no attendance SSE/WS
   feed in the inspected extension. The QR already has a better three-module margin.
4. `attendanceRequest` collapses several failures into generic denied/conflict text.
   A missing account link, expired code, ended class and roster mismatch need their
   actual next action, not a repeated generic LINE sign-in attempt.
5. Existing scans/events are append-only and roster-owned. Preserve this foundation.
   There is no need to import CourseMax's account, enrollment or attendance tables.
6. Retroactively generated calendar sessions are not proof that attendance was ever
   collected. Today's missing-scan projection can label them absent after their end;
   reporting must distinguish missing historical evidence from a collected absence.

These are code findings. The reported iOS/Android/LINE failures have not been
reproduced on real devices, and SDK/cookie/provider configuration has not been changed.

## The smallest useful loop

Teacher opens today's class → large stable QR renews automatically → student scans
with LINE or the phone camera → server reserves the valid scan → existing login only
if needed → same class resumes automatically → committed receipt appears immediately
on the phone → teacher sees the arrival without refresh → later class-state changes
and corrections update the student's own status → both histories/report use the same
server result.

### Scan and sign-in

- Ordinary camera links stay ordinary HTTPS links. Do not force a LINE app switch.
  In LINE use the existing LIFF session path when available; retain ordinary native
  Google/linked-LINE/password routes as appropriate, not an app-only dead end.
- Reserve before provider login/SDK waits. Carry an opaque handoff and validated
  same-origin destination through the current auth/MFA flow. The handoff contains
  no student identity, grants no membership and records no attendance by itself.
- Raw-code and reserved-handoff completion converge in one service after challenge
  lookup. Only server-held handoff state may supply a reserved arrival time; do not
  accept an arbitrary client timestamp or insert a scan from a separate LIFF writer.
- Match CourseMax's useful bound: at most ten minutes to finish, capped by class end.
  Use the server-observed reservation time, not client time or login-completion time.
  Recheck current session/version, actor and roster before committing a scan.
- Keep raw QR fragments out of auth return URLs. Only the opaque resumable handle
  crosses the flow. Do not assume cookies/sessionStorage transfer across browsers;
  carry the handle explicitly in a supported same-origin continuation. A browser
  switch starts a fresh native auth transaction in that context; never transfer
  OAuth binding cookies, OAuth state or provider tokens between browsers.
- Repeat completion by the same actor returns the same durable receipt. A different
  actor cannot consume that completed handoff. Native sign-out, revocation and MFA
  remain authoritative. No LINE-only signup or automatic Google/LINE merge.
- Use existing-session-first recovery. Show Link LINE only for an actually unlinked
  LINE account; provider cancellation, network failure and expiry are not all that
  error. Preserve the attempt when retrying within its valid lifetime. Native LIFF
  also rejects reused ID-token proofs; do not weaken that check or loop on the same
  SDK token. If no native session can be reused, offer the existing fresh LINE OAuth
  path with the same continuation instead of repeatedly failing LIFF initialization.

### QR and phone experience

- One QR stage, black on white, at least four modules of quiet space, no logo overlay
  and no animation inside the code. Add a projector/fullscreen layout that is actually
  larger than the current 320px cap. Measure symbol density before adding a short URL
  alias; retain fragment privacy. Copy link remains the existing accessible fallback.
- Fetch the next rotating code before the old one expires; retain the still-valid
  code during a transient fetch failure. Never present an expired code as working.
  Keep the QR's size/position stable; show connection/renewal status outside it.
- Phone states are reading → signing in only if required → recording → recorded.
  On server acknowledgement use a brief checkmark/ring animation and friendly EN/TH
  copy, with class, arrival time and effective result. The receipt stays visible;
  no fake progress, replay celebration, auto-dismissed proof or confetti before commit.
- Acknowledge once per new receipt. Reduced motion retains the same immediate text
  and icon. Optional supported haptics must not be needed for success; no forced audio.
- Keep a live/reconnecting indicator, last confirmed result and one useful recovery
  action. A lost connection is not a successful check-in or a newly absent student.
- Teacher view separates the stationary QR from a live private roster. Hold ordering
  while editing, preserve search/scroll and highlight only newly committed arrivals.
  Projector view contains aggregate counts, not student identities or private evidence.

Interior checked at existing MIT pin `314800833bf01e23e6ae74c2a17fbdaac3688c84`:
reviewed `live-activity.tsx`, `icon-morph.tsx`, `new-items-pill.tsx`, `value-flash.tsx`
and the extension's Interior `DESIGN.md`. Prefer headless arrival/counter patterns
and existing native controls/motion dependency. Do not copy the auto-dismissed live
activity as the durable receipt, or an interactive icon-morph button as a passive
success icon. The cached upstream root DESIGN.md is absent; fetch/read its pinned
version before copying implementation. Record license/provenance for copied source.
No new animation or transport dependency is needed.

## SSOT — one owner for each fact

| Fact | Authority / planned use |
| --- | --- |
| Person and signed-in provider | Native `User`, provider identities and native session/MFA/revocation. No attendance account. |
| Academic participant | Existing `SchoolStudent` + `AcademicRosterEntry` within `AcademicClass`; roster ID owns evidence, actor user ID records who acted. Never email/name/provider-subject matching. |
| Date, timing, delivery mode and no-class state | Existing `AttendanceSession` and immutable calendar lineage. No parallel timetable/session for LINE, QR or reporting. |
| Rotating invitation | Existing `AttendanceChallenge`, hashed code, kind, expiry and session version. Possessing it is not attendance or roster membership. |
| Login continuation | Short-lived handoff bound to that challenge/session/version and observed arrival. Reuse existing Redis infrastructure for transient continuation; it is not an academic ledger. Final idempotency resolves to the scan/receipt, not a second record. |
| Actual scan evidence | Existing immutable `AttendanceScan` / receipt. Preserve original computed status, actor, roster and server time. Both transports call the same acceptance path. |
| Teacher correction | Proposed typed `attendance_decided` entries in existing append-only `AttendanceEvent`, validated against the same session/roster under the existing transaction. Latest attributable decision for that pair wins; returning to scan-derived status appends a reset decision, never deletes history. Do not add a competing mutable AttendanceRecord table. |
| Effective attendance | Extend one `scan_projection`/policy path: no-class first, then current teacher decision, then scan-derived result, then eligible collected-session missing status. Immutable original receipt remains separate from effective status. |
| Leave request | Later request/history records why approval was requested. Approval appends through the same decision writer atomically; never count request state as a second attendance result. |
| Teacher/student summary, CSV and any later score consumer | One aggregate over the effective projection. Completed, collected, eligible sessions only; no-class/future/uncollected history excluded. Preserve established reporting arithmetic rather than recalculate in React. |
| Real-time delivery | Committed event cursor plus canonical projection. Stream messages and animation state are disposable views, never another status writer. |

Handoff storage needs atomic one-use claim/completion semantics and bounded retention;
a storage outage cannot create attendance. Do not add a second Redis service or a
background worker. Keep completed-handoff metadata briefly beyond its usable deadline
so an authenticated same-actor retry can resolve an already committed receipt, even
if cache finalization or its acknowledgement failed. That does not extend permission
to create a new scan; canonical scan uniqueness/receipt lookup is the final arbiter.
Validate roster eligibility before permanently binding a fresh handoff to an actor.
The authenticated direct scan path remains available to someone already signed in
with a valid current QR.

**Historical coverage:** QR-open evidence already shows that collection was started.
A backfilled session without collection/scan/decision evidence remains not recorded,
not an invented absence. An individual retrospective decision applies to that student;
it must not manufacture absences for everyone else. Do not add a new mandatory
"attendance collected" toggle. Reporting must use known roster observation/history
without inventing an official enrollment/withdrawal effective date from sync time or
current membership alone. Existing evidence survives withdrawals and corrections.

## Real-time delivery, without another authority

Use same-origin authenticated SSE for one-way updates; there is no existing attendance
WebSocket manager worth duplicating. POST returns the committed receipt immediately.
The stream pushes canonical changes to the teacher and the affected student's phone.

Start with a bounded server read of existing committed events, targeted at roughly
one-second delivery, not a new broker/outbox/worker. Return a snapshot/cursor together,
reconnect after a cursor and deduplicate by event/receipt identity. Re-read the
canonical projection after invalidation; never replay status by guessing from strings.
Refresh at session clock boundaries even without a new event. Recheck scope during
streaming and on reconnect; an open stream must not retain revoked privileges.

Student feeds expose only their own result; teacher roster data stays in authorized
staff view. There are two nginx layers: the owned staging gateway and the app's native
API proxy. Send `X-Accel-Buffering: no` from the SSE endpoint for the inner layer and
disable buffering only for the exact stream path in the owned gateway. The inner
proxy consumes that header; assuming it reaches the outer proxy would break timely
delivery. Preserve existing auth/forwarded headers and all unrelated routing. Bound
DB work, close abandoned streams, and release connections between reads; do not hold
a request-scoped DB session for the lifetime of a StreamingResponse. Use existing
native auth refresh/reconnect behavior. A short active-page polling fallback keeps
check-in usable if streaming fails, clearly labeled reconnecting rather than called
server push. No LINE push/multicast/broadcast is involved.

## Implementation queue and proof

1. **Calendar UI first.** Deploy existing `9fc87afb`, not an attendance redesign.
   Verify full/abridged calendar selection, past dates, unknown modes, save/reload,
   teacher/student EN/TH desktop/mobile; retain API `746c8aa2` behavior and recovery.
2. **One arrival slice.** Resumable early handoff + normal-camera/LINE return path +
   automatic check-in + stable auto-renewing QR + committed phone animation + live
   teacher/own-phone updates and reconnect. No extra student confirmation or policy
   setup. Keep native permissions and use the existing attendance models/writer.
3. **Close the teacher/student loop.** Append-only correction decision, student own
   current/history view and shared summary/CSV with honest historical coverage.
   Follow with minimal leave requests/approval using that same decision writer.
   Attachments, advanced thresholds, location, compulsory follow-up scans, games and
   attendance scoring are not prerequisites and are not added opportunistically.

Focused proof for slice 2 must complete tasks, not just render components:

- Already signed-in camera and LINE users scan to exactly one persisted receipt.
- Signed-out user completes native Google/linked-LINE login after QR expiry but
  within the reserved handoff lifetime; arrival time remains the reservation time.
- LINE external-browser/LIFF redirects preserve destination; switching contexts does
  not depend on shared browser storage. Unlinked LINE gets the correct recovery;
  cancellation/offline SDK does not falsely mark attendance or discard a valid attempt.
- Same-actor retries, double taps, remounts and reconnects do not duplicate evidence
  or counts. Different-actor handoff reuse, wrong class and revoked membership fail.
- Teacher sees arrival and phone sees session cancellation without refresh, within
  the delivery target on a healthy connection. Reconnect recovers current state;
  projectors/other students never receive named private attendance data.
- QR remains stationary and decodable through renewal; exercise real iOS/Android
  normal cameras and LINE in-app scanning, distance and projector conditions. Synthetic
  browser tests cannot establish physical scanability or actual provider acceptance.
- Test EN/TH mobile plus teacher desktop, reduced motion, keyboard/status announcements
  and slow/offline recovery. For the later correction slice, teacher decisions change
  effective status on both screens while preserving original receipts; summaries and
  CSV agree, no-class is excluded and backfilled/uncollected dates do not become absence.

No real attendance data is imported, no user is impersonated, and no attendance
implementation/configuration/provider change is made by this planning checkpoint.
