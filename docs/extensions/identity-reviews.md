# School identity review

## Current scope — 2026-11-04

Deployed at 2026-11-04 04:58 UTC: source `53d3d248`, image `b73530fb`, healthy at
`https://learn.route66.click`; release `identity-53d3d248-20261104`. This is the
student-record review slice, not full identity/provider acceptance.

- Students request review from Account → School identity or a conflicted My classes
  view. The server attaches their verified-number/owned roster record; no IDs to type.
- Teachers use the existing roster Flag identity action, then view/refresh its request
  and result in the same saved roster. Identical retries reuse the open request;
  a different report cannot silently replace its original reason.
- Existing platform administrators open My classes → Identity reviews. They see
  the saved student/class context and current organization-scoped account evidence.
  Confirm verified match invokes the existing exact-match writer and native course-
  access repair. Close without changing identity records that distinct outcome.
- A current-evidence token rejects stale/concurrent decisions; the shared academic
  transaction lock gives one decision. Notes survive stale UI responses.
- Existing conflicting ownership, multiple verified claims and separate manual/
  registrar records cannot be merged or transferred. Closing a report does not
  claim that an ownership conflict is resolved. Google re-sign-in and original-
  account recovery remain the appropriate user actions for those cases.

This is the student-record review slice, including teacher and administrator actions;
not staff-directory reassignment, general account recovery or full identity parity.
A genuine student's provider/device acceptance still requires their participation.

## One existing authority

`services/identity_reviews.py` projects requests/decisions over append-only
`AcademicClassEvent`. Existing teacher `identity_review_requested` events are readable
without backfill. New `identity_review_decided` events hold the reviewer, reason and
bounded current evidence. Private decision evidence is outside the raw class-event
feed; teachers/students receive scoped outcome projections, not private Google email
or subjects, other-user account details or administrator notes.

There is no new table, migration, account writer, enrollment writer, service or flag.
Unlinked records can only use `academic_rosters.reconcile`; existing ownership and
roster IDs are unchanged. Native READ repair reuses `learning_access.refresh_course`;
an optional access failure leaves identity matching intact and produces the existing
repair task. Roles, manual memberships and academic work are not transferred.

Routes are mounted through the existing owned academic router:

- `GET/POST /academic-classes/identity-reviews/own`
- `GET /academic-classes/identity-reviews?status=open|closed`
- `GET /academic-classes/identity-reviews/{case_id}`
- `POST /academic-classes/identity-reviews/{case_id}/decision`
- `GET /academic-classes/{class_id}/identity-reviews`

Existing native authentication, organization scope, manager checks, same-origin
writes and private/no-store responses apply. Administrator matching is not a new
institutional proof method: conflicting evidence cannot be approved.

## Focused evidence

Private evidence: `~/.local/state/learnhouse-identity-reviews-20261104/`.

- Final image passes 56 baked PostgreSQL/HTTP/parser/roster/boundary checks, including
  13 review/access
  tests: persisted requests and decisions, duplicate/stale/concurrent decisions,
  own-only/org scope, role denial, no ownership merge, deferred exact matching,
  School → My classes → native private-course READ, and optional access failure
  preserving an unrelated manual grant. Earlier source selection passed 45 checks;
  the duplicate-report refinement also passes the focused 13-test selection.
- 12 real-component teacher/admin/student EN/TH 1440/390 flows and 28 existing roster
  component regressions passed. Synthetic HTTP is not native-auth acceptance.
- Shared Interior controls/native tabs retained; mobile administrator navigation uses
  two rows rather than splitting the LearnHouse name. Inline review, not independent.
- GitHub run `41772137685` passes full bundle/types. Packaged EN1440/TH390 workflows
  cover six native-auth student/teacher/admin journeys: four persistent requests/
  decisions, two exact matches, School → My classes → native private-course READ,
  teacher receipts, private-note exclusion and student denial. The fixture was
  corrected to copy the actual owned launcher before these passing checks.
- Actual parent `d85f488b` reads the resulting synthetic history and private course;
  all eleven academic/identity/access fingerprints match before/after code rollback.
- 1,265 API files, 5,530 web entries and 2,646 retained assets verified. Saved image
  archive contains all 74 blobs. Four live EN/TH entry/denial checks, API hashes,
  BUILD_ID, unchanged schema/runtime/peer IDs and existing worker leadership pass.
- Normal admission RAM 3.41GiB/disk 31.57GiB; observed minimum 3.407GiB. Only app replaced
  and gateway reloaded, no migration or capacity override. Fresh quiesced DB/schema/
  content checksums pass. Keep compatible parent/current archives and current data;
  rollback is code-only and never deletes review or scheduled history.
- Boundary and 31 tooling checks pass. No real-data test shortcuts or real provider/
  device acceptance; a genuine student must still participate in that acceptance.

## Separate roster-refresh issue

The owner confirmed the configured NRRU roster file was correct and instructed us
to move on. Two scheduled attempts had recorded `source_failed` at the 2026-11-04
03:13 UTC check. Correct source content does not prove the automated fetch/parser
succeeded; that technical issue remains separate and was not changed by this slice.
