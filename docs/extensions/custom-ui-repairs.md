# Custom UI audit repairs — deployed 2026-11-04

Live source `e142f6e35ae045e330f8fd6872ea671a2727deab`, image
`310ed40ac89d145aad2967e505b59bcfd917629eccf55f8d22f566949ac6320c`.
Release `ui-repairs-e142f6e3-20261104`, activated 08:09 UTC.

The eight findings from the private `CUSTOM-UI-AUDIT-2026-11-04.md` are repaired:

- **F01:** Lazy-mount administrator reviews once, then hide rather than unmount.
  Keep schedule planning mounted across Details/Official roster and saved-roster review.
- **F02:** Focus the member reason field immediately after opening its inline editor;
  Close restores the originating member action. No new dialog or writer.
- **F03:** Enabled shared input/select/textarea boundaries use `#858585` on white
  (above 3:1); decorative pale borders and the pinned light Interior bezel remain.
- **F04:** School recovery repeats the failed status, staff-search or Google operation,
  rather than guessing from existing status. Student status retry does not staff-search.
- **F05:** Shared class-loading failure/retry is above the tabs, visible on the default tab.
- **F06:** Schedule links directly to the existing saved-roster review and returns to the
  preserved planning draft. The full affected-student list and explicit large-drop
  acknowledgement remain required; the separate incomplete apply path was removed.
- **F07:** Google/LINE link recovery links retain native navigation with 44px minimum height.
- **F08:** Calendar filters compute one result collection and show localized no-match with
  Clear filters; clearing restores both filters and focus to the academic-year selector.

## Evidence

- GitHub run **41792969444**: full frontend bundle and types at exact live source.
- **46** focused source checks; **31** extension tooling checks and placement gate.
- **15** new real-component synthetic browser scenarios: EN1440/TH390 for admin,
  student status retry, staff search, schedule/large-drop handoff, calendar and both
  linking pages; extra EN320 long-roster focus test. Immediate focus/viewport checks,
  computed contrast, preserved drafts, explicit single apply, no page errors/overflow.
- **40** existing component regressions: 12 identity review + 28 roster-refresh flows.
- **Two packaged persisted native-auth workflows / six actor journeys**, EN1440/TH390:
  School request → teacher flag → administrator decision → My classes → private-course
  READ. Added packaged tab-draft, immediate editor focus and control-border assertions.
- **Four live anonymous entry/denial checks**, EN/TH ×1440/390, no page errors/overflow.
- Image proof: unchanged parent layers/runtime configuration, **1,265 unchanged API
  files**, **5,532 web entries**, **2,663 retained static assets**, exact BUILD_ID;
  complete saved archive with **76 verified blobs**.

Only app replaced/gateway reloaded. Owned launcher, schema, environment, limits,
mounts and DB/Redis/gateway IDs unchanged. Fresh quiesced database/schema/content
snapshots checksum-verified. Minimum observed activation RAM **3.073 GiB**, normal
admission, no override. No migration or live academic/identity mutation for testing.

Retain `b73530fb` parent/archive for code-only rollback; never restore older academic
history. One packaging candidate was rejected for wrapper-file permissions before
activation; corrected overlay passed full hash/mode verification. All isolated
fixture volumes removed after proof, builder stopped; no unrelated cleanup.

Private evidence: `~/.local/state/learnhouse-ui-repairs-20261104/`.
Synthetic/packaged checks do not establish real-provider/device, screen-reader or
200% zoom acceptance. The historical audit's 13/20 score is not retroactively changed;
this is focused repair verification, not a new full audit. Real scheduled registrar
`source_failed` diagnosis and broader identity/academic parity remain separate.
