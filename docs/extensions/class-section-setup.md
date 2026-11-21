# Setting up a registrar section

Teachers open a section from **My classes**. The workspace contains Overview,
Timetable and Roster; unfinished teaching-plan and syllabus tabs are not shown.
A connected class links to its roster and sessions/attendance, and to native course
content when that content is available to the account.

## Ordinary setup

An active teaching assignment and an explicit binding to the official subject are
sufficient to set up another section of that course. The teacher chooses the course
only when several already-assigned courses match, then selects **Set up class and
load roster**. No administrator request is required for this path.

The API rechecks the teacher's own registrar timetable and the existing assignment
and binding. It retrieves the exact section's official roster before saving the
class and initial roster together. Source failure leaves no partial class; retrying
completed setup returns the existing class. Manual membership, identity matching,
history and withdrawal behavior use the existing roster service.

This does not grant native roles, authorship, course READ access or enrollment.
Those remain under their existing authorities.

## When a course choice is actually missing

An unassigned/unmapped section uses the existing course-match request and review
screen. A request is persisted evidence, not component-local success state. Reopening
or reloading the section reads its saved status; a pending request is not offered
again. Pending sections refresh status periodically and also provide manual refresh.
Completing the connection makes the open workspace offer its actual class actions.
A conflicting official connection is shown as a conflict, not another setup action.

## Implementation

- `GET /api/v1/academic-classes/connections/section` — own section status and eligible
  already-assigned courses; query integers are parsed without loosening write DTOs.
- `POST /api/v1/academic-classes/connections/setup` — verified, idempotent direct setup.
- Existing request, preview and administrator connection routes remain in use for new
  mappings and access-policy decisions.
- Successful JSON responses must parse successfully: interrupted response bodies
  propagate cancellation instead of becoming `{}` and corrupting refreshed UI state.

No schema change, new native hook, calendar generation, syllabus editor, unattended
refresh, historical migration or cutover is part of this change. The site's old
“Preview only” footer is native organization configuration, not workspace code.

See [automatic acquisition](nrru-automatic-acquisition.md) and
[native access ownership](learning-access.md).
