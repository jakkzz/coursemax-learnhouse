# Institutional mapping / API-boundary dry run

## Source inclusion review — 2026-10-17

Restored from the private cleanup archive at the owner's request and rechecked
against `7b601298`. **77 focused tests pass**: 30 planner, 22 mock-HTTP and 25
attendance-policy regressions. A current-contract regression was corrected: school
classes may have `course_id: null`. Unrelated unmatched rows no longer invalidate a
valid mapping; exact unmatched rows still require authority review, and duplicates
remain ambiguous. No automatic linking, runtime registration, deployment or data
change is introduced.

The findings and pinned-image proof below are historical. The native learning-access
bridge has since been implemented; see [learning-access.md](learning-access.md).
This advisory rehearsal neither replaces it nor defines the current product backlog.

## Historical scope and decision

Owner requested a dry run and cost-effective, sequential GPT-family implementation.
This implements an **offline advisory planner and mock-only HTTP rehearsal**. It
DOES NOT replace the agreed internal extension with an independent service, enable
an import/enrollment writer, configure real classes, or deploy anything.

Audit IDs: A05/A06, B01/B02, O04/O05. None is accepted in full by this work.
Inspected source: `81e6e2b5` (documentation HEAD; deployed application source remains
`bf4f2908`). Pinned upstream baseline: `45cf5d4f78cf537064070dc8e315a64990d14966`.

**Current architecture remains:** browser → our extension's FastAPI endpoints →
extension tables/shared native database session. Native LearnHouse owns accounts,
sessions, courses, content and learning access. Our extension owns institutional
bindings, teacher assignments, classes, rosters and academic evidence. CourseMax
is not a runtime dependency. A native course ID is not an institutional class ID.

Recommendation: keep this deployed boundary until a separately reviewed API-only
contract proves equivalent authorization, concurrency, access and retention. HTTP
separation alone would not remove the extension's database/native-adapter coupling.
See [development.md](development.md) and [dry-run.md](dry-run.md).

## Observed API capabilities, not presumed support

| Need | Inspected source / endpoint | Finding |
| --- | --- | --- |
| Native course read/create/update | `src/routers/courses/courses.py`: `/api/v1/courses/id/{course_id}`, `/api/v1/courses/{course_uuid}`, `POST /api/v1/courses/` | Native APIs exist; course authorization and feature gates remain final. Titles/codes are never crosswalk identity. No native course is created here. |
| Institutional course/teacher mapping | `route66_ext/routers/academic_classes.py`: `GET /api/v1/academic-classes/courses`, `POST .../teaching-assignments` | OUR extension APIs, not upstream APIs. Explicit superadmin review; mutation appends an event and commits shared DB state. Null mapping/code means unconfigured, not an empty roster. |
| Term/section class | Same module: `GET/POST /api/v1/academic-classes`, `POST .../{class_id}/configuration` | Existing institutional APIs enforce explicit binding, authority, uniqueness/version and unused-class correction. No title-based inference. |
| Official roster | Same module: `GET .../{class_id}/roster`, `POST .../{class_id}/roster/preview`, `POST .../{class_id}/roster/apply` | Reviewed source import already exists. Preview contacts the registrar and writes a Redis preview; it is NOT an offline dry run. Apply requires actor/org/class/version-bound confirmation. Neither endpoint is called here. |
| Service authentication | `route66_ext/routers/school_identity.py::context` | Requires a native `PublicUser`; `APITokenUser` is rejected. An independent service cannot simply reuse these routes with an org API token. No copied browser session, token impersonation or caller actor-ID workaround. |
| Native enrollment/access | `src/routers/admin.py`: `POST /api/v1/admin/{org_slug}/enrollments/{user_id}/{course_uuid}`, `GET .../courses/{course_uuid}/access/{user_id}` | Native APIs exist. Require API-token authentication, org/rights and plan checks. `src/services/admin/admin.py::_resolve_org_slug` explicitly checks Pro; do not assume edition/plan eligibility or bypass it. Actual entitlement/auth compatibility was not tested by this dry run. |
| Safe retry/effects | `src/services/admin/admin.py::enroll_user` | Multiple commits, existing enrollment returns 400, analytics emitted. Not an atomic transaction with institutional mapping/roster apply. Needs reviewed idempotency/reconciliation and side-effect handling, not blind POST retries. |
| Withdrawal/history | Same service: `unenroll_user`; native bulk unenrollment | Deletes trail steps/progress and enrollment. NOT a safe registrar-withdrawal operation. Never use it as automatic reconciliation or compensation. |
| Even read-only HTTP | `src/services/api_tokens/api_tokens.py::validate_api_token_for_auth` | Successful token authentication can update last-used/hash state. GET is not inherently a zero-write live operation. This rehearsal uses no live requests or credentials. |

No upstream-only public API was established for our institutional crosswalk or
stable exact verified-number evidence. Do not substitute public profile/email/name
lookups for provider-owned identity. Account creation/merging and student matching
are outside this rehearsal; no student records are loaded.

## Implemented, sequential slices

1. **Pure planner:** `apps/api/src/route66_ext/services/mapping_dry_run.py`.
   Inputs are explicitly selected synthetic native course/teacher IDs plus exact
   official course ID, academic year, semester and section, and two API-shaped
   snapshots. All exact class candidates are counted before class ID/manageability
   checks. Duplicate malformed/nonmanageable candidates cannot disappear.
