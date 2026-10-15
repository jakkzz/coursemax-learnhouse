# Teacher planning preview

Status: corrected source validated; owner approved staging deployment. Packaging/live acceptance pending. Owner confirmed all three meanings of class table (weekly grid, dated teaching plan, roster), and a teacher-only clickable preview first. Audit areas B01–B03/C01; no parity acceptance or real academic writer implied.

## Direction contract

**THESIS:** Extend My classes with one clearly labelled teaching-preview entry. Separate the weekly pattern, dated semester plan, roster and course-wide syllabus instead of hiding all setup under attendance or school identity.

**OWN-WORLD:** Inherit LearnHouse native sans typography, white grouped data surfaces, blue wayfinding/read-only provenance and existing labelled weekday colors. Neutral data first; amber identifies review exceptions. Teachers work in a normally lit classroom/office; preserve the existing light workspace and native controls.

**STORY:** Select a fictional section, inspect weekly meetings, combine sample calendar/outline into a reviewable dated proposal, accept only in memory, review a sample roster diff, and inspect a shared syllabus. Every screen says this is fictional and not connected to the registrar.

**FIRST VIEWPORT:** Exit-to-My-classes action, concise preview disclosure, course title and section selector, then compact task navigation and the selected task. Overview leads with one next decision, not a metric wall. Signature interaction: one proposal feeds a dated plan and its attendance handoff while keeping closure and make-up visibly linked.

**FORM:** User-confirmed extension of existing My classes and the proposed course/class task grouping, not a new visual identity or open page concept tournament. Code-led; no image assets or image-generation tools needed. Preserve unrelated `.impeccable/`; this owned document holds the development-only surface contract.

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Boundaries and placement

Native LearnHouse remains account/course/content/access authority; extension owns existing institutional class/roster/attendance services. This preview introduces no backend authority, native hook, route, grant, school search, academic write or enrollment bridge. All proposal/roster/review interactions are fictional component memory, discarded on exit/reload, with no storage or API client in preview modules. Native styling remains authoritative; DESIGN.md does not change.

Owned files: ClassesWorkspace.tsx integration; teaching-preview/{TeacherPlanningPreview.tsx,model.ts,copy.ts,preview.module.css}; tests/teacher-planning-preview.test.mjs; this document. Entry shown only for existing server-projected staff discovery or manageable classes; discovery is not permission to create real classes. No student account setup/manual student flow. Existing REST/WS authorization untouched.

Weekly grid collapses to labelled day groups on mobile. The dated plan groups meetings by week and identifies closure/make-up/delivery separately from topics. Roster search/filter/review preserves sample manual members, stable IDs, missing-once active entries and withdrawn history. The syllabus is clearly course-wide and shared by both sections, read-only with simulated review, not a second authoring system or configured Gradebook. Publication/import/generation backends remain future work.

## Validation — source-ready, not deployed

- All 41 current web tests, the source-placement gate and 13 boundary-tool tests pass with no new native hook. Initial before-implementation test failure is retained.
- **Corrected final production bundle and generated-route TypeScript pass.** Accepted archives are `teacher-planning-preview-web-confirm-20261015`. The earlier terminated attempt remains failed evidence, not acceptance. A private build-script copy extends only bounded TypeScript/polling timeouts; CPU/memory limits, safety floors and artifact checks remain unchanged.
- Six final compiled EN/TH1440/930/390 teacher journeys pass against the corrected bundle: existing School/classes behavior, all five views, weekly grid/section selection, closure/make-up review and invalidation, roster search/filter/cancel/review/apply, shared syllabus, section isolation, exit/reload discard and return-focus restoration. Zero preview academic/school API calls, academic writes, page errors or horizontal overflow. Selected-task navigation contrast is at least8.01:1. This is synthetic teacher acceptance, not genuine institutional/student acceptance.
- Mechanical detector ran once: no findings. One correction batch resolves verbose mobile hierarchy/navigation and ambiguous select names. Batched final visual confirmation and finish review pass; review is inline, not independent. Existing DESIGN.md and unrelated `.impeccable/` remain unchanged; no shipping raster assets.
- Owner explicitly approved deletion of exactly two rebuildable tmpfs UI copies. Their accepted archives were checksum/full-tar verified first; Docker mount/accessibly visible process checks and deletion manifests retained. Container/image/volume ID sets remained unchanged. No other cleanup, pruning, service restart, backup/image removal or live academic/account mutation. Available RAM recovered above3GiB before the accepted retry.
- Protected evidence: `teacher-planning-preview-20261015`, with final browser reports/captures under `confirmation/`, cleanup record, accepted build/type logs and inline review. Original and failed artifacts remain preserved. Owner subsequently approved staging deployment. Packaging, baked verification, protected backups/rollback and live checks are required before advancing the release pointer. Parent is healthy `4d9b24e0`; no academic writer or real-data setup authorized.
