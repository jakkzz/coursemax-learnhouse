# Academic classes and roster-first student identity

Implementation checkpoint, 2026-10-14. **Source implementation, not an activated release.** The live staging image remains `coursemax-learnhouse:8be3f82e`. No real courses, student rosters, historical evidence or accounts were migrated by this work.

## Task flow

1. A platform superadmin explicitly assigns an existing organization member to a native course and approves its official registrar course identifier and course code. This changes neither native roles nor content authorship. Directory self-confirmation and corporate email do not grant this authority.
2. The assigned teacher creates a semester/section class using that approved mapping and an explicit official class identifier. Every section of an assigned course is within that teacher's class scope. An official class/term cannot be taken by another native course.
3. The teacher loads a fixed-origin registrar preview, checks changes and explicitly applies it. Actor/organization/class/version-bound previews expire after ten minutes and are consumed once. The source validates CP874, approved course code, year, section, declared semester, ten-digit numbers, duplicates and completeness. Failed/empty/incomplete responses never withdraw anyone.
4. Exact, active, server-verified NRRU Google evidence matches on both roster import and Google completion. Nine-digit hints are never padded. Names, personal email and profile edits are not ownership proof.
5. Students see their own matched registrar details and active classes only. Manual teacher-added memberships are distinct from registrar evidence. Course content remains behind native publication/access rules; these records do not grant dashboard or authorship access.

## Preservation and exceptions

- Six additive tables and migration `f25c930d8e22`, after `f14b820c7d11`; no account/role/student backfill. Academic class events are database-enforced append-only. Downgrade refuses to delete history.
- Regular teacher-added memberships survive absent registrar rows. Registry-owned members withdraw after two accepted missing snapshots; reactivation keeps the same IDs. Identical snapshots cannot be immediately applied twice (30-minute duplicate guard).
- Verified-number claims can fill the same user's manual identity in place before an official roster arrives. This retains identity and membership IDs and is not institutional enrollment evidence. Existing separate/conflicting identities are never silently merged or transferred.
- Native chosen profile names remain unchanged. Official names, faculty/program and original registration status codes are retained as roster facts and immutable per-row event snapshots; status codes are not guessed into lifecycle decisions.
- Correcting an unused setup is optimistic, audited and cannot move it to another native course. Any membership or applied snapshot locks the scope. Course mappings with class history require separate administrator review.
- Teaching assignments, member changes and review flags require meaningful reasons. Revoked teacher authority is rechecked before applying cached previews. Review flags do not resolve conflicts or reassign evidence.
- Course deletion is blocked before file removal when teaching/class history exists.

## Surfaces

- `/classes`: assigned/own class list, focused setup and roster workspace, searches/filters, preview confirmation, verified-account manual membership and history-preserving withdrawal/restore.
- `/account/school-identity`: own matched official name/title, faculty/program or truthful waiting/review state.
- Own server-projected Classes profile-menu discovery, without browser domain/name inference.
- All class APIs live under `/api/v1/academic-classes` with native actor, organization, assignment and exact-origin write gates, private/no-store headers and bounded fixed-origin source access. No student portal, university login/session copying, proactive messaging or automatic real-data import.

## Validation and limits

- Isolated PostgreSQL/auth/service suite; full bounded production bundle and generated-route TypeScript checks.
- Eight compiled synthetic teacher/student EN/TH flows at 1440 and 390 pixels: setup → preview confirmation → applied roster, search, verified manual addition, history-preserving withdrawal, own student details/classes and reload; no page errors/overflow or peer-student details. A stale owned test server was detected and stopped; accepted flows use the final compiled bundle.
- Scoped School color/status polish retained; Classes attribution is in-flow rather than covering roster actions.
- Finish review is inline, not independent. Real registrar/provider acceptance, actual institution approval, administrative dispute resolution, private-course learning access, academic timetable/attendance/grading parity and real migration remain separate gates.
- Before activation: freeze migration DDL, protect current DB/content/runtime and rollback image, verify baked source/artifacts, install additive schema without stamping/backfill, switch app only, verify native identity/security policy and account4 grant remain intact. Do not claim deployment based on this checkpoint.
