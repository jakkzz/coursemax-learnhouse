# Roster-driven native learning access

**Backend implementation; not deployed or activated.** No real mappings, classes,
students, groups, grants, imports or migrations were created during development.
The existing integrated-extension boundary remains authoritative. This is not an
API-token service, an upstream plugin API, or a complete enrollment/parity port.

## Ownership

Institutional rosters decide eligibility; a reviewed native UserGroup supplies
private-course READ access through native LearnHouse RBAC. Enrollment, progress,
authorship, roles, publication and institutional teacher assignment remain separate.
The bridge never creates or modifies Trail, TrailRun, TrailStep, accounts, courses,
groups, course-resource links, roles, assignments, publication or student identities.
In particular, it never calls native destructive unenrollment.

A learner still enrolls through the ordinary native learning flow. Membership alone
is not enrollment and does not populate the enrolled-course dashboard or create
learning progress. The native course HTTP handler and resource checker remain final
access authorities, including publication, organization membership and feature gates.

## Explicit activation contract

Before activation, a platform administrator must have reviewed the exact official
course binding, native course, term/sections, teacher assignments and roster evidence.
Courses with different native IDs remain distinct; this bridge does not infer course
identity from names or codes, configure assignments or fetch the registrar.

The administrator selects an **existing empty dedicated native UserGroup** in the
same organization, with exactly one native resource link to that private course.
Creating that group and its link stays in the native administrative workflow and
its existing policy. **Linking a first group changes native “Users Only” access:**
a private course with no linked groups permits its signed-in organization members;
adding a group restricts that fallback. Review existing access/manual grants before
that separate native policy change. The bridge never adds the resource link or
claims such a restriction preserves every prior implicit reader. It cannot take
over an already-populated group.
Native course/group UUID ambiguity rejects, counting all candidates (including other
organizations) before trusting the selected numeric ID. Once selected, the group's
ID/UUID/org/course binding is permanent. It may be
disabled/re-enabled, but not reassigned to a different group or course.

### Inactive deployment guard

`ROUTE66_LEARNING_ACCESS_CONFIGURATION_ENABLED` defaults to `false`; only the exact
value `true` permits configuration apply after native authorization. Deployment does
not enable it. The optional owned `deploy/staging/learning-access.compose.yaml` and
`learning-access.env.example` document wiring, but are not applied for this inactive
release. Preview remains read-only. Enabling requires separate recovery/setup and
real-data authority review. Freezing new configuration does not stop reconciliation
of previously approved delegations or silently preserve stale grants. This release
requires zero existing bridge configuration events before deployment and rollback.

The existing `/api/v1/academic-classes` extension mount gains:

- `GET /{class_id}/learning-access/preview?group_id={id}&enabled=true`
- `POST /{class_id}/learning-access/apply`

Both use the existing native user session, same-organization membership and
platform-superadmin/native `usergroups.action_update` authorization. The existing
native Standard-plan check is retained; deployment mode/edition policy is not
reimplemented. Service tokens, caller-supplied actor IDs and copied sessions are
not substitutes. Responses are private/no-store. GET follows existing read/CORS
policy; POST additionally enforces the existing exact-origin/duplicate-cookie guard.

Preview reports eligible/add/remove/preserved-manual/waiting/conflict counts and
publication status, without names or student numbers. Apply requires:

```json
{
  "group_id": 30,
  "enabled": true,
  "confirm_changes": true,
  "expected_fingerprint": "<64 lowercase hexadecimal characters from preview>",
  "request_id": "<new 32-character lowercase UUID hex>",
  "reason": "Reviewed purpose of this synthetic example"
}
```

This is a schema example, **not permission or instructions to activate real data**.
Unknown fields, numeric substitutes for booleans, invalid IDs, missing confirmation
and stale previews reject. The digest binds actor, organization, selected course,
group identity/links/members, configuration, roster versions and eligibility/proofs.
A matching request retry returns its durable receipt; reusing the request identifier
with a different actor, class or payload rejects. A new intentional decision needs a
fresh preview/request ID. Preview takes a transaction lock but writes no grant or
configuration and does not contact the registrar or Redis roster-preview store.

## Eligibility and history

Eligibility is the union of active academic roster rows for the selected native
course across its sections/terms. A different native course never contributes.
Registry ownership requires an exact ten-digit verified canonical Google claim,
matching stable student ownership and no competing active claimant. Nine-digit
hints, names, personal email, profile edits and administrative status cannot confer
registry ownership. Manual roster rows retain their explicit selected-user authority
but still require current verified Google evidence and native org membership.
Unmatched or conflicting students are not granted access and are never transferred
or merged. There is no student-portal lookup or silent roster import.

