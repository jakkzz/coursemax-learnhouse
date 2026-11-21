"""Bounded parser for NRRU's RTF course-roster export.

This module deliberately has no web, database, or native-library dependencies.  It
accepts only the small RTF subset used by the registrar; it is not a general RTF
renderer.
"""

import re

MAX_BYTES = 2 * 1024 * 1024
_MAX_DEPTH = 64
_MAX_TEXT = 4 * 1024 * 1024
_MAX_PHYSICAL_ROWS = 11050
_MAX_CELLS = 64
_MAX_FIELD = 200

# Destinations which can contain large/non-display data.  Unknown destinations
# carrying RTF's \* marker are skipped as well.
_DESTINATIONS = {
    "fonttbl", "colortbl", "stylesheet", "pict", "object", "objdata",
    # NRRU places course/term declarations and sometimes the table in an RTF
    # page header.  Headers are therefore display content for this source, not a
    # destination that can be discarded.  Footers remain non-roster noise.
    "info", "footer", "footerl", "footerr",
    "filetbl", "listtable", "listoverridetable", "themedata", "datastore",
    "xmlnstbl", "generator",
}
_HEADER = ("เลขที่", "รหัสประจำตัว", "ชื่อ", "เอก", "กลุ่ม", "สถานภาพ", "จาก", "สัปดาห์")
_ACTIVE = {"", "0", "1", "3", "5", "6"}
_INACTIVE = {"2", "4"}


def _clean(value):
    """Normalize registrar layout whitespace without altering actual content."""
    return " ".join(value.split())


def _rtf_rows(content):
    if not isinstance(content, bytes):
        raise ValueError("Registrar RTF must be bytes")
    if len(content) > MAX_BYTES:
        raise ValueError("Registrar RTF exceeds supported size")
    if b"\x00" in content or any(b < 32 and b not in (9, 10, 13) for b in content):
        raise ValueError("Binary registrar payload is not supported")
    start = 3 if content.startswith(b"\xef\xbb\xbf") else 0
    while start < len(content) and content[start] in b" \t\r\n":
        start += 1
    if content[start:start + 5].lower() != b"{\\rtf":
        raise ValueError("Registrar source is not supported RTF")

    # Each state is [uc fallback width, destination skipped, destination-open].
    stack = []
    state = [1, False, True]
    parts = []
    cells = []
    rows = []
    text_size = 0
    fallback = 0
    root_closed = False
    i = start
    n = len(content)

    def emit(text):
        nonlocal fallback, text_size
        if state[1] or not text:
            return
        if fallback:
            if len(text) <= fallback:
                fallback -= len(text)
                return
            text = text[fallback:]
            fallback = 0
        text_size += len(text)
        if text_size > _MAX_TEXT:
            raise ValueError("Registrar RTF text exceeds supported size")
        parts.append(text)
        state[2] = False

    def end_cell():
        if len(cells) >= _MAX_CELLS:
            raise ValueError("Registrar row has too many cells")
        cells.append(_clean("".join(parts)))
        parts.clear()

    def end_row():
        if parts:
            end_cell()
        if cells:
            rows.append(list(cells))
            if len(rows) > _MAX_PHYSICAL_ROWS:
                raise ValueError("Registrar RTF has too many rows")
        cells.clear()
        parts.clear()

    while i < n:
        b = content[i]
        if root_closed:
            if b not in b" \t\r\n":
                raise ValueError("Data follows the RTF root group")
            i += 1
            continue
        if b == 123:  # {
            if len(stack) >= _MAX_DEPTH:
                raise ValueError("Registrar RTF nesting is too deep")
            stack.append(state)
            state = [state[0], state[1], True]
            i += 1
            continue
        if b == 125:  # }
            if not stack:
                raise ValueError("Unbalanced registrar RTF braces")
            state = stack.pop()
            i += 1
            if not stack:
                root_closed = True
            continue
        if not stack:
            raise ValueError("Registrar RTF text is outside its root group")
        if b != 92:  # ordinary CP874 text
            j = i + 1
            while j < n and content[j] not in b"{}\\":
                j += 1
            try:
                # Raw CR/LF are RTF source formatting, not rendered text.
                text = content[i:j].decode("cp874").replace("\r", "").replace("\n", "")
            except UnicodeDecodeError:
                raise ValueError("Registrar RTF contains invalid CP874 text") from None
            emit(text)
            i = j
            continue

        i += 1
        if i >= n:
            raise ValueError("Truncated registrar RTF escape")
        marker = content[i]
        if marker == 39:  # \'hh
            if i + 2 >= n:
                raise ValueError("Truncated registrar RTF hex escape")
            pair = content[i + 1:i + 3]
            if not re.fullmatch(br"[0-9A-Fa-f]{2}", pair):
                raise ValueError("Malformed registrar RTF hex escape")
            try:
                emit(bytes((int(pair, 16),)).decode("cp874"))
            except UnicodeDecodeError:
                raise ValueError("Invalid CP874 registrar RTF hex escape") from None
            i += 3
            continue
        if marker in (92, 123, 125):
            emit(chr(marker))
            i += 1
            continue
        if not (65 <= marker <= 90 or 97 <= marker <= 122):
            # RTF control symbols.  Only these have textual meaning here.
            if marker == 42:  # \* destination marker
                state[1] = True
            elif marker == 126:
                emit("\u00a0")
            elif marker == 95:
                emit("\u2011")
            elif marker == 45:
                pass  # optional hyphen
            i += 1
            continue

        j = i
        while j < n and ((65 <= content[j] <= 90) or (97 <= content[j] <= 122)):
            j += 1
        word = content[i:j].decode("ascii").lower()
        sign = 1
        if j < n and content[j] == 45:
            sign = -1
            j += 1
        number_start = j
        while j < n and 48 <= content[j] <= 57:
            j += 1
        if j - number_start > 10:
            raise ValueError("Registrar RTF control number is too long")
        number = sign * int(content[number_start:j]) if j > number_start else None
        if j < n and content[j] == 32:
            j += 1
        i = j

        if word == "bin":
            raise ValueError("Binary data in registrar RTF is not supported")
        if state[2] and word in _DESTINATIONS:
            state[1] = True
        if state[1]:
            continue
        if word == "uc":
            if number is None or not 0 <= number <= 16:
                raise ValueError("Invalid registrar RTF Unicode fallback width")
            state[0] = number
        elif word == "u":
            if number is None or not -32768 <= number <= 32767:
                raise ValueError("Invalid registrar RTF Unicode value")
            point = number if number >= 0 else number + 65536
            if 0xD800 <= point <= 0xDFFF:
                raise ValueError("Unsupported registrar RTF Unicode surrogate")
            # The Unicode character itself is never part of a preceding fallback.
            fallback = 0
            emit(chr(point))
            fallback = state[0]
        elif word == "cell":
            end_cell()
        elif word == "row":
            end_row()
        elif word in ("line", "par"):
            emit(" ")
        # Other formatting controls, including cellx, deliberately have no effect.

    if stack or not root_closed:
        raise ValueError("Unbalanced registrar RTF braces")
    if fallback:
        raise ValueError("Truncated registrar RTF Unicode fallback")
    if cells or _clean("".join(parts)):
        raise ValueError("Registrar RTF contains an unterminated row")
    if not rows:
        raise ValueError("Registrar RTF contains no table rows")
    return rows


