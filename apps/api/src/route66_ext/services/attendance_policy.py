"""Deterministic attendance rules; not authentication or a persistence service.

All times must come from the server. Legacy naive timestamps mean UTC, never the
host's local timezone. Callers must separately verify native sessions, class and
roster ownership, QR/handoff proof and current authority inside their transaction.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Iterable, Literal

AttendanceStatus = Literal["present", "late", "absent", "excused"]
SessionState = Literal["scheduled", "no_class"]
ScanKind = Literal["entry", "heartbeat"]
CheckinOutcome = Literal["accepted", "no_class", "not_open", "ended", "entry_cutoff"]
CHECKIN_OPEN_EARLY = timedelta(minutes=30)
CHECKIN_TOKEN_TTL = timedelta(seconds=120)
DEFAULT_AT_RISK_PERCENT = 80.0


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("attendance timestamps must be datetimes")
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    starts_at: datetime
    ends_at: datetime
    state: SessionState = "scheduled"
    grace_minutes: int = 10
    late_threshold_minutes: int = 20

    def __post_init__(self) -> None:
        if self.state not in ("scheduled", "no_class"):
            raise ValueError("invalid attendance session state")
        if _utc(self.ends_at) <= _utc(self.starts_at):
            raise ValueError("session must end after it starts")
        for value in (self.grace_minutes, self.late_threshold_minutes):
            if type(value) is not int or value < 0:
                raise ValueError("attendance cutoffs must be nonnegative integers")
        if self.late_threshold_minutes < self.grace_minutes:
            raise ValueError("entry cutoff cannot precede the present/late boundary")


@dataclass(frozen=True, slots=True)
class CheckinDecision:
    outcome: CheckinOutcome
    computed_status: Literal["present", "late"] | None = None


def decide_checkin(
    policy: SessionPolicy,
    *,
    arrived_at: datetime,
    kind: ScanKind = "entry",
    has_record: bool = False,
) -> CheckinDecision:
    """Use server arrival BEFORE lock queuing, then a locked current policy.

    A cutoff denial never creates an absent record. Repeated entry and heartbeat
    scans bypass only the *first-entry* cutoff, not no-class or session windows.
    Existing earliest arrival and manual overrides must be preserved by the writer.
    """
    if kind not in ("entry", "heartbeat") or type(has_record) is not bool:
        raise ValueError("invalid scan context")
    now = _utc(arrived_at)
    start, end = _utc(policy.starts_at), _utc(policy.ends_at)
    if policy.state == "no_class":
        return CheckinDecision("no_class")
    if now < start - CHECKIN_OPEN_EARLY:
        return CheckinDecision("not_open")
    if now > end:
        return CheckinDecision("ended")
    if kind == "entry" and not has_record and now > start + timedelta(minutes=policy.late_threshold_minutes):
        return CheckinDecision("entry_cutoff")
    status = "present" if now <= start + timedelta(minutes=policy.grace_minutes) else "late"
    return CheckinDecision("accepted", status)


def token_is_current(*, expires_at: datetime, arrived_at: datetime) -> bool:
    """An expiry equal to arrival is expired; this does not verify QR ownership."""
    return _utc(arrived_at) < _utc(expires_at)


def missing_attendance_status(policy: SessionPolicy, *, now: datetime) -> str:
    """Read-only projection, never a persisted absence or evidence mutation."""
    current = _utc(now)
    if policy.state == "no_class":
        return "no_class"
    if current < _utc(policy.starts_at):
        return "upcoming"
    if current < _utc(policy.ends_at):
        return "unrecorded"
    return "absent"


def counts_as_completed_session(
    policy: SessionPolicy, *, now: datetime, withdrawn_at: datetime | None = None
) -> bool:
    """No-class/future sessions do not count; withdrawal boundary is inclusive.

    The caller selects this student's class-owned sessions and validates roster
    lifecycle/history. Do not pass a current withdrawal timestamp as a substitute
    for historical membership when a student has been withdrawn and reactivated.
    """
    return (
        policy.state == "scheduled"
        and _utc(policy.ends_at) <= _utc(now)
        and (withdrawn_at is None or _utc(policy.starts_at) <= _utc(withdrawn_at))
    )


@dataclass(frozen=True, slots=True)
class AttendanceSummary:
    total_sessions: int
    present: int
    late: int
    absent: int
    excused: int
    percent: float | None
    at_risk: bool


def summarize_attendance(
    total_sessions: int,
    recorded_statuses: Iterable[AttendanceStatus],
    *,
    at_risk_threshold: float | None = None,
) -> AttendanceSummary:
    """Aggregate only eligible completed sessions, after ownership validation.

    Missing records count as absence; late and excused count as attended. Preserve
    CourseMax's two-decimal rounding before its strict below-threshold risk test.
    """
    if type(total_sessions) is not int or total_sessions < 0:
        raise ValueError("invalid completed session count")
    threshold = DEFAULT_AT_RISK_PERCENT if at_risk_threshold is None else at_risk_threshold
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not isfinite(threshold) or not 0 <= threshold <= 100:
        raise ValueError("risk threshold must be a finite percentage")
    statuses = list(recorded_statuses)
    if len(statuses) > total_sessions or any(s not in ("present", "late", "absent", "excused") for s in statuses):
        raise ValueError("invalid completed-session attendance records")
    present, late, excused = (statuses.count(s) for s in ("present", "late", "excused"))
    absent = statuses.count("absent") + total_sessions - len(statuses)
    percent = round((present + late + excused) / total_sessions * 100, 2) if total_sessions else None
    return AttendanceSummary(total_sessions, present, late, absent, excused, percent, percent is not None and percent < threshold)

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
