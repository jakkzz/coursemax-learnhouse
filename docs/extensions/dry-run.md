# Isolated extension dry run — 2026-10-14

## Scope and observed result

This is an **offline extraction rehearsal**, not an implemented plugin, deployment,
new-upstream merge test or permission to restore native security code. Source:
`cfad1e042e45318051c547df044525a9ed3f7069`; inspected upstream baseline:
`45cf5d4f78cf537064070dc8e315a64990d14966`. No upstream branch was fetched/merged.
The inspected baseline has no general institutional plugin loader we can assume.
Enterprise hooks are not an invitation to use Enterprise code or impersonate its
registration mechanism.

The tracked delta contains **181 paths: 138 added, 43 modified upstream files**:

| Surface | Added | Existing files changed |
| --- | ---: | ---: |
| API (models/services/routes/tests/migrations) | 48 | 12 |
| Web (pages/components/assets/tests/config) | 30 | 30 |
| Deployment | 57 | 0 |
| App Nginx | 0 | 1 |
| Other own documentation | 3 | 0 |

[Machine-readable inventory](boundary.json) classifies every historical path with
its proposed destination/rationale. Additions are not equivalent to upstream edits,
but additions inside native discovery trees still create integration dependencies.
The baseline is researched/pinned, not the latest upstream release.

`scripts/extensions/dry_run.py` copied **28 owned backend modules** into a NEW
scratch `src/route66_ext/` package, rewrote their direct static imports and module
reference strings, and copied one pure-policy test module. All **29 Python copies
compile**, with **zero stale owned static import references**. The relocated
attendance policy passed **25 offline synthetic tests**. The remaining owned-module
adapter surface contains **18 native modules / 50 import statements**, including
imports inside functions. This graph is evidence of coupling, not a supported API.
Thirteen boundary/rewrite-tool tests also pass, including isolated Git fixtures
proving unstaged, staged and already committed native changes, deletion and new
untracked native files are rejected while owned/preserved paths are allowed.

The scratch copy is outside the repository in protected local evidence; original
application code and live services are unchanged. No framework dependencies were
installed, no provider/registrar requests, database operations, build, restart,
cleanup, import, messages or privilege changes were performed by this dry run.
The next actual extraction still needs full runtime and PostgreSQL/UI acceptance.

## Proposed package, not an already available extension

```text
apps/api/src/route66_ext/
  bootstrap.py                 # explicit router/model registration; no migration on import
  config.py                    # validated own flags/config; secrets stay server-side
  adapters/                    # ONLY imports of native LearnHouse internals
    accounts.py                # user/org/roles, native transaction/learner creation
    sessions.py                # native issuance/policy/MFA/revocation contracts
    courses.py                 # course/access/enrollment/lifecycle contracts
    storage.py                 # validated native file paths/uploads/profile attachments
  db/                          # own models, same existing table/FK names
  routers/                     # existing public paths retained
  services/                    # Google/LINE/NRRU/classes/attendance rules
  security/                    # proof, provider claims and authorization
  migrations/                  # own migration implementation; stable discovered wrappers
  tests/                       # own policy/integration + native adapter contract tests
apps/web/extensions/route66/
  adapters/                    # native session/org/course/context consumption
  auth/ school/ classes/ attendance/
  locales/ assets/ tests/
apps/web/app/.../page.tsx       # individually registered thin route wrappers only
```

Do not rename published tables, revision IDs, provider namespaces, session claims,
URLs or retained receipts merely to match this folder layout. Existing `src/db/*`
compatibility modules may remain as exact reviewed model-registration shims while
native discovery needs them. Avoid two declarations of the same SQLModel class.
New features go in the extension, not those legacy locations.

## Concrete extraction decisions

| Current feature | Extension destination | Native boundary that remains |
| --- | --- | --- |
| Proof/transactions, Google/LINE handoffs, identities | Owned auth/security/models/routes | Native account creation, organization policy, issuance/MFA/revocation adapter |
| Provider profile/name/avatar import | Owned profile service + storage adapter | Manual edit lock/cancellation hook before native profile write |
| School evidence, directory/timetable, roster matching | Owned NRRU/class modules | Native user/course/org identity and enrollment/access adapter |
| Session/QR/receipt/no-class attendance | Owned attendance modules | Authorized linked class, native session and stable roster evidence |
| New teacher/student/account screens | Owned web components/copy | Native session/org context and thin route/menu/account delegates |
| Synthetic Classes preview | Own preview/demo module only | Manager-hosted route; never a real enrollment authority |
| Six historical migration revisions | Own implementation, retain discovered revision wrappers | SQLModel metadata registration and coordinated Alembic graph |
| Build/headroom/source/runtime packaging | Own deploy scripts/config wrapper where supported | Current Next config/server wrapper/Nginx patches stay explicit until proven replaceable |
| Superadmin self-role UI predicate, owner email DTO | Small compatibility patches or proposed upstream fixes | Do not change grants or weaken ordinary-manager/privacy restrictions |

