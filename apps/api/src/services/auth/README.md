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

## Before connecting a route

Require a browser-bound, single-use transaction with server-owned nonce/PKCE and
explicit sign-in/link intent. Resolve a persisted provider subject with uniqueness,
retirement and active-account checks. Unknown LINE identities must not register.
Reuse native session issuance and organization gates; do not introduce a second
account/session authority. Provision separate evaluator clients only after these
controls are integrated and tested.

## Offline tests

From `apps/api/`, with the locked API dependencies installed:

```sh
python -m unittest discover -s src/tests/services -p test_provider_proof.py -v
```

Tests generate ephemeral signing keys and use HTTPX mock transports. They do not
contact providers, need credentials, create accounts or write a database. They
prove the verifier contract, not an end-to-end OAuth or account-linking flow.
