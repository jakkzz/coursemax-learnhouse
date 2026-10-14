import unittest
from unittest.mock import AsyncMock
import httpx
from src.route66_ext.services.nrru_directory import teacher_hint, student_hint, parse_candidates, search_directory, DirectoryUnavailable, URL, MAX_BYTES

def fixture(*records):
    rows = ''.join(f'<tr><td><a href="teach_time.asp?officerid={id}&amp;f_cmd=2&amp;officercode={id}">{th}</a></td><td>{en}</td></tr>' for id,th,en in records)
    return ('<h1>ตารางสอนอาจารย์</h1><table>'+rows+'</table>').encode('cp874')

class DirectoryTests(unittest.IsolatedAsyncioTestCase):
    def test_email_hint_is_not_staff_permission(self):
        self.assertEqual(teacher_hint('jakkrit.s@nrru.ac.th','nrru.ac.th'),'jakkrit')
        for email,hd in [('6900000001@nrru.ac.th','nrru.ac.th'),('jakkrit.s@nrru.ac.th',None),('jakkrit.s@gmail.com','nrru.ac.th'),('jakkrit.s@nrru.ac.th.evil','nrru.ac.th'),("jack'.s@nrru.ac.th",'nrru.ac.th')]:
            self.assertIsNone(teacher_hint(email,hd))
    def test_student_school_menu_hint_needs_verified_institutional_evidence(self):
        self.assertEqual(student_hint('6900000001@nrru.ac.th','nrru.ac.th'),'6900000001')
        self.assertEqual(student_hint('690000001@nrru.ac.th','nrru.ac.th'),'690000001')
        for email,domain in [('6900000001@nrru.ac.th',None),('6900000001@gmail.com','nrru.ac.th'),('jakkrit.s@nrru.ac.th','nrru.ac.th'),('69@nrru.ac.th','nrru.ac.th')]:
            self.assertIsNone(student_hint(email,domain))

    def test_multiple_names_and_only_known_source_fields(self):
        items=parse_candidates(fixture(('12','อาจารย์ตัวอย่าง ก','Demo Teacher A'),('13','อาจารย์ตัวอย่าง ข','Demo Teacher B')))
        self.assertEqual([x['officer_id'] for x in items],['12','13'])
        self.assertEqual(set(items[0]),{'officer_id','officer_code','name_th','name_en'})
    def test_empty_results(self):
        self.assertEqual(parse_candidates(fixture()),[])
    def test_changed_page_rejected(self):
        with self.assertRaises(DirectoryUnavailable):parse_candidates(b'<html>Gateway login</html>')
    def test_conflicting_duplicate_rejected(self):
        with self.assertRaises(DirectoryUnavailable):parse_candidates(fixture(('12','ตัวอย่าง ก','A'),('12','ตัวอย่าง ข','B')))
    async def test_fixed_post_no_cookies_auth_or_redirect(self):
        def transport(r):
            self.assertEqual(str(r.url),URL);self.assertEqual(r.method,'POST')
            self.assertNotIn('cookie',r.headers);self.assertNotIn('authorization',r.headers)
            self.assertIn(b'f_officername=jakkrit',r.content)
            return httpx.Response(200,content=fixture(('12','ตัวอย่าง ก','Demo')))
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport),headers={'Authorization':'secret'},cookies={'native':'secret'}) as c:
            self.assertEqual(len(await search_directory('jakkrit',c)),1)
    async def test_redirect_and_size_rejected(self):
        for status,body in [(302,b''),(200,b'x'*(MAX_BYTES+1))]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(status,content=body))) as c:
                with self.assertRaises(DirectoryUnavailable):await search_directory('jakkrit',c)
    async def test_wildcard_and_sql_hint_rejected(self):
        for hint in ['jack*',"jack' OR 1=1",'690001','jakkrit.s']:
            with self.assertRaises(ValueError):await search_directory(hint)

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
