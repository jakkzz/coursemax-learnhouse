# Auth UI refinement — 2026-10-13

Owner direction: fix all five critique findings; LINE directly after Google;
matching neutral control family with provider icons. Preserve Google primary,
password/MFA flows, Google-owned linked-only LINE and irreversible retirement.

## Implemented

- Shared ProviderButton/Icon:48px minimum, same label/icon slot/radius/padding,
  12px provider gap, Google then LINE above the distinct password form. No green
  LINE button; neutral outlined secondary. Busy provider handoff blocks competing
  starts. Keyboard outline remains dark after the existing transition settles.
- Account Sign-in methods first: owned Connected/Not connected status, not inferred
  from capability flags; unknown/loading/error/retry are separate states.
  Connected Google has no misleading ordinary replacement/unlink control; LINE
  Connect/Manage uses the existing recent-Google management route.
- Google `/auth/google/account` is read-only, returns only `linked`, requires a
  validated PublicUser, selects that user's active canonical binding and sends
  private/no-store + Cookie/Authorization Vary. No subject/email/identity ID,
  actor-ID parameter, account mutation, provider request or signup behavior.
- Consistent16px mobile/24px desktop section insets, semantic task headings,
  left-aligned bounded password form and44px account actions.
- Account attribution stays visible in document flow; fixed mobile tabs and page
  end reserve safe-area clearance. Other surfaces retain existing watermark rules.
- New task/status copy is English/Thai. Source menu/credits are preserved.

## Assets

Root public assets deliberately avoid tenant-rewriting nested static paths:
`provider-google.svg` is the same Google product logo formerly loaded remotely
from `https://fonts.gstatic.com/s/i/productlogos/googleg/v6/24px.svg`.
`provider-line.svg` comes from Simple Icons16.18.0 (`icons/line.svg`, CC0); provider
marks remain their owners' trademarks. Icons are decorative beside text labels;
no arbitrary authored SVG/remote-media policy is introduced.

## Validation and limits

-77 isolated PostgreSQL/native HTTP tests (four new Google connection/privacy cases).
-181 auth/policy/MFA/logout/user privacy regressions and101 proof/OAuth/Redis tests.
-3 web overlay packaging tests; full bundle AND generated-route TypeScript pass.
-Compiled-artifact browser tasks at1440/390/768: Google/LINE order/navigation,
  equal48px buttons,12px gap, locally rendered icons, keyboard focus, password
  login, native pending-MFA handoff, linked/unlinked and correct action routes,
  outage vs unlinked, successful retry, title grid,44px actions and mobile
  footer/tab clearance. English/Thai login checked; no overflow/page errors.
-Provider/API navigation in that UI harness is mocked; actual native authorization
  is tested separately. Physical devices/Safari, real provider lifecycle and broad
  migration/private-file acceptance are not inferred. Inline degraded finish review
  (no subagent exposed) ships this scoped incumbent extension only.

## Recoverable staging recipe

`Dockerfile.auth-ui` uses retained reviewed LINE parent5625764a, no pull/network,
no migrations/flag changes. A separately validated complete web tree is compared
against that exact parent's `/app/web` using `create_web_overlay.py`; only changed
bytes are added. Type conflicts fail closed. Old hashed assets remain for in-flight
clients. Every desired regular file/link is recorded in the private manifest and
verified in the candidate image; a diff archive alone is not validation.

This avoids duplicating unchanged dependencies on a host near its disk floor.
Recheck25GiB disk/3GiB available RAM (27GiB before any pull). Never prune as a side
effect. Use an isolated code-only context, protected pre-release snapshots, app-only
recreate and health/gateway verification; retain5625764a rollback. Source disclosure
must point at the actual deployed revision. No CourseMax service/data/credentials,
rosters, academic evidence, identity settings or messaging may change.
