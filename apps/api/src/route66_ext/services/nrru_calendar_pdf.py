"""Deterministic reader for NRRU semester teaching-calendar announcements (page text only).

Recognizes the registrar layout: semester/year title, term opening, holiday and
no-class rows, make-up rows, the last teaching day and the odd/even week table.
No AI, network or clock. Week rotations come only from the table's odd/even
labels. Page conflicts become review questions in ``Payload.unresolved``; any
other layout returns None so the native AI reader can be tried instead.
"""
from datetime import date, timedelta
import re

from src.route66_ext.services import calendar_plan as planner

METHOD = 'nrru_calendar_text_v1'
MONTHS = ('มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
          'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม')
_DIGITS = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')
# Legacy Thai font private-use glyph variants (Windows/Mac Thai PUA) to standard characters.
_GLYPHS = str.maketrans({
    '\uf700': 'ฐ', '\uf701': '\u0e34', '\uf702': '\u0e35', '\uf703': '\u0e36', '\uf704': '\u0e37',
    '\uf705': '\u0e48', '\uf706': '\u0e49', '\uf707': '\u0e4a', '\uf708': '\u0e4b', '\uf709': '\u0e4c',
    '\uf70a': '\u0e48', '\uf70b': '\u0e49', '\uf70c': '\u0e4a', '\uf70d': '\u0e4b', '\uf70e': '\u0e4c',
    '\uf70f': 'ญ', '\uf710': '\u0e31', '\uf711': '\u0e4d', '\uf712': '\u0e47', '\uf713': '\u0e48',
    '\uf714': '\u0e49', '\uf715': '\u0e4a', '\uf716': '\u0e4b', '\uf717': '\u0e4c',
    '\uf718': '\u0e38', '\uf719': '\u0e39', '\uf71a': '\u0e3a'})
# Extracted NRRU text sometimes loses upper vowels and tone marks; match on the skeleton.
_DROPPED = re.compile('[ัิ-ื็-๎]')


def _skeleton(text):
    """(skeleton, original index of each skeleton character)."""
    text = text.translate(_DIGITS)
    keep = [i for i, ch in enumerate(text) if not _DROPPED.match(ch)]
    return ''.join(text[i] for i in keep), keep


def _sk(text):
    return _skeleton(text)[0]


_MONTH = {_sk(m): n for n, m in enumerate(MONTHS, 1)}
_WEEKDAY = {_sk(k): v for k, v in planner._DAYS.items() if len(k) > 2 and '฀' <= k[0] <= '๿'}
M = '(?:' + '|'.join(sorted(_MONTH, key=len, reverse=True)) + ')'
WD = '(' + '|'.join(sorted(_WEEKDAY, key=len, reverse=True)) + ')'
Y = r'\d(?: ?\d){3}'
DASH = r'\s*[–—-]\s*'
DAYS = rf'\d{{1,2}}(?:{DASH}\d{{1,2}})?(?:\s*,\s*\d{{1,2}}(?:{DASH}\d{{1,2}})?)*'
GROUP = re.compile(rf'(?P<days>{DAYS})\s*(?P<month>{M})\s*(?P<year>{Y})')
DATES = rf'{DAYS}\s*{M}\s*{Y}(?:\s*[,–—-]\s*{DAYS}\s*{M}\s*{Y})*'
ONE = rf'\d{{1,2}}\s*{M}\s*{Y}'

_TITLE = re.compile(rf'ภาคการศกษาท\s*(\d)\s*ปการศกษา\s*({Y})')
_TABLE_TERM = re.compile(rf'ภาคการศกษาท\s*(\d)\s*/\s*({Y})')
_OPEN = re.compile(rf'^({DATES})\s*เปดภาคการศกษาท\s*(\d)\s*ปการศกษา\s*({Y})')
_CLOSED = re.compile(rf'^({DATES})\s*(วนหยุด|งดการเรยนการสอน)')
_MAKEUP_FIRST = re.compile(rf'^{WD}ท\s*({ONE})\s*วนสอนชดเชยวน{WD}ท\s*({ONE})')
_MAKEUP_TABLE = re.compile(rf'^สปดาหสอนชดเชย\s*วนท\s*({ONE})\s*วนสอนชดเชยวน{WD}ท\s*({ONE})')
_SECTION = re.compile(r'^สปดาห(คู|ค)(?=\s)')
_WEEK = re.compile(r'(ครงท\s*\d+\s*)?สปดาหท\s*(\d+)\s*(.*)')
_LAST_DAY = 'วนสุดทายของการเรยนการสอน'
_LEADING = re.compile(rf'^(?:{WD}ท\s*)?({ONE})')


