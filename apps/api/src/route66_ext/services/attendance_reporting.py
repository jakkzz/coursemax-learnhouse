"""Batched attendance history, coverage, aggregate and CSV projections."""
from __future__ import annotations

import base64
import binascii
import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime
import io
import unicodedata
from zoneinfo import ZoneInfo

from sqlmodel import select

from src.route66_ext.db.academic_classes import AcademicClass, AcademicClassEvent, AcademicRosterEntry, SchoolStudent
from src.route66_ext.db.class_attendance import AttendanceEvent, AttendanceScan, AttendanceSession
from src.route66_ext.services import class_attendance
from src.route66_ext.services.attendance_policy import _utc, summarize_attendance

_DECISION = 'attendance_decided'
_MEMBERSHIP_KINDS = (
    'registry_member_added', 'registry_member_seen', 'registry_member_reactivated',
    'registry_member_missing', 'registrar_membership_confirmed',
    'manual_member_added', 'manual_membership_changed',
)
_STATUSES = ('present', 'late', 'absent', 'excused')
_HISTORY_LIMIT = 50
_COVERAGE_DESCRIPTION = 'Percentages cover recorded or known-eligible completed sessions only; partial coverage is shown separately.'


@dataclass(frozen=True)
class MembershipTimeline:
    intervals: tuple[tuple[datetime, datetime | None], ...]
    transitions: tuple[tuple[datetime, int, str], ...]

    def at(self, value: datetime) -> str:
        moment = _utc(value)
        if any(start <= moment and (end is None or moment <= end) for start, end in self.intervals):
            return 'active'
        prior = [row for row in self.transitions if row[0] <= moment]
        return prior[-1][2] if prior else 'unknown'


@dataclass
class ClassAttendanceData:
    cls: AcademicClass
    entries: list[tuple[AcademicRosterEntry, SchoolStudent]]
    sessions: list[AttendanceSession]
    scans: dict[tuple[int, int], list[AttendanceScan]]
    decisions: dict[tuple[int, int], list[AttendanceEvent]]
    collected: set[int]
    timelines: dict[int, MembershipTimeline]


def _membership_transition(event: AcademicClassEvent, manual: bool) -> tuple[str | None, bool]:
    if event.kind == 'manual_member_added':
        return 'active', True
    if event.kind == 'manual_membership_changed':
        status = event.details.get('status')
        return (status if status in ('active', 'withdrawn') else None), True
    if event.kind == 'registrar_membership_confirmed':
        return None, manual
    if manual:
        return None, manual
    if event.kind in ('registry_member_added', 'registry_member_seen', 'registry_member_reactivated'):
        return 'active', manual
    if event.kind == 'registry_member_missing':
        status = event.details.get('status')
        return (status if status in ('active', 'withdrawn') else None), manual
    return None, manual


def build_membership_timeline(events: list[AcademicClassEvent]) -> MembershipTimeline:
    intervals: list[tuple[datetime, datetime | None]] = []
    transitions: list[tuple[datetime, int, str]] = []
    active_since: datetime | None = None
    manual = False
    for event in sorted(events, key=lambda row: (_utc(row.created_at), row.id)):
        status, manual = _membership_transition(event, manual)
        if status is None:
            continue
        observed_at = _utc(event.created_at)
        transitions.append((observed_at, event.id, status))
        if status == 'active':
            if active_since is None:
                active_since = observed_at
        elif active_since is not None:
            intervals.append((active_since, observed_at))
            active_since = None
    if active_since is not None:
        intervals.append((active_since, None))
    return MembershipTimeline(tuple(intervals), tuple(transitions))


async def load_membership_timelines(db, class_id: int, entries: list[tuple[AcademicRosterEntry, SchoolStudent]]):
    events = (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.class_id == class_id, AcademicClassEvent.kind.in_(_MEMBERSHIP_KINDS)
    ).order_by(AcademicClassEvent.created_at, AcademicClassEvent.id))).all()
    by_student: dict[int, list[AcademicClassEvent]] = {}
    for event in events:
        if event.student_id is not None:
            by_student.setdefault(event.student_id, []).append(event)
    return {entry.id: build_membership_timeline(by_student.get(entry.student_id, [])) for entry, _ in entries}


