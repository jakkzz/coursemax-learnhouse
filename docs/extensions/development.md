# Extension-first agent contract

Owner direction: minimize edits to original LearnHouse code while integrating NRRU
and ported CourseMax behavior. This is a maintained internal boundary, **not an
upstream-supported plugin API**. [Audited dry run](dry-run.md) and
[historical patch inventory/policy](boundary.json) are required reading.
For current table ownership, foreign keys, attendance storage and native integration,
see [Custom architecture and database relationships](custom-architecture.md).

## Default placement

- Backend feature logic, models, DTOs, provider config, routes, policies and tests:
  `apps/api/src/route66_ext/`.
- Web feature components, orchestration, copy, adapters and tests:
  `apps/web/extensions/route66/`; public assets: `apps/web/public/route66/`.
- Boundary tooling/docs: `scripts/extensions/`, `docs/extensions/`.
- Deployment recipes: own `deploy/staging/` surface; no shared-host changes.
- Framework-discovered route/model/migration wrappers outside those paths require
  an EXACT recorded exception. A wrapper delegates; no business logic. Keep existing
  deployed URLs, table names, revision IDs, identity ownership and receipts stable.
- Existing feature modules scattered through native trees are legacy, not an
  example to copy. Extract them under a reviewed plan; don't widen that footprint.

## Before writing a feature

1. State audit IDs, native authority, extension authority and the concrete task.
   Check if native behavior is already adequate; don't duplicate course/content,
   account/session, enrollment, grade or evidence authorities.
2. Inspect the pinned native contract. Record supported hooks and the adapter calls
   needed; do not assume a plugin registry, API or Enterprise entitlement.
3. List changed files BEFORE editing. Default to owned paths. If an original/native
   path is needed, explain why an adapter/thin owned route cannot safely suffice.
4. **Request approval for the minimal core-hook exception before editing it.** An
   ordinary feature request is not blanket permission for scattered native edits.
   Specify invariant, exact path, alternatives, synthetic regressions and replacement/
   upstream-update plan. Freeze existing patches until safely replaced; do not remove
   security/retention fixes merely to obtain a cleaner diff.
5. Add a failing synthetic test; implement the smallest vertical slice. Run the
   boundary gate while changes are still easy to review.

## Adapter and native-hook rules

- Only backend `route66_ext/adapters/` imports native internals. Extension business
  logic uses typed, bounded adapter operations; no raw client actor IDs or JWT claims
  as authority. Existing imports are migration debt, not a waived future rule.
- One native account/session authority. Native courses own content/learning access;
  our NRRU class metadata/roster owns official class eligibility and academic evidence.
  Complete native enrollment/access through an authorized adapter, not a second login
  or independently writable course catalog.
- Native membership/session/policy rechecks and extension row locks share the proper
  transaction and lock order. Adapters do not commit midway, infer privilege from
  email/domain/directory/content authorship, or silently enroll on a timetable hint.
- Keep native helpers in native files; route extension branches through explicit,
  reviewed delegates. No extension business rules embedded in native handlers.
- No runtime monkeypatch, production dependency override, duplicate-route shadowing,
  import-time DDL/network/side-effect, or regex source rewriting as an integration API.
- Preserve guards BEFORE irreversible file/profile operations. DB FKs are not a
  filesystem-deletion strategy. Native auth patches are retained until every direct
  consumer (MFA/refresh/logout/etc.) has an equivalent tested path.
- Native configuration/context/build patches are exceptions too. Prefer own config
  composition/resources, translation namespace, context consumption and deployment
  wrappers where actually supported; don't claim an unsupported wrapper works.

## Database and migration rules

Own models reference stable native IDs. New tables use an own prefix where suitable;
never rename deployed tables or rewrite immutable provenance for cosmetics. Explicitly
register metadata before native startup/autogenerate; test discovery and fresh/existing
schema guards. Preserve revision IDs/ancestry and native email-uniqueness constraints.
Do not edit old upstream revisions, stamp away divergence, auto-apply migration on
module import, create an uncoordinated second chain or restore an old DB for rollback.
Separate locations/branches require a reviewed Alembic dependency/merge contract.

## Review and completion

Run:

```sh
python3 -B scripts/extensions/check_boundary.py
python3 -B -m unittest discover -s scripts/extensions -p 'test_*.py' -q
```

The gate covers source placement, not adapter import discipline or runtime safety;
review those separately. A gate failure is a STOP-and-review signal, not permission
to broaden prefixes or refresh `snapshot`. Exact exceptions in `boundary.json` need
`reason`, `approval_reference`, `tests`, `replacement_plan` and matching `sha256`.
Review the policy/tool itself so changing it cannot silently authorize core patches.
Its historical inventory is not approval for new edits. Never commit unrelated
preserved workflow/critique files to make a clean worktree.

Each completion report records:
- owned paths + exact native hooks retained/added/removed and why;
- adapter contracts/native source pin and upstream conflict impact;
- policy/permission/concurrency/retention/native-auth regression evidence;
- full production web build/types and persisted EN/TH teacher/student tasks for UI;
- metadata/migration/image packaging/source-disclosure impact and safe recovery;
- what is merely planned/static/source-only versus runtime-validated/deployed.

Before an upstream upgrade, review a pinned candidate in an isolated checkout and
run adapter/auth/MFA/revocation/access/deletion/metadata/migration/UI regressions.
Never run automatic `npx learnhouse update` on the live fork. Capacity gates,
protected backups, rollback images, evidence preservation and deployment approvals
remain mandatory; fewer merge conflicts do not prove semantic compatibility.

No runtime dependency on CourseMax; retirement and historical data deletion remain
separate approvals. No real records, credentials/provider tokens, registrar sessions,
outbound messages or live-account impersonation in tests. LINE Messaging webhook work
belongs here when ported, with signature verification/dedup and proactive sends off.
Maintain AGPL/Enterprise attribution and corresponding-source obligations; isolation
is not a license workaround.
