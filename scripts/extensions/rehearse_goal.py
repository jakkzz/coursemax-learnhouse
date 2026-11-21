#!/usr/bin/env python3
"""Read-only SOURCE CONTRACT AUDIT for the goal sequence.

This module reads text files only.  It never imports application modules, contacts a
service, writes application data, or treats source observations as runtime acceptance.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

AUDIT_CAPABILITIES = {
    "A01": "Google/linked LINE login, profile/email gating, browser recovery",
    "A02": "Provider linking, merge, Google replacement, retired identities",
    "A03": "Admin profile/lifecycle, suspension, revocation, anonymization/audit",
    "A04": "Verification/admin email and delivery-event deduplication",
    "A05": "Platform/course roles, instructor assignment, dual-role view",
    "A06": "Safe course/catalog/offering administration and setup audit",
    "A07": "Masked provider secrets and non-secret configuration",
    "A08": "Runtime capability discovery plus independent authorization",
    "B01": "Catalog, landing/setup workspaces, dashboards and enrollment",
    "B02": "Registrar/manual roster, conflicts, membership/sync history",
    "B03": "Terms/weeks/rotation, holidays/make-up and document review",
    "B04": "Run-of-show and chapter-owned supplementary lessons",
    "B05": "Entry/exit QR, handoffs, cutoffs, replay safety and soft geofence",
    "B06": "No-class state/history and attendance denominator",
    "B07": "Absence/review/excusal, risk summaries and CSV",
    "B08": "Class-specific LINE group QR management/protected viewing",
    "B09": "LINE in-app roster task hub and authorized check-in/tool joins",
    "C01": "Guided setup, focused authoring, preview/autosave/deep links",
    "C02": "Draft/import/review/publication/restore/unpublish/scheduling",
    "C03": "Approved Thai style examples and protected-text exclusions",
    "C04": "Authored media, protected resources, activation/order/credits",
    "C05": "Presentations, slide versions/views, lesson complete/reopen",
    "C06": "Curated media/license manifest and bundled material files",
    "C07": "Review cards/activity revisions and offering snapshots/drift",
    "C08": "Reference originals, source-backed outcomes and rubric alignment",
    "C09": "Thai teaching-document export and actual-file fidelity",
    "C10": "English/Thai, mobile/help/legal, safe login and deep links",
    "D01": "Student/staff coursework hubs, queues, status and history",
    "D02": "Text/link/file/mixed submissions and structured worksheets",
    "D03": "Sealed quizzes/order, resume/clocks/extensions, essays and evidence",
    "D04": "Independent answer/score policies and content revisions",
    "D05": "Category redistribution/rounding and weekly participation",
    "D06": "Rubrics, criteria, missing/excused, team scores and releases",
    "D07": "Atomic prepare/execute/cancel bulk release and revision binding",
    "D08": "Review/dispute requests, messages, decisions and history",
    "D09": "Finalize/reopen, frozen reports, preview and safe CSV/PDF",
    "D10": "Grading-assistant readiness/activation and human apply/reject",
    "D11": "Advisory speech/video analysis, provenance and retention",
    "D12": "Immutable receipts, scan/quarantine, private preview/download",
    "E01": "Team Sorter automatic/manual grouping, ratings and moves",
    "E02": "Project teams/tasks, membership and contribution scoring",
    "E03": "Peer review snapshots/responses, privacy and finalization",
    "E04": "Bingo prompts, scopes, cards and peer-confirm claims",
    "E05": "Live Board Q&A, anonymity/accountability and polls",
    "E06": "Authorized join/streams/reconnect and fan-out correctness",
    "E07": "Bulletin, pin/edit/archive, links and class-safe task details",
    "E08": "LINE contacts/webhooks plus exceptional-send authorization/audit",
    "O01": "Quiz timeout and assessment-policy reconciliation workers",
    "O02": "Roster sync and scheduled chapter publication/cancellation",
    "O03": "Private storage/scanning plus optional transcription/purge",
    "O04": "Health/watchdog, revisions, images, restore, rollback, headroom",
    "O05": "Safe parsing/fetching/providers/media and credential boundaries",
}

# Explicit reviewed order.  Dependencies are phase IDs, never prose positions.
PHASE_MANIFEST = [
    {"id": "LH-00", "depends_on": [], "audit_ids": [], "authority": "shared/native preservation",
     "capability": "preserve handoff and settle launch decisions",
     "exit_tasks": ["owner launch decisions", "recoverable references", "approved preservation before deletion"]},
    {"id": "LH-01", "depends_on": ["LH-00"], "audit_ids": ["A07", "A08", "C10", "O04"], "authority": "native base; extension adapters",
     "capability": "usable private LearnHouse base and operational safeguards",
     "exit_tasks": ["private-file authorization", "coordinated restore", "compatible rollback", "mobile synthetic task acceptance"]},
    {"id": "LH-02", "depends_on": ["LH-01"], "audit_ids": ["A01", "A02", "A03", "A04"], "authority": "native account/session; extension provider proofs",
     "capability": "Google and linked LINE identity, recovery, lifecycle and audit",
     "exit_tasks": ["native session/lifecycle routes", "provider acceptance", "revocation and recovery matrix"]},
    {"id": "LH-03", "depends_on": ["LH-02"], "audit_ids": ["A05", "A06", "B01", "B02", "B03"], "authority": "native course/access; extension institutional class evidence",
     "capability": "course, offering, roster and institutional foundation",
     "exit_tasks": ["synthetic class authorization", "official/manual roster reconciliation", "term and document review"]},
    {"id": "LH-04", "depends_on": ["LH-03"], "audit_ids": ["B05", "B06", "B07", "B08", "B09"], "authority": "extension attendance evidence; native roster/session",
     "capability": "attendance, absence/reporting and LINE classroom access",
     "exit_tasks": ["absence and override handlers", "historical reports and CSV", "LINE/device/handoff and geofence acceptance"]},
    {"id": "LH-05", "depends_on": ["LH-03"], "audit_ids": ["E01", "E02", "E03", "E04", "E05", "E06"], "authority": "extension tools under native class authorization",
     "capability": "teams, peer tools, live classroom tools and streams",
     "exit_tasks": ["cross-class denial", "privacy thresholds", "reconnect and distributed fan-out decision"]},
    {"id": "LH-06", "depends_on": ["LH-04", "LH-05"], "audit_ids": ["C07", "C08", "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10", "D11", "D12", "E08", "O01", "O03"], "authority": "native content/access plus governed extension evidence",
     "capability": "task hubs, submissions, assessment, Gradebook and governance",
     "exit_tasks": ["immutable submissions", "governed grading/release/dispute", "workers, exports, concurrency and recovery"]},
    {"id": "LH-07", "depends_on": ["LH-06"], "audit_ids": ["B04", "C01", "C02", "C03", "C04", "C05", "C06", "C09", "E07", "O02", "O05"], "authority": "native authoring/player where equivalent; extension institutional context",
     "capability": "syllabus editor, dated teaching plan, authoring, presentations and teaching UX",
     "exit_tasks": ["actual persisted syllabus and plan", "publication/recovery", "EN/TH mobile teacher/student walkthroughs"]},
    {"id": "LH-08", "depends_on": ["LH-07"], "audit_ids": [], "authority": "owner acceptance ledger",
     "capability": "close all 52 audit decisions without implicit acceptance",
     "exit_tasks": ["52 accepted/deferred/retired decisions", "restore/provider/upgrade evidence", "owner parity acceptance"]},
    {"id": "LH-09", "depends_on": ["LH-08"], "audit_ids": [], "authority": "approved migration interfaces; native target authorities",
     "capability": "approved real-data migration, reconciliation and cutover last",
     "exit_tasks": ["explicit migration approval", "idempotent dry-run and reconciliation", "rollback/final delta", "approved cutover and source retention"]},
]

REQUIRED_FILES = [
    "apps/web/extensions/route66/components/Dashboard/Pages/ClassesPreview/ClassesPreview.tsx",
    "apps/web/extensions/route66/app/orgs/[orgslug]/dash/classes-preview/page.tsx",
    "apps/web/app/orgs/[orgslug]/dash/classes-preview/page.tsx",
    "apps/web/extensions/route66/components/Objects/Classes/ClassesWorkspace.tsx",
    "apps/web/extensions/route66/components/Objects/Classes/TeacherTimetable.tsx",
    "apps/web/extensions/route66/components/Objects/Account/subpages/SchoolIdentity.tsx",
    "apps/api/src/route66_ext/bootstrap.py",
    "apps/api/src/route66_ext/routers/academic_classes.py",
    "apps/api/src/route66_ext/routers/class_connections.py",
    "apps/api/src/route66_ext/routers/learning_access.py",
    "apps/api/src/route66_ext/adapters/native_learning_access.py",
    "apps/api/src/route66_ext/db/class_attendance.py",
    "apps/api/src/route66_ext/services/class_attendance.py",
    "apps/api/src/route66_ext/routers/class_attendance.py",
    "apps/web/extensions/route66/app/orgs/[orgslug]/(withmenu)/attendance/page.tsx",
    "apps/web/app/orgs/[orgslug]/(withmenu)/attendance/page.tsx",
]
MENU_PATHS = [
    "apps/web/components/Dashboard/Menus/DashLeftMenu.tsx",
    "apps/web/components/Dashboard/Menus/DashMobileMenu.tsx",
]
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".py"}


def validate_manifest(manifest: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids = [p.get("id") for p in manifest]
    if any(not isinstance(i, str) or not i for i in ids):
        errors.append("phase IDs must be non-empty strings")
    if len(ids) != len(set(ids)):
        errors.append("duplicate phase ID")
    positions = {phase_id: index for index, phase_id in enumerate(ids) if isinstance(phase_id, str)}
    edges: dict[str, list[str]] = {}
    seen_audits: list[str] = []
    for index, phase in enumerate(manifest):
        phase_id = phase.get("id")
        deps = phase.get("depends_on")
        audits = phase.get("audit_ids")
        if not isinstance(deps, list) or not isinstance(audits, list):
            errors.append(f"{phase_id or index}: dependencies and audit IDs must be lists")
            continue
        edges[str(phase_id)] = [str(dep) for dep in deps]
        for dep in deps:
            if dep not in positions:
                errors.append(f"{phase_id}: missing dependency {dep}")
            elif positions[dep] >= index:
                errors.append(f"{phase_id}: dependency {dep} is not earlier")
        for audit_id in audits:
            if audit_id not in AUDIT_CAPABILITIES:
                errors.append(f"{phase_id}: unknown audit ID {audit_id}")
            seen_audits.append(audit_id)
        for field in ("authority", "capability", "exit_tasks"):
            if not phase.get(field):
                errors.append(f"{phase_id}: missing {field}")
    duplicates = sorted({item for item in seen_audits if seen_audits.count(item) > 1})
    if duplicates:
        errors.append("duplicate audit IDs: " + ", ".join(duplicates))
    missing = sorted(set(AUDIT_CAPABILITIES) - set(seen_audits))
    if missing:
        errors.append("unassigned audit IDs: " + ", ".join(missing))
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting:
            errors.append(f"dependency cycle at {node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in edges.get(node, []):
            if dep in edges:
                visit(dep)
        visiting.remove(node); visited.add(node)
    for node in edges:
        visit(node)
    return sorted(set(errors))


def _read(root: pathlib.Path, relative: str, malformed: list[str]) -> str:
    path = root / relative
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError):
        malformed.append(relative)
        return ""
    if "\x00" in text:
        malformed.append(relative)
        return ""
    return text


def _contract(name: str, passed: bool, files: list[str], detail: str) -> dict[str, Any]:
    return {"name": name, "observed": passed, "files": files, "detail": detail,
            "claim": "source contract observed" if passed else "source contract missing",
            "runtime_evidence_required": True}


def audit(root: str | pathlib.Path, manifest: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root = pathlib.Path(root)
    manifest = PHASE_MANIFEST if manifest is None else manifest
    manifest_errors = validate_manifest(manifest)
    missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
    malformed: list[str] = []
    texts = {path: _read(root, path, malformed) for path in REQUIRED_FILES if (root / path).is_file()}

    production_sources: list[tuple[str, str]] = []
    source_roots = [root / "apps/web/extensions/route66", root / "apps/api/src/route66_ext"]
    for source_root in source_roots:
        if not source_root.is_dir():
            continue
        for path in source_root.rglob("*"):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES and not ({"tests", "test", "__pycache__"} & set(path.parts)) and not path.name.startswith("test_"):
                relative = str(path.relative_to(root))
                production_sources.append((relative, _read(root, relative, malformed)))
    fixture_pattern = re.compile(r"(?:from\s*|import\s*\(|require\s*\(|import\s+|export\s+[^;]*?from\s*)['\"][^'\"]*(?:tests?/fixtures|fixtures/ClassesPreview)[^'\"]*['\"]", re.S)
    fixture_imports = sorted(path for path, text in production_sources if fixture_pattern.search(text))

    preview_files = REQUIRED_FILES[:2]
    forbidden_preview = re.compile(r"useReducer|localStorage|sessionStorage|\b(?:role|view|query)\b")
    redirect_checks = []
    for path in preview_files:
        text = texts.get(path, "")
        redirect_checks.append(bool(re.search(r"import\s*\{\s*redirect\s*\}\s*from\s*['\"]next/navigation['\"]", text)
                                    and re.search(r"redirect\(\s*['\"]/classes['\"]\s*\)", text)
                                    and not forbidden_preview.search(text)))
    delegate = texts.get(REQUIRED_FILES[2], "")
    redirect_ok = all(redirect_checks) and "@/extensions/route66/app/orgs/[orgslug]/dash/classes-preview/page" in delegate

    school = texts.get(REQUIRED_FILES[5], "")
    identity_ok = all(token in school for token in ("/api/v1/school-identity/me", "/api/v1/school-identity/search", "/api/v1/school-identity/confirm", "confirm_own_name"))
    timetable = texts.get(REQUIRED_FILES[4], "")
    timetable_ok = "/api/v1/school-identity/me" in timetable and "TeacherTimetable" in timetable and "SchoolTimetable" in timetable
    workspace = texts.get(REQUIRED_FILES[3], "")
    workspace_ok = "<TeacherTimetable" in workspace and "/api/v1/academic-classes" in workspace and "nativeCoursePath" in workspace

    bootstrap = texts.get(REQUIRED_FILES[6], "")
    academic_router = texts.get(REQUIRED_FILES[7], "")
    bridge_ok = all(token in bootstrap for token in ("academic_classes.router", "class_attendance.router", "school_identity.router")) and all(
        token in academic_router for token in ("class_connections_router", "learning_access_router", "include_router")) and all(
        texts.get(path, "") for path in REQUIRED_FILES[8:11])
    attendance_ok = all(texts.get(path, "") for path in REQUIRED_FILES[11:16]) and "router = APIRouter" in texts.get(REQUIRED_FILES[13], "") and "@/extensions/route66" in texts.get(REQUIRED_FILES[15], "")

    menu_links = []
    for path in MENU_PATHS:
        if (root / path).is_file() and "/dash/classes-preview" in _read(root, path, malformed):
            menu_links.append(path)

    contracts = [
        _contract("legacy preview redirects to /classes and ignores role/view/query state", redirect_ok, preview_files + [REQUIRED_FILES[2]], "Both compatibility entries redirect; native route delegates to the extension."),
        _contract("production has no static/dynamic fixture import or re-export", not fixture_imports, [p for p, _ in production_sources], "Test fixture files are allowed; production imports/re-exports are not."),
        _contract("SchoolIdentity fetch/search/confirm contract", identity_ok, [REQUIRED_FILES[5]], "Self-confirmation is not admin identity-review acceptance."),
        _contract("TeacherTimetable consumes its own school identity endpoint", timetable_ok, [REQUIRED_FILES[4]], "The timetable projection is distinct from native course content."),
        _contract("classes workspace integrates timetable, class API and native course handoff", workspace_ok, [REQUIRED_FILES[3]], "Native content/progress remain authoritative."),
        _contract("native access bridge source registration and owned files", bridge_ok, REQUIRED_FILES[6:11], "Connection/access code is present; runtime activation and acceptance remain required."),
        _contract("persisted attendance source and routes", attendance_ok, REQUIRED_FILES[11:16], "Attendance/check-in source exists; absence/reporting is not inferred."),
    ]
    structural_failures = sorted(set(missing + malformed + fixture_imports))
    if not redirect_ok: structural_failures.append("redirect_contract")
    if not identity_ok: structural_failures.append("school_identity_contract")
    if not timetable_ok: structural_failures.append("teacher_timetable_contract")
    if not workspace_ok: structural_failures.append("classes_integration_contract")
    if not bridge_ok: structural_failures.append("native_bridge_registration_contract")
    if not attendance_ok: structural_failures.append("attendance_source_contract")
    structural_failures.extend("manifest: " + error for error in manifest_errors)
    structural_failures = sorted(set(structural_failures))

    audit_entries = []
    phase_for = {audit_id: phase["id"] for phase in manifest for audit_id in phase.get("audit_ids", []) if audit_id in AUDIT_CAPABILITIES}
    for audit_id, capability in AUDIT_CAPABILITIES.items():
        audit_entries.append({"id": audit_id, "capability": capability, "phase": phase_for.get(audit_id),
                              "decision": "pending", "runtime_evidence_required": True})

    return {
        "name": "SOURCE CONTRACT AUDIT",
        "acceptance": "NOT runtime, deployment, migration, parity, or user-task acceptance",
        "read_only": True, "app_modules_imported": False, "network": False, "database": False,
        "ok": not structural_failures,
        "counts": {"audit_ids": len(audit_entries), "phases": len(manifest), "contracts_observed": sum(c["observed"] for c in contracts),
                   "contracts_total": len(contracts), "structural_failures": len(structural_failures), "pending_audit_decisions": len(audit_entries)},
        "manifest_errors": manifest_errors,
        "phase_manifest": manifest,
        "audit_ledger": audit_entries,
        "source_contracts": contracts,
        "topology": {"required_files_missing": missing, "malformed_sources": sorted(set(malformed)),
                     "production_test_fixture_imports": fixture_imports, "legacy_preview_redirect_observed": redirect_ok,
                     "legacy_native_menu_links": menu_links},
        "observed_not_accepted": {
            "native_class_connection": "source contract observed; runtime evidence required",
            "attendance_checkin_no_class": "source contract observed; runtime evidence required",
        },
        "remaining_blockers": [
            "production source retirement is not deployed or runtime-verified",
            "actual syllabus editor and persisted dated teaching plan are missing",
            "absence submission/review/override, historical reporting and CSV remain missing",
            "identity correction/admin-review handlers and acceptance remain missing",
            "student task hub is missing; native content/progress must remain authoritative",
            "parent review found seven academic tables empty; no historical migration is authorized",
            "all 52 audit IDs require accepted or explicitly approved defer/retire decisions",
            "approved real-data migration, reconciliation and cutover must occur last",
        ] + (["legacy preview menu links remain; exact native paths require narrow prior review: " + ", ".join(menu_links)] if menu_links else []),
        "structural_failures": structural_failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    result = audit(args.root)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
