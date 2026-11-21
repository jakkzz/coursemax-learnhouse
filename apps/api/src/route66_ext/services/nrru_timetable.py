"""Own confirmed staff timetable; never follows roster, contact or QR links."""
import asyncio
import re
from urllib.parse import parse_qs, urlsplit
import httpx
from bs4 import BeautifulSoup
from src.route66_ext.services.nrru_directory import URL, MAX_BYTES, DirectoryUnavailable


def parse_timetable(raw, officer_id, officer_code):
    soup=BeautifulSoup(raw.decode('cp874'), 'html.parser')
    text=soup.get_text(' ',strip=True)
    if 'ตารางสอนอาจารย์' not in text:
        raise DirectoryUnavailable('directory_changed')
    term=None
    for a in soup.find_all('a',href=True):
        u=urlsplit(a['href']); q=parse_qs(u.query)
        if u.scheme or u.netloc or u.path!='teach_time.asp' or not (q.get('d1') or q.get('d2')):continue
        if q.get('officerid')!=[officer_id] or q.get('officercode')!=[officer_code]:
            raise DirectoryUnavailable('directory_changed')
        y,s=q.get('acadyear',[''])[0],q.get('semester',[''])[0]
        if not re.fullmatch(r'25[0-9]{2}|26[0-9]{2}',y) or s not in ('1','2','3'):
            raise DirectoryUnavailable('directory_changed')
        current={'academic_year':int(y),'semester':int(s)}
        if term and current!=term:raise DirectoryUnavailable('directory_changed')
        term=current
    if term is None:raise DirectoryUnavailable('directory_changed')
    slots=[]
    for td in soup.find_all('td'):
        label=td.get_text(' ',strip=True)
        slot=re.fullmatch(r'([0-2]?[0-9]:[0-5][0-9])-([0-2]?[0-9]:[0-5][0-9])',label)
        if slot:slots.append(slot.groups())
    found={}
    for a in soup.find_all('a',href=True):
        u=urlsplit(a['href']);q=parse_qs(u.query)
        if u.scheme or u.netloc or u.path!='class_info_2.asp':continue
        if q.get('acadyear')!=[str(term['academic_year'])] or q.get('semester')!=[str(term['semester'])]:
            raise DirectoryUnavailable('directory_changed')
        identifier=q.get('courseid',[''])[0];code=a.get_text(' ',strip=True);name=a.get('title','').strip()
        cell=a.find_parent('td');details=' '.join(cell.get_text(' ',strip=True).split()) if cell else ''
        section=re.search(r'\(([A-Za-z][A-Za-z0-9/-]{0,20})\)',details)
        if not re.fullmatch(r'[0-9]{1,20}',identifier) or not re.fullmatch(r'[0-9]{6,12}',code) or not name or len(name)>300 or not section or len(details)>1000:
            raise DirectoryUnavailable('directory_changed')
        key=(identifier,section[1]);entry=found.setdefault(key,dict(registry_course_id=identifier,course_code=code,title=name,section=section[1],meetings=[]))
        if entry['title']!=name or entry['course_code']!=code:raise DirectoryUnavailable('directory_changed')
        row=cell.find_parent('tr'); cells=row.find_all('td',recursive=False) if row else []
        day=cells[0].get_text(' ',strip=True) if cells else ''
        if not any(c is cell for c in cells) or not slots:raise DirectoryUnavailable('directory_changed')
        try:
            position=next(i for i,c in enumerate(cells) if c is cell)
            index=sum(int(c.get('colspan','1')) for c in cells[:position])-1
            span=int(cell.get('colspan','1'))
            if span<1 or index<0 or index+span>len(slots):raise ValueError()
            start,end=slots[index][0],slots[index+span-1][1]
        except (ValueError,IndexError):raise DirectoryUnavailable('directory_changed') from None
        meeting={'day':day,'start_time':start,'end_time':end,'details':details}
        if meeting not in entry['meetings']:entry['meetings'].append(meeting)
    if len(found)>100:raise DirectoryUnavailable('directory_changed')
    if not found and 'ไม่พบข้อมูลตารางสอน' not in text:
        raise DirectoryUnavailable('directory_changed')
    from src.route66_ext.services.calendar_plan import official_course_facts
    for entry in found.values():
        entry.update(official_course_facts(entry['meetings']))
    return {**term,'classes':list(found.values()),'source':'https://reg.nrru.ac.th/registrar/teach_time.asp', 'authority':'registrar_read_only_not_learnhouse_assignment'}

async def teacher_timetable(officer_id, officer_code, academic_year=None, semester=None, client=None):
    if not all(isinstance(n,str) and re.fullmatch(r'[0-9]{1,20}',n) for n in (officer_id,officer_code)):
        raise ValueError('invalid_officer')
    params={'f_cmd':'2','officerid':officer_id,'officercode':officer_code}
    if academic_year is not None or semester is not None:
        from datetime import date
        if type(academic_year)!=int or abs(academic_year-(date.today().year+543))>1 or type(semester)!=int or semester not in (1,2,3):
            raise ValueError('invalid_term')
        params.update(acadyear=str(academic_year),semester=str(semester))
    async def fetch(c):
        request=httpx.Request('GET',URL,params=params,extensions={'timeout':dict.fromkeys(('connect','read','write','pool'),8.0)})
        try:
            async with asyncio.timeout(10):
                r=await c.send(request,stream=True,auth=None,follow_redirects=False)
                try:
                    if r.status_code!=200:raise DirectoryUnavailable('directory_unavailable')
                    raw=bytearray()
                    async for chunk in r.aiter_bytes():
                        if len(raw)+len(chunk)>MAX_BYTES:raise DirectoryUnavailable('directory_unavailable')
                        raw.extend(chunk)
                    result=parse_timetable(bytes(raw),officer_id,officer_code)
                    if academic_year is not None and (result['academic_year']!=academic_year or result['semester']!=semester):
                        raise DirectoryUnavailable('directory_changed')
                    return result
                finally:await r.aclose()
        except (httpx.HTTPError,TimeoutError,UnicodeError):raise DirectoryUnavailable('directory_unavailable') from None
    if client is not None:return await fetch(client)
    async with httpx.AsyncClient(trust_env=False) as c:return await fetch(c)

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
