"""Academic class/roster authority, separate from native content and account roles."""
import json,secrets
from datetime import datetime,timezone,timedelta
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel,ConfigDict,Field,StrictBool,field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.route66_ext.adapters.core_events_database import get_db_session
from src.route66_ext.routers.school_identity import context, private
from src.route66_ext.routers.google_subject_auth import boundary, resources, throttle
from src.route66_ext.db.academic_classes import AcademicClass, TeachingAssignment, SchoolStudent, AcademicRosterEntry, AcademicClassEvent, CourseRegistryBinding
from src.route66_ext.adapters.db_courses_courses import Course
from src.route66_ext.adapters.db_users import User
from src.route66_ext.db.school_identity import SchoolGoogleEvidence
from src.route66_ext.db.provider_identity import ProviderIdentity
from src.route66_ext.adapters.db_user_organizations import UserOrganization
from src.route66_ext.services import academic_rosters as service

router=APIRouter()
class Body(BaseModel):
    model_config=ConfigDict(extra='forbid')
    @field_validator('reason',check_fields=False)
    @classmethod
    def meaningful_reason(cls,value):
        value=value.strip()
        if len(value)<5:raise ValueError('A meaningful reason is required')
        return value
class Assignment(Body):
    course_id:int=Field(gt=0)
    user_id:int=Field(gt=0)
    active:StrictBool=True
    reason:str=Field(min_length=5,max_length=500)
    registry_course_id:str|None=Field(default=None,pattern=r'^[1-9][0-9]{0,19}$')
    course_code:str|None=Field(default=None,min_length=3,max_length=30,pattern=r'^[A-Za-z0-9-]+$')
class ClassSetup(Body):
    course_id:int=Field(gt=0)
    academic_year:int=Field(ge=2500,le=2700)
    semester:int=Field(ge=1,le=3)
    section:str=Field(min_length=1,max_length=40,pattern=r'^[A-Za-z0-9/-]+$')
    registry_course_id:str=Field(pattern=r'^[1-9][0-9]{0,19}$')
    registry_class_id:str=Field(pattern=r'^[1-9][0-9]{0,19}$')
    @field_validator('section')
    @classmethod
    def canonical_section(cls,value):return value.upper()
class Correction(ClassSetup):
    expected_version:int=Field(ge=0)
    reason:str=Field(min_length=5,max_length=500)
class Apply(Body):
    preview_id:str=Field(pattern=r'^[A-Za-z0-9_-]{32,64}$')
    confirm_changes:StrictBool
class ManualMember(Body):
    email:str=Field(min_length=3,max_length=320)
    reason:str=Field(min_length=5,max_length=500)
class Membership(Body):
    expected_version:int=Field(ge=0)
    status:str=Field(pattern=r'^(active|withdrawn)$')
    reason:str=Field(min_length=5,max_length=500)
class Flag(Body):reason:str=Field(min_length=5,max_length=500)

async def staff_class(db,user,org_id,class_id):
    cls=await db.get(AcademicClass,class_id)
    if cls is None:raise HTTPException(404,'Class not found')
    await service.can_manage(db,user,cls,org_id);return cls

async def commit(db):
    try:await db.commit()
    except IntegrityError:
        await db.rollback();raise HTTPException(409,'An existing course, class or identity owns this record. Reload; ask an administrator to review.') from None

async def summary(db,cls,course,manageable):
    entries=(await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.class_id==cls.id))).all()
    return {'id':cls.id,'course_id':course.id,'course_uuid':course.course_uuid,'course_name':course.name,
        'course_available':bool(course.public and course.published),'academic_year':cls.academic_year,'semester':cls.semester,
        'section':cls.section,'manageable':manageable,'version':cls.version,'last_synced_at':cls.last_synced_at,
        'active_count':sum(e.status=='active' for e in entries) if manageable else None,
        'registry_course_id':cls.registry_course_id if manageable else None,'registry_class_id':cls.registry_class_id if manageable else None}

@router.get('/courses')
async def courses(request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db)
    assigned=(await db.exec(select(TeachingAssignment).where(TeachingAssignment.user_id==user.id,TeachingAssignment.active==True))).all()
    ids={a.course_id for a in assigned}
    courses=(await db.exec(select(Course).where(Course.org_id==config.org_id))).all()
    bindings={b.course_id:b for b in (await db.exec(select(CourseRegistryBinding))).all()}
    courses=[{'id':c.id,'name':c.name,'course_uuid':c.course_uuid,'registry_course_id':bindings[c.id].registry_course_id if c.id in bindings else None,'course_code':bindings[c.id].course_code if c.id in bindings else None,'private':c.public is False} for c in courses if user.is_superadmin or c.id in ids]
    teachers=[];assignments=[]
    if user.is_superadmin:
        members=(await db.exec(select(User).join(UserOrganization,UserOrganization.user_id==User.id).where(UserOrganization.org_id==config.org_id))).all()
        teachers=[{'id':u.id,'name':' '.join([u.first_name,u.last_name]).strip() or u.username,'username':u.username} for u in members]
        rows=(await db.exec(select(TeachingAssignment).join(Course,Course.id==TeachingAssignment.course_id).where(Course.org_id==config.org_id))).all()
        assignments=[{'course_id':a.course_id,'user_id':a.user_id,'active':a.active} for a in rows]
    return {'courses':courses,'can_assign_teachers':user.is_superadmin,'teachers':teachers,'teaching_assignments':assignments}

