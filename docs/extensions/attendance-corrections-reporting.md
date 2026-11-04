# Attendance corrections, history and CSV — implementation checkpoint

2026-11-04. **Implemented and pushed; not deployed.**
Application source `f23ccdf0157a77d55b070a9e121c7df0b058c87f` (feature `41c8163e`
plus a backend-test-only refinement). Successful web artifact source `41c8163e`;
both `apps/web` trees equal `b0c5d685733ac2e48c76cd01e0cc22806b69338f`.
Live remains `e142f6e3` / `310ed40a`, release `ui-repairs-e142f6e3-20261104`.

## Delivered source behavior

- Native-authorized teacher decisions append `attendance_decided` to the existing
  immutable attendance journal. Present/Late/Absent/Excused/reset, meaningful reason,
  exact class/member, evidence-token conflict detection and UUID idempotency.
  Original scan times/statuses/receipts and QR session version remain unchanged.
- Session/own views, new scans, old challenge retries, saved receipts, history,
  summary and CSV use the canonical correction-aware projection.
- Observed roster membership intervals preserve manual control and withdrawal/
  reactivation gaps. Unknown/uncollected history is not invented absence; an explicit
  retrospective decision establishes only its reviewed pair. No-class suppresses
  outcomes/denominator without deleting history; restoration recovers evidence.
- Manager summaries/CSV share server arithmetic, known coverage and date selection;
  paged member/own histories do not truncate totals at the session picker's200 rows.
  Reports use a read-only repeatable-read snapshot and its database timestamp.
  UTF-8 BOM/quoted CRLF export neutralizes formula-leading text and omits reasons,
  provider details, raw journal and QR secrets.
- EN/TH teacher inline editor, focus/return, stale review with preserved draft,
  exact lost-response retries (including auth recovery), own history and corrected
  receipts, class summaries and credentialed CSV download are wired.
- Withdrawn owners retain an explicit My classes → My attendance history-only link;
  no restored native course availability, roster management or new scan permission.
- Manager history requests supersede earlier member requests; auth/access loss clears
  privileged report data. Network503 keeps recoverable context. Projector remains
  aggregate physical scans, not counts of excused corrections.

No new table/migration, account/enrollment writer, scheduler, service, dependency,
activation flag or native hook. Leave requests remain the next slice.

## Sequential subagents and parent integration

Four `openai-codex/gpt-5.6-sol` Pi agents, **one at a time**:

1. Backend implementation and focused PostgreSQL/HTTP tests.
2. Frontend wiring, bilingual copy and real-component fixtures.
3. Read-only review of the combined workflow.
4. Minimal repairs/regressions for the seven reviewed issues.

Parent checked handoffs, ran actual tests, corrected browser package resolution,
control labeling and selector assertions, added the 1000-member query-bound test,
localized coverage text and reconciled historical-read versus lost-identity streaming.
Private prompts/sessions/handoffs/logs:
`~/.local/state/learnhouse-attendance-implementation-20261104/`.

## Observed validation

- GitHub **41820493946** passed full frontend bundle/types at exact web source.
- **36 PostgreSQL/HTTP/policy checks pass**:10 correction/reporting tests (including
  two reviewers, lost acknowledgement, rollback, snapshot timing,205 sessions,
 1000 members with fewer than30 SQL statements per summary/export), one withdrawn
  class projection check and25 actual pure-policy checks.
- Existing attendance/arrival regression run: **23/24 passed**. Its remaining test
  still expected withdrawal to revoke historical reading. Refined it to assert own
  history continues after withdrawal and true identity loss closes the stream;
  that exact test then passed separately. Do not call this a fresh24-test rerun.
- **Five component browser workflows pass** using actual attendance components,
  synthetic same-origin HTTP/SSE and pinned native CSS: English desktop teacher
  correction/stale/auth/lost-ack/race/export flow, Thai mobile manager report/export,
  English desktop/Thai mobile own-history flows, mobile corrected-receipt/reset.
  No page errors/overflow. Unrelated shell is substituted; not native-auth acceptance.
- **Seven Bun client tests /52 assertions**,26 focused source checks,20 offline plan
  rehearsal checks and31 tooling tests pass; extension boundary/diff checks pass.
- Impeccable detector during frontend agent returned `[]`; parent inspected desktop/
  mobile report/history captures. This is not accessibility certification, physical
  device/provider or a new full audit. Final localized coverage copy is typechecked;
  the retained visual captures precede that small text refinement.

## Resource boundary and remaining delivery

The shared lock was respected throughout; refused attempts waited. Package preparation
was admitted at25.09GiB free, with normal RAM headroom. Afterwards free disk was
**24.43GiB**, below the global25GiB build floor. Six bounded rechecks later
found about24.997GiB—still below the same unchanged floor. Packaging/build, packaged native-auth
proof and app activation must wait for normal capacity. Do not lower the threshold,
prune retained images/evidence, clear swap, or restart other workloads to force it.
No candidate image was built and no live records/services/schema were changed.

Already retained: verified GitHub artifact/checksum/source, prepared web overlay,
source snapshot and exact current-image OCI layout. Its76 blobs are hash-verified;
identical immutable blobs are hard-linked to retained recovery files, not duplicated
or modified. Complete layout restore command is in `parent-layout-verification.json`.
The normal current rollback archive is also retained. No existing folder/image pruned.

Once admitted:

1. Build/verify the candidate from the prepared parent plus owned API/web overlay
   with maintenance wrapper and `--builder vps-limited`; verify all required bytes,
   modes, runtime configuration and retained assets. Save a complete recoverable image.
2. Build a **correction-aware fallback** (new API projection on retained frontend),
   then exercise actual native-auth teacher/student correction → current/receipt/
   history → matching CSV → reset at EN1440/TH390 in isolated stores.
3. Rehearse that actual fallback reading new synthetic decision history without any
   data restoration or fingerprint drift. Current old API ignores decisions and is
   **not** a valid rollback after the first new decision.
4. Fresh recovery snapshots and ordinary app-only deployment; bounded live entry/
   permission and byte/configuration checks. Do not create real attendance as a test.

These are concrete unfinished delivery checks, not new owner approvals or flags.
The [rehearsed plan](attendance-corrections-reporting-plan.md) remains the scope;
B05/B06/B07 are not accepted parity. Real scheduled roster acquisition, leave and
broader provider/device/historical-migration acceptance remain separate.
