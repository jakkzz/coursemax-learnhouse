"""Roster-first identity reconciliation; caller owns the atomic transaction.

One bounded advisory lock orders Google admission, roster imports and membership
writes before user/identity locks. No native roles, account merges or grade writes.
"""
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import re
from html.parser import HTMLParser
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import select
from src.route66_ext.db.academic_classes import AcademicClass, AcademicRosterEntry, SchoolStudent, AcademicClassEvent, TeachingAssignment
from src.route66_ext.db.school_identity import SchoolGoogleEvidence
from src.route66_ext.db.provider_identity import ProviderIdentity
from src.route66_ext.adapters.db_courses_courses import Course
from src.route66_ext.services.nrru_directory import student_hint

ROSTER_URL='https://reg.nrru.ac.th/registrar/student_inclass_all.asp'

async def serialize(db):
    await db.execute(text('SELECT pg_advisory_xact_lock(664466, 1)'))

def event(db,actor,kind,details,cls=None,student=None):
    db.add(AcademicClassEvent(actor_user_id=actor,kind=kind,details=details,
        class_id=cls.id if cls else None,student_id=student.id if student else None))

async def active_claims(db):
    rows=(await db.exec(select(SchoolGoogleEvidence).join(ProviderIdentity,ProviderIdentity.id==SchoolGoogleEvidence.identity_id).where(
        ProviderIdentity.provider=='google',ProviderIdentity.retired_at.is_(None),ProviderIdentity.user_id==SchoolGoogleEvidence.user_id))).all()
    claims={}
    for e in rows:
        number=student_hint(e.email,e.hosted_domain)
        if number and len(number)==10:claims.setdefault(number,{}).setdefault(e.user_id,e.identity_id)
    return claims

async def reconcile(db,actor,number,claims=None,cls=None):
    claims=claims if claims is not None else await active_claims(db)
    profile=(await db.exec(select(SchoolStudent).where(SchoolStudent.student_number==number))).first()
    if profile is None or not profile.has_registry_evidence:return 'waiting_for_roster'
    owners=claims.get(number,{})
    if not owners:return 'unlinked'
    if len(owners)!=1:
        event(db,actor,'identity_conflict',{'reason':'multiple_verified_claims'},cls,profile);return 'conflict'
    user_id,identity_id=next(iter(owners.items()))
    other=(await db.exec(select(SchoolStudent).where(SchoolStudent.user_id==user_id))).first()
    if (profile.user_id is not None and profile.user_id!=user_id) or (other and other.id!=profile.id):
        event(db,actor,'identity_conflict',{'reason':'existing_identity_or_manual_membership','claimant_user_id':user_id},cls,profile);return 'conflict'
    if profile.user_id is None:
        profile.user_id=user_id;profile.identity_id=identity_id;db.add(profile)
        event(db,actor,'student_identity_matched',{'user_id':user_id,'identity_id':identity_id,'role_grants':False},cls,profile)
    return 'matched'

async def reconcile_login(db,user_id):
    # Called AFTER newly verified Google evidence is flushed, BEFORE session commit.
    claims=await active_claims(db)
    for number,owners in claims.items():
        if user_id not in owners:continue
        manual=(await db.exec(select(SchoolStudent).where(SchoolStudent.user_id==user_id))).first()
        reserved=(await db.exec(select(SchoolStudent).where(SchoolStudent.student_number==number))).first()
        if manual and manual.student_number is None and reserved is None and set(owners)=={user_id}:
            # Correct this same user's manual identity in place; never move
            # roster IDs, work or membership, and never claim registrar facts.
            manual.student_number=number;manual.identity_id=owners[user_id];db.add(manual)
            event(db,user_id,'verified_number_added_to_manual_identity',{'role_grants':False},student=manual)
            await db.flush()
        await reconcile(db,user_id,number,claims)

async def own_student(db,user_id,evidence):
    hint=student_hint(evidence.email,evidence.hosted_domain) if evidence else None
    if not hint or len(hint)!=10:return None,'waiting_for_roster' if hint else None
    profile=(await db.exec(select(SchoolStudent).where(SchoolStudent.student_number==hint))).first()
    if not profile or not profile.has_registry_evidence:return None,'waiting_for_roster'
    owners=(await active_claims(db)).get(hint,{})
    if set(owners)!={user_id} or profile.user_id!=user_id:return None,'conflict'
    return profile,'matched'

async def can_manage(db,user,cls,org_id):
    course=await db.get(Course,cls.course_id)
    if not course or course.org_id!=org_id:raise HTTPException(404,'Class not found')
    assignment=(await db.exec(select(TeachingAssignment).where(TeachingAssignment.course_id==cls.course_id,TeachingAssignment.user_id==user.id,TeachingAssignment.active==True))).first()
    if not user.is_superadmin and assignment is None:raise HTTPException(403,'This course is not assigned to you')
    return course

def source_url(cls):
    return ROSTER_URL+'?'+urlencode({'classid':cls.registry_class_id,'courseid':cls.registry_course_id,'acadyear':cls.academic_year,'semester':cls.semester,'backto':'teach_time'})

