# Interior custom UI

## Review decision

Retained `ea53a354`'s controlled native Radix behavior, lazy loading, mounted drafts and class search. The navigation hierarchy was subsequently flattened after owner feedback, as recorded below. The review baseline had 75 passing web checks and four real-component teacher/student browser journeys; subsequent enhancement and deployment are recorded below.

Enhance consistency rather than replacing those controls. Existing surrounding inputs, blue source navigation and flat source panels do not yet share Interior's material vocabulary. Do not restore the earlier archived alternate tabs/press-state implementation.

## Hierarchy correction after owner review

The owner screenshot exposed a missed composition problem: three equally prominent
navigation rails crowded out the class task. Earlier isolated-control checks did not
validate that hierarchy in the real account shell. The classes page now has one native
rail for NRRU classes, LearnHouse classes and School calendar, with mounted panels and
the existing selection/refresh behavior retained. Duplicate account links and generic
intro copy are removed; identity access remains in the native sidebar/mobile navigation.

Correction deployed as `5c8007ae` / `coursemax-learnhouse:classes-navigation-20261017`.
78 source checks, confirmed production bundle/types, four teacher/student journeys in
the actual compiled Next account shell at EN1060/TH390 (including empty term), and two
live read-only login/navigation journeys pass. Native API and protected evidence remain
unchanged; no institution/provider acceptance is implied.

## Direction contract

**THESIS** One tactile, task-first custom interface, preserving the working school/class/calendar organization.

**OWN-WORLD** Owner-pinned Interior at `314800833bf01e23e6ae74c2a17fbdaac3688c84`. White bezel, lifted panel, recessed well and pressable cap. Native LearnHouse typography, including Thai; blue means selection/information, green success, red errors. Preserve meaningful weekday colors.

**STORY** Find the class, read its source facts, then perform the next task. Identity, membership, account matching, calendar publication and schedule application remain separate.

**FIRST VIEWPORT** Keep native account navigation and one compact class-workspace rail. No repeated account links or nested source/subtab rails. Put class facts and term choices immediately below, search directly above its rows, and calendar review before its original-source panel. Keep bounded sign-in/link forms.

**FORM** Operate mode, user-pinned direction, code-led. The signature is the raised selected cap in a recessed navigation rail, with a small button depression. Native keyboard, pointer cancellation and focus behavior remain authoritative; reduced motion removes travel. No new animation dependency.

**FINISH** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Provenance and scope

Upstream https://github.com/ddoemonn/interior, MIT, copyright 2026 ozzy. Reviewed `app/globals.css` and `components/interior/{tabs,segmented-control,loading-button,accordion,press-depth}.tsx`. The pinned upstream commit has no `DESIGN.md`. Adapted material CSS and its MIT notice live in `apps/web/extensions/route66/components/interior/`.

Native controls already supply form submission, disabled/pressed behavior, date/select semantics, focus and dialog/tab cancellation. Keep those authorities rather than copying the demo async timer. The shared component consolidation below adds controlled radio keyboard navigation only where earlier feature-specific choice rails had none. Shared styling is scoped to custom feature roots, never the native shell or organization administration. Existing requests, confirmations, permissions and saved evidence are unchanged.

Active surfaces include school identity and timetable, sign-in methods/provider buttons, auth link/callback/LIFF, class connections and rosters, attendance/check-in/receipts, calendar preview/editor and class schedule views. Retired preview fixtures stay untouched. No new raster assets.

## Shared component consolidation — 2026-10-17

Interior is the persistent standard for existing/new custom modules, not just a CSS
reference. `adapters/ui.ts` now exports a shared Interior `Button` wrapping the
native button/Slot; all existing custom consumers inherit it. Provider/link/retry,
identity search, connection and calendar actions use controlled reserved-space
loading labels. Request owners still decide busy/result state; no demo success timer.

`CopyButton`/`useCopyToClipboard` replace attendance and LIFF clipboard implementations.
Modern API, fallback, visible/live error feedback, focus restoration, feedback reset
and unmount cleanup share one implementation. The five bespoke class/calendar choice
rails use `SegmentedControl` with controlled radio selection, roving focus, disabled
skipping and arrows/Home/End. Native Radix tabs retain mounted drafts/search; native
dialogs retain Escape/focus/privacy behavior. Native date/select/disclosure and
calendar-grid controls already fit their tasks and remain native. No new dependency,
backend/auth state, native-shell restyle, branding asset or boundary exception.

Additional reviewed upstream files at the same pinned MIT commit

| Source | SHA-256 | Adaptation |
| --- | --- | --- |
| `loading-button.tsx` | `73d3ef59e0894c0fceb225240f02fa746cb852f1955a6a1e526609a9495e3051` | Native button with CSS reserved label faces; no demo controller/motion dependency |
| `copy-button.tsx` | `ad4e1da987540d9aea9a0412259a811aa04a3a751c4793aef188be4e70e54319` | Headless clipboard hook plus native shared button; fallback/focus/error/unmount recovery |
| `segmented-control.tsx` | `6252ce52d2ca9f53067ea90f84641c35cc49620362e5377c710edfd6fe4149af` | Controlled radio choices; CSS selected cap instead of animated layout state |

The MIT notice remains beside these adaptations. No upstream `DESIGN.md` exists at
the pin; the maintained local `components/interior/DESIGN.md` describes the adaptation.

Reproducible component-browser contracts (reviewed dependencies, no installation)

```sh
NODE_PATH=<reviewed-web-node_modules> \
PLAYWRIGHT_MODULE_PATH=<playwright-module> \
PLAYWRIGHT_BROWSERS_PATH=<reviewed-browsers> \
LEARNHOUSE_NATIVE_WEB=<compiled-native-web> \
LEARNHOUSE_UI_EVIDENCE=<private-output-directory> \
BUN_BIN=<bun> node apps/web/extensions/route66/tests/interior-controls.browser.mjs
```

Validation passes 83 web source contracts, six attendance-client tests/44 assertions,
18 deduplicated real-component EN/TH desktop/mobile journeys (including the committed
shared-control contracts), three compiled-native-shell journeys, the full native
bundle and independent generated-route TypeScript. The native build caught and fixed
a clipboard prop-name type collision before packaging. One batched screenshot review
preserved the existing hierarchy and opaque projector. No new raster assets.

Evidence is private at `interior-consolidation-20261017/`. Deployment is not implied
by these checks; see the newest deployment entry. These synthetic contracts do not
establish real provider/device/institutional acceptance.

## Initial deployment — superseded by navigation correction

Deployed 2026-10-17, frontend source `7c483a0171ab9210a4ed4d5f909dab18485a0630`.
78 web checks, full production bundle/generated-route TypeScript, 18 isolated
real-component EN1440/TH390 flows and two fresh-native-login live read-only calendar
flows pass. Fixed selected-source specificity and reduced-motion travel in one bounded
visual pass and final confirmation. No page errors/overflow; detector returned `[]`.

The 1,027 actual-parent API files remain byte-identical. Native shell/image Config,
permissions, saved academic/calendar evidence and security policies are preserved;
no migration or institutional parse/publication/schedule apply. The exact previous
calendar-dates image is retained for compatible code rollback. Real Google/LINE
exchange, owner-browser/device and institutional acceptance remain unchecked.
See [deployment.md](deployment.md) for the live image and evidence pointers.