@router.post('/teaching-assignments')
async def assign(body:Assignment,request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db);boundary(request,config)
    if not user.is_superadmin:raise HTTPException(403,'Administrator approval required')
    await service.serialize(db)
    course=await db.get(Course,body.course_id)
    member=(await db.exec(select(UserOrganization).where(UserOrganization.user_id==body.user_id,UserOrganization.org_id==config.org_id))).first()
    if not course or course.org_id!=config.org_id or not member:raise HTTPException(404,'Course or organization member not found')
    binding=await db.get(CourseRegistryBinding,body.course_id)
    if body.active:
        if not body.registry_course_id or not body.course_code:raise HTTPException(422,'Approve the official course identifier and code; names alone do not map courses')
        if binding and (binding.registry_course_id,binding.course_code)!=(body.registry_course_id,body.course_code):
            classes=(await db.exec(select(AcademicClass).where(AcademicClass.course_id==body.course_id))).all()
            if classes:raise HTTPException(409,'Course mapping has class history. Separate administrator review is required.')
        binding=binding or CourseRegistryBinding(course_id=body.course_id,registry_course_id=body.registry_course_id,course_code=body.course_code)
        binding.registry_course_id=body.registry_course_id;binding.course_code=body.course_code;db.add(binding)
    record=(await db.exec(select(TeachingAssignment).where(TeachingAssignment.course_id==body.course_id,TeachingAssignment.user_id==body.user_id))).first()
    if record is None:record=TeachingAssignment(course_id=body.course_id,user_id=body.user_id)
    record.active=body.active;db.add(record)
    service.event(db,user.id,'teaching_assignment_changed',body.model_dump())
    await db.flush()
    from src.route66_ext.services.learning_access import refresh_course
    await refresh_course(db,user.id,body.course_id)
    await commit(db)
    return {'saved':True,'active':record.active,'native_roles_changed':False}

@router.get('')
async def classes(request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,evidence=await context(request,db)
    from src.route66_ext.services.academic_projection import project
    return await project(db,user,config.org_id,evidence,request=request)

@router.post('')
async def create(body:ClassSetup,request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db);boundary(request,config);await service.serialize(db)
    cls=AcademicClass(**body.model_dump());await service.can_manage(db,user,cls,config.org_id)
    binding=await db.get(CourseRegistryBinding,body.course_id)
    if not binding or binding.registry_course_id!=body.registry_course_id:raise HTTPException(409,'An administrator must approve this course mapping before class setup')
    cls.registry_course_code=binding.course_code
    db.add(cls)
    try:await db.flush()
    except IntegrityError:
        await db.rollback();raise HTTPException(409,'This section or registrar class is already bound. It cannot be taken from another course.') from None
    service.event(db,user.id,'class_created',body.model_dump(),cls);await commit(db)
    return {'id':cls.id,'version':cls.version}

@router.post('/{class_id}/configuration')
async def correct(class_id:int,body:Correction,request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db);boundary(request,config);await service.serialize(db);cls=await staff_class(db,user,config.org_id,class_id)
    entries=(await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.class_id==class_id))).all()
    from src.route66_ext.db.class_attendance import AttendanceSession
    attendance=(await db.exec(select(AttendanceSession.id).where(AttendanceSession.class_id==class_id).limit(1))).first()
    if body.course_id!=cls.course_id or cls.version!=body.expected_version or cls.last_synced_at or entries or attendance:
        raise HTTPException(409,'Only an unused class setup can be corrected. Preserve existing roster/history; ask an administrator to review.')
    binding=await db.get(CourseRegistryBinding,cls.course_id)
    if not binding or binding.registry_course_id!=body.registry_course_id:raise HTTPException(409,'Use the administrator-approved official course mapping')
    before={key:getattr(cls,key) for key in ClassSetup.model_fields}
    for key in ClassSetup.model_fields:setattr(cls,key,getattr(body,key))
    cls.registry_course_code=binding.course_code;cls.version+=1;db.add(cls);service.event(db,user.id,'unused_class_setup_corrected',{'before':before,'after':{key:getattr(cls,key) for key in ClassSetup.model_fields},'reason':body.reason},cls)
    await commit(db);return {'saved':True,'version':cls.version}

