# Superadmin own organization-role control

Deployed 2026-10-14: source/image `d43256b0`, frontend-only overlay on exact retained `4c512c94` parent.

The Users role dropdown incorrectly blocked every own-account edit, although the backend permits platform superadmins to edit their own organization role. It now retains all loading/organization-management gates and exempts only a strictly `true`, server-projected `is_superadmin` from the own-account block. Ordinary organization managers remain blocked from changing their own role. This control edits organization membership roles, not the independent platform-superadmin grant.

Validation: five predicate regressions, full production bundle/generated-route TypeScript, eight compiled mocked superadmin/ordinary-manager EN/TH1440/390 flows (including simulated role update and reload), four live existing synthetic-superadmin EN/TH1440/390 control/open-options/reload flows without selecting another role, native identity/class API guards and two live native-auth flows. No live role mutation was performed. All API Python bytes match the parent image; no schema, account privilege, provider ownership or security-policy changes. Only the staging app was replaced; protected DB/content/runtime backups and saved/checksummed `4c512c94` rollback retained.

The mechanical detector reported two existing unmodified color warnings in member actions; the fix changes only the permission predicate. Review is inline, not independent. CourseMax and unrelated services are unchanged.
