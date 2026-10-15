# Registrar timetable color pass — source-ready

2026-10-15. Scoped `colorize` refinement of the Registrar timetable in `/classes`, preserving the native LearnHouse visual system. Not deployed; live remains `7fe104c9`.

## Color roles

- Cool blue information hierarchy: softly tinted header, dark-blue titles, course/section identifiers and selected-term context. Read-only provenance remains explicit.
- Blue-bordered controls with existing keyboard focus and neutral surrounding surfaces. No new primary action or animation.
- Traditional Thai weekday categories: Monday amber, Tuesday pink, Wednesday green, Thursday orange, Friday sky blue, Saturday violet, Sunday rose. Clock icon and the original day label remain visible. These are weekday categories, not attendance or identity states.
- Unknown/combined source labels use a neutral category; never infer a day or rewrite the authoritative label. Thai/English full names and common abbreviations share categories.
- Header supporting copy uses the blue foreground family on its tinted surface. White course rows and neutral room details preserve reading contrast. Forced-colors mode uses system Canvas/CanvasText and an outline on day labels.

## Owned changes

Only `apps/web/extensions/route66/` implementation/tests:

- `components/Objects/Account/subpages/SchoolTimetable.tsx`
- `components/Objects/Account/subpages/timetable-colors.module.css`
- `components/Objects/Account/subpages/timetable-colors.ts`
- `tests/timetable-colors.test.mjs`

No native hook, global design/token policy, dependencies, API, authentication, course assignments, enrollment, registrar facts, academic data or privacy authority changed. Existing request, source, term persistence and search semantics remain.

## Validation

- New synthetic category tests failed before implementation. All 33 web regressions and 13 boundary-tool tests pass; source-placement policy unchanged.
- Full production build and generated-route TypeScript checks pass using retained `coursemax-learnhouse:7fe104c9` build image.
- Four compiled English/Thai 1440/390 teacher task flows pass: term/search/reload, source failures/retry, both school tabs and assigned-roster return. Seven weekdays plus neutral fallback exercised, with original Thai/English labels and repeated meetings. Zero academic writes/page errors/horizontal overflow.
- Computed minimum normal-color contrasts: day labels 7.97:1, header text 8.11:1, control borders 3.76:1. Header/weekday/control text meets 4.5:1 and control boundaries 3:1.
- Forced-colors mode preserves labels and system-color outlines. Deuteranopia, protanopia and tritanopia captures reviewed with labels retained. Color is never the only information channel.
- Mechanical detector ran once with no findings; bounded batched desktop/mobile review. Inline review, not independent. Contrast harness resolves transparent native-input backgrounds against the actual ancestor surface rather than treating transparency as black.

Protected evidence/build archives are outside the repository under `timetable-color-20261015` and `timetable-color-web-20261015`. No build artifacts or private screenshots added to source. No deploy, image switch, database/account/roster changes, student account setup, messages or cleanup. Deployment remains subject to its normal approval/backups/retained compatible image/baked/live gates. This is visual task acceptance, not institutional or full academic parity acceptance.