def _year(text):
    value = int(re.sub(r'\D', '', text))
    return value - 543 if value > 2400 else value


def dates(text):
    """Every date in a Thai date list such as '10 – 11, 13 – 14 สิงหาคม 2569, 1 ตุลาคม 2569'."""
    text, found, previous = _sk(text), [], None
    for group in GROUP.finditer(text):
        month, year = _MONTH[group['month']], _year(group['year'])
        days = []
        for part in group['days'].split(','):
            bounds = [int(n) for n in re.split(r'[–—-]', part)]
            days.extend(date(year, month, d) for d in range(bounds[0], bounds[-1] + 1))
        if previous is not None and found and re.fullmatch(DASH, text[previous:group.start()]):
            days = [found[-1] + timedelta(days=n) for n in range(1, (days[0] - found[-1]).days)] + days
        found.extend(days)
        previous = group.end()
    return found


def thai(day):
    return f'{day.day} {MONTHS[day.month - 1]} {day.year + 543}'


def _lines(pages):
    for item in pages:
        number, text = (item['page'], item['text']) if isinstance(item, dict) else item
        for line in (text or '').splitlines():
            line = line.translate(_GLYPHS).strip()
            if line:
                skeleton, index = _skeleton(line)
                yield number, line, skeleton, index


def _original(line, index, position):
    return line[index[position]:].strip() if position < len(index) else ''


