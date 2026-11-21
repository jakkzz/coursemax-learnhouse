# Student school identity — roster-first port contract

Owner clarified on 2026-10-14: student search requires registrar login. Use CourseMax's class-roster-first logic instead. **Do not build student-portal login/search, scrape its protected pages or copy university/CourseMax sessions.** This contract is not a deployment claim. The class setup/import/two-way matching source is implemented, validated and deployed at source `4c512c94`; see the [academic classes release](academic-classes.md). No real roster/mapping/student migration was performed.

## Authorities and sequence

1. An authorized teacher sets up a term-specific class/section under an explicitly assigned LearnHouse course. Reusable course content, teacher assignment, offering/section, institutional identity and roster membership are distinct authorities. A school email, staff-name confirmation or content-authorship record does not grant class management.
2. Bind the class explicitly to its official NRRU registry course/class identifiers, academic year, semester and section. Do not take a registry class already bound elsewhere or infer equivalence between similarly named courses.
3. That class pulls its official roster through the fixed CourseMax-style `student_inclass_all.asp` source. Validate academic-year/section context, decode CP874 and reject malformed or duplicate student rows before applying a snapshot. No university-login credentials, guessed profile endpoint or institution-wide roster crawl.
4. Store official student-number identity and registrar name/title, faculty/program separately from native login/profile fields. Preserve class-specific membership and stable roster-entry identities; school details are not an instruction to overwrite a student's chosen profile name.
5. Reconcile when **either side arrives**: roster import after student registration, or a new server-verified Google identity after the roster exists. Require verified Google email, NRRU hosted-domain evidence and an exact institutional student number. Names, personal email/profile edits and nine-digit account hints do not stand in for the source's ten-digit canonical number. Never add padding or invent a number.
6. Only a successful unambiguous match to a configured class roster exposes the matched school details and personal class list. Before that, School can show the verified institutional account hint with **Waiting for a class roster match**; it must not claim confirmed school enrollment or no real-world classes.

## Preservation and conflicts

- No new account/session authority, email merges, account transfers, automatic staff/admin roles or proactive messages.
- Course-scoped active membership controls current class access. Linking identity is distinct from changing membership, attendance or grades.
- Preserve manual members and withdrawn/history rows. CourseMax's repeated-missing-snapshot policy withdraws only registry-owned active rows after two accepted missing snapshots; never withdraw on a transport/parser failure.
- Stable roster/profile ownership, append-only sync/membership/conflict evidence, unique-number/user ownership and deterministic locking must close import/sign-in/concurrent-claim races.
- Duplicate user/number claims or evidence-bearing manual/registry collisions go to administrator review; teachers may flag them. Do not silently move attempts, submissions, scores/releases, attendance or historical audit evidence.
- Students receive only their own matched records; no student directory/list-of-peers endpoint. Teachers see every section of explicitly assigned courses, not all institutional classes.
- Do not manufacture historical Google evidence or import real student data merely because the source is reachable. Validate the port with synthetic fixtures and retain the accepted-parity/data-migration gates.

## CourseMax references

- `backend/app/services/nrru_roster_source.py`: fixed source URL, course/class/year/semester context, CP874 parsing and ten-digit roster number.
- `backend/app/services/nrru_roster.py`: snapshot application, manual preservation and repeated-missing withdrawal.
- `backend/app/services/roster_identity.py`: server-verified Google claim extraction, exact-number reconciliation, stable membership resolution, locks and structured conflicts.

Read from the pinned CourseMax source when the old checkout is unavailable. These are behavioral references, not permission to copy real rosters, runtime secrets or academic evidence into the fork.

## Current implementation boundary

The prepared own-only school projection and English/Thai student state now report `waiting_for_class_roster` / `waiting_for_roster`, not a missing student-lookup connection. Staff directory/timetable work remains separate. The canonical class/offering setup writer, reviewed roster import and two-way student matching are still required; do not replace them with a hard-coded matched state or catalog fallback. Existing production-bundle/browser/finish/release blockers remain, and staging is unchanged.