def parse_course_roster(content: bytes, cls):
    """Return active students in ``cls.section`` from an NRRU course RTF."""
    rows = _rtf_rows(content)

    section = _clean(str(getattr(cls, "section", ""))).casefold()
    code = _clean(str(getattr(cls, "registry_course_code", "")))
    try:
        year = int(cls.academic_year)
        semester = int(cls.semester)
    except (AttributeError, TypeError, ValueError):
        raise ValueError("Class has invalid registrar term metadata") from None
    if not section:
        raise ValueError("Class has no registrar section")
    if not code:
        raise ValueError("Class has no registrar course code")

    header_indexes = [i for i, row in enumerate(rows) if tuple(row[:8]) == _HEADER]
    if len(header_indexes) != 1:
        raise ValueError("Registrar RTF has no unambiguous supported roster header")
    header_index = header_indexes[0]
    metadata = rows[:header_index]

    declarations = []
    for row in metadata:
        for cell in row:
            match = re.search(r"รายวิชา\s+([^\s()]+)", cell)
            if match:
                declarations.append(match.group(1))
    if len(declarations) != 1 or declarations[0].casefold() != code.casefold():
        raise ValueError("Registrar course code does not match the approved course mapping")

    term_text = " ".join(cell for row in metadata for cell in row)
    terms = re.findall(r"ปีการศึกษา\s*([1-3])\s*/\s*([0-9]{4})", term_text)
    if len(terms) != 1 or (int(terms[0][0]), int(terms[0][1])) != (semester, year):
        raise ValueError("Registrar term does not match this class")

    selected = []
    selected_seen = set()
    total = 0
    for row in rows[header_index + 1:]:
        ordinal_like = bool(row and re.fullmatch(r"[0-9]+", row[0]))
        # Registrar student rows carry fields in columns 1..6. A merged/padded
        # footer can have 24 cells and digits in column 0, so that alone must
        # not turn footer prose into a student.
        # NRRU has seven identity/status cells plus sixteen weekly cells.
        # Some generators retain one additional empty trailing table cell.
        supported_width = len(row) == 23 or (len(row) == 24 and not row[23])
        roster_shaped = supported_width and any(row[1:7])
        if not roster_shaped:
            # A short, table-shaped ordinal row is a damaged student row.  Small
            # numeric footer rows are ignored rather than interpreted as students.
            if ordinal_like and len(row) >= 7 and not supported_width:
                raise ValueError("Incomplete registrar student row; snapshot rejected")
            continue
        if not ordinal_like or int(row[0]) < 1:
            raise ValueError("Invalid registrar roster ordinal")
        if not re.fullmatch(r"[0-9]{10}", row[1]):
            raise ValueError("Invalid registrar student number")
        if not row[2]:
            raise ValueError("Incomplete registrar student row; snapshot rejected")
        status = row[5]
        if status not in _ACTIVE | _INACTIVE:
            raise ValueError("Unsupported registrar student status")
        if any(len(value) > _MAX_FIELD for value in row[:7]):
            raise ValueError("Registrar student field exceeds supported length")
        total += 1
        if total > 10000:
            raise ValueError("Registrar roster exceeds supported size")
        if _clean(row[4]).casefold() != section:
            continue
        if status in _INACTIVE:
            continue
        if row[1] in selected_seen:
            raise ValueError("Duplicate registrar student number in selected section")
        selected_seen.add(row[1])
        selected.append({
            "student_number": row[1],
            "full_name_th": row[2],
            "faculty": "",
            "program": row[3],
            "registry_status_code": status or None,
            "display_position": int(row[0]),
        })
        if len(selected) > 1000:
            raise ValueError("Selected registrar roster exceeds supported size")

    if not selected:
        raise ValueError("No complete active roster for selected section")
    return selected


__all__ = ["MAX_BYTES", "parse_course_roster"]
