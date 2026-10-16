"""Pure academic-calendar payload validation and deterministic meeting planner.

No database, network or clock access. Rotations, teaching weeks and make-up
dates come only from the reviewed payload; nothing is inferred from week-number
parity, exam labels or weekday guesses.
"""
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator

Rotation = Literal['odd', 'even', 'teaching', 'midterm', 'final']
PATTERNS = ('onsite', 'online', 'even_onsite')


class _Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Week(_Model):
    number: int = Field(ge=1, le=40)
    starts_on: date
    ends_on: date
    rotation: Rotation
    teaching: bool
    note: str | None = Field(default=None, max_length=300)
    page: int | None = Field(default=None, ge=1, le=500)
    uncertain: bool = False


class Closure(_Model):
    affected_on: date
    makeup_on: date | None = None
    note: str = Field(min_length=1, max_length=500)
    page: int | None = Field(default=None, ge=1, le=500)
    uncertain: bool = False

    @field_validator('note')
    @classmethod
    def present(cls, value):
        if not value.strip():
            raise ValueError('Enter the closure reason')
        return value.strip()


class Term(_Model):
    semester: int = Field(ge=1, le=3)
    starts_on: date
    ends_on: date
    weeks: list[Week] = Field(default_factory=list, max_length=40)
    closures: list[Closure] = Field(default_factory=list, max_length=200)
    page: int | None = Field(default=None, ge=1, le=500)
    uncertain: bool = False


class Payload(_Model):
    # First release: NRRU calendars and every UI date use Bangkok time.
    timezone: Literal['Asia/Bangkok'] = 'Asia/Bangkok'
    terms: list[Term] = Field(default_factory=list, max_length=3)
    unresolved: list[str] = Field(default_factory=list, max_length=50)


def empty_payload():
    return Payload().model_dump(mode='json')


def issues(payload: Payload, page_count: int | None = None):
    """Every reason this reviewed calendar cannot be published yet (empty = publishable)."""
    found = []
    if not payload.terms:
        found.append('Add at least one term')
    if len({t.semester for t in payload.terms}) != len(payload.terms):
        found.append('Each semester can appear only once')
    for text in payload.unresolved:
        found.append('Unresolved: ' + text)
    for term in payload.terms:
        label = f'Semester {term.semester}'
        if term.starts_on > term.ends_on:
            found.append(f'{label}: term ends before it starts')
        if term.uncertain:
            found.append(f'{label}: term dates are marked uncertain')
        if not term.weeks:
            found.append(f'{label}: add its weeks')
        numbers = [w.number for w in term.weeks]
        if len(set(numbers)) != len(numbers):
            found.append(f'{label}: week numbers must be unique')
        previous = None
        for week in term.weeks:
            if week.starts_on > week.ends_on:
                found.append(f'{label} week {week.number}: ends before it starts')
            if week.starts_on < term.starts_on or week.ends_on > term.ends_on:
                found.append(f'{label} week {week.number}: outside the term dates')
            if previous and (week.starts_on <= previous.ends_on or week.number <= previous.number):
                found.append(f'{label} week {week.number}: weeks must be in order without overlap')
            if week.teaching and (week.ends_on - week.starts_on).days > 6:
                # One occurrence per slot per teaching week keeps meeting identity unique.
                found.append(f'{label} week {week.number}: a teaching week can span at most 7 days')
            if week.uncertain:
                found.append(f'{label} week {week.number}: marked uncertain')
            previous = week
        dates = [c.affected_on for c in term.closures]
        if len(set(dates)) != len(dates):
            found.append(f'{label}: each closure date can appear once')
        closed = set(dates)
        for closure in term.closures:
            day = closure.affected_on.isoformat()
            if not term.starts_on <= closure.affected_on <= term.ends_on:
                found.append(f'{label} closure {day}: outside the term dates')
            if closure.makeup_on == closure.affected_on:
                found.append(f'{label} closure {day}: make-up date must differ')
            if closure.makeup_on in closed:
                found.append(f'{label} closure {day}: make-up date is itself closed')
            if closure.uncertain:
                found.append(f'{label} closure {day}: marked uncertain')
        for item in [term, *term.weeks, *term.closures]:
            if page_count is not None and item.page is not None and item.page > page_count:
                found.append(f'{label}: page {item.page} is not in the source PDF')
                break
    return found