The NRRU bridge is **NRRU → LearnHouse-native users/courses/access + our backend
extension**. My classes is our projection of linked NRRU classes, not an official
upstream feature, separate catalog or independent login. Native course access/
enrollment integration remains unfinished. Read-only staff directory/timetable
association does not authorize teaching, enrollment or course ownership. CourseMax
is the source/reference to port from and eventual retirement target, never a runtime
dependency of the extension. LINE login/LIFF is present; messaging webhook/task hub
is not yet ported and must enter the extension when implemented.

## Native seams: do not simply revert these patches

**Authentication is the highest-risk extraction.** Existing changes span native
`security/auth.py`, `security/session_context.py`, `routers/auth.py`, `routers/mfa.py`,
`services/auth/session.py` and `services/orgs/auth_policy.py`. Their provider-subject
resolution, strict issuer/audience, org policy, refresh replay handling, revocation,
logout and single-use MFA cannot be replaced by moving the Google router. A
FastAPI dependency override alone does not intercept direct helper calls in
refresh/MFA/logout/collaboration. Keep legacy password behavior and retired unsafe
Google paths safe throughout; never re-enable native email-only Google resolution.

Prefer explicit, small calls into extension adapters at these seams, with native
policy still authoritative. Where upstream lacks a safe hook, obtain approval for
a minimal compatibility patch. No runtime monkeypatching, production
`dependency_overrides`, source-string rewriting at startup, import-order route
shadowing, or arbitrary callback replay. Until a patch has a tested replacement,
retain and freeze it rather than claim zero upstream changes.

**Lifecycle requires pre-side-effect hooks.** Course retention must veto deletion
BEFORE files are removed, inside the same serialization contract as class writes.
An FK/DB trigger alone cannot restore files already deleted. Profile edits must
lock/cancel provider attachment before manual writes so unsaved/manual choices win.
These are deliberate native hooks, not an excuse for embedding feature logic.

**Database discovery needs explicit verification.** Native Alembic walks `src/db`,
and native startup runs `SQLModel.metadata.create_all`. Moving models out of that
tree without registration can omit them from autogenerate or create tables without
guards. Prove bootstrap ordering, fresh and existing schema behavior and guard
installation offline first. The native-user unique email index is an explicit
schema exception; do not remove it when extracting the self DTO. Preserve six
revision IDs/ancestry and reconcile the actual staging schema (frozen additive SQL,
not a fully stamped migration chain). A future separate migration location/branch
requires tested config and merge/dependency design; this dry run does not add one.

**Web routing needs wrappers, not core duplication.** Keep callback/check-in/receipt
URLs stable. Move owned UI/provider orchestration and translations behind adapters;
retain only individually reviewed delegates in login/AuthContext, account menus,
HeaderProfileBox, routing/BFF/cookie policy, i18n and layout where necessary.
Preserve SSR/hydration, native tokens, host-only cookies, exact-origin checks,
private-cache/referrer headers and attribution. Do not fork the whole native shell.

## Extraction sequence and acceptance gates

1. Introduce owned package, explicit bootstrap and adapters; retain old import
   shims where required. Move pure policies/parsers/proof first. No schema changes.
2. Move own models/services/routers/tests with stable identities and transactions.
   Prove model discovery, native creation/access, FK/guards and concurrency.
3. Extract provider logic while preserving/shortening reviewed native auth hooks.
   Test password + Google + LINE + MFA + refresh + logout + revocation + denied
   sessions through every native consumer; optional-import failure cannot break login.
4. Move UI into owned frontend modules with thin registered routes/menu/account
   delegates. Complete the actual NRRU→native enrollment/access bridge, not a demo
   catalog. Synthetic desktop/mobile EN/TH persisted teacher/student tasks required.
5. Replace/remove each historical patch only after equivalent tested behavior;
   inventory retained hooks and optional upstreamable fixes. Update image recipes
   for every moved file and verify actual baked bytes/complete web artifact.
6. Rehearse an explicitly pinned new upstream update in a separate disposable
   checkout, reconcile migration heads/metadata, run full adapter/auth/permissions/
   retention/task regressions and document conflicts. Do not run the CLI updater on
   staging. Runtime upgrades still need capacity/backups/rollback and approval.

No coordinated upgrade safety, full extraction or production parity is accepted
by the 25 pure-policy tests. No unported feature is implemented by this document.

## Reproduce without touching live services

From the fork root, choose a NEW scratch path outside the repository:

```sh
python3 -B scripts/extensions/dry_run.py --out /absolute/new/scratch-path
(cd /absolute/new/scratch-path/apps/api && \
 python3 -B -m unittest src.route66_ext.tests.services.test_attendance_policy -q)
python3 -B -m unittest discover -s scripts/extensions -p 'test_*.py' -q
python3 -B scripts/extensions/check_boundary.py
```

The boundary gate compares against the recorded snapshot, including committed,
staged, unstaged and nonignored untracked changes. It allows only declared owned
paths or exact-content exceptions with rationale, approval reference, tests and
replacement plan. Preserved unrelated untracked workflow/`.impeccable/` are not
permission to add/edit them. It is an advisory gate, not an authorization boundary:
review changes to the policy/tool itself; do not refresh the snapshot to hide a
failure. Historical added modules outside the new namespace are frozen too, except
own deployment paths. Future exact route/model/migration shims require review.
