"""Table cells from a PDF by physical position, using pypdf's own font decoding.

pypdf's text extraction batches several text-show operators and reports them at
one position, which merges neighbouring table columns. Here every Tj/TJ is
decoded separately (font encoding, then the font's character map, exactly as
pypdf does) at its real start point, and columns come from the page's own
vertical table rules. The PDF is only read, never modified.
"""
from io import BytesIO

_TEXT = (b'Tj', b'TJ', b"'", b'"')


def _decode(raw, font):
    if isinstance(raw, str):  # already text (rare literal strings)
        return raw
    if isinstance(font.encoding, str):
        try:
            text = raw.decode(font.encoding, 'surrogatepass')
        except Exception:
            text = raw.decode('charmap', 'surrogatepass')
    else:
        text = ''.join(font.encoding.get(b, chr(b)) for b in raw)
    return ''.join(font.character_map.get(c, c) for c in text)


def _page(page):
    # pypdf 6.21 (upstream 1.4.3) moved its font decoder into generic.
    from pypdf.generic._font import Font
    fonts = {}
    for name, ref in (page.get('/Resources', {}).get('/Font') or {}).items():
        try:
            fonts[name] = Font.from_font_resource(ref.get_object())
        except Exception:
            pass
    runs, rules, state = [], [], {'font': None, 'saved': []}

    def before(op, args, cm, tm):
        if op == b'q':
            state['saved'].append(state['font'])  # the font is part of the graphics state
        elif op == b'Q':
            state['font'] = state['saved'].pop() if state['saved'] else state['font']
        elif op == b'Tf' and args:
            state['font'] = fonts.get(args[0])
        elif op == b're' and len(args) == 4:
            x, y, w, h = (float(a) for a in args)
            if abs(w * cm[0]) < 2 and abs(h * cm[3]) > 5:  # a thin vertical table rule
                rules.append(x * cm[0] + cm[4])
        elif op in _TEXT and args and state['font'] is not None:
            parts = args[-1] if op == b'TJ' else [args[-1]]
            text = ''.join(_decode(p, state['font']) for p in parts if isinstance(p, (bytes, str)))
            if text.strip():
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                runs.append((y, x, text))

    page.extract_text(visitor_operand_before=before)
    return runs, sorted({round(x) for x in rules})


def tables(data):
    """[{page, lines: [{y, cells: {column: text}}]}] for pages that have table rules."""
    from pypdf import PdfReader
    found = []
    for number, page in enumerate(PdfReader(BytesIO(data)).pages, 1):
        runs, edges = _page(page)
        if len(edges) < 3:
            continue
        lines = []
        for y, x, text in sorted(runs, key=lambda r: (-r[0], r[1])):
            if not lines or abs(lines[-1]['y'] - y) >= 2:
                lines.append({'y': y, 'parts': []})
            lines[-1]['parts'].append((x, text))
        for line in lines:
            cells = {}
            for x, text in sorted(line.pop('parts')):
                column = sum(1 for edge in edges if edge <= x + 0.5)
                cells[column] = cells.get(column, '') + text
            line['cells'] = {c: ' '.join(t.split()) for c, t in cells.items() if t.strip()}
        found.append({'page': number, 'lines': [l for l in lines if l['cells']]})
    return found