_DAYS = {
    'จันทร์': 0, 'จ': 0, 'monday': 0, 'mon': 0,
    'อังคาร': 1, 'อ': 1, 'tuesday': 1, 'tue': 1,
    'พุธ': 2, 'พ': 2, 'wednesday': 2, 'wed': 2,
    'พฤหัสบดี': 3, 'พฤหัส': 3, 'พฤ': 3, 'thursday': 3, 'thu': 3,
    'ศุกร์': 4, 'ศ': 4, 'friday': 4, 'fri': 4,
    'เสาร์': 5, 'ส': 5, 'saturday': 5, 'sat': 5,
    'อาทิตย์': 6, 'อา': 6, 'sunday': 6, 'sun': 6,
}
_DAY_KEYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')


def weekday(label):
    key = re.sub(r'^วัน', '', (label or '').strip()).rstrip('.').strip().casefold()
    return _DAYS.get(key)


def _clock(value):
    match = re.fullmatch(r'([0-2]?[0-9]):([0-5][0-9])', (value or '').strip())
    if not match or int(match[1]) > 23:
        raise ValueError(value)
    return time(int(match[1]), int(match[2]))


_WEEKS_TOKEN = re.compile(r'\bW\s*:', re.IGNORECASE)
_WEEKS_EXACT = re.compile(r'\bW\s*:\s*\(([0-9,\s-]{1,60})\)')


def official_weeks(details):
    """Registrar W:(a-b[,c...]) teaching weeks; None when the source states none.

    Raises ValueError for any W: syntax outside this strict, bounded form so
    it is reviewed rather than silently treated as every week.
    """
    text = details or ''
    tokens = _WEEKS_TOKEN.findall(text)
    if not tokens:
        return None
    exact = _WEEKS_EXACT.findall(text)
    if len(tokens) != 1 or len(exact) != 1:
        raise ValueError(text)
    weeks = set()
    for part in exact[0].split(','):
        match = re.fullmatch(r'\s*([0-9]{1,2})\s*(?:-\s*([0-9]{1,2})\s*)?', part)
        if not match:
            raise ValueError(text)
        first, last = int(match[1]), int(match[2] or match[1])
        if not 1 <= first <= last <= 40:
            raise ValueError(text)
        weeks.update(range(first, last + 1))
    return frozenset(weeks)


def slots(meetings):
    """Official timetable meetings -> stable slot facts; unknown days are errors."""
    result, errors, seen = [], [], {}
    for meeting in meetings:
        day = weekday(meeting.get('day'))
        try:
            start, end = _clock(meeting.get('start_time')), _clock(meeting.get('end_time'))
        except ValueError:
            errors.append('Official meeting time is not recognized: ' + str(meeting.get('start_time')) + '-' + str(meeting.get('end_time')))
            continue
        if day is None:
            errors.append('Official meeting day is not recognized: ' + str(meeting.get('day')))
            continue
        if end <= start:
            errors.append('Official meeting ends before it starts')
            continue
        try:
            weeks = official_weeks(meeting.get('details'))
        except ValueError:
            errors.append('Official meeting weeks are not recognized; review this meeting: ' + str(meeting.get('details'))[:200])
            continue
        key = f'{_DAY_KEYS[day]}-{start:%H%M}-{end:%H%M}'
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key += f'-{seen[key]}'
        result.append({'slot_key': key, 'weekday': day, 'start': start, 'end': end, 'weeks': weeks,
                       'location': (meeting.get('details') or '')[:1000] or None})
    return sorted(result, key=lambda s: (s['weekday'], s['start'], s['slot_key'])), errors


def _mode(pattern, rotation):
    if pattern != 'even_onsite':
        return pattern
    return {'even': 'onsite', 'odd': 'online'}.get(rotation)


