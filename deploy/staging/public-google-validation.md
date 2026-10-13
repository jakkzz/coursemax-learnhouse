# Public Google validation checkpoint — 2026-10-13

The owner confirmed Google access is working after deployed fix
`80bdc5b7bc48ad3d0c284efd708c631226cdb290`.

- Actual Google completion requests returned HTTP 200 twice after the fix.
- Public **Continue with Google** creates a native learner for a new verified
  subject or signs in its existing permanent owner. No email-based account merge.
- The real callback previously returned 503 because standard learner discussion
  creation was misclassified as staff permission. The fix permits discussion
  creation only; global moderation and administrative writes remain prohibited.
- 44 isolated PostgreSQL/HTTP cases pass, including the native learner rights shape,
  denied global moderation, first/returning subject and existing-email collisions.
- Parent web bundle/generated-route type checks and desktop/mobile task flows pass.
- Only the app was recreated and gateway reloaded; DB/Redis/gateway IDs preserved.
  Retained images and protected backups provide rollback. CourseMax is unchanged.

Owner confirmation and HTTP success establish this real Google path, not every
account/provider-policy edge case, provider MFA, continuous collaboration/file
session lifecycle, private-file protection, full migration-chain compatibility,
coordinated recovery or academic feature parity. Those gates remain separate.

Evidence and identity details stay in private release records, not this public fork.
