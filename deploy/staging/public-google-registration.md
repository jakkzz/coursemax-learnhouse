# Public Google registration

Owner approval on 2026-10-13 permits anyone visiting learn.route66.click to register
using a server-verified Google identity and verified email.

Set `LEARNHOUSE_GOOGLE_PUBLIC_REGISTRATION_ENABLED=true` in the private
`runtime/google-native.env` loaded by `native-google.compose.yaml`. Default is false:
without this explicit opt-in, registration still uses the exact email allowlist.
The configuration is evaluated by the API, not by browser-supplied flags.

Public registration bypasses the email admission list only. It does not bypass
provider proof, state/nonce/PKCE, exact Origin, throttling, email uniqueness,
permanent Google-subject ownership, organization auth policy, quotas or MFA.
It creates the reviewed native learner role (4), not staff/admin rights or course
rosters. Existing email collisions require explicit authenticated linking and never
merge accounts. Password signup remains blocked; password sign-in remains available.

Login offers **Sign in with Google** and **Sign up with Google**. Existing Google
identities choose sign-in; new identities choose sign-up. This change does not add
an implicit sign-in-to-registration fallback. LINE remains disabled.

Validation uses disposable PostgreSQL and real ephemeral RSA/JWKS with mocked
provider endpoints. Actual provider consent/signup acceptance requires a real
Google account and is not implied by those fixtures.
