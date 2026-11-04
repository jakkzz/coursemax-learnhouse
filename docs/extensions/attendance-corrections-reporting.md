# Attendance corrections, history and CSV — deployed

2026-11-04 12:01 UTC. **Deployed and verified.**
Application source `f23ccdf0157a77d55b070a9e121c7df0b058c87f` (feature `41c8163e`
plus a backend-test-only refinement). Successful web artifact source `41c8163e`;
both `apps/web` trees equal `b0c5d685733ac2e48c76cd01e0cc22806b69338f`.
Live source `f23ccdf0`, image `6fe00d32`, release `attendance-f23ccdf0-20261104`.
Web source/BUILD_ID remains the exact successful artifact `41c8163e`.
Correction-aware fallback is `88335321` (same new API, retained `e142f6e3` frontend).

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
- **60 baked PostgreSQL/HTTP/policy checks pass** in the final candidate:10 correction/
  reporting tests (concurrency, lost acknowledgement, rollback, snapshot timing,205
  sessions and1000 members with fewer than30 SQL statements per summary/export),
  one withdrawn-class projection,25 pure policy and24 existing attendance/arrival
  regressions. This fresh complete run supersedes the earlier23/24 plus isolated retry.
- **Two packaged native-auth teacher/student workflows (four actor journeys)** pass
  at EN1440/TH390: actual QR scan, correction, committed phone/receipt update, own
  history, matching manager summary/CSV, reset; withdrawn own-history navigation
  remains available and new scans are denied. Persisted six decisions/two original
  scans, unchanged native roles and QR session version.
- **Actual correction-aware fallback** passes three native-auth read journeys;
  corrected history, own receipts and summary remain readable, with all15 academic/
  attendance/identity/access fingerprints identical across the code-only change.
- **Four live anonymous entry/denial checks** pass EN/TH ×1440/390: providers/password
  visible; report/history/CSV and valid anonymous decision writes all denied401;
  no page errors/overflow. No real account or attendance mutation for acceptance.
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

## Deployment, resources and recovery

The earlier source checkpoint waited below25GiB; no gate was weakened. Capacity
recovered before the owner's deployment request. Candidate build minimum available
RAM3.021GiB; fallback3.076GiB. Activation admission RAM3.15GiB/disk28.47GiB passed
normal gates; minimum observed during activation **2.694GiB**, no override.
Only app replaced/gateway reloaded. Owned launcher, schema, environment, limits,
mounts and DB/Redis/gateway identities verify unchanged. Fresh quiesced DB/schema/
content snapshots and checksums pass; no migration/stamp/backfill or real-data test.
The roster worker retains Redis leadership; actual source acquisition is not asserted.

Candidate verification and live re-verification cover **1267 API files,5536 web
entries,2681 retained static assets**, source/BUILD_ID, parent layers and runtime
configuration. Complete recoverable OCI layouts are retained: parent76, candidate80,
fallback78 verified blobs. Identical immutable blobs are hard-linked to retained
recovery files, never modified. Restore commands are in each layout proof; the
existing complete parent archive is also retained. No folders/images were pruned.
Fixtures were torn down and the idle owned builder stopped.

The release's `rollback.compose.json` selects tested correction-aware image
`88335321`, **not** the old unaware API. Keep new decisions/scans/history intact;
never restore an older database or reset decisions for code rollback. Full old
`310ed40a` is retained for provenance, not a safe post-decision reader.

One isolated seed attempt used two asyncio loops with the same engine and failed;
combined it into one loop, recreated only disposable fixtures and reran successfully.
This was fixture plumbing, not an application or production defect.

Implementation, packaging, recovery rehearsal and bounded deployment are complete.
The [rehearsed plan](attendance-corrections-reporting-plan.md) remains the scope;
B05/B06/B07 are not accepted parity. Real scheduled roster acquisition, leave and
broader provider/device/historical-migration acceptance remain separate.
