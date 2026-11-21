# Optional Google profile enrichment

Implementation is default-off. It does not activate LINE, change Google identity,
email, roles, MFA, session policy, enrollment, or messaging.

## Behavior

- Extract optional profile attributes **after** provider proof verification.
  Malformed optional names/photo/locale are discarded; identity stays strict.
- Fill empty Google-created account names once. Existing native names/photos win.
  Password-account linking does not imply permission to import a profile.
- Returning Google accounts are eligible only when creation/update timestamps still
  match. Earlier edits make the whole import skipped: an empty field is not assumed
  to be permission to replace a deliberate clear. New manual name/avatar edits
  cancel any pending import under the same user lock.
- Display name and supported locale hint remain in private import state. This
  release does **not** change browser language or add a public nickname field.
- No enrichment while an MFA challenge is pending. A later fully authenticated
  Google completion may initialize the profile.
- Avatar work runs after a successful login response/account commit. A private
  database lease prevents duplicate work. Interrupted jobs retry on later verified
  logins, at most three attempts; there is no independent scheduler.
- Exact HTTPS Google hosts only; all DNS answers must be ordinary public addresses.
  The connection uses a numeric pinned destination, original Host and verified
  TLS/SNI. No redirects, credentials, shared client cookies, proxy environment,
  compressed HTTP responses, or unbounded downloads. LINE host parsing is future
  infrastructure only; the import controller accepts Google only.
- Bounds: 5 seconds total download, 2 MiB encoded bytes, four million decoded pixels,
  dimensions at most 4096; PNG output at most 512×512. Decode JPEG/PNG/WebP, reject
  animation/corruption/markup and bound WebP canvases before decoder allocation.
  Re-encode pixels without source metadata.
- Native **filesystem** storage only for this release. S3 import is unsupported,
  fails optionally, and needs its own cleanup/acceptance work. No remote URL is
  written to `avatar_image`.
- Recheck identity ownership/retirement and manual-avatar eligibility before
  attachment. Clean only this job's staged object after a fresh locked read proves
  it unattached. Ambiguous DB/cleanup failure retains the object, never deletes a
  potentially referenced avatar. A hard process crash can retain an opaque orphan;
  no broad automatic deletion or orphan-recovery acceptance is claimed.
- Clear provider picture URLs on terminal states. Logs/reprs omit URL/name claims.

## Validation (offline synthetic only)

- 13 profile/download/normalization/native-filesystem tests, including pinned-IP Host/SNI, no inherited
  credentials, mixed/private/multicast/transition DNS, metadata removal and limits.
- 56 isolated PostgreSQL/native HTTP/ownership tests, including existing learner
  permissions, profile success, duplicate jobs, manual races/clears, old edits,
  bounded failure/recovery, missing-table login survival, MFA gating and additive
  migration/bootstrap validation.
- 101 proof/OAuth/Redis/handoff tests, including verified optional Google/LINE claims.
- 88 existing native auth/session/MFA/logout regression tests.

From the repository root, run `bash deploy/staging/test_provider_profile.sh`,
`bash deploy/staging/test_identity_postgres.sh`, and `bash deploy/staging/test_oauth_redis.sh`.
The profile harness is network-disabled and has no live application volumes.

These tests make no real provider photo request and do not prove real Google image
transport/UI acceptance, full migration-chain rollback, or disaster recovery.

## Build / deployment

`Dockerfile.google-profile` is API-only, on the already validated `80bdc5b7` image;
review each copied file. The web artifact and runtime dependencies are unchanged.
Use an isolated context, no pulls, resource floor checks, protected DB/content
backups, retained rollback image, and app-only recreation. Preserve DB/Redis/gateway.

1. Validate additive revision `e92d7f04ab16` (parent `d84e13a6b902`); no live account
   backfill, destructive downgrade, automatic Alembic stamping or full-chain claim.
   Existing create_all tables must pass the revision's structural checks.
2. The existing native-Google Compose combination remains unchanged. Add
   `google-profile.compose.yaml` only for the reviewed release and explicitly set
   `LEARNHOUSE_GOOGLE_PROFILE_IMPORT_ENABLED=true` in its `app-image.env`.
   `google-profile.env.example` defaults false. Omission or false disables import.
3. Verify health and unchanged Google/password/session gates, then validate a real
   Google sign-in and resulting native name/avatar on desktop/mobile. Until then,
   provider-photo/UI acceptance remains pending.
4. Roll back by disabling the flag/recreating only app with the retained image.
   Keep additive import state and imported native files/names; do not destroy
   provenance or automatically reverse user-visible profile data.

No deployment or runtime activation is implied by this implementation document.