@router.get('/{class_id}/roster')
async def roster(class_id:int,request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db);cls=await staff_class(db,user,config.org_id,class_id)
    rows=(await db.exec(select(AcademicRosterEntry,SchoolStudent).join(SchoolStudent,SchoolStudent.id==AcademicRosterEntry.student_id).where(AcademicRosterEntry.class_id==class_id).order_by(AcademicRosterEntry.display_position,AcademicRosterEntry.id))).all();claims=await service.active_claims(db)
    students=[]
    linked=(await db.exec(select(SchoolStudent).where(SchoolStudent.user_id.is_not(None)))).all()
    linked_by_user={p.user_id:p.id for p in linked}
    for entry,p in rows:
        owners=claims.get(p.student_number,{})
        conflicted=bool(p.student_number and (len(owners)>1 or (p.user_id and owners and p.user_id not in owners)
            or any(linked_by_user.get(uid,p.id)!=p.id for uid in owners)))
        students.append({'id':entry.id,'student_number':p.student_number,'full_name_th':p.full_name_th,'faculty':p.faculty,'program':p.program,'status':entry.status,'source':entry.source,'missing_count':entry.missing_count,'account_status':'conflict' if conflicted else 'matched' if p.user_id else 'unlinked'})
    events=(await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.class_id==class_id).order_by(AcademicClassEvent.id.desc()).limit(20))).all()
    return {'class_id':cls.id,'version':cls.version,'last_synced_at':cls.last_synced_at,'students':students,
        'events':[{'id':e.id,'kind':e.kind,'created_at':e.created_at,'details':e.details} for e in events]}

@router.post('/{class_id}/roster/preview')
async def preview(class_id:int,request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db);boundary(request,config);cls=await staff_class(db,user,config.org_id,class_id)
    async with resources(config) as (redis,_):
        await throttle(redis,request,config,'roster-source-'+str(user.id))
        import asyncio
        try:rows,digest=await asyncio.wait_for(service.fetch_roster(cls),timeout=10)
        except (ValueError,TimeoutError):raise HTTPException(503,'Registrar roster is unavailable or does not match this class. Check the registry IDs, year and section; retry.') from None
        await db.refresh(cls);await service.can_manage(db,user,cls,config.org_id)
        current=(await db.exec(select(AcademicRosterEntry,SchoolStudent).join(SchoolStudent,SchoolStudent.id==AcademicRosterEntry.student_id).where(AcademicRosterEntry.class_id==cls.id))).all()
        incoming={r['student_number'] for r in rows};existing={p.student_number for e,p in current};missing=[(e,p) for e,p in current if e.source=='registry' and e.status=='active' and p.student_number not in incoming]
        token=secrets.token_urlsafe(32);payload={'user_id':user.id,'org_id':config.org_id,'class_id':cls.id,'version':cls.version,'source_hash':digest,'rows':rows}
        await redis.set('lh:roster:'+config.deployment+':'+token,json.dumps(payload),ex=600)
    return {'preview_id':token,'incoming_count':len(rows),'added_count':len(incoming-existing),'missing_count':len(missing),'withdraw_count':sum(e.missing_count>=1 for e,p in missing),'source_url':service.source_url(cls),'expires_in':600,'version':cls.version}

@router.post('/{class_id}/roster/apply')
async def apply(class_id:int,body:Apply,request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db);boundary(request,config)
    if not body.confirm_changes:raise HTTPException(400,'Review and confirm roster changes')
    await service.serialize(db);cls=await staff_class(db,user,config.org_id,class_id)
    async with resources(config) as (redis,_):
        await throttle(redis,request,config,'roster-apply-'+str(user.id));key='lh:roster:'+config.deployment+':'+body.preview_id;raw=await redis.get(key)
        if raw is None:raise HTTPException(409,'Preview expired or already used. Load the roster again.')
        data=json.loads(raw)
        if (data['user_id'],data['org_id'],data['class_id'],data['version'])!=(user.id,config.org_id,cls.id,cls.version):raise HTTPException(409,'Class or permission changed. Load a new preview.')
        if cls.last_source_hash==data['source_hash'] and cls.last_synced_at and datetime.now(timezone.utc)-cls.last_synced_at<timedelta(minutes=30):raise HTTPException(409,'This roster was recently applied. Wait before checking another missing snapshot.')
        if await redis.eval("if redis.call('GET',KEYS[1]) == ARGV[1] then redis.call('DEL',KEYS[1]); return 1 end; return 0",1,key,raw)!=1:raise HTTPException(409,'Preview already used. Load a new preview.')
        counts=await service.apply_roster(db,cls,data['rows'],data['source_hash'],user.id)
        await commit(db)
    return {'applied':True,'counts':counts,'version':cls.version}