def read(pages, academic_year=None):
    """Recognized NRRU calendar -> {'method', 'payload', 'notes'}; None for other layouts."""
    lines = list(_lines(pages))
    whole = '\n'.join(s for _, _, s, _ in lines)
    title = _TITLE.search(whole)
    if 'ราชภฏนครราชสมา' not in whole or title is None:
        return None
    semester, year = int(title[1]), int(re.sub(r'\D', '', title[2]))
    unresolved, notes = [], []
    opened = last_day = None
    closures, no_class_ranges, first_makeups, table_makeups, weeks = {}, [], {}, {}, {}
    section = None
    previous = None

    def weekday_matches(name, day, page):
        if _WEEKDAY[name] != day.weekday():
            unresolved.append(f'Page {page}: {thai(day)} is not the weekday the document names; check the PDF')

    for page, line, skeleton, index in lines:
        try:
            if (match := _OPEN.match(skeleton)) and int(match[2]) == semester and int(re.sub(r'\D', '', match[3])) == year:
                opened = opened or (dates(match[1])[0], page)
            elif match := _CLOSED.match(skeleton):
                days = dates(match[1])
                reason = _original(line, index, match.start(2))[:500]
                for day in days:
                    closures.setdefault(day, (reason, page))
                if match[2] == 'งดการเรยนการสอน':
                    no_class_ranges.append((days, reason, page))
            elif match := _MAKEUP_FIRST.match(skeleton):
                makeup, original = dates(match[2])[0], dates(match[4])[0]
                weekday_matches(match[1], makeup, page); weekday_matches(match[3], original, page)
                first_makeups[original] = (makeup, page)
            elif match := _MAKEUP_TABLE.match(skeleton):
                original, makeup = dates(match[1])[0], dates(match[3])[0]
                weekday_matches(match[2], makeup, page)
                table_makeups[original] = (makeup, page)
            if _LAST_DAY in skeleton and previous is not None:
                same = dates(skeleton)
                leading = _LEADING.match(previous)
                last_day = last_day or ((same[0] if same else dates(leading[2])[0]) if same or leading else None)
            if match := _TABLE_TERM.search(skeleton):
                if (int(match[1]), int(re.sub(r'\D', '', match[2]))) != (semester, year):
                    unresolved.append(f'Page {page}: the week table names semester {match[1]}/{match[2]}, not {semester}/{year}')
            if match := _SECTION.match(skeleton):
                section = 'even' if match[1] == 'คู' else 'odd'
            if match := _WEEK.search(skeleton):
                number, rest = int(match[2]), match[3]
                label = _original(line, index, match.start(3))
                if match[1]:
                    rotation = section
                elif 'ระหวางภาค' in rest or 'กลางภาค' in rest:
                    rotation = 'midterm'
                elif 'ปลายภาค' in rest:
                    rotation = 'final'
                else:
                    rotation = None
                listed = re.match(rf'วนท\s*({DATES})', rest)
                if rotation is None:
                    unresolved.append(f'Page {page}: week {number} has no odd/even or exam label')
                elif number in weeks:
                    unresolved.append(f'Page {page}: week {number} is listed more than once')
                elif listed:
                    after = _original(line, index, match.start(3) + listed.end())
                    weeks[number] = {'days': dates(listed[1]), 'rotation': rotation, 'page': page,
                                     'note': after[:300] or None, 'explicit': bool(match[1])}
                elif 'งดการเรยนการสอน' in rest:
                    weeks[number] = {'days': None, 'rotation': rotation, 'page': page, 'note': label[:300], 'explicit': True}
                else:
                    unresolved.append(f'Page {page}: week {number} has no dates')
        except (ValueError, KeyError, TypeError):
            unresolved.append(f'Page {page}: a date on this line is not valid: {line[:120]}')
        previous = skeleton
    sections = {w['rotation'] for w in weeks.values() if w['explicit']}
    if opened is None or not {'odd', 'even'} <= sections:
        return None
    if academic_year is not None and academic_year != year:
        unresolved.append(f'The document is for academic year {year}, but this calendar is {academic_year}')

    # Make-ups: the announcement rows are primary; the week table is cross-checked, never rewritten.
    makeups = dict(first_makeups or table_makeups)
    if first_makeups:
        by_makeup = {m: (o, p) for o, (m, p) in first_makeups.items()}
        conflicts = {}
        for original, (makeup, page) in table_makeups.items():
            if makeup in by_makeup and by_makeup[makeup][0] != original:
                kept, kept_page = by_makeup[makeup]
                conflicts.setdefault((page, kept_page), []).append(f'{thai(makeup)}: {thai(original)} vs {thai(kept)}')
            elif makeup not in by_makeup:
                unresolved.append(f'Page {page} lists a make-up on {thai(makeup)} for {thai(original)} '
                                  'that the make-up rows do not list')
        for (page, kept_page), items in conflicts.items():
            unresolved.append(f'หน้า {page} และหน้า {kept_page} ระบุวันเดิมของการสอนชดเชย {len(items)} รายการไม่ตรงกัน '
                              f'ร่างนี้ใช้หน้า {kept_page} โปรดยืนยันวันเดิม / Pages {page} and {kept_page} disagree on the '
                              f'original date of {len(items)} make-ups; the draft uses page {kept_page}. Confirm the original dates')
            notes.append(f'Make-up originals, page {page} vs page {kept_page}: ' + '; '.join(items))

    numbered = sorted(weeks)
    rows = []
    for position, number in enumerate(numbered):
        item = weeks[number]
        days = item['days']
        if days is None:
            # A "no teaching" week takes its dates from the matching no-class row between its neighbours.
            low = max((d for n in numbered[:position] if weeks[n]['days'] for d in weeks[n]['days']), default=None)
            high = min((d for n in numbered[position + 1:] if weeks[n]['days'] for d in weeks[n]['days']), default=None)
            ranges = [r for r in no_class_ranges if (low is None or min(r[0]) > low) and (high is None or max(r[0]) < high)]
            if len(ranges) != 1:
                unresolved.append(f'Week {number}: no-teaching week dates are not stated; add them from the PDF')
                continue
            days = ranges[0][0]
            notes.append(f'Week {number} has no teaching ({thai(min(days))} – {thai(max(days))}); '
                         'only its closed days and official make-ups are planned')
        mondays = {d - timedelta(days=d.weekday()) for d in days}
        # Listed dates omit holidays; the week still covers closures in the same calendar week.
        span = days + [c for c in closures if c - timedelta(days=c.weekday()) in mondays]
        rows.append(planner.Week(number=number, starts_on=min(span), ends_on=max(span), rotation=item['rotation'],
            teaching=item['days'] is not None, note=item['note'] if item['rotation'] in ('midterm', 'final') or item['days'] is None else None,
            page=item['page'], uncertain=item['rotation'] in ('midterm', 'final')))
        if item['rotation'] in ('midterm', 'final'):
            notes.append(f'Week {number} is labelled "{item["note"] or item["rotation"]}" without saying classes stop; '
                         'marked uncertain: confirm whether regular classes meet')

    start, start_page = opened
    planned_end = max([w.ends_on for w in rows] + [m for m, _ in makeups.values()], default=start)
    if last_day is None:
        unresolved.append(f'The last teaching day is not stated; the draft ends on {thai(planned_end)}')
        last_day = planned_end
    elif last_day < planned_end:
        unresolved.append(f'The last teaching day {thai(last_day)} is before scheduled teaching on {thai(planned_end)}')
        last_day = planned_end

    term_closures, outside = [], 0
    for day in sorted(closures):
        reason, page = closures[day]
        if not start <= day <= last_day:
            outside += 1
            continue
        makeup = makeups.get(day)
        term_closures.append(planner.Closure(affected_on=day, makeup_on=makeup[0] if makeup else None, note=reason, page=page))
    for original, (makeup, page) in sorted(makeups.items()):
        if original not in closures:
            unresolved.append(f'Page {page}: make-up on {thai(makeup)} replaces {thai(original)}, which is not listed as a holiday or no-class day')
    if outside:
        notes.append(f'{outside} holiday dates outside this semester were not imported')
    if 'สอบปลายภาค' in whole:
        notes.append('Final examinations do not create class meetings and were not imported')
    term = planner.Term(semester=semester, starts_on=start, ends_on=last_day, weeks=rows, closures=term_closures, page=start_page)
    payload = planner.Payload(terms=[term], unresolved=list(dict.fromkeys(unresolved))[:50])
    odd = ', '.join(str(w.number) for w in rows if w.rotation == 'odd')
    even = ', '.join(str(w.number) for w in rows if w.rotation == 'even')
    notes.insert(0, f'Semester {semester}/{year}: {thai(start)} – {thai(last_day)}; odd weeks {odd}; even weeks {even}; '
                    f'{len(term_closures)} closed days, {sum(1 for c in term_closures if c.makeup_on)} with make-ups')
    return {'method': METHOD, 'payload': payload, 'notes': notes}


