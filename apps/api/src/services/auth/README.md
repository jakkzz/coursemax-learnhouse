# Provider-proof foundation

`provider_proof.py` verifies external proof without resolving accounts or issuing
sessions. It is **not wired to login routes**. Existing Google login still uses
`utils.py`; merely installing this module does not change that behavior.

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

These primitives are not connected to existing native OAuth routes. Unit tests
exercise an atomic in-memory store and the Redis command contract. The opt-in
integration suite also runs the real Lua script against disposable Redis, including
32 simultaneous callbacks, expiry, malformed records and context/actor isolation.
Native HTTP/cookie integration and provider-account acceptance are still required.

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
