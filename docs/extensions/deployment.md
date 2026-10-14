# Internal extension release deployed — 2026-10-14

Live `learn.route66.click`: source/image **fe1877c9**. Source extraction details:
[extraction.md](extraction.md); agent contract: [development.md](development.md).
This is namespace isolation, not a new enrollment bridge or full CourseMax parity.

## Observed release

- 157 isolated PostgreSQL/auth/attendance/discovery tests, 73 proof/profile tests,
  26 frontend tests and 13 boundary-tool tests passed. Candidate image native app
  import/OpenAPI plus 35 facade/policy tests passed from baked files.
- Full production web bundle/types and eight compiled EN/TH teacher/student tasks
  passed at 1440/390 with persistent receipts, expiry recovery and no-class/restore.
- Eight live EN/TH attendance entry/private denial/class-return flows and two native
  auth flows passed without academic writes, errors or horizontal overflow. No
  real Google/LINE provider exchange or physical LIFF/device parity claimed.
- 989 tracked API Python files and 5,276 desired web entries verified against baked
  bytes/links/modes. Both implementations and compatibility discovery shims included.
- Protected DB/content/runtime backups and saved/checksummed attendance-capable
  a9a1c84b parent retained. DB restored on isolated socket and identity snapshots
  matched; content/runtime archive integrity passed. Not coordinated off-host DR.
- Only staging app replaced; gateway reloaded. All other container IDs unchanged;
  CourseMax healthy/untouched. Identity/profile/account-grant snapshots, runtime
  file bytes, feature flags and security policy preserved. Preflight environment
  comparison accounts for Compose's escaped `$$` versus actual regex `$` anchor;
  the deployed anchored origin policy itself is unchanged.
- Schema-only PostgreSQL dumps are byte-identical before/after (excluding pg_dump's
  random restrict markers). No migration, stamping, table rename, backfill, real
  class/roster import, grant, proactive message or shared-host mutation.
- Final observed resources:17.74 GiB free disk /5.71 GiB available RAM. Recheck
  before subsequent heavy operations; no cleanup beyond the separately approved
  exact scratch-directory batch.
- Scoped inline architecture/unchanged-UI task review, not an independent review.
  Existing institutional/privacy/device/parity gates remain unresolved.

The compatible parent supports the same attendance schema/receipts. Code rollback
retains the DB, files, identity grants and all new evidence; never restore an old DB.
Do not use an older pre-attendance image for evidence-bearing rollback.

## Requested upstream pull rehearsal

Migration source committed/pushed to `coursemax/staging`, then upstream fetched.
Remote default branch is **dev**, at **45cf5d4f78cf537064070dc8e315a64990d14966**;
remote main is **253cfb1cfc3eda1db7ca3b2d5617877420064fe4**.

An actual `git pull --no-rebase --no-tags upstream dev` ran in a detached isolated
worktree at fe1877c9. Result: **Already up to date; zero conflicts; zero incoming
commits**. Isolated boundary gate passed; primary/deployed source unchanged.

Important: upstream dev is still the same pin used for this fork. No newer upstream
change was exercised. This is NOT proof that future upgrades merge cleanly or remain
compatible. 43 historical original-file patches remain; only the router integration
changed further, while the other 42 were retained byte-identically. Rehearse a new
pinned upstream delta and all adapter/security/lifecycle/migration/task contracts
when one becomes available. Never run the automatic CLI updater on the live fork.
