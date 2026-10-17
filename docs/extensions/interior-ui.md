# Interior custom UI

## Review decision

Keep `ea53a354`'s NRRU class-list/calendar subtabs. Its controlled native Radix tabs, lazy loading, mounted drafts and class search are useful working behavior. Baseline has 75 passing web checks and four real-component teacher/student browser journeys. This is source readiness, not a deployed production build.

Enhance consistency rather than replacing those controls. Existing surrounding inputs, blue source navigation and flat source panels do not yet share Interior's material vocabulary. Do not restore the earlier archived alternate tabs/press-state implementation.

## Direction contract

**THESIS** One tactile, task-first custom interface, preserving the working school/class/calendar organization.

**OWN-WORLD** Owner-pinned Interior at `314800833bf01e23e6ae74c2a17fbdaac3688c84`. White bezel, lifted panel, recessed well and pressable cap. Native LearnHouse typography, including Thai; blue means selection/information, green success, red errors. Preserve meaningful weekday colors.

**STORY** Find the class, read its source facts, then perform the next task. Identity, membership, account matching, calendar publication and schedule application remain separate.

**FIRST VIEWPORT** Keep native account navigation and the new NRRU subtabs. Compact source/task navigation above class facts, search directly above its rows, calendar review before its original-source panel. Keep bounded sign-in/link forms.

**FORM** Operate mode, user-pinned direction, code-led. The signature is the raised selected cap in a recessed navigation rail, with a small button depression. Native keyboard, pointer cancellation and focus behavior remain authoritative; reduced motion removes travel. No new animation dependency.

**FINISH** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Provenance and scope

Upstream https://github.com/ddoemonn/interior, MIT, copyright 2026 ozzy. Reviewed `app/globals.css` and `components/interior/{tabs,segmented-control,loading-button,accordion,press-depth}.tsx`. The pinned upstream commit has no `DESIGN.md`. Adapted material CSS and its MIT notice live in `apps/web/extensions/route66/components/interior/`.

Native controls already supply keyboard navigation, disabled/pressed behavior, date/select semantics, focus and dialog cancellation. Keep them instead of copying a second headless controller or the demo async timer. Shared styling is scoped to custom feature roots, never the native shell or organization administration. Existing requests, confirmations, permissions and saved evidence are unchanged.

Active surfaces include school identity and timetable, sign-in methods/provider buttons, auth link/callback/LIFF, class connections and rosters, attendance/check-in/receipts, calendar preview/editor and class schedule views. Retired preview fixtures stay untouched. No new raster assets.