async def load_class_data(db, cls: AcademicClass) -> ClassAttendanceData:
    entries = (await db.exec(select(AcademicRosterEntry, SchoolStudent).join(
        SchoolStudent, SchoolStudent.id == AcademicRosterEntry.student_id
    ).where(AcademicRosterEntry.class_id == cls.id).order_by(
        AcademicRosterEntry.display_position, AcademicRosterEntry.id))).all()
    sessions = (await db.exec(select(AttendanceSession).where(
        AttendanceSession.class_id == cls.id).order_by(AttendanceSession.starts_at.desc(), AttendanceSession.id.desc()))).all()
    session_ids = [row.id for row in sessions]
    scans_by_pair: dict[tuple[int, int], list[AttendanceScan]] = {}
    decisions_by_pair: dict[tuple[int, int], list[AttendanceEvent]] = {}
    collected: set[int] = set()
    if session_ids:
        scans = (await db.exec(select(AttendanceScan).where(
            AttendanceScan.session_id.in_(session_ids)).order_by(AttendanceScan.arrived_at, AttendanceScan.id))).all()
        for scan in scans:
            scans_by_pair.setdefault((scan.session_id, scan.roster_entry_id), []).append(scan)
            collected.add(scan.session_id)
        events = (await db.exec(select(AttendanceEvent).where(
            AttendanceEvent.session_id.in_(session_ids), AttendanceEvent.kind.in_(('checkin_opened', _DECISION))
        ).order_by(AttendanceEvent.id))).all()
        for event in events:
            if event.kind == 'checkin_opened':
                collected.add(event.session_id)
            elif isinstance(event.details.get('roster_entry_id'), int):
                decisions_by_pair.setdefault((event.session_id, event.details['roster_entry_id']), []).append(event)
    timelines = await load_membership_timelines(db, cls.id, entries)
    return ClassAttendanceData(cls, list(entries), list(sessions), scans_by_pair, decisions_by_pair, collected, timelines)


def session_local_date(session: AttendanceSession) -> date:
    return _utc(session.starts_at).astimezone(ZoneInfo(session.timezone)).date()


def sessions_in_range(sessions, from_date: date | None, to_date: date | None):
    if from_date and to_date and from_date > to_date:
        raise ValueError('The attendance date range is invalid.')
    return [row for row in sessions if (from_date is None or session_local_date(row) >= from_date)
            and (to_date is None or session_local_date(row) <= to_date)]


def session_dto(row: AttendanceSession):
    return {key: getattr(row, key) for key in (
        'id', 'class_id', 'title', 'starts_at', 'ends_at', 'timezone', 'grace_minutes',
        'late_threshold_minutes', 'state', 'version', 'calendar_kind', 'academic_week', 'slot_key',
        'nominal_on', 'replaces_session_id', 'rotation', 'mode', 'location', 'note')}


def pair_projection(data: ClassAttendanceData, entry: AcademicRosterEntry, session: AttendanceSession, as_of: datetime):
    key = (session.id, entry.id)
    eligibility = data.timelines[entry.id].at(session.starts_at)
    projection = class_attendance.scan_projection(session, data.scans.get(key, []), as_of,
        decisions=data.decisions.get(key, []), collected=session.id in data.collected,
        eligibility=eligibility, class_version=data.cls.version, roster_entry_id=entry.id)
    return projection, eligibility


def member_aggregate(data: ClassAttendanceData, entry: AcademicRosterEntry, student: SchoolStudent,
                     sessions: list[AttendanceSession], as_of: datetime):
    coverage = {'session_count': len(sessions), 'known_denominator': 0, 'unknown_membership': 0,
        'uncollected': 0, 'not_eligible': 0, 'no_class': 0, 'incomplete': 0}
    statuses: list[str] = []
    for session in sessions:
        if session.state == 'no_class':
            coverage['no_class'] += 1
            continue
        if _utc(session.ends_at) > _utc(as_of):
            coverage['incomplete'] += 1
            continue
        projection, _ = pair_projection(data, entry, session, as_of)
        status = projection['effective_status']
        if status in _STATUSES:
            statuses.append(status)
        elif status == 'unknown':
            coverage['unknown_membership'] += 1
        elif status == 'not_eligible':
            coverage['not_eligible'] += 1
        elif status == 'unrecorded':
            coverage['uncollected'] += 1
        else:
            coverage['incomplete'] += 1
    calculated = summarize_attendance(len(statuses), statuses)
    coverage['known_denominator'] = calculated.total_sessions
    gaps = coverage['unknown_membership'] + coverage['uncollected']
    coverage['status'] = 'partial' if gaps else 'none' if calculated.total_sessions == 0 else 'complete'
    meaningful_risk = calculated.total_sessions > 0 and gaps == 0 and entry.status == 'active'
    risk = 'at_risk' if meaningful_risk and calculated.at_risk else 'not_at_risk' if meaningful_risk else 'unknown'
    summary = asdict(calculated)
    summary['at_risk'] = calculated.at_risk if meaningful_risk else None
    return {'roster_entry_id': entry.id, 'student_number': student.student_number, 'name': student.full_name_th,
            'membership': entry.status, 'summary': summary, 'coverage': coverage, 'risk': risk}


