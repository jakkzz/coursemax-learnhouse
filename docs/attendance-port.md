# Class attendance — session, QR and receipt slice

Status: implemented and validated; deployment evidence is recorded separately.
Audit: B05/B06 partly implemented; B07 policy foundation only. None is accepted in
full. Parent `8d401a26` includes deployed classes `4c512c94` and role UI `d43256b0`.

## Teacher and student tasks

Open **My classes → Attendance**. An explicitly assigned teacher schedules a
session with Bangkok times, a title, present/late grace and first-entry cutoff.
The teacher opens an entry or follow-up QR, renews it on expiry and closes the
privacy-safe display to inspect/search/filter class attendance. No student rows or
history are rendered while displaying a QR. A reasoned, optimistic no-class/restore
action stops check-in, preserves evidence and invalidates earlier challenges.

The student scans the code, confirms check-in and receives a private immutable
receipt. The saved receipt link survives reload. Student session views show only
their own scans, never the class roster or teacher history. A receipt is scan
evidence, not a grade. Expired codes provide current-code guidance. Login uses the
native application; a same-tab short-lived pending fragment supports sign-in
return, but the teacher must renew if login takes longer than the code's lifetime.

## Ownership and storage

- Native account/session authority; no second login or imported CourseMax cookie.
- `AttendanceSession` belongs to one `AcademicClass`; `AttendanceScan` belongs to
  its stable `AcademicRosterEntry`. Never bind academic evidence by mutable email.
- Four additive tables, revision `f36da41e9f33` after `f25c930d8e22`. No backfill.
- Schedules are retained and immutable; state/version alone may advance. Scan,
  challenge and event updates/deletes/truncation are blocked by database triggers.
  A scan-scope trigger checks class/session/challenge/kind consistency. No delete API.
- Existing global roster transaction lock serializes membership/teaching changes
  with scan decisions. Native actor, organization, current teacher assignment,
  roster activity and conflicting number claims are independently checked.
- One scan per challenge/roster entry, unique receipt IDs, earliest-arrival
  projection and latest-follow-up projection. Concurrent/repeated submissions
  return one original receipt; an authorized retry can retrieve it after expiry
  without adding evidence. Withdrawn members cannot submit new scans. Own receipts
  remain readable by their original actor within the organization.
- Exact-origin writes, native anonymous denial, private/no-store reads and bounded
  actor-specific throttling; browser actor headers never authorize a scan.
- Raw tokens are returned only to the teacher and submitted in authenticated POST
  bodies. Only their SHA-256 digest is stored. QR URLs carry tokens in fragments,
  not HTTP paths/query strings; fragments are removed after capture. No outbound
  messaging, geolocation collection, portal login or real roster import.

## Timing and reporting rules

The stdlib-only `attendance_policy.py` has no DB, network, clock or authentication
side effects. Callers capture server arrival before lock queuing and evaluate the
current policy after the lock. Defaults preserve reviewed CourseMax semantics:

- Opens 30 minutes before start, inclusively; end remains inclusive for scans.
- QR lifetime is 120 seconds; expiry equal to arrival is expired.
- Grace defaults to 10 minutes, first-entry cutoff to 20 minutes. Equality remains
  accepted. A new entry after the cutoff is rejected without writing an absence.
- Repeat entry and follow-up/heartbeat scans bypass only the first-entry cutoff,
  never the session window or no-class state. First heartbeat evidence is allowed.
- No-class sessions are excluded from the attendance denominator; missing evidence
  becomes a read-only absent projection only after session completion.
- Present, late and excused count as attended; missing completed-session records
  count absent. Zero sessions yields no percent/risk; two-decimal rounding precedes
  strict below-threshold risk comparison (default 80%).
- New API times require an explicit offset and valid IANA timezone. The current
  scheduling UI deliberately uses Bangkok; it does not activate other-zone UI
  policy. Legacy naive timestamps mean UTC; instant comparisons handle DST folds.
- Pure withdrawal boundary is inclusive at session start. Historical membership
  eligibility must be implemented before multi-session summaries are exposed;
  current withdrawn/reactivated state is not a historical membership substitute.

Reference reviewed: CourseMax `aaa540d5035bf9bc241c361237e5e2374e1ba19d`,
attendance/checkin services, reporting/policy and integrity tests. Rules adapted,
not a private source-tree or real academic-data transplant.

## Validation

```sh
LEARNHOUSE_API_TEST_IMAGE=coursemax-learnhouse:d43256b0 \
  bash deploy/staging/test_attendance_postgres.sh
```

147 isolated PostgreSQL/auth/policy/HTTP tests pass, including anonymous/header
spoof denial, cross-class/withdrawn denial, revoked teacher, foreign origin,
concurrent one-receipt behavior, expiry, no-class restore, immutable evidence,
migration/bootstrap parity and the exact frozen deployment SQL/9 triggers.
The harness uses cached images, private Unix sockets, disposable synthetic stores,
no live volumes/network/credentials, and removes its own fixture container.

The full bounded frontend bundle and generated-route TypeScript checks pass. Eight
compiled teacher/student EN/TH tasks at 1440/390 pass schedule → QR → membership
search → no-class/restore → reload and student scan → receipt → saved-link reload
→ expired code → same-page fresh follow-up. No page errors/overflow; student
projections/QR display contain no peer details. An initial browser test reload
raced link navigation; accepted runs explicitly await the receipt URL before reload.
Thirteen wrapper/role-control regressions pass. Mechanical UI detector: no findings.
Inline scoped finish review, not an independent or real institutional acceptance.

## Deployment and recovery

`deploy/staging/Dockerfile.attendance` derives from the exact retained `d43256b0`
image. Package only seven reviewed API files and a complete validated web delta;
verify all baked bytes, links and modes. Use an isolated build context, protected
DB/content/runtime backups, restore verification and retained/saved parent image.
The frozen `attendance-schema.sql` is tested against the models and installed
atomically as an additive delta, without Alembic stamping or historical backfill.
This does not certify the full inherited Alembic chain. Restart only staging app;
reload its gateway after health, preserving stores and all provider/security policy.
Record health, authenticated/anonymous checks, exact source-menu revision, immutable
schema guards and unchanged identity/service snapshots before declaring deployment.

After attendance/class evidence exists, the old parent may hide retention guards or
features. Do not blindly roll back to it: review a compatible guarded rollback or
forward recovery. Never downgrade evidence, restore an old DB, erase student scans
or revert the owner's audited superadmin grant to undo code changes.

## Still separate work

This is not full CourseMax attendance parity: absence submit/withdraw/review,
manual overrides, historical withdrawal eligibility, aggregate risk/CSV screens,
LINE class QR/LIFF task access, soft geofence and stronger login handoff are still
open. Calendar/week/rotation (B03) is not implemented by session scheduling. No
migration, real registrar/provider/device acceptance or CourseMax cutover is claimed.
