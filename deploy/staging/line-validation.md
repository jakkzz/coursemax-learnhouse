# LINE staging release validation — 2026-10-13

## Observed deployment

- Source `5625764a79c1a9191f9b4dfa06c05cafefcbe05a`, image
  `coursemax-learnhouse:5625764a`.
- Image ID `sha256:0c42f506401b7c0948b82ce71f180539b795be091276e88ce17d957d83b16cef`.
- Only `learnhouse-staging-app-1` recreated; gateway reloaded after app health.
  All other running container IDs preserved, including DB/Redis/gateway/CourseMax.
- Existing Google keys preserved. LINE fields share protected private
  `runtime/google-oauth.env`; both LINE and LIFF gates enabled with owner approval.
- Org1 accepts password, Google and LINE; other security policy settings unchanged.
  Google public create-or-sign-in remains available; LINE has no registration path.
- No schema migration, Alembic stamping, copied bindings, academic/student import,
  message send path, host/security change or CourseMax cutover.

## Evidence and limits

355 backend checks pass: 73 isolated PostgreSQL/native HTTP, 101 proof/OAuth/Redis,
181 user/privacy/auth/MFA regressions. LINE tests include linked-only sign-in,
account collision, cancellation/replay, actor changes, original auth time through
refresh/MFA, native logout, one-use MFA completion, lock/membership/revocation,
permanent unlink, LIFF verification/replay and conflicting browser owners.

Full Next bundle and generated-route TypeScript pass. Desktop1440/mobile390 task
checks assert Google confirmation, forwarded Origin, callback scrubbing,
link/disconnect outcomes, disconnect cancellation, native MFA handoff and
user-initiated LIFF SDK access. Provider/API/SDK fixtures for these complete link
flows are mocked; PostgreSQL separately verifies the actual backend authority.
Scoped inline interface review says `ship` for the incumbent extension, not a
new/global design-system, accessibility or provider acceptance claim. Static
interface detector found no new findings. Existing muted footer/MFA secondary text
and preview branding remain incumbent drift, not newly approved tokens.

Live native HTTP verifies Google/password policy preservation, LINE/LIFF
capabilities, real Redis state/PKCE/secure host-only cookies/cancel/replay, denied
public LINE registration/cross-origin access, recent-Google management requirements,
self-email privacy and logout/private-content guards. Live desktop admin and mobile
student tasks confirm Google-primary/password/LINE surfaces, cancellation,
Account Settings email, synthetic private lesson access, LIFF not loading its SDK
before user action, no overflow and no page errors. Provider navigation is
intercepted; no real provider subject is linked by deployment tests. A separate
no-login real-provider authorization preflight returned200 and reached LINE's
login page. No credentials were entered and no consent/callback/identity linking
was performed; this is not real sign-in acceptance.

**Real LINE consent/link/sign-in, provider MFA/refresh/unlink lifecycle and actual
LINE-device LIFF access still need owner acceptance.** SDK cached-token retry after
native-session loss is explicitly fail-closed with Google recovery. This is native
identity access, not the later official roster-owned classroom/task/attendance port.

## Recovery and capacity

Protected pre-release PostgreSQL/content/runtime snapshots and checksums retained.
Parent `ec2002cd` image remains. Private rollback disables LINE flags, restores
parent app, then restores saved org policy/source menu; identities/evidence remain.
No destructive schema downgrade or data rollback is required for this additive port.
These snapshots are not a coordinated off-host disaster-recovery acceptance.

Owner approved up to2GiB verified-unused build-cache cleanup. Exact-ID cleanup
processed30 unused/non-shared records, bounded below2GiB; images, containers and
volumes unchanged. Disk increased25.02→25.81GiB before the successful build;
post-deployment floor still passes (~25.38GiB,4.67GiB available memory).
This permission is consumed, not standing authorization for further cleanup.

Private evidence: `~/.local/state/learnhouse-launch/releases/line-5625764a-20261013/`,
plus `line-identity-20261013/`, `line-browser-20261013/`,
`line-web-build-reviewed-20261013/` and `line-cache-cleanup-20261013/`.
No credentials, user profiles, provider subject values or private screenshots are
published with this source validation record.