@router.post('/{class_id}/roster/manual')
async def manual(class_id:int,body:ManualMember,request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db);boundary(request,config);await service.serialize(db);cls=await staff_class(db,user,config.org_id,class_id)
    from sqlalchemy import func
    targets=(await db.exec(select(User).join(UserOrganization,UserOrganization.user_id==User.id)
        .join(SchoolGoogleEvidence,SchoolGoogleEvidence.user_id==User.id)
        .join(ProviderIdentity,ProviderIdentity.id==SchoolGoogleEvidence.identity_id)
        .where(UserOrganization.org_id==config.org_id,func.lower(SchoolGoogleEvidence.email)==body.email.strip().lower(),
            ProviderIdentity.user_id==User.id,ProviderIdentity.provider=='google',ProviderIdentity.retired_at.is_(None)))).all()
    if len(targets)>1:raise HTTPException(409,'Multiple accounts claim this verified email. Administrator review is required; no automatic selection or merge.')
    target=targets[0] if targets else None
    if target is None:raise HTTPException(404,'Existing verified organization account not found; ask the student to sign in first')
    profile=(await db.exec(select(SchoolStudent).where(SchoolStudent.user_id==target.id))).first()
    if profile is None:
        verified=(await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id==target.id))).first()
        from src.route66_ext.services.nrru_directory import student_hint
        number=student_hint(verified.email,verified.hosted_domain) if verified else None
        number=number if number and len(number)==10 else None
        if number and (await db.exec(select(SchoolStudent).where(SchoolStudent.student_number==number))).first():
            raise HTTPException(409,'This institutional identity already has a record. Administrator review is required; no accounts or roster entries will be merged.')
        # A verified-number claim is not registrar evidence. Keep existing
        # memberships stable when the official roster subsequently arrives.
        profile=SchoolStudent(user_id=target.id,student_number=number,identity_id=verified.identity_id if number else None,full_name_th=' '.join([target.first_name,target.last_name]).strip() or target.username,faculty='',program='');db.add(profile);await db.flush()
    entry=(await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.class_id==cls.id,AcademicRosterEntry.student_id==profile.id))).first()
    if entry is not None:raise HTTPException(409,'This person already has a roster entry. Change that entry; do not create a duplicate.')
    count=(await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.class_id==cls.id))).all()
    entry=AcademicRosterEntry(class_id=cls.id,student_id=profile.id,source='manual',display_position=max([e.display_position for e in count],default=0)+1);db.add(entry);cls.version+=1;db.add(cls)
    service.event(db,user.id,'manual_member_added',{'reason':body.reason,'user_id':target.id},cls,profile)
    from src.route66_ext.services.learning_access import refresh_course
    await db.flush();await refresh_course(db,user.id,cls.course_id)
    await commit(db);return {'added':True}

@router.post('/{class_id}/roster/{entry_id}/membership')
async def membership(class_id:int,entry_id:int,body:Membership,request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db);boundary(request,config);await service.serialize(db);cls=await staff_class(db,user,config.org_id,class_id)
    entry=await db.get(AcademicRosterEntry,entry_id)
    if not entry or entry.class_id!=cls.id:raise HTTPException(404,'Roster entry not found')
    if cls.version!=body.expected_version:raise HTTPException(409,'Roster changed; reload before changing membership')
    entry.status=body.status;entry.source='manual';entry.missing_count=0;db.add(entry);cls.version+=1;db.add(cls)
    service.event(db,user.id,'manual_membership_changed',{'entry_id':entry_id,'status':body.status,'reason':body.reason},cls,await db.get(SchoolStudent,entry.student_id))
    from src.route66_ext.services.learning_access import refresh_course
    await db.flush();await refresh_course(db,user.id,cls.course_id)
    await commit(db);return {'saved':True}

@router.post('/{class_id}/roster/{entry_id}/flag')
async def flag(class_id:int,entry_id:int,body:Flag,request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    private(response);user,config,_=await context(request,db);boundary(request,config);await service.serialize(db);cls=await staff_class(db,user,config.org_id,class_id)
    entry=await db.get(AcademicRosterEntry,entry_id)
    if not entry or entry.class_id!=class_id:raise HTTPException(404,'Roster entry not found')
    service.event(db,user.id,'identity_review_requested',{'entry_id':entry_id,'reason':body.reason},cls,await db.get(SchoolStudent,entry.student_id));await commit(db)
    return {'flagged':True,'identity_changed':False}

# Reuse the existing extension mount; no native router/bootstrap hook is added.
from src.route66_ext.routers.learning_access import router as learning_access_router
router.include_router(learning_access_router)
from src.route66_ext.routers.class_connections import router as class_connections_router
router.include_router(class_connections_router)

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
