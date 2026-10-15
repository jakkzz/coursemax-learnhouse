# Class connections and roster-based native course access

Implementation update, 2026-10-15. Release validation/deployment is recorded in
[deployment.md](deployment.md) and the private current-release record. The prior
396d1a01 backend was inactive; its extra activation flag is now removed. Normal
native-session administrator review in the product is the approval boundary.

## Usable workflow

1. A confirmed teacher opens an actual section in **My classes** and chooses
   **Request this class connection**. The server verifies the exact official course,
   academic year, semester and section against that account's own registrar
   timetable. Directory association remains self-attestation, not permission.
2. The request appears in the administrator's **My classes** queue. The administrator
   selects the correct existing **private native course**. There is a direct native
   course-manager link if it must first be created. Course names never prove identity.
3. Paste the official class-roster URL if not already supplied. Its class/course/
   year/semester identifiers are extracted and cross-checked, never guessed or
   manually transcribed. The public timetable does not expose the class identifier.
   No arbitrary URL is fetched; roster fetching still rebuilds the existing fixed
   registrar URL and validates the actual section/header before import.
4. Review the course, requesting teacher, exact section and native access-policy
   effect, then **Connect class**. One caller-owned transaction creates only missing
   mapping/assignment/class metadata, provisions the dedicated native group/link,
   and configures reviewed READ access. Existing classes/history cannot be taken
   from another course. Replays return the existing connection.
5. The teacher uses the existing **Load official roster → review → Apply roster**
   workflow. No roster is imported merely by opening, requesting or connecting a
   class. Manual members, two-accepted-missing-snapshot withdrawal and exact-number
   ownership remain the existing authorities.

Advanced manual setup remains available but is no longer the primary path. A teacher
cannot approve their own request or turn a staff email/name into native privileges.
One account/session authority remains; no API token, actor override, impersonation
or copied browser session is used.

## Native authority, limits and first-group policy

The owned adapter checks actual platform-superadmin status, org membership and
native `usergroups.action_update`; provisioning additionally checks native
`usergroups.action_create`, native Standard-plan entitlement and the native
actual-database-row quota helper. Its bounded group/resource/membership operations
flush but never commit. Native group helpers cannot be called directly here because
those helpers commit internally, breaking the shared reviewed transaction.

Only a dedicated group linked to one same-org private course is used. First-time
adoption of an existing group still requires it to be empty. Omitted group IDs
provision the dedicated group through the reviewed action; teachers never need to
look up native IDs. UUID ambiguity counts all candidates, including other orgs.

**The first group restricts native private-course organization-wide fallback.**
Preview and confirmation disclose this, with a direct native manager route to review
and preserve necessary manual readers first. No claim is made that all prior
implicit readers remain eligible. Course visibility/publication is never changed.

READ eligibility includes exact verified roster owners and explicitly assigned,
Google-verified org teachers. This is not authorship or UPDATE/DELETE permission.
A configuration explicitly records `students_and_assigned_teachers`; historical
student-only configurations do not silently expand on ordinary refresh. Assignment
changes and fresh Google completion refresh applicable delegations. Native REST,
org, publication, feature, edition and plan checks remain final.

Private-course navigation now consults the native READ checker rather than treating
`public=false` as unavailable. Reading access is **not enrollment**: native Trail,
TrailRun, TrailStep and the enrolled dashboard remain native-owned. Learners use the
ordinary native start/enroll flow; no destructive unenrollment is ever called.

## Recovery without holding sign-in hostage

Native access reconciliation runs in a savepoint. A plan/configuration/adapter
failure does not roll back verified Google evidence or an accepted roster. The
failure branch grants nothing, releases only still-live **provably bridge-owned**
rows, preserves manual/recreated rows, and appends a repair task. Serious shared
DB failures are not hidden or represented as successful writes.

**My classes** gives administrators a direct repair task; the roster has **Retry
access** and **Review access repair**. Explicit reviewed recovery can provision a
replacement dedicated group. It appends a configuration linked to its predecessor;
old bindings, memberships and evidence are retained, never reassigned or rewritten.
Only exact old owned rows are released; old groups/resource links/manual grants are
not deleted. Deleted/recreated groups, group/link drift and plan restoration are
normal repair cases, not reasons to deploy behind another activation flag.

Membership ownership requires `(id, user_id, creation_date)`, matching fixed group
identity and an earlier matching authorization event. Invalid provenance prevents
new grants and creates review work; it is not silently adopted as ownership.
Unprovable rows cannot be automatically removed or repaired by inventing receipts.
Deliberate DB/history damage still requires expert evidence review; neither automatic
login reconciliation nor the repair action rewrites immutable history to hide it.

There is no background retry worker/outbox, automatic term completion, student-portal
lookup, LINE push, second enrollment/account/catalog writer, or historical DB/file
restore as compensation. Actual historical migration and platform cutover remain
separate from routine class setup.

## HTTP contract

All routes reuse `/api/v1/academic-classes`, the native session and configured org.
Responses are private/no-store with Cookie/Authorization variation. GET retains the
existing CORS contract; POST requires exact origin and duplicate-cookie protection.
Bodies forbid unknown fields and use strict confirmations/IDs where applicable.

- `POST /connections/requests` — own verified timetable section; optional roster URL.
- `GET /connections/requests` — own requests, or administrator review/repair queue.
- `POST /connections/requests/{id}/preview` — administrator selects native course.
- `POST /connections/requests/{id}/connect` — confirmation, fingerprint, request UUID.
- `GET /{class_id}/learning-access/status` — assigned staff/admin status only.
- `POST /{class_id}/learning-access/retry` — reconcile existing approval or request setup.
- `GET /{class_id}/learning-access/preview?enabled=true&replace_group=false`.
- `POST /{class_id}/learning-access/apply` — reviewed configuration/recovery.

Access apply accepts optional positive `group_id`, strict `enabled`, strict
`replace_group` (default false), strict `confirm_changes`, 64-hex fingerprint,
32-hex request UUID and a meaningful reason. No environment activation flag is
required. A stale preview rejects before grants. Savepoints preserve atomicity even
when callers catch errors; the existing roster advisory lock orders cooperating
identity, roster and membership writers. Native administrators remain independent
writers, never silently overwritten.

## Validation

```sh
LEARNHOUSE_API_TEST_IMAGE=coursemax-learnhouse:learning-access-396d1a01 \
LEARNHOUSE_TEST_LEARNING_ACCESS=1 \
  bash deploy/staging/test_attendance_postgres.sh
python3 -B scripts/extensions/check_boundary.py
python3 -B -m unittest discover -s scripts/extensions -p 'test_*.py' -q
node --test apps/web/extensions/route66/tests/*.test.mjs
```

The disposable PostgreSQL/native-session suite covers connection authorization,
confirmation, source matching, real native HTTP READ before/after delegation,
no UPDATE/DELETE elevation, both arrival orders, conflicts, active sections,
withdrawal, plan/group recovery, manual/recreated rows, provenance, idempotency and
unchanged enrollment/progress evidence. Full corrected bundle, separate types and
compiled teacher/admin/student desktop/mobile journeys are required for this UI.
Synthetic provider/quota/MFA fixtures and browser bootstrap are not genuine provider,
institutional student, full license, device, migration or parity acceptance.
