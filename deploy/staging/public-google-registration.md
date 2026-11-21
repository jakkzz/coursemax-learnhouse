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

Public mode offers one primary **Continue with Google** action above password
recovery. Its explicit public-register transaction becomes a verified `continue`
handoff: a permanently bound Google subject signs in; an unbound subject creates a
learner, unless its email conflicts with an existing account (explicit linking only).
Retired/reserved subjects never create replacement accounts. Signin-only transactions
still never register accounts. Restricted mode preserves separate signup/signin.
LINE remains disabled.

Validation uses disposable PostgreSQL and real ephemeral RSA/JWKS with mocked
provider endpoints. Actual provider consent/signup acceptance requires a real
Google account and is not implied by those fixtures.
