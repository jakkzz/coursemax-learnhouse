# LINE identity port — prepared, not deployed or activated

The owner approved explicit linking → linked-only sign-in → lifecycle validation →
LINE in-app access. This is the identity slice, not the later academic roster/task
hub, attendance port, content migration or cutover. CourseMax stays authoritative.

## Set up credentials now

Use a LINE Login channel and LIFF application under the same reviewed LINE
provider. Subjects are provider-scoped: do not silently switch providers or infer
account equivalence. Reusing CourseMax credentials requires separate approval.

In the LINE Developers console:

- Callback URL: `https://learn.route66.click/auth/callback/line`
- LIFF endpoint: `https://learn.route66.click/liff`
- LIFF size: Full; scopes: `openid profile`
- Keep access limited to reviewed testers until real-provider acceptance.
- No Messaging API channel access token is required. No push/reply/send path is
  implemented by this port.

Put the channel ID, channel secret, provider ID and LIFF app ID in private
`~/.local/state/learnhouse-launch/runtime/google-oauth.env` alongside the existing
Google OAuth keys (directory0700/file0600; no separate line.env),
following `line.env.example`. Do not put secrets in chat, Git, screenshots or logs.
Generate an independent ≥32-byte OAuth transaction secret; never reuse Google or
CourseMax signing secrets. Both activation flags default false. Configuration alone
is not activation, provider acceptance or permission to migrate real bindings.

## Authorities and protections

- A recent (≤5-minute) native Google session, verified account and active Google
  binding are required for linking/unlinking. Refresh preserves original
  authentication time; refreshing is not reauthentication. Old Google sessions
  without that claim continue working but must reauthenticate to manage LINE.
- OAuth state/nonce/S256PKCE, browser/host/intent/deployment and exact actor-session
  binding use the existing one-use transaction authority. Cancellation consumes
  the transaction before any provider exchange.
- LINE exchanges and token verification are server-side, bounded and redacted.
  LINE email/name/avatar claims never merge, register, rename or grant access.
- Existing linked identities mint the same native `lh:user:<id>` sessions, with
  LINE provenance, membership, org policy, account lock, revocation and MFA guards.
- Unlink requires confirmation and expected binding ID. Retirement is permanent:
  reservation/audit evidence remains, LINE access/refresh/pending MFA fail, Google
  remains available. Relinking a retired subject needs a separate reviewed recovery
  workflow; the UI warns before confirmation.
- LIFF uses a separate one-use browser challenge and verifies the SDK ID token at
  LINE's verify endpoint. The SDK does not offer our OAuth nonce/PKCE contract;
  these protections must not be claimed for LIFF. A token digest is reserved in
  Redis through provider expiry before native session/MFA issuance. Unknown users
  never register; a different signed-in browser owner cannot silently switch.
- A valid current LINE session for the verified owner can continue without minting
  new credentials. A previously used SDK token without that native session fails
  closed; Google is the recovery route. Real-device retry/SDK token-cache behaviour
  is still an acceptance gate, not presumed successful.
- The LIFF SDK is loaded from the fixed official HTTPS URL only after the user
  chooses Continue. Provider ID tokens are not logged or saved in application
  storage. Account settings disclose connection state, not LINE subject/profile.

## Validation and release gates

`test_identity_postgres.sh` exercises Google/ownership and LINE/LIFF against
isolated PostgreSQL and mocked provider HTTP. The existing 101 proof/OAuth/Redis
and 181 user/privacy/auth/MFA regressions also pass. These are synthetic, not
real LINE consent; release validation records the exact final count.

Full web bundle and generated-route TypeScript pass after owner-approved exact-ID
unused/non-shared build-cache cleanup (under the 2GiB cap; application images,
containers and volumes unchanged). The earlier tmpfs-only attempt was SIGKILLed
under its bounded memory limit. Desktop1440/mobile390 browser tasks exercise
Google confirmation, origin forwarding, callback cancellation/scrubbing, link
results, disconnect cancellation/confirmation, MFA handoff and user-initiated LIFF
SDK access. Their API/provider/SDK fixtures are mocked; they do not prove real
LINE consent, provider tokens or device behaviour. Protected release evidence
retains screenshots, tests, source/artifact checksums and scoped interface review.

`test_native_web_types.sh` is generated-route TypeScript only, using a disposable
pinned-image installation in tmpfs. Its generated dependencies are trimmed after
route generation to fit the memory budget. It produces no releasable bundle.
`build_native_web.sh` remains the full bundle AND generated-route type gate.

Before activation: finish full web/type validation and desktop1440/mobile390 tasks;
validate cancellation, collision, reauthentication, explicit unlink and MFA UI;
review credentials, org1 password+google+line policy and runtime flags; snapshot
DB/content/runtime and retain parent `ec2002cd`/rollback evidence. Use the isolated
`Dockerfile.line` recipe with validated artifacts and all existing overrides plus
`line.compose.yaml`. App-only recreation, health wait and gateway reload; preserve
DB/Redis/gateway/CourseMax IDs. No schema migration, backfill or Alembic stamping.

Real LINE consent/link/sign-in, LINE MFA/refresh/logout/revocation and real-device
LIFF access require separate observed acceptance after activation. The native home
and resource authorization remain authoritative. A roster-owned classroom hub,
attendance and Messaging API integration are NOT implemented here.
