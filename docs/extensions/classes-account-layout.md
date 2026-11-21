# My classes — native account layout

## Scope and authority

Owner request: make My classes use the same layout as School identity. This is a
presentation change, not academic setup, migration or parity acceptance. `/classes`
and its server-side session guard remain unchanged.

The owned `ClassesAccountLayout.tsx` composes the same native presentation used by
`components/Objects/Account/AccountClient.tsx`: `GeneralWrapperStyled`, breadcrumbs,
a sticky 288/320px profile sidebar, a flexible content column, the mobile account
name and the native mobile actions bar. The shared School pages navigation still
selects My classes; native account links are not falsely marked as the current page.
Extra class-list and section-detail padding is removed so content aligns with School
identity. No native component, route delegate, boundary policy or historical patch
was edited.

## Adapter contracts

`extensions/route66/adapters/ui.ts` re-exports the existing native breadcrumbs,
sidebar, mobile actions, session context and organization URL helper. Display data
comes from the existing native session; there is no new account or navigation
configuration authority. Reimplementing the account menu or adding a core layout
hook was unnecessary.

The native outer shell reserves mobile footer space only for account URLs. The
owned `classes-account-layout.module.css` supplies that same 6rem plus safe-area
clearance below 48rem, scoped to `.lh-org-font-root:has(.accountWorkspace)`. This is
an explicit **visual DOM contract**, not an upstream-supported plugin API: review
the shell class, breakpoint and native account spacing on upstream changes. There
is no DOM mutation, runtime patch, global token change or unscoped style override.

Native sources remain frozen; the current upstream baseline is `45cf5d4f`. A future
native shared account-layout slot could replace the small owned composition after
an explicitly reviewed hook and equivalent regression acceptance.

## Preserved behavior

Registrar facts, original meetings, all five section views, exact unambiguous class
linking, term/search/return focus, roster management and canonical schedule/released
course handoffs remain unchanged. Native REST authorization remains final. Missing
class mappings, rosters, plans and syllabi are not populated or invented.

## Release gates and recovery

- Extension web tests, boundary/tooling checks and `git diff --check`.
- Full production bundle, post-bundle TypeScript and separate generated-route types.
- Compiled English/Thai teacher and student journeys at 1440/1920/930/390: matching
  account framing, five tasks, exact/ambiguous links, canonical handoffs, original
  meetings, search/term/reload/recovery and return focus. Mobile footer clearance,
  keyboard focus, selected navigation contrast, errors, overflow and writes checked.
- Bounded rendered finish/documenter review is inline, not independent. Existing
  PRODUCT/DESIGN prototype wording is pre-existing drift, not a new design authority.
- Exact compatible parent `coursemax-learnhouse:f9bc5b2a`; new owned image recipe
  `deploy/staging/Dockerfile.classes-account-layout`. Verify every required baked web
  byte/link/mode and unchanged backend/config/migrations before activation.
- Fresh protected DB/content/runtime backups, isolated socket restore, saved exact
  parent image and preservation checks. Recreate only staging app; reload its gateway.
  Roll back the app only: never restore historical live DB/files or undo evidence.
- Live native-bootstrap English/Thai desktop/mobile navigation/auth/private-access
  gates and separately scoped actual-owner read-only browser smoke. These do not
  establish institutional student, provider-device, enrollment or full migration parity.
