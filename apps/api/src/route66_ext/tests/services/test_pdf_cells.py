"""Positioned PDF table cells from generated PDFs; synthetic text, rules and fonts only."""
from io import BytesIO
import unittest

from src.route66_ext.services import pdf_cells


def make_pdf(pages, fonts, to_unicode=None):
    """pages: [content-stream text]; fonts: {name: /Differences list or None} over Helvetica.

    to_unicode: {code: character} becomes a /ToUnicode CMap on every font, as real Thai fonts carry.
    """
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject
    writer = PdfWriter()
    resources = DictionaryObject()
    for name, differences in fonts.items():
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        if differences:
            items = ArrayObject()
            for code, glyph in differences:
                items += [NumberObject(code), NameObject(glyph)]
            font[NameObject('/Encoding')] = DictionaryObject({NameObject('/Type'): NameObject('/Encoding'),
                NameObject('/BaseEncoding'): NameObject('/WinAnsiEncoding'), NameObject('/Differences'): items})
        if to_unicode:
            cmap = DecodedStreamObject()
            pairs = ''.join(f'<{code:02X}> <{ord(c):04X}>\n' for code, c in sorted(to_unicode.items()))
            cmap.set_data(('/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Synthetic def '
                           '1 begincodespacerange <00> <FF> endcodespacerange '
                           f'{len(to_unicode)} beginbfchar\n{pairs}endbfchar endcmap CMapName currentdict /CMap '
                           'defineresource pop end end').encode())
            font[NameObject('/ToUnicode')] = writer._add_object(cmap)
        resources[NameObject(name)] = writer._add_object(font)
    for content in pages:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): resources})
        stream = DecodedStreamObject()
        stream.set_data(content.encode('latin-1'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def rules(edges, top=760, height=740):
    return ''.join(f'{x} {top - height} 0.5 {height} re f\n' for x in edges)


def thai_table_pdf(pages):
    """Thai table PDF: pages = [(edges, [(x, y, text)])]; Thai text mapped through the font's /ToUnicode CMap."""
    chars = sorted({c for _, lines in pages for *_, text in lines for c in text if ord(c) > 126})
    codes = {c: 128 + i for i, c in enumerate(chars)}
    assert len(codes) <= 127

    def hexed(text):
        return '<' + ''.join(f'{codes.get(c, ord(c)):02x}' for c in text) + '>'

    streams = [rules(edges) + ''.join(f'BT /T 10 Tf 1 0 0 1 {x} {y} Tm {hexed(text)} Tj ET\n' for x, y, text in lines)
               for edges, lines in pages]
    return make_pdf(streams, {'/T': None}, {code: c for c, code in codes.items()})


class PdfCellsTests(unittest.TestCase):
    def test_columns_come_from_rules_and_each_text_operator_keeps_its_own_position(self):
        content = rules([100, 200, 300, 400]) + (
            # One text object, several Tj/TJ moved by Td: pypdf batches these; cells must not merge.
            'BT /F1 10 Tf 1 0 0 1 110 680 Tm (left) Tj 100 0 Td (mid) Tj 100 0 Td [(ri) -200 (ght)] TJ ET\n')
        tables = pdf_cells.tables(make_pdf([content, 'BT /F1 10 Tf 1 0 0 1 50 50 Tm (no rules) Tj ET'], {'/F1': None}))
        self.assertEqual(len(tables), 1)  # the page without table rules is not a table
        self.assertEqual(tables[0]['page'], 1)
        self.assertEqual([l['cells'] for l in tables[0]['lines']], [{1: 'left', 2: 'mid', 3: 'right'}])

    def test_font_follows_graphics_state_save_and_restore(self):
        content = rules([100, 200, 300, 400]) + (
            'BT /F1 10 Tf 1 0 0 1 110 700 Tm (A) Tj ET\n'
            'q BT /F2 10 Tf 1 0 0 1 210 700 Tm (A) Tj ET Q\n'
            'BT 1 0 0 1 310 700 Tm (A) Tj ET\n')  # after Q the saved font (F1) applies again
        pdf = make_pdf([content], {'/F1': None, '/F2': [(65, '/Z')]})
        self.assertEqual(pdf_cells.tables(pdf)[0]['lines'][0]['cells'], {1: 'A', 2: 'Z', 3: 'A'})

    def test_thai_text_decodes_through_the_fonts_own_map(self):
        pdf = thai_table_pdf([([100, 200, 300], [(110, 700, 'กิจกรรม'), (210, 700, '1 ม.ค. 72')])])
        self.assertEqual(pdf_cells.tables(pdf)[0]['lines'][0]['cells'], {1: 'กิจกรรม', 2: '1 ม.ค. 72'})


if __name__ == '__main__':
    unittest.main()