2. **Mock HTTP adapter:** `apps/api/src/route66_ext/adapters/mapping_dry_run_api.py`.
   Reads only the two existing extension projections using HTTPX `MockTransport`
   at a fixed `.invalid` origin. A real/default/subclass transport is rejected.
   No production mode, configurable origin, auth/cookies, redirects, retries,
   registrar requests or write method. Fresh clients prevent response-cookie
   propagation. Bodies are streamed/capped at 256 KiB; each read has a two-second
   deadline (four seconds maximum for both). Private/no-store JSON is required;
   duplicate keys, non-finite numbers, bad responses and ordinary handler/stream
   failures are redacted. Cancellation propagates. Mock handlers are trusted Python
   test code, not a sandbox for arbitrary code.
3. **Tests/review:** matching tests under
   `apps/api/src/route66_ext/tests/services/test_mapping_dry_run*.py`.
   GPT proposals were parent-reviewed before application, not blindly copied.

Every report contains `writes_performed: 0`, `authorization_granted: false`.
Even `linked` means **review a roster preview**, not import or access granted.
A missing class in an actor-scoped/redacted snapshot means review class setup,
NOT verified real-world absence or permission to create it. Non-admin catalog
responses conceal assignment lists: `assignment_review_required` means not
established by this snapshot, never a claim that the teacher has no assignment.
The admin capability flag cannot establish the selected teacher's assignment.
Course IDs 17 and 22 stay separate even with identical title/official identifiers.

There are no native edits/hooks, new routes/bootstrap registrations, migrations,
new dependencies, UI changes, grants, runtime configuration or authority transfer.
This module is not imported by the running application. No production web build or
live browser acceptance is claimed for this non-UI, unregistered source work.

## Historical observed validation

- 49 new offline tests: 27 planner + 22 mock-HTTP; 25 existing attendance-policy
  regressions also pass (**74 total**).
- Same 74 tests pass with Python **3.14.7** and pinned cached application image
  `coursemax-learnhouse:bf4f2908`: no network, read-only source/root, non-root UID,
  all capabilities dropped, no app/data/runtime volumes, bounded 384 MiB/0.5 CPU.
  Host Python 3.12.3/HTTPX 0.28.1 run also passes; target dependency pin is unchanged.
- Six synthetic HTTP scenarios pass: unavailable course, missing mapping, unverified
  assignment, setup review, exact link, ambiguous duplicate. Zero live requests.
- Source-placement gate, 13 boundary-tool tests, 41 existing web tests pass.
- Expected pre-implementation failures and the review-finding failing regressions
  are retained privately, not rewritten as successful evidence.
- Three GPT-5.6-luna calls completed **strictly sequentially**: two implementation
  proposals (low thinking), one bounded review (medium). Tools/context discovery/MCP
  disabled for workers; only supplied synthetic contracts/source were provided.
  Separate review identified ordinary fixture exception leakage; parent added two
  failing tests, fixed the boundary and reran all tests. This is bounded model
  review plus parent closure, not independent post-fix runtime/security acceptance.
- Worker usage: 16,969 reported tokens; catalog-estimated worker cost approximately
  $0.0103. Not invoice-verified, not a cheapest-model comparison, and excludes parent
  usage. No settings/model catalog/auth changes or model downloads.

Reproduce from the fork (HTTPX already pinned; no installation needed):

```sh
(cd apps/api && python3 -B -m unittest \
  src.route66_ext.tests.services.test_mapping_dry_run \
  src.route66_ext.tests.services.test_mapping_dry_run_api \
  src.route66_ext.tests.services.test_attendance_policy -v)
python3 -B scripts/extensions/check_boundary.py
python3 -B -m unittest discover -s scripts/extensions -p 'test_*.py' -q
node --test apps/web/extensions/route66/tests/*.test.mjs
```

## Historical ordered implementation recommendations

1. **Choose the runtime boundary explicitly.** The approved internal-extension
   architecture stays in force. API-only separation is an evaluated option, not
   silently approved by this dry run. Freeze existing native auth/retention patches.
2. **Prove native authority/auth/edition contracts offline.** Verify supported native
   enrollment/access behavior and entitlement with synthetic native HTTP integration
   tests; design any delegated service authority without copied sessions, issuing
   impersonated user tokens, trusting client actor IDs, a second login or privileges
   inferred from school identity. Never widen grants, token rights or license gates.
3. **Implement one safe enrollment/access integration**, only once the boundary is
   reviewed. Preserve stable accounts, manual/native grants, progress and evidence.
   Evaluate eligibility across every relevant active class: withdrawal from one
   section must not revoke another section's valid access. Do not use destructive
   unenrollment or re-enrollment resets. A separate process needs durable command
   receipts/idempotency, rechecks, reconciliation and recovery, not imaginary
   cross-HTTP transactions or a competing academic writer.
4. **Finish reviewed setup UX/source handoffs** to existing mapping/assignment/class
   and preview/apply authorities; exact official IDs and a chosen native course,
   never timetable-derived authorization. Real configuration/import remains separate
   from a source-only dry run, with its own reviewed evidence/authority.
5. **Native task acceptance and release:** permission/concurrency/retention tests,
   persisted teacher/student EN/TH desktop/mobile tasks, full corrected web build
   if UI changes, baked-source verification, capacity/backups/app-only recovery.
   No release, student import, enrollment bridge, full parity or cutover accepted
   by the mock tests. No old DB/files restored for rollback.

For the present unregistered source slice, recovery is simply not wiring it into
runtime; existing deployed image/schema/data stay unchanged. No destructive cleanup
or data rollback is needed or authorized.
