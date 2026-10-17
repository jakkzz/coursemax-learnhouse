"""Prepare editable native syllabus content from a pinned semester plan, not invented curriculum."""
from src.route66_ext.services import calendar_plan as planner


def document(cls, calendar, revision, planning, th=False, course_name=''):
    payload = planner.course_payload(planner.Payload.model_validate(revision.payload), cls.semester,
        planner.CoursePlanning.model_validate(planning) if planning else None)
    term = next(t for t in payload.terms if t.semester == cls.semester)
    t = lambda en, thai: thai if th else en
    nodes = []
    day = lambda value: f'{value.day}/{value.month}/{value.year + 543}' if th else str(value)

    def text(kind, value, **attrs):
        nodes.append({'type': kind, **({'attrs': attrs} if attrs else {}),
                      'content': [{'type': 'text', 'text': value}]})

    text('heading', t('Course syllabus', 'ประมวลรายวิชา'), level=1)
    text('paragraph', f'{cls.registry_course_code} · {cls.registry_title or course_name} · {cls.semester}/{cls.academic_year}')
    text('paragraph', f'{calendar.name} · {t("Calendar revision", "ฉบับปฏิทิน")} {revision.number}')
    text('paragraph', t('Draft for instructor completion. Calendar dates do not supply course outcomes, topics or grading rules.',
                        'ฉบับร่างสำหรับผู้สอนเติมรายละเอียด ปฏิทินไม่ได้ระบุผลลัพธ์การเรียนรู้ หัวข้อเนื้อหา หรือเกณฑ์คะแนนของรายวิชา'))
    for heading in (t('Course description', 'คำอธิบายรายวิชา'), t('Learning outcomes', 'ผลลัพธ์การเรียนรู้'),
                    t('Assessment and grading', 'การประเมินผลและเกณฑ์คะแนน')):
        text('heading', heading, level=2)
        text('paragraph', t('Complete from the approved course specification.', 'เติมข้อมูลตามข้อกำหนดรายวิชาที่ได้รับอนุมัติ'))
    text('heading', t('Semester academic dates', 'กำหนดการศึกษาของภาคเรียน'), level=2)
    for event in payload.events:
        if event.semester != cls.semester or event.program != (planning['program'] if planning else calendar.track) or event.kind == 'other':
            continue
        text('paragraph', f'{day(event.starts_on)} – {day(event.ends_on)} · {event.program} · {event.title}' + (f' · {event.note}' if event.note else ''))
    text('heading', t('Weekly teaching outline', 'แผนการสอนรายสัปดาห์'), level=2)
    if planning:
        text('paragraph', t('These are teacher-reviewed course planning weeks, not an official school-wide rotation. Review exams, holidays and make-ups.',
                            'สัปดาห์เหล่านี้ใช้วางแผนรายวิชาโดยผู้สอน ไม่ใช่สัปดาห์หรือการสลับรูปแบบเรียนส่วนกลาง โปรดตรวจสอบช่วงสอบ วันหยุด และวันชดเชย'))
    for week in term.weeks:
        text('heading', f'{t("Week", "สัปดาห์ที่")} {week.number} · {day(week.starts_on)} – {day(week.ends_on)}', level=3)
        text('paragraph', t('Complete the topic, learning activities and assessment for this week.', 'เติมหัวข้อ กิจกรรมการเรียนรู้ และการประเมินผลของสัปดาห์นี้') if week.teaching else
             t('No regular teaching in this calendar week. Complete any exam or other arrangements separately.', 'ปฏิทินระบุว่าไม่มีการสอนตามตารางปกติในสัปดาห์นี้ โปรดเติมการสอบหรือกิจกรรมอื่นแยกต่างหาก'))
        if week.note:
            text('paragraph', week.note)
    for closure in term.closures:
        text('paragraph', f'{day(closure.affected_on)} · {closure.note}' +
             (f' · {t("Make-up", "สอนชดเชย")} {day(closure.makeup_on)}' if closure.makeup_on else ''))
    return {'type': 'doc', 'content': nodes}
