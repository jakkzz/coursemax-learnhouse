# Provider-proof foundation

`provider_proof.py` verifies external proof without resolving accounts or issuing
sessions. `google_subject_auth.py` now connects it through transactions, handoff,
subject ownership and native session policy. Activation is deny-by-default; the old
Google `/auth/oauth` bridge returns410 instead of using email lookup. Source wiring
and tests do not establish deployment, browser acceptance or actual Google acceptance.

- Google: signed RS256 ID token, fixed JWKS endpoint, issuer/audience/authorized
  party, expiry/issued-at, transaction nonce, subject and verified email.
- LINE OAuth: server-side verification with an expected transaction nonce.
- LINE LIFF: separate server-side verification entry point without pretending that
  a LIFF token has an application-created OAuth transaction nonce.
- LINE namespace is reviewed server configuration, not a client-selected channel
  mapping. Google uses a canonical issuer/global subject namespace.
- Provider email is not an account lookup or merge key. LINE proof does not imply
  verified email, permission to link, or permission to register.
- Fixed endpoints, no redirects, bounded time/response sizes and redacted errors.

## OAuth transactions

`oauth_transactions.py` adds server-created state, nonce and S256 PKCE, a Secure/
HttpOnly/host-only browser binding, explicit sign-in/register/link intents, and
configuration-bound callback URLs. Google and LINE endpoints are fixed. LINE
registration intent is rejected; account resolution is still a separate gate.

Records are short-lived and authenticated. The Redis adapter uses NX creation and
one atomic compare/delete Lua script. A wrong browser, actor/session, provider,
client, namespace, origin, intent or deployment cannot consume the valid record.
Consume before provider exchange, including denial callbacks; never restore a
consumed transaction after provider/network failure. Rotate transaction secrets
following a restore and do not transfer pending transactions between environments.

Use `StartedTransaction.public_response()` for the browser JSON and
`binding_cookie()` only for server Set-Cookie. Never serialize the complete
transaction object to a browser. Callback intent can be an untrusted hint, but must
match the original cryptographically bound intent. Link actor/session context must
always come from verified native authentication, not request JSON.

The Google subject-owned routes use these primitives rather than the retired native
OAuth bridge. Unit tests exercise an atomic in-memory store and the Redis command contract. The opt-in
integration suite also runs the real Lua script against disposable Redis, including
32 simultaneous callbacks, expiry, malformed records and context/actor isolation.
Native HTTP/cookie integration and provider-account acceptance are still required.

## Google-first server handoff

`google_handoff.py` joins browser-bound transaction consumption, fixed-endpoint Google
code redemption and real ID-token proof verification. It consumes before exchanging,
including cancellation, and never restores consumed state after provider/admission
failure. PKCE, callback URI, nonce and client come from server-owned configuration
and the consumed transaction. Each request is capped at 64 KiB/5 seconds; a single
10-second budget covers redemption plus proof verification. Provider credentials and
native headers/cookies never cross into unrelated requests or returned result fields.

New staging registration requires an explicit, normalized verified-email allowlist;
empty means deny. Personal Gmail and institutional addresses are both eligible when
listed. This is admission only: no account lookup/merge by email, no `.ac.th` privilege
or enrollment grant, and no public registration switch. Existing signin/link intents
return internal proof/context only; signin must not fall back to creating a user.

The frozen result is **not a browser response** and must not be serialized directly.
Native ownership/account/session/MFA/org checks and atomic registration are integrated
by `native_google.py` and the new router. No credentials are enabled by this module. Public password
signup and LINE UI remain later work; existing bootstrap password login is unchanged.

The cached-image Redis harness also runs the handoff matrix with real transaction
consumption, ephemeral RSA-signed ID tokens and mocked fixed Google endpoints, once
with an atomic in-memory store and once with Redis. It does not contact Google or
constitute native session/provider-account end-to-end acceptance.

## Persisted identity ownership

`provider_identities.py` adds private subject ownership on native user IDs. It does
not create accounts, search/update email, assign roles, issue sessions or implement
merges. Unknown LINE proof yields linking guidance, never account creation.

- A provider/issuer/namespace/subject is unique, including after retirement.
- One active identity per provider per user; ordinary linking cannot replace it.
- Linking LINE requires an active Google binding and verified native email.
- Google replacement requires current and new verified proofs plus an expected
  binding and reason. User-row locks, unique constraints and savepoints preserve
  the losing account's access in races and roll back partial retirements.
- Identity ownership is immutable; events are append-only. Foreign keys restrict
  native user deletion while identity evidence exists. Lifecycle/merge APIs must
  respect this boundary rather than bypass database guards.
- Migration `c71a02d9ef40` installs the schema/guards and supports native
  create_all-first bootstrap. It imports no identities. Downgrade locks both tables
  and refuses to destroy any retained binding/event.

Ownership resolution is not session authorization. The native Google controller
locks/rechecks the binding/account, enforces org/MFA policy and mints `lh:user:<id>`
subjects with issuer/audience/UUID/binding claims. Provider REST/refresh/MFA validation
rechecks active ownership and revocation; retirement denies old bound tokens. Password
sessions retain their compatible email-subject format under the same native authority.
Continuous collaboration/file lifecycle acceptance remains separate; replacement is
not exposed as an ordinary linking endpoint. Proof and actor/session context must
always be server-verified, not request-body assertions.

