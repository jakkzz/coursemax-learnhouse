# Automatic NRRU class acquisition

## User task

Select the term and section in the existing own-staff timetable. Request its
connection; an authorized administrator chooses the matching private LearnHouse
course. The review retrieves the official roster automatically and shows the
selected section's count and reading-access effect. Confirmation atomically saves
the class, teaching assignment, initial roster and approved native reading setup.
No pasted roster URL or transcribed registrar identifier is required.

Refresh uses the same server-selected source through the existing roster review.
This slice does **not** install an unattended periodic synchronization worker or
create dated attendance sessions from weekly meeting times. Reviewed term weeks,
rotation, holidays and makeup facts remain necessary for dated planning.

## Sources and authority

- Existing real class IDs retain the CP874 `student_inclass_all.asp` source.
- Without a class ID, use the official fixed-origin
  `teach_stdlistRTFallgroup.asp` export with server-known course/year/semester.
- The export contains multiple sections. Validate its course code, semester/year,
  supported table header, student rows and exact section; never import all groups.
- Preserve an absent official class ID as NULL, not a generated pseudo-ID. The
  official course/year/semester/section tuple is globally unique across native
  courses; count all existing candidates before choosing one.
- Empty faculty/program fields are absent facts, not a reason to invent or erase
  previously recorded facts. Exact ten-digit verified identity matching remains.
- Manual memberships and withdrawals retain their source, decision, stable IDs and
  display position even when the person also appears in a registrar snapshot.
- Source failure, unsupported content, stale review or authorization failure cannot
  create a partial connection. Idempotent replay never imports a second snapshot;
  connection to an already accepted recent identical snapshot does not count twice.
- Native sessions, roles, authorship, publication, plans/quotas and enrollment remain
  native authorities. Assigned-teacher READ does not imply editing or enrollment.

RTF parsing is bounded to 2 MiB and a supported text/table subset. It never renders
objects, executes content, follows redirects, accepts an arbitrary URL, uses portal
credentials or calls CourseMax. The selected-row digest ignores unrelated RTF
formatting noise; immutable source receipts identify the source and digest policy.

## Schema and recovery

Owned revision `f47eb52fa044` descends from `f36da41e9f33`. It permits a missing
`registry_class_id` and adds `uq_official_course_section_term`. Duplicate official
tuples stop migration before DDL; no records are merged or reassigned. Downgrade
refuses while a NULL-ID source class exists.

`src.route66_ext.migrations.config.migration_config()` composes native revision
wrappers with the new owned `migrations/versions` directory. Historical owned
implementations are not loaded twice. No native migration wrapper/hook was added.
For this existing unversioned native-bootstrap staging database, the explicit
`deploy/staging/apply_nrru_source_migration.py` invokes this checked revision only,
under the academic lock and a transaction. It refuses versioned/unexpected schemas,
never stamps an inferred native head and never writes academic rows. Deployment
must first rehearse that exact image/entrypoint against a protected isolated restore.

App rollback to the saved pre-feature image is allowed only with zero NULL-ID
classes. Otherwise forward repair must retain the new evidence. Never restore an
old live database, content, grants, memberships or progress for app recovery.

## Acceptance scope

The read-only official-source dry run selected 45 P7 rows for 1/2569; exact student
numbers were validated in memory, with no student records printed/saved and no
academic writes. Source inspection is not genuine institutional/provider acceptance.
Synthetic PostgreSQL/native-session and compiled bilingual desktop/mobile tasks
cover the connection and preserved native authority. Deployment status and exact
revision are recorded separately in `deployment.md`; no historical import/cutover
is implied. All changes are extension/deployment-owned; native boundary policy and
historical native hashes are unchanged.
