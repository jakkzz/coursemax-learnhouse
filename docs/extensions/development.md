# Extension-first agent contract

Owner direction: fast, smooth development using KISS (keep it simple) and DRY
(don't repeat yourself). Reuse LearnHouse and the existing extension; do not turn
ordinary development into production hardening or a compliance exercise.

This is a maintained internal boundary, **not an upstream-supported plugin API**.
[Custom architecture](custom-architecture.md) describes current tables and native
links; it is not a list of new security requirements. Consult the
[historical dry run](dry-run.md) and [boundary inventory](boundary.json) when changing
those integration seams, not as mandatory reading before every small edit.

## Development mode

- Deliver the smallest working solution and iterate. Prefer a direct implementation
  over speculative frameworks, new services, configurable layers or default-off flags.
- Do not add security controls, restrictions, legal/compliance rules or approval
  workflows unless the requested behavior needs them. Preserve existing working
  login/permission behavior rather than redesigning it incidentally.
- Ordinary coding, fixes, tests, commits/pushes and already agreed staging work do
  not need repeated permission. Keep real product decisions in the product.
- Use isolated synthetic fixtures, test doubles and prototypes freely. Clear test
  boundaries matter; production-style infrastructure is not required to try an idea.
- Fix a concrete observed risk at its relevant boundary; do not expand the task into
  a general security audit. Production readiness is separate work when requested.
- Keep existing data/secrets/shared services intact. Actual migrations, destructive
  operations and shared-host changes have different consequences from local edits;
  apply only the checks relevant to the operation being performed.

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

## Normal feature loop

1. Read the relevant code; reuse native behavior or existing helpers when adequate.
2. Make the smallest usable vertical slice in the owned paths. Add a focused
   regression for a bug or meaningful behavior change; a new process document is
   not a prerequisite for implementation.
3. Run relevant checks, inspect the result and continue. Summarize what changed,
   what was checked and any actual remaining gap.

The reviewed native boundary still identifies exceptional core changes. If one is
actually necessary, identify the smallest concrete exception instead of widening
prefixes or rewriting core. Ordinary work inside the existing boundary needs no
separate proposal, repeated approval or advance list of every edited file.

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

## Checks proportional to the change

| Change | Normal development checks |
| --- | --- |
| Documentation | Verify facts, links and formatting. No app build, DB restore or deployment. |
| Small backend change | Focused unit/integration regressions for affected behavior; no unrelated frontend build. |
| UI change | Relevant type/component checks and affected user flow; desktop/mobile and Thai/English when impacted. Not every historical journey for every label. |
| Model/schema change | Relevant schema/migration tests in an isolated DB; recovery checks before applying to shared data. |
| Staging app delivery | Build affected artifacts, verify the candidate and health, and preserve the relevant recovery path. No unrelated service restarts. |

The inexpensive source-placement check is useful during development:

```sh
python3 -B scripts/extensions/check_boundary.py
```

Run the tooling unittest suite when changing boundary/tooling behavior or confirming
that contract, not as a substitute for relevant feature tests:

```sh
python3 -B -m unittest discover -s scripts/extensions -p 'test_*.py' -q
```

A boundary failure identifies a concrete integration issue to resolve, not a reason
to invent more security controls or silently widen policy. Exact native exceptions
retain their existing recorded contract. Leave unrelated work untouched.

Completion reports should be short: changed behavior, relevant checks, actual
runtime/deployment status if applicable, and unresolved issues. A local development
iteration does not need a production-release dossier. Wider regressions/builds are
appropriate for wider changes or artifacts actually being deployed, not every edit.

Before an upstream upgrade, review a pinned candidate in an isolated checkout and
run adapter/auth/MFA/revocation/access/deletion/metadata/migration/UI regressions.
Never run automatic `npx learnhouse update` on the live fork. Capacity gates,
protected backups, rollback images, evidence preservation and deployment approvals
remain mandatory; fewer merge conflicts do not prove semantic compatibility.

No runtime dependency on CourseMax; retirement and historical data deletion remain
separate approvals. Use synthetic fixtures rather than real records, credentials/
provider tokens, registrar sessions, outbound messages or live-account impersonation
in tests. LINE Messaging webhook work belongs here when ported, with signature
verification/dedup and proactive sends off.
Maintain AGPL/Enterprise attribution and corresponding-source obligations; isolation
is not a license workaround.
