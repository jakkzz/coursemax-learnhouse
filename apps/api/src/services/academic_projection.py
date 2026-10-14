"""Role-scoped class projection shared by class and own-school APIs."""
from sqlmodel import select
from src.db.academic_classes import AcademicClass,TeachingAssignment,SchoolStudent,AcademicRosterEntry
from src.db.courses.courses import Course
from src.services.academic_rosters import own_student

async def summary(db,cls,course,manageable):
    entries=(await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.class_id==cls.id))).all()
    return {'id':cls.id,'course_id':course.id,'course_uuid':course.course_uuid,'course_name':course.name,
        'course_available':bool(course.public and course.published),'academic_year':cls.academic_year,'semester':cls.semester,
        'section':cls.section,'manageable':manageable,'version':cls.version,'last_synced_at':cls.last_synced_at,
        'active_count':sum(e.status=='active' for e in entries) if manageable else None,
        'registry_course_id':cls.registry_course_id if manageable else None,'registry_class_id':cls.registry_class_id if manageable else None}

async def project(db,user,org_id,evidence):
    assignments=(await db.exec(select(TeachingAssignment).where(TeachingAssignment.user_id==user.id,TeachingAssignment.active==True))).all();staff_ids={a.course_id for a in assignments}
    student,match_status=await own_student(db,user.id,evidence)
    owned=(await db.exec(select(SchoolStudent).where(SchoolStudent.user_id==user.id))).all();owned_ids={p.id for p in owned}
    entries=(await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.student_id.in_(owned_ids or {-1}),AcademicRosterEntry.status=='active'))).all()
    student_class_ids={e.class_id for e in entries if e.source=='manual' or (student and e.student_id==student.id)}
    rows=(await db.exec(select(AcademicClass,Course).join(Course,Course.id==AcademicClass.course_id).where(Course.org_id==org_id).order_by(AcademicClass.academic_year.desc(),AcademicClass.semester.desc(),Course.name,AcademicClass.section))).all()
    data=[]
    for cls,course in rows:
        manager=user.is_superadmin or course.id in staff_ids
        if manager or cls.id in student_class_ids:data.append(await summary(db,cls,course,manager))
    return {'classes':data,'student_match_status':match_status,'can_create':user.is_superadmin or bool(staff_ids),'can_assign_teachers':user.is_superadmin}
