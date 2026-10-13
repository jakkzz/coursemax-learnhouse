# Account Settings email fix — staging 2026-10-13

Owner reported the blank email field after Google name import.

**Root cause:** verified Google email was already stored at native learner
registration. Account Settings fetched `/users/id/{id}`, whose public response
model dropped email even for the account owner. No further provider fetch or
email/account merge was required.

**Fix:** `UserReadSelf` extends the restricted public view with native email only.
The numeric lookup returns it only for a validated `PublicUser` session matching
both account ID and UUID. Other-user lookups, API tokens (even colliding IDs), and
public UUID/username lookups remain redacted. Platform/internal fields stay hidden.
Responses are `private, no-store` and vary on Cookie/Authorization.

- Deployed source: `ec2002cd133c9eb2212707606d4bf9512073b753`.
- Image: `coursemax-learnhouse:ec2002cd`,
  `sha256:51c30c8d3bb5e1a579319261c12e479d7068e9f3e4c0076a0942cada8056d201`.
- API-only, three files hashed against isolated source context. Parent
  `28d4519c` retained; validated web and Google profile import remain unchanged.
- 157 user/router/privacy/email/auth/MFA tests and 57 isolated PostgreSQL/Google
  HTTP tests pass, including real native Google-session owner email serialization
  and cross-user/token redaction (synthetic provider proof).
- Live native HTTP verifies owner email equals their stored account, no internal
  metadata, no-store, password login/logout and Google start/cancellation gates.
- Actual desktop admin1440/mobile student390 Account Settings email inputs equal
  each synthetic authenticated account's email. Existing login/link/private-lesson
  task flows still pass, without layout overflow or page errors.
- Only app recreated and gateway reloaded. DB/Redis/gateway/CourseMax container IDs
  preserved. Protected DB/content/runtime backups and rollback script retained.
  No schema changes, email writes, account merges, new provider requests or messaging.
- Resource gate passes: 25.04 GiB free disk, 5.12 GiB available RAM; no pulls/pruning.

Real owner's next page refresh is still their acceptance step; browser fixture
Google navigation is not real provider/photo acceptance. LINE remains disabled.
No broader migration/parity/DR claim is made. Private release evidence remains
outside the public repository at `releases/account-email-final-20261013/`.