def plan(payload: Payload, semester: int, meetings, pattern, label):
    """Planned calendar meetings for one class; returns (rows, warnings, errors)."""
    if pattern not in PATTERNS:
        return [], [], ['Choose a meeting pattern']
    term = next((t for t in payload.terms if t.semester == semester), None)
    if term is None:
        return [], [], [f'This calendar has no semester {semester}']
    zone = ZoneInfo(payload.timezone)
    slot_rows, errors = slots(meetings)
    if not slot_rows and not errors:
        errors.append('The official timetable has no meeting times for this section')
    closures = {c.affected_on: c for c in term.closures}
    rows, warnings = [], []

    def row(kind, week, slot, day, nominal, state, mode, note):
        starts = datetime.combine(day, slot['start'], zone).astimezone(timezone.utc)
        ends = datetime.combine(day, slot['end'], zone).astimezone(timezone.utc)
        title = f'{label} · สัปดาห์ที่ {week.number}' + (' (ชดเชย)' if kind == 'makeup' else '')
        return {'calendar_kind': kind, 'academic_week': week.number, 'slot_key': slot['slot_key'],
                'nominal_on': nominal, 'starts_at': starts, 'ends_at': ends, 'timezone': payload.timezone,
                'state': state, 'rotation': week.rotation, 'mode': mode, 'location': slot['location'],
                'note': note, 'title': title[:160], 'makeup_for': nominal if kind == 'makeup' else None}

    for week in term.weeks:
        if not week.teaching:
            continue
        if (week.ends_on - week.starts_on).days > 6:
            errors.append(f'Week {week.number} spans more than 7 days; split it before scheduling')
            continue
        for slot in slot_rows:
            # Official W: weeks filter by the original academic week; make-ups follow it.
            if slot['weeks'] is not None and week.number not in slot['weeks']:
                continue
            day = week.starts_on + timedelta(days=(slot['weekday'] - week.starts_on.weekday()) % 7)
            if day > week.ends_on:
                continue
            mode = _mode(pattern, week.rotation)
            if mode is None:
                errors.append(f'Week {week.number} needs an explicit odd or even rotation for the alternating pattern')
                continue
            closure = closures.get(day)
            if closure is None:
                rows.append(row('regular', week, slot, day, day, 'scheduled', mode, None))
                continue
            rows.append(row('regular', week, slot, day, day, 'no_class', mode, closure.note))
            if closure.makeup_on is None:
                continue
            makeup = closure.makeup_on
            if makeup in closures:
                errors.append(f'Make-up for {day.isoformat()} is on another closed date')
                continue
            rows.append(row('makeup', week, slot, makeup, day, 'scheduled', mode, closure.note))
            if makeup.weekday() >= 5:
                warnings.append(f'Make-up for {day.isoformat()} is on a weekend ({makeup.isoformat()})')
            if not term.starts_on <= makeup <= term.ends_on:
                warnings.append(f'Make-up for {day.isoformat()} is outside the term ({makeup.isoformat()})')
    teaching = {w.number for w in term.weeks if w.teaching}
    for slot in slot_rows:
        if slot['weeks'] is not None and not slot['weeks'] <= teaching:
            missing = ', '.join(str(n) for n in sorted(slot['weeks'] - teaching))
            warnings.append(f"Official weeks {missing} for {slot['slot_key']} are not teaching weeks in this calendar")
    active = sorted((r for r in rows if r['state'] == 'scheduled'), key=lambda r: (r['starts_at'], r['slot_key']))
    for before, after in zip(active, active[1:]):
        if after['starts_at'] < before['ends_at']:
            warnings.append(f"Meetings overlap on {after['starts_at'].astimezone(zone).date().isoformat()}")
    rows.sort(key=lambda r: (r['starts_at'], r['calendar_kind'], r['slot_key']))
    return rows, sorted(set(warnings)), sorted(set(errors))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str, ensure_ascii=False)


def fingerprint(value):
    return sha256(canonical(value).encode()).hexdigest()


__all__ = [name for name in globals() if not name.startswith("__")]
