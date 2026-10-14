# LearnHouse fork: extension-first instructions

Read `docs/extensions/development.md`, `docs/extensions/dry-run.md` and
`docs/extensions/boundary.json` BEFORE coding. Read upstream `CONTRIBUTING.md` and
framework instructions for affected apps. When this checkout is under the private
handoff workspace, also read `../AGENTS.md`, `../STATUS.md`, `../PLAN.md` and the
referenced scope/identity documents; current decisions supersede historical notes.

## Current deployed extraction

Live source/image `fe1877c9`; read `docs/extensions/deployment.md` for actual scope.
Owned feature code is extracted; 43 historical original-file patches remain, with
only the router registration changed further. No schema/data migration. Current
upstream default `dev` is still our original `45cf5d4f` baseline: isolated pull
reported zero incoming commits/conflicts, NOT future upgrade compatibility.

## Mandatory boundary

- Put our backend logic/tests in `apps/api/src/route66_ext/`, frontend logic/copy/
  tests in `apps/web/extensions/route66/`. Feature code has been extracted there;
  old feature paths are compatibility delegates, not places to add logic. Read
  `docs/extensions/extraction.md` and the exact extraction map before refactoring.
- Avoid original LearnHouse edits. Native integration uses typed adapters and minimal
  explicit hooks; request approval BEFORE a new core-hook edit and record exact file,
  invariant, alternatives, tests and replacement/update plan. Route/model/migration
  wrappers outside owned paths need exact reviewed registration too.
- Do not auto-refresh the boundary snapshot, widen allowlists, modify checker policy
  to hide failures, monkeypatch native internals, shadow duplicate routes or silently
  restore unsafe native auth. Current auth/lifecycle/retention patches remain frozen
  until a tested replacement exists.
- Run `python3 -B scripts/extensions/check_boundary.py` and
  `python3 -B -m unittest discover -s scripts/extensions -p 'test_*.py' -q`.
  These are advisory source-placement tests, not runtime or upgrade acceptance.
- One LearnHouse account/session/content/access authority. Our NRRU bridge/class
  metadata/academic evidence is an extension, not a parallel catalog/login or runtime
  dependency on old CourseMax. My classes is not an upstream-official feature.
- Preserve identity ownership, native org policy, private access, transactions and
  immutable evidence. Keep deployed URLs/table names/revision IDs stable during moves.
- Synthetic tests only; real data migration/provider credentials/retirement require
  specific approval. LINE login/LIFF does not imply Messaging webhook parity. No
  proactive sends by default; no real-session copying or fabricated student emails.
- No automatic upstream updater on the live fork. Pin and rehearse updates separately
  with adapter/auth/MFA/refresh/revocation/enrollment/lifecycle/migration/UI tests.
- Respect AGPL/Enterprise attribution/source obligations. Don't publish private
  institutional records, secrets or evidence with this public source fork.
- Communicate in English; retain natural Thai/English product copy and mobile tasks.

Changes must report owned paths, every unavoidable native hook, actual acceptance
and deployment scope. Existing untracked `.github/workflows/native-google-web.yaml`
and `.impeccable/` are unrelated: leave untouched/uncommitted.

Deployment, cleanup and host mutations are separate from an offline dry run. On the
shared staging host retain >=10 GiB disk (>=12 GiB pre-pull) and >=3 GiB available
RAM; recheck before heavy operations. No broad cleanup or unrelated restarts.
