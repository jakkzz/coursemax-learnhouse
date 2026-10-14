# NRRU own-directory association — implementation checkpoint

**Prepared, not deployed.** Existing synthetic preview remains live at f308348a.

## Approved flow

- An authenticated user's active Google binding supplies server-verified email and hosted-domain evidence on their next Google completion. No old-account backfill, email merge or role inference.
- For an NRRU hosted-domain email shaped like `firstname.initial@nrru.ac.th`, derive a bounded ASCII firstname search hint. Numeric student addresses are not treated as staff. The hint is never proof of ownership.
- Fixed HTTPS POST to `https://reg.nrru.ac.th/registrar/teach_time.asp`, `f_cmd=1`, `f_officername=<hint>`, `f_maxrows=100`. Decode CP874; extract officer identifier/code and Thai/English names only. No timetable or student imports.
- Display every matching record, including one match; require an explicit selection and own-name confirmation. No automatic first-result match.
- Candidates stay in private Redis for ten minutes, bound to the native user, active identity and exact Google evidence version. Confirmations consume the search once. Unknown choices, changed evidence, cross-account reuse and conflicting directory ownership are rejected.
- Save a unique private self-confirmed directory association and native audit event. This is self-attestation, **not institutional approval**. Corrections/ownership disputes require a separately reviewed administrator workflow.

## Interfaces and limits

Own-only GET `/api/v1/school-identity/me` and `/timetable`, POST `/search` and `/confirm`. Read responses are private/no-store. Writes use exact same-origin checks, native session authorization, active-binding evidence and bounded throttling. Fixed-origin transport forwards no native credentials/cookies, follows no redirects and caps response bytes/time.

Prepared native `/classes` and `/account/school-identity` surfaces are outside `/dash`, so a teacher never needs dashboard-administration rights. Account desktop/mobile navigation includes School identity. Profile dropdown conditionally shows **School** from the own-only server projection: confirmed staff directory record or verified NRRU numeric student-account hint, not browser email/name inference. A confirmation refreshes menu discovery without requiring reload. Numeric identifiers are retained verbatim (9/10-digit hints; no zero padding) and do not prove registrar enrollment. English/Thai forms have explicit candidate selection, confirmation, retry and empty states.

Confirmed staff can read their own fixed-origin registrar timetable with explicit year/semester context. Course code/title/section, meeting day/time and source details come from bounded CP874 parsing; repeated meetings remain distinct. No roster, QR/contact or external links are followed. Five-minute private source cache, bounded own-user transport/rate checks, academic-year window and returned officer/term checks apply. Sample inspected own source shows three classes/four meetings in 1/2569 and zero in 2/2569; do not infer an empty history from the current semester. This is **read-only registrar data, not LearnHouse assignments**.

Owner confirmed student search requires registrar login. **Do not implement student-portal search/login.** Use the [roster-first student identity contract](roster-first-student-identity.md): authorized teacher class setup → official class roster → exact verified student-number reconciliation when either the roster or student identity arrives. Before matching, recognized institutional accounts show their verified-email identifier and **Waiting for a class roster match** (`waiting_for_class_roster` / `waiting_for_roster`), not a missing lookup connection or invented school profile. Registrar name/title/faculty/program and personal class list come from matched configured class rosters; identity linking does not mutate membership or academic evidence. Class/offering setup, reviewed import and reconciliation backend remain to be implemented. The LearnHouse-assigned course list is deliberately empty in this initial identity port: no assignment authority/writer exists yet. Future explicit term/section matching must supply that authority; do not use native content authorship, email domain or all-catalog results as substitutes. No course/enrollment/administration grants, profile-name rewrites or messaging occur here.

## Validation and release gate

81 isolated PostgreSQL/native auth tests pass, including new Google evidence, migration/model compatibility, own scoped search/confirmation, multiple matches, foreign/replayed candidate rejection, unique-record conflict, correction blocking, unchanged native roles, conditional staff/student menu, staff-only own timetable gate and empty assigned courses. 15 bounded directory/timetable parser tests and 31 provider-proof cases pass. Generated-route TypeScript passes after fixing ownership-safe type-harness copying and using the existing react-hot-toast dependency.

Production bundle has **not passed**: initial Turbopack and diagnostic webpack builds timed out; reviewed Turbopack build was SIGKILLed. Diagnostic engine changes were reverted. No valid new web artifact, compiled bilingual desktop/mobile browser acceptance, finish-review verdict, new app image, schema activation or staging switch. Do not deploy from `BUILD_FINISHED` or type-only evidence.

When validated: use exact retained f308348a parent and `Dockerfile.school-identity`, clean complete web extraction/manifest verification and app-only release with protected pre-release snapshots. Apply reviewed additive migration f14b820c7d11 without manufacturing historical Google evidence or Alembic stamping. Retain tables/history on code rollback. The separate owner-confirmed platform-superadmin grant is an audited live administrative operation, not baked into source, signup or rollback.
