# Google profile staging release — 2026-10-13

Owner requested **"implement now"** after the offline implementation. Optional
Google name/photo import is now deployed and explicitly enabled on
https://learn.route66.click.

- Deployed source: `28d4519ca2bacc74c14c5c3c454674c040f5081d`.
- Image: `coursemax-learnhouse:28d4519c`,
  `sha256:83f78cc76485b3abfcc88f4ff839c1d3e5646caadd30ee287a96aff79cd67852`.
- API-only layer on retained `80bdc5b7`; previously validated web unchanged.
- Eight baked API/migration files hashed against isolated source context.
- Candidate runs pass 13 offline profile/image/native-storage tests, 56 isolated
  PostgreSQL/native HTTP tests and 101 proof/OAuth/Redis tests. Earlier 88 native
  auth/MFA/logout regressions remain applicable; no dependency/web changes.
- Reviewed additive `e92d7f04ab16` schema delta applied and structurally verified,
  without Alembic stamping or account/profile backfill. Private import state was
  empty before activation. This is not full migration-chain/rollback acceptance.
- App alone recreated, gateway reloaded. DB, Redis, gateway and CourseMax container
  IDs preserved. Protected DB/content/runtime backups and prior immutable image
  retained; no broad cleanup, image pulls or data deletion.
- All three app-process health checks pass. Native password login/profile/logout,
  secure host-only cookies, Google start/PKCE/cancellation/replay denial, explicit
  password-confirmed linking, origin denial, retired legacy endpoints and private
  lesson authorization verified against the live release.
- Desktop admin1440/mobile student390 task flows pass; no page errors or horizontal
  overflow. Google browser navigation was an intercepted redirect fixture, **not**
  actual Google provider/photo acceptance.
- Runtime importer flag true and native filesystem storage verified. Default remains
  false in source/config; use all five Compose files and release flag for operations.
- Source menu updated through supported organization API to the deployed commit.
- Resource gate still passes: 25.04 GiB free disk, 4.90 GiB available RAM. No pulls.

**Pending:** owner's next successful Google sign-in and resulting actual native
name/photo display. Existing edits/photos, changed pre-feature profiles and
password-linked accounts remain protected/skipped. Optional photo failure must not
invalidate login. No direct live profile mutation or real provider photo request
was used as a deployment test. LINE remains disabled; CourseMax is unchanged.

S3 import, hard-crash orphan recovery, broad account/MFA/lifecycle/parity and
coordinated off-host disaster recovery remain separate unaccepted gates.
Implementation and rollback policy: [google-profile-import.md](google-profile-import.md).
Private evidence remains outside the public repository.
