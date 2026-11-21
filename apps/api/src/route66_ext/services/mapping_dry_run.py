"""Pure, advisory setup rehearsal; NOT authorization or an executable write plan.

Consumes synthetic snapshots shaped like our existing extension APIs. No route,
bootstrap import, persistence, account matching or enrollment is introduced.
"""
from __future__ import annotations

import re


_REGISTRY_ID = re.compile(r"[1-9][0-9]{0,19}")
_SECTION = re.compile(r"[A-Za-z0-9/-]{1,40}")


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _registry_id(value: object) -> bool:
    return isinstance(value, str) and _REGISTRY_ID.fullmatch(value) is not None


def _section(value: object) -> bool:
    return isinstance(value, str) and _SECTION.fullmatch(value) is not None


def _year(value: object) -> bool:
    return type(value) is int and 2500 <= value <= 2700


def _semester(value: object) -> bool:
    return type(value) is int and 1 <= value <= 3


def _target_valid(target: object) -> bool:
    return (isinstance(target, dict)
            and _positive_int(target.get("course_id"))
            and _positive_int(target.get("teacher_id"))
            and _registry_id(target.get("registry_course_id"))
            and _year(target.get("academic_year"))
            and _semester(target.get("semester"))
            and _section(target.get("section")))


def _catalog_valid(catalog: object) -> bool:
    if (not isinstance(catalog, dict)
            or not isinstance(catalog.get("courses"), list)
            or not isinstance(catalog.get("teaching_assignments"), list)
            or type(catalog.get("can_assign_teachers")) is not bool):
        return False
    for row in catalog["courses"]:
        if (not isinstance(row, dict) or not _positive_int(row.get("id"))
                or "registry_course_id" not in row):
            return False
        binding = row["registry_course_id"]
        # Native extension returns null for courses not yet configured.
        if binding is not None and binding != "" and not _registry_id(binding):
            return False
    return all(isinstance(row, dict)
               and _positive_int(row.get("course_id"))
               and _positive_int(row.get("user_id"))
               and type(row.get("active")) is bool
               for row in catalog["teaching_assignments"])


def _projection_valid(projection: object) -> bool:
    if not isinstance(projection, dict) or not isinstance(projection.get("classes"), list):
        return False
    for row in projection["classes"]:
        if (not isinstance(row, dict)
                or "course_id" not in row
                or (row["course_id"] is not None and not _positive_int(row["course_id"]))
                or "registry_course_id" not in row
                or not _year(row.get("academic_year"))
                or not _semester(row.get("semester"))
                or not _section(row.get("section"))):
            return False
        # Student projections legitimately conceal official IDs. Never infer them.
        if row["registry_course_id"] is not None and not _registry_id(row["registry_course_id"]):
            return False
        # Deliberately defer id/manageable checks until ALL exact matches are counted.
    return True


def _result(status: str, step: str, course_id: int | None, class_id: int | None = None) -> dict:
    return {"status": status, "next_step": step, "course_id": course_id,
            "class_id": class_id, "writes_performed": 0, "authorization_granted": False}


def plan_mapping(target: dict, catalog: dict, projection: dict) -> dict:
    """Review exact, explicitly selected identifiers without authorizing a mutation.

    Assignment lists are admin-only in the current API. A missing assignment in
    a non-admin snapshot is UNKNOWN, not proof that the teacher is unassigned.
    Even an admin flag cannot establish the selected teacher's assignment.
    """
    course_id = target.get("course_id") if isinstance(target, dict) else None
    if not _positive_int(course_id):
        course_id = None
    if not (_target_valid(target) and _catalog_valid(catalog) and _projection_valid(projection)):
        return _result("invalid_input", "review_input", course_id)

    courses = [row for row in catalog["courses"] if row["id"] == course_id]
    if len(courses) > 1:
        return _result("review_required", "review_ambiguity", course_id)
    if not courses:
        return _result("course_unavailable", "select_existing_course", course_id)
    binding = courses[0]["registry_course_id"]
    if binding is None or binding == "":
        return _result("mapping_required", "administrator_review", course_id)
    if binding != target["registry_course_id"]:
        return _result("mapping_conflict", "administrator_review", course_id)

    assignments = [row for row in catalog["teaching_assignments"]
                   if row["course_id"] == course_id and row["user_id"] == target["teacher_id"]]
    if len(assignments) > 1:
        return _result("review_required", "review_ambiguity", course_id)
    if not assignments or assignments[0]["active"] is not True:
        return _result("assignment_review_required", "administrator_review", course_id)

    keys = ("registry_course_id", "academic_year", "semester", "section")
    candidates = [row for row in projection["classes"]
                  if all(row[key] == target[key] for key in keys)]
    if len(candidates) > 1:
        return _result("review_required", "review_ambiguity", course_id)
    if not candidates:
        # Review means verify absence with server authority; it is not permission
        # to create a class hidden by this actor-scoped or redacted projection.
        return _result("class_setup_required", "review_class_setup", course_id)
    candidate = candidates[0]
    if (not _positive_int(candidate.get("id")) or candidate["course_id"] != course_id
            or candidate.get("manageable") is not True):
        return _result("review_required", "review_class_authority", course_id)
    return _result("linked", "review_roster_preview", course_id, candidate["id"])
