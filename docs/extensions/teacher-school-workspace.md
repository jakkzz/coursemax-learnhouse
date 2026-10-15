# Teacher school workspace — deployed

2026-10-15. Live source/image **7fe104c9** at `learn.route66.click`. Scoped refinement of `/classes` and `/account/school-identity`, preserving LearnHouse's native visual system and existing URLs. Audit context: B01/B02/C10; this does not accept those items in full.

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

The owner approved staging deployment after source acceptance. Frontend-only image `coursemax-learnhouse:7fe104c9` overlays the exact attendance-capable `fe1877c9` parent. 5,283 desired web entries verified against baked bytes/links/modes; all 995 measured backend/configuration/migration files remain identical. Source committed and pushed only to the owner-controlled fork; no upstream changes or push.

Protected DB/content/runtime backups and a saved/checksummed `fe1877c9` rollback image are retained. The fresh database backup was restored over an isolated, network-disabled PostgreSQL socket and identities matched; content/runtime archives and checksums passed. This is not coordinated off-host DR acceptance.

Only the staging app was replaced; the existing gateway reloaded. Other container IDs, runtime files/environment, identity profiles/provider ownership and audited grants are unchanged. Schema dumps match except random pg_dump restriction markers. No migration, backfill, real import, account/assignment/roster change, proactive message or broad host mutation. Existing source-menu link updated through the supported native API to the exact deployed revision. No student account setup or manual student testing.

Four live English/Thai 1440/390 native-bootstrap workspace flows and two native-auth flows passed without school/academic writes, page errors or overflow. Private/no-store, foreign-origin denial and anonymous denial checks passed. The native bootstrap did not impersonate an institutional teacher. Separately, the owner's manually signed-in teacher Chrome verified identity → classes, semester selection, search/clear and reload persistence against their own actual read-only registrar timetable. This does not approve class mappings, rosters, enrollment integration or institutional staff status.

Current protected release record: `releases/teacher-7fe104c9-20261015` outside Git; final build archives and test evidence remain protected. Compatible code rollback retains the live database, identities and all new academic evidence; never restore an old database for a UI rollback. Inline review, not independent; remaining provider/device, private-file and full academic parity gates remain separate.
