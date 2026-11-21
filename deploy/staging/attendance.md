# Attendance staging release — 2026-10-14

Deployed source/image **`a9a1c84b`** at `learn.route66.click`. Open **My classes →
Attendance** for an authorized class. This release adds session scheduling,
expiring entry/follow-up QR display, roster-authorized check-in, immutable private
receipts, searchable teacher attendance and reasoned no-class/restore controls.
[Contract and remaining parity work](../../docs/attendance-port.md).

## Observed release evidence

- 147 isolated PostgreSQL/auth/policy tests, 60 OAuth/proof regressions and 13
  frontend wrapper/role-control regressions passed.
- Full production frontend bundle and generated-route TypeScript passed. Eight
  compiled teacher/student EN/TH tasks passed at 1440/390, including persisted
  receipt-link navigation/reload, expiry recovery and same-page follow-up codes.
- Eight live native-admin/student EN/TH1440/390 checks passed attendance entry,
  unknown QR rejection, private receipt denial and return to classes, with no
  academic writes. Two existing live native-auth flows passed. These empty-state
  live checks are not an institutional teacher/student attendance acceptance.
- All 5,242 desired baked web entries and seven API files match reviewed bytes,
  links and modes. Exact source revision is offered through the native source menu.
- Protected pre-release PostgreSQL/content/runtime backups and saved/checksummed
  `d43256b0` parent retained. PostgreSQL restored on an isolated private Unix socket
  and identity snapshots matched. Content/runtime archive integrity passed; this
  is not an off-host coordinated full-application disaster-recovery acceptance.
- Four additive tables and nine database guards installed from frozen, tested SQL
  atomically, without stamping/backfill. All four attendance tables were empty at
  verification: no real students, rosters, teaching assignments or attendance
  evidence imported/created by this release.
- Only staging app container replaced; gateway configuration unchanged and process
  reloaded after app health. All other running container IDs, native profiles,
  provider ownership, account grants and identity policy preserved. CourseMax
  remained healthy and unchanged. No proactive messaging or infrastructure cleanup.
- Finish verdict: scoped **ship**, inline review/documentation rather than an
  independent review; native visual system retained, detector had no findings.

## Operational caution

Before build/packaging/migration/restart, the resource gates passed. The final
post-release host check found 20.25 GiB free disk but only 2.58 GiB available RAM;
a recheck was 2.45 GiB. App remained healthy at about 510 MiB. Further heavy
operations are blocked until the 3 GiB RAM reserve recovers. No pruning, cache
flush, unrelated restart or memory-control change was made. Do not treat these
observations as an approval to relax the reserve or clean shared infrastructure.

Code rollback preserves the additive schema and all new evidence, never restores
an old DB or undoes an account grant. The retained parent is usable only while
attendance tables remain empty; after evidence exists, review a compatible guarded
rollback or forward recovery. Absence/overrides, historical summaries/CSV, LINE
classroom/device acceptance, calendar parity and real migration remain separate.