class Rows(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.rows=[];self.row=None;self.parts=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row=[]
        elif tag in ('td','th') and self.row is not None:self.parts=[]
    def handle_data(self,data):
        if self.parts is not None:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.parts is not None:
            self.row.append(' '.join(''.join(self.parts).split()));self.parts=None
        elif tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None;self.parts=None

def parse_roster(content,cls):
    try:html=content.decode('cp874')
    except UnicodeDecodeError:raise ValueError('Registrar text could not be decoded') from None
    parser=Rows();parser.feed(html)
    if str(cls.academic_year) not in html or not any(cls.section.casefold()==cell.casefold() for row in parser.rows for cell in row):raise ValueError('Registrar year/section does not match this class')
    before_header=[]
    def roster_header(row):return len(row)>=5 and ('ลำดับ' in row[0] or row[0].casefold() in ('no','no.','#')) and 'รหัส' in row[1] and 'ชื่อ' in row[2]
    for row in parser.rows:
        if roster_header(row):break
        before_header.extend(row)
    code=getattr(cls,'registry_course_code','')
    if not code or not re.search(r'(?<![A-Za-z0-9])'+re.escape(code)+r'(?![A-Za-z0-9])',' '.join(before_header)):
        raise ValueError('Registrar course code does not match the approved course mapping')
    declared=re.search(r'ภาค(?:การศึกษา|เรียน)\s*(?:ที่)?\s*[:\s]*([1-3])',html)
    if declared and int(declared[1])!=cls.semester:raise ValueError('Registrar semester does not match this class')
    header=False;faculty='';result=[];seen=set()
    for row in parser.rows:
        if roster_header(row):header=True;continue
        if not header:continue
        if len(row)==1 and row[0]:faculty=row[0];continue
        if not row or not row[0].isdigit():continue
        if len(row)<5 or not re.fullmatch('[0-9]{10}',row[1]) or not faculty or not row[2] or not row[3] or int(row[0])<1:raise ValueError('Incomplete registrar student row; snapshot rejected')
        if row[1] in seen:raise ValueError('Duplicate registrar student number; snapshot rejected')
        if any(len(v)>200 for v in [faculty,row[2],row[3]]) or len(row[4])>80:raise ValueError('Registrar student field exceeds supported length')
        seen.add(row[1]);result.append({'student_number':row[1],'full_name_th':row[2],'faculty':faculty,'program':row[3],'registry_status_code':row[4] or None,'display_position':int(row[0])})
    if not result or len(result)>1000:raise ValueError('No complete roster or roster exceeds supported size')
    return result

async def fetch_roster(cls):
    url=source_url(cls)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8),follow_redirects=False,trust_env=False) as client:
            async with client.stream('GET',url,headers={'User-Agent':'LearnHouseRoster/1.0'}) as response:
                if response.status_code!=200:raise ValueError('Registrar roster is unavailable')
                data=bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data)>512*1024:raise ValueError('Registrar response exceeds supported size')
    except httpx.HTTPError:raise ValueError('Registrar roster is unavailable') from None
    raw=bytes(data);return parse_roster(raw,cls),sha256(raw).hexdigest()

async def apply_roster(db,cls,rows,source_hash,actor):
    # Revalidate server-owned preview rows, never accept browser-supplied names.
    claims=await active_claims(db)
    existing=(await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.class_id==cls.id))).all()
    by_student={e.student_id:e for e in existing};seen=set();counts={'added':0,'reactivated':0,'missing':0,'withdrawn':0,'matched':0,'conflicts':0}
    for row in rows:
        profile=(await db.exec(select(SchoolStudent).where(SchoolStudent.student_number==row['student_number']))).first()
        if profile is None:
            profile=SchoolStudent(student_number=row['student_number'],full_name_th=row['full_name_th'],faculty=row['faculty'],program=row['program'],has_registry_evidence=True);db.add(profile);await db.flush()
        else:
            for key in ('full_name_th','faculty','program'):setattr(profile,key,row[key])
            profile.has_registry_evidence=True;db.add(profile)
        seen.add(profile.id);entry=by_student.get(profile.id)
        if entry is None:
            entry=AcademicRosterEntry(class_id=cls.id,student_id=profile.id,display_position=row['display_position']);counts['added']+=1;kind='registry_member_added'
        else:
            kind='registrar_membership_confirmed' if entry.source=='manual' else 'registry_member_seen'
            if entry.status=='withdrawn':counts['reactivated']+=1;kind='registry_member_reactivated'
            entry.status='active';entry.source='registry';entry.missing_count=0;entry.display_position=row['display_position']
        entry.registry_status_code=row.get('registry_status_code')
        db.add(entry);event(db,actor,kind,{'student_number':row['student_number'],'full_name_th':row['full_name_th'],'faculty':row['faculty'],'program':row['program'],'registry_status_code':entry.registry_status_code},cls,profile)
        status=await reconcile(db,actor,row['student_number'],claims,cls)
        counts['matched']+=status=='matched';counts['conflicts']+=status=='conflict'
    for entry in existing:
        if entry.student_id in seen or entry.source=='manual' or entry.status!='active':continue
        entry.missing_count+=1;counts['missing']+=1
        if entry.missing_count>=2:entry.status='withdrawn';counts['withdrawn']+=1
        db.add(entry);event(db,actor,'registry_member_missing',{'missing_count':entry.missing_count,'status':entry.status},cls,await db.get(SchoolStudent,entry.student_id))
    cls.version+=1;cls.last_source_hash=source_hash;cls.last_synced_at=datetime.now(timezone.utc);db.add(cls)
    event(db,actor,'roster_snapshot_applied',{'source_hash':source_hash,'counts':counts,'version':cls.version},cls)
    await db.flush();return counts

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