def class_summary(data: ClassAttendanceData, as_of: datetime, from_date: date | None = None, to_date: date | None = None):
    sessions = sessions_in_range(data.sessions, from_date, to_date)
    return {'class_id': data.cls.id, 'as_of': as_of, 'range': {'from': from_date, 'to': to_date},
            'coverage_description': _COVERAGE_DESCRIPTION,
            'members': [member_aggregate(data, entry, student, sessions, as_of) for entry, student in data.entries]}


def _encode_cursor(session: AttendanceSession) -> str:
    raw = _utc(session.starts_at).isoformat() + '|' + str(session.id)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip('=')


def _decode_cursor(value: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)).decode()
        starts_at, row_id = raw.rsplit('|', 1)
        parsed = datetime.fromisoformat(starts_at)
        if parsed.tzinfo is None or int(row_id) < 1:
            raise ValueError
        return _utc(parsed), int(row_id)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise ValueError('The attendance history cursor is invalid.') from None


def member_history(data: ClassAttendanceData, entry: AcademicRosterEntry, sessions: list[AttendanceSession],
                   as_of: datetime, before: str | None = None):
    ordered = sorted(sessions, key=lambda row: (_utc(row.starts_at), row.id), reverse=True)
    if before:
        cursor = _decode_cursor(before)
        ordered = [row for row in ordered if (_utc(row.starts_at), row.id) < cursor]
    page, more = ordered[:_HISTORY_LIMIT], len(ordered) > _HISTORY_LIMIT
    history = []
    for session in page:
        projection, eligibility = pair_projection(data, entry, session, as_of)
        decisions = data.decisions.get((session.id, entry.id), [])
        history.append({'session': session_dto(session), 'membership_at_session': eligibility,
            'collected': session.id in data.collected, **projection,
            'decisions': [class_attendance.decision_dto(row) for row in reversed(decisions)]})
    return history, _encode_cursor(page[-1]) if more and page else None


def own_report(data: ClassAttendanceData, entry: AcademicRosterEntry, student: SchoolStudent, as_of: datetime,
               from_date: date | None = None, to_date: date | None = None, before: str | None = None):
    sessions = sessions_in_range(data.sessions, from_date, to_date)
    aggregate = member_aggregate(data, entry, student, sessions, as_of)
    history, next_before = member_history(data, entry, sessions, as_of, before)
    return {'class_id': data.cls.id, 'as_of': as_of, 'range': {'from': from_date, 'to': to_date},
        'coverage_description': _COVERAGE_DESCRIPTION,
        'member': {key: aggregate[key] for key in ('roster_entry_id', 'student_number', 'name', 'membership')},
        'summary': aggregate['summary'], 'coverage': aggregate['coverage'], 'risk': aggregate['risk'],
        'history': history, 'next_before': next_before}


def manager_history(data: ClassAttendanceData, entry: AcademicRosterEntry, student: SchoolStudent,
                    as_of: datetime, before: str | None = None):
    history, next_before = member_history(data, entry, data.sessions, as_of, before)
    return {'class_id': data.cls.id, 'as_of': as_of,
        'member': {'roster_entry_id': entry.id, 'student_number': student.student_number,
                   'name': student.full_name_th, 'membership': entry.status},
        'history': history, 'next_before': next_before}


def _safe_text(value) -> str:
    text = '' if value is None else str(value)
    index = 0
    while index < len(text) and (text[index].isspace() or unicodedata.category(text[index]).startswith('C')):
        index += 1
    return "'" + text if index < len(text) and text[index] in '=+-@' else text


def summary_csv(report: dict) -> bytes:
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\r\n', quoting=csv.QUOTE_ALL)
    writer.writerow(('Student number', 'Name', 'Membership', 'Known denominator', 'Present', 'Late', 'Absent',
        'Excused', 'Percentage', 'Coverage', 'Unknown membership', 'Uncollected', 'Not eligible', 'No class',
        'Incomplete', 'Risk', 'From', 'To', 'As of'))
    range_from = report['range']['from'].isoformat() if report['range']['from'] else ''
    range_to = report['range']['to'].isoformat() if report['range']['to'] else ''
    as_of = _utc(report['as_of']).isoformat()
    for member in report['members']:
        summary, coverage = member['summary'], member['coverage']
        writer.writerow([_safe_text(member['student_number']), _safe_text(member['name']), _safe_text(member['membership']),
            summary['total_sessions'], summary['present'], summary['late'], summary['absent'], summary['excused'],
            '' if summary['percent'] is None else f"{summary['percent']:.2f}", _safe_text(coverage['status']),
            coverage['unknown_membership'], coverage['uncollected'], coverage['not_eligible'], coverage['no_class'],
            coverage['incomplete'], _safe_text(member['risk']), range_from, range_to, as_of])
    return ('\ufeff' + output.getvalue()).encode('utf-8')


# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith('__')]
