# Teacher school workspace — source-ready, not deployed

2026-10-15. Scoped refinement of `/classes` and `/account/school-identity`, preserving LearnHouse's native visual system and existing URLs. Audit context: B01/B02/C10; this does not accept those items in full.

## Teacher tasks

- Consistent My classes / School identity navigation with current-page semantics and keyboard focus.
- School identity concentrates on the owned directory record, the explicit self-confirmation limitation, and a direct route to My classes. Existing search, own-name confirmation, sign-in, student and conflict paths remain.
- Confirmed staff see their own read-only registrar timetable in My classes. It is not a teaching assignment, enrollment authority, or a second catalog.
- When no LearnHouse classes exist, the timetable is immediately available and the empty class state explains the required administrator assignment and term/section setup. Unused class-search controls are hidden.
- With existing LearnHouse classes, roster and attendance actions stay first; the registrar timetable is progressively disclosed and fetched only when opened.
- Timetable supports semester/year selection, course/section/day/room search, clear-search recovery, repeated meetings and truthful empty/error states. The chosen term survives reload within the browser tab, keyed by the owned staff record. No identity or roster data is stored in browser storage.
- Student-specific content and authority are not expanded; teacher introduction/help is selected only from the server's own staff projection. No student account was prepared or used for manual testing.

## Boundary and authorities

All implementation/tests are inside `apps/web/extensions/route66/`:

- `components/Objects/Account/subpages/{SchoolIdentity,SchoolTimetable,SchoolWorkspaceNav}.tsx`
- `components/Objects/Account/subpages/{school-workspace-model.ts,school-identity.module.css}`
- `components/Objects/Classes/{ClassesWorkspace,TeacherTimetable}.tsx`
- `tests/school-workspace.test.mjs`

No native hook added, edited, or removed. Native accounts/sessions/content/access and extension class/roster evidence retain their existing authorities. The UI uses authenticated own-only GET projections and existing native UI adapters. No backend, schema, migration, privileges, course assignments, enrollment, roster, academic history, feature flags or source-placement policy changed. Existing historical hooks remain frozen. Upstream remains pinned to `45cf5d4f`; this is not an upstream-update rehearsal.

## Validation

- Initial synthetic model test failed before implementation; all 30 web regression tests pass afterward.
- Source-placement gate and 13 boundary-tool tests pass, without changing the boundary policy.
- Full production web bundle and generated-route TypeScript checks pass from the final source using the retained `coursemax-learnhouse:fe1877c9` build image.
- Four compiled production teacher task flows: English/Thai at 1440/390. Each covers identity → classes → semester/search → reload → return navigation, school/timetable failure and retry, assigned-class roster open/return and collapsed timetable. Zero academic writes, page errors or horizontal overflow. Selected-navigation AA contrast and visible keyboard focus checked.
- Mechanical Impeccable detector: no findings. Batched desktop/mobile visual review and one final confirmation; review performed inline, not independently.
- Harness fixes: standalone server bound consistently for native proxy rewrites, URL/current-tab readiness awaited before navigation assertions, contrast measured after resolving CSS colors through the browser (including OKLCH). An initial eager timetable request race was fixed by waiting for class-list discovery before mounting the teacher context; final lazy-fetch assertions pass.

The owner's signed-in teacher account was inspected read-only through the approved LearnHouse browser origin. Compiled acceptance uses fictional teacher/API fixtures, not copied account sessions or institutional records. These tests do not establish new provider/device, institutional approval, native enrollment-bridge or full academic parity acceptance.

## Release boundary

No deployment, image switch, real import, account change or shared-host mutation performed. Live staging remains the existing `fe1877c9` release. Final build archives and protected test evidence are retained outside the repository. Deployment requires its normal approval, capacity, backups, retained compatible image, baked-artifact verification and live acceptance gates. Any later code rollback must retain the database, identities and all academic evidence; do not restore an old database for a UI rollback.
