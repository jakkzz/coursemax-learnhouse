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

## Direction contract

**THESIS** One tactile, task-first custom interface, preserving the working school/class/calendar organization.

**OWN-WORLD** Owner-pinned Interior at `314800833bf01e23e6ae74c2a17fbdaac3688c84`. White bezel, lifted panel, recessed well and pressable cap. Native LearnHouse typography, including Thai; blue means selection/information, green success, red errors. Preserve meaningful weekday colors.

**STORY** Find the class, read its source facts, then perform the next task. Identity, membership, account matching, calendar publication and schedule application remain separate.

**FIRST VIEWPORT** Keep native account navigation and one compact class-workspace rail. No repeated account links or nested source/subtab rails. Put class facts and term choices immediately below, search directly above its rows, and calendar review before its original-source panel. Keep bounded sign-in/link forms.

**FORM** Operate mode, user-pinned direction, code-led. The signature is the raised selected cap in a recessed navigation rail, with a small button depression. Native keyboard, pointer cancellation and focus behavior remain authoritative; reduced motion removes travel. No new animation dependency.

**FINISH** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Provenance and scope

Upstream https://github.com/ddoemonn/interior, MIT, copyright 2026 ozzy. Reviewed `app/globals.css` and `components/interior/{tabs,segmented-control,loading-button,accordion,press-depth}.tsx`. The pinned upstream commit has no `DESIGN.md`. Adapted material CSS and its MIT notice live in `apps/web/extensions/route66/components/interior/`.

Native controls already supply keyboard navigation, disabled/pressed behavior, date/select semantics, focus and dialog cancellation. Keep them instead of copying a second headless controller or the demo async timer. Shared styling is scoped to custom feature roots, never the native shell or organization administration. Existing requests, confirmations, permissions and saved evidence are unchanged.

Active surfaces include school identity and timetable, sign-in methods/provider buttons, auth link/callback/LIFF, class connections and rosters, attendance/check-in/receipts, calendar preview/editor and class schedule views. Retired preview fixtures stay untouched. No new raster assets.

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