_TRACKS = (('ภาคปกต', 'ภาคปกติ'), ('ภาคพเศษ', 'ภาคพิเศษ'), ('กศ.ปช', 'ภาค กศ.ปช.'))
_HEADER_YEAR = re.compile(rf'ปการศกษา\s*({Y})')


def metadata(pages, filename=None):
    """Calendar year/group/name stated in the first-page header; None where it is not stated.

    Only the announcement header (up to its semester/year line) is read, so later
    cross-program references never change the group. Name falls back to the filename.
    """
    header = []
    for page, line, skeleton, _ in _lines(pages[:1]):
        if dates(skeleton) and header:
            break  # first dated row: the header has ended
        header.append(skeleton)
        if _TITLE.search(skeleton):
            break
    text = ' '.join(header)
    stated = _TITLE.search(text) or _HEADER_YEAR.search(text)
    year = int(re.sub(r'\D', '', stated[stated.re.groups])) if stated else None
    year = year if year and 2500 <= year <= 2700 else None
    found = sorted((text.find(key), label) for key, label in _TRACKS if key in text)
    track = found[0][1] if found else None
    title = 'ปฏิทินการเรียนการสอน' if 'ปฏทนการเรยนการสอน' in text else 'ปฏิทินการศึกษา' if 'ปฏทนการศกษา' in text else None
    if title and year and track:
        name = f'{title} {track} ปีการศึกษา {year}'
    else:
        stem = re.sub(r'\.pdf$', '', (filename or '').strip(), flags=re.IGNORECASE)
        name = ' '.join(re.sub(r'[_]+', ' ', stem).split())[:200] or None
    return {'academic_year': year, 'track': track, 'name': name}


__all__ = ['METHOD', 'dates', 'metadata', 'read', 'thai']