After explicit activation, accepted roster imports, manual membership changes and
fresh Google reconciliation refresh the existing configured course within the same
caller-owned transaction and existing roster advisory-lock ordering. A new claimant
for another profile's exact number also refreshes that profile's course: ambiguity
revokes only the old bridge-owned grant, never transfers student ownership. Registry
withdrawal remains the existing two-accepted-missing-snapshot policy. Source failures
are not missing snapshots. Another active section preserves eligibility.

`AcademicClassEvent` stores append-only configuration, native membership provenance
and apply receipts; no schema migration is needed. Each owned native membership is
identified by exact `(id, user_id, creation_date)` plus its fixed group binding.
Membership events identify the initiating actor, reconciliation trigger and the
administrator configuration event that authorized automation. Malformed provenance
or inconsistent event/class/course bindings require review rather than being silently
ignored. Events are not rewritten or deleted.

Only exact bridge-created rows can be removed. Pre-existing/manual/recreated native
memberships are never adopted or removed. Other groups, authorship, manual grants,
roles, chosen names, enrollment IDs, grades and progress remain untouched. Disabling
removes only bridge-owned memberships, not every remaining route to access. No
compensating enrollment deletion or historical database/file restore is appropriate.

## Transactions, drift and operational limits

Native adapter operations flush but do not commit. Apply uses a savepoint so partial
configuration/grants/receipts roll back even if a caller catches an error and commits
its outer transaction. Our writers serialize and lock the native group/course; exact
request replays and concurrent identical applies create one grant/receipt. Native
administrators remain independent authorities: their non-cooperating changes are not
overwritten or treated as bridge ownership.

Unexpected group/resource/UUID/org drift, duplicate native rows, or native plan denial
fail closed. Enabled reconciliation rolls back its source transaction on failure;
**this can block an affected fresh Google login or roster change until administrator
repair**. There is no background retry worker or outbox. A disabled configuration
is not refreshed automatically. Restore the approved native group/link/plan before
reviewing a disable; a deleted/recreated fixed group or damaged immutable provenance
requires separately reviewed recovery, not automatic reassignment, privilege bypass
or historical evidence rollback. This operational recovery/UI path remains an
activation gate, not claimed solved by the backend tests. An inactive code deployment
is permitted only with configuration locked off and zero prior delegations, verified
before deployment; that does not authorize enabling this feature.

There is no scheduler to infer term completion, automatic native enrollment, API-only
service credential contract, full provider-retirement lifecycle acceptance, teacher
setup UI or real institutional student end-to-end acceptance in this slice. Genuine
institutional proof, real mappings/imports, full native enrollment UX and lifecycle/
recovery acceptance remain separately gated. No live activation is authorized here.

## Validation

Run the full isolated native PostgreSQL/auth/roster/attendance/boundary suite plus
learning-access tests using an existing compatible cached API image:

```sh
LEARNHOUSE_API_TEST_IMAGE=coursemax-learnhouse:bf4f2908 \
LEARNHOUSE_TEST_LEARNING_ACCESS=1 \
  bash deploy/staging/test_attendance_postgres.sh
```

`LEARNHOUSE_TEST_LEARNING_ACCESS_ONLY=1` additionally selects only the new access
and pure policy suites for iteration; it is not a replacement for the full gate.
The disposable fixture has no network or live volumes, uses synthetic credentials,
a Unix socket, dropped capabilities, read-only API root and bounded CPU/RAM/tmpfs.
Its WAL/tmpfs budget was increased after retaining an initial fixture-capacity failure.

The original suite passed 197 tests: 157 existing and 40 new (30 PostgreSQL/native
HTTP integration cases and 10 pure membership-policy cases). Inactive deployment
adds default-off, non-truthy configuration and continued-reconciliation gate
regressions (200 full tests). Native imports for this slice
are confined to the bounded production adapter and an unregistered test-only facade.
The 13 boundary-tool and 41 existing web tests also pass. Two sequential GPT-5.6-luna
workers supplied a bounded policy proposal and source review; final corrections and
review closure are parent-verified, not independent post-fix acceptance.

Tests cover actual native session-cookie HTTP preview/confirm/apply/retry and native
course HTTP access before/after grant/revocation, native feature guard and draft
rejection, no UPDATE/DELETE elevation, both arrival orders, exact-number conflicts,
multiple sections, two-snapshot withdrawal, manual/recreated membership retention,
plan denial, stale preview, malformed provenance, concurrency, caught-error rollback
and unchanged existing Trail/TrailRun/TrailStep evidence. External providers, usage
quota/MFA fixture defaults and synthetic identities are not real institutional or
edition/license/device acceptance. No browser/compiled-web acceptance is claimed:
this change does not alter the frontend.
