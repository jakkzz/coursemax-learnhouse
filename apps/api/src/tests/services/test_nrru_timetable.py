from datetime import date
import unittest
import httpx
from src.services.nrru_timetable import parse_timetable, teacher_timetable
from src.services.nrru_directory import DirectoryUnavailable
YEAR=date.today().year+543

def fixture(empty=False,wrong_owner=False):
    owner='99' if wrong_owner else '12'
    prefix=f'<h1>ตารางสอนอาจารย์</h1><a href="teach_time.asp?officerid={owner}&amp;officercode=34&amp;d1=1&amp;acadyear={YEAR}&amp;semester=1">Year</a>'
    if empty:return (prefix+'ไม่พบข้อมูลตารางสอน').encode('cp874')
    header='<tr><td>Day/Time</td>'+''.join(f'<td>{h}:00-{h+1}:00</td>' for h in range(7,17))+'</tr>'
    # Two byte-identical lesson cells must remain two meetings, not Tag-equality dedup.
    cell=f'<td colspan="3"><a href="class_info_2.asp?courseid=1001&amp;acadyear={YEAR}&amp;semester=1" title="วิชาตัวอย่าง">990001</a> (P1)<br>3 (3-0-6) W:(1-16)<br>DEMO-101</td>'
    return (prefix+'<table>'+header+'<tr><td>พุธ</td><td colspan="2"></td>'+cell+'<td></td>'+cell+'<td></td></tr></table>').encode('cp874')

class TimetableTests(unittest.IsolatedAsyncioTestCase):
    def test_two_meetings_same_class_preserved_and_no_private_contacts(self):
        result=parse_timetable(fixture(),'12','34')
        self.assertEqual(result['academic_year'],YEAR);self.assertEqual(result['semester'],1)
        self.assertEqual(len(result['classes']),1)
        meetings=result['classes'][0]['meetings'];self.assertEqual(len(meetings),2)
        self.assertEqual([(m['start_time'],m['end_time']) for m in meetings],[('9:00','12:00'),('13:00','16:00')])
        self.assertNotIn('email',result);self.assertNotIn('students',result)
    def test_empty_source_is_explicit_not_guessed(self):
        self.assertEqual(parse_timetable(fixture(empty=True),'12','34')['classes'],[])
        with self.assertRaises(DirectoryUnavailable):parse_timetable(b'<html>Unavailable</html>','12','34')
    def test_source_officer_mismatch_rejected(self):
        with self.assertRaises(DirectoryUnavailable):parse_timetable(fixture(wrong_owner=True),'12','34')
    def test_missing_timetable_rows_fail_closed(self):
        with self.assertRaises(DirectoryUnavailable):parse_timetable(fixture(empty=True).replace('ไม่พบข้อมูลตารางสอน'.encode('cp874'),b''),'12','34')
    async def test_transport_uses_only_own_fixed_teacher_query_no_secrets(self):
        def transport(r):
            self.assertEqual(r.url.host,'reg.nrru.ac.th');self.assertEqual(r.url.path,'/registrar/teach_time.asp')
            self.assertEqual(r.url.params['officerid'],'12');self.assertEqual(r.url.params['officercode'],'34')
            self.assertNotIn('cookie',r.headers);self.assertNotIn('authorization',r.headers)
            return httpx.Response(200,content=fixture())
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport),cookies={'session':'secret'},headers={'Authorization':'secret'}) as c:
            self.assertEqual(len((await teacher_timetable('12','34',YEAR,1,c))['classes']),1)
    async def test_term_and_redirect_guards(self):
        for year,term in [(YEAR-2,1),(YEAR,4),(YEAR,None),(None,1)]:
            with self.assertRaises(ValueError):await teacher_timetable('12','34',year,term)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(302))) as c:
            with self.assertRaises(DirectoryUnavailable):await teacher_timetable('12','34',YEAR,1,c)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=fixture()))) as c:
            with self.assertRaises(DirectoryUnavailable):await teacher_timetable('12','34',YEAR,2,c)