Run isolated PostgreSQL tests from the repository root:

```sh
bash deploy/staging/test_identity_postgres.sh
```

The harness uses cached pinned images, a private Unix socket, no network or live
volumes, disposable native-user fixtures, and capacity gates. It checks migration
and create_all bootstrap, competing ownership/replacement, audit retention and
rollback even when the caller catches an error and commits its outer transaction.
This is not a complete native migration-chain/HTTP/provider acceptance rehearsal.

## Before connecting a route

Require a browser-bound, single-use transaction with server-owned nonce/PKCE and
explicit sign-in/link intent. Resolve a persisted provider subject with uniqueness,
retirement and active-account checks. Unknown LINE identities must not register.
Reuse native session issuance and organization gates; do not introduce a second
account/session authority. Provision separate evaluator clients only after these
controls are integrated and tested. Apply exact-origin/CSRF and rate-limit guards,
reject ambiguous security cookies, authorize linking against a currently active,
verified Google-bound account, and recheck lifecycle/ownership before issuing the
native session. Do not infer these permissions from a valid OAuth transaction.

## Native Google routes and activation

Public capabilities and server-owned POST start/complete live under
`/api/v1/auth/google`. Exact configured HTTPS Origin is required for mutations;
ambiguous security cookies and excess attempts are rejected. Linking authenticates
the initiating session and requires its existing password for non-Google sessions.
Registration uses the handoff admission allowlist, a validated PostgreSQL email
uniqueness index, a reviewed global learner role and one outer account/membership/
binding transaction. There is no email merge, institution privilege or enrollment grant.

Server-only configuration:

- `LEARNHOUSE_GOOGLE_SUBJECT_LOGIN_ENABLED=true` (otherwise disabled)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `LEARNHOUSE_GOOGLE_REGISTRATION_EMAILS`: JSON list of explicitly approved emails;
  empty disables registration, not linked sign-in
- `LEARNHOUSE_GOOGLE_ORG_ID`: reviewed target organization
- `LEARNHOUSE_OAUTH_TRANSACTION_SECRET`: independently generated >=32 bytes
- `LEARNHOUSE_OAUTH_DEPLOYMENT`: environment-specific transaction namespace
- Native hosting SSL/domain and Redis configuration must be valid

Keep secrets out of Git/builds. Frontend capabilities gate visible Google controls;
the callback sends code/state to the native controller, never exchanges Google tokens.
Cookie sharing requires explicit server `LEARNHOUSE_SESSION_COOKIE_TENANCY=multi`;
absent/single is host-only and ignores browser tenancy hints. Staging must stay single.
MFA challenges are single-use after successful factor verification. Provider logout
requires a successful revocation write; failures do not pretend to end the session.
Issuance/cutoff timestamps preserve fractional seconds so fresh login after logout works.

`d84e13a6b902` adds lower(email) uniqueness without merging/deleting legacy rows;
collisions or incompatible indexes stop for review. A schema-delta test is not a full
native Alembic-chain acceptance. Do not activate registration before validating schema,
org/role/admission policy, a full web build and actual desktop/mobile/provider flows.

The isolated PostgreSQL harness runs40 cases, including21 ownership cases plus native
account/session/MFA/refresh/logout and HTTP callback cases. Provider HTTP tests use
actual ephemeral RSA/JWKS proofs with mocked Google URLs, not real Google accounts.
Existing native auth/MFA regression coverage also passes88 cases.

## Offline tests

From `apps/api/`, with the locked API dependencies installed:

```sh
python -m unittest discover -s src/tests/services -p test_provider_proof.py -v
python -m unittest discover -s src/tests/services -p test_oauth_transactions.py -v
```

Tests generate ephemeral signing keys and use HTTPX mock transports. They do not
contact providers, need credentials, create accounts or write a database. They
prove verifier/transaction contracts, not an end-to-end OAuth or account-linking
flow. Transaction unit tests use only the Python standard library.

## Real Redis integration

From the repository root:

```sh
bash deploy/staging/test_oauth_redis.sh
```

This resource-gated harness uses pinned **already cached** API/Redis images,
`--pull=never`, no TCP networking, no host ports and no application volumes or
secrets. The two disposable containers share only a private temporary Unix socket.
It runs all proof/transaction unit tests plus the real Redis integration tests.
The fixture disables persistence and removes only its own socket/container.

## Optional provider profile enrichment (default-off)

`provider_profile.py` extracts optional attributes only after provider verification;
malformed enrichment never changes identity validity. `profile_import.py` connects
Google only after native login succeeds (not a pending MFA challenge), initializes
eligible empty names once, and schedules optional avatars after commit/response.
`provider_avatar.py` pins public destination IPs while preserving verified original
TLS/SNI, bounds download/decoded pixels and re-encodes metadata-free native PNG.
Private import state preserves manual edits and durable bounded retry leases.
Display-name/locale hints are private; LINE and language preferences stay unchanged.

See [the complete deployment/acceptance contract](../../../../../deploy/staging/google-profile-import.md).
No activation is implied by source/tests. Run isolated PostgreSQL and Redis harnesses
plus `bash deploy/staging/test_provider_profile.sh` offline.
