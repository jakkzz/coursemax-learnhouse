'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, CalendarClock, Clock3, MapPin } from 'lucide-react'
import { Button } from '@/extensions/route66/adapters/ui'
import { nativeCoursePath, type AcademicClassLink, type RegistrarClassContext } from './model'
import { SectionConnection } from '../ClassConnections'
import { weekdayKey } from '../../Account/subpages/timetable-colors'
import colors from '../../Account/subpages/timetable-colors.module.css'
import styles from './workspace.module.css'

type View = 'overview' | 'timetable' | 'plan' | 'roster' | 'syllabus'
export default function RealTeachingWorkspace({ context, linked, linksKnown, th, onClose, onOpenRoster, onChanged }: {
  context: RegistrarClassContext; linked: AcademicClassLink | null; linksKnown: boolean; th: boolean
  onClose: () => void; onOpenRoster: () => void; onChanged?: () => void
}) {
  const [view, setView] = useState<View>('overview'), heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { window.scrollTo(0, 0); heading.current?.focus({ preventScroll: true }) }, [])
  const c = context.classRow
  const t = th ? {
    back: 'กลับสู่ชั้นเรียนของฉัน', section: 'กลุ่มเรียน', title: 'พื้นที่ชั้นเรียน', tasks: 'งานของชั้นเรียน',
    source: 'ข้อมูลจริงจากตารางสอนของคุณ · อ่านอย่างเดียว', sourceHelp: 'แสดงข้อมูลจากทะเบียนของบัญชีที่เข้าสู่ระบบ การเปิดหน้านี้ไม่สร้างชั้นเรียน รายชื่อ หรือวันสอนในระบบ',
    overview: 'ภาพรวม', timetable: 'ตารางสอน', plan: 'แผนการสอน', roster: 'รายชื่อ', syllabus: 'ประมวลรายวิชา', courseCode: 'รหัสวิชา', term: 'ภาคเรียน / ปีการศึกษา', overviewTitle: 'ข้อมูลชั้นเรียน', meetings: 'คาบเรียนตามทะเบียน', connection: 'การเชื่อมข้อมูลชั้นเรียน', connected: 'เชื่อมกับชั้นเรียนที่ได้รับมอบหมายแล้ว', notConnected: 'ยังไม่ได้เชื่อมกับข้อมูลรายวิชา',
    weekly: 'วันและเวลาจากทะเบียน', weeklyHelp: 'ข้อมูลด้านล่างเป็นตารางประจำสัปดาห์ ข้อความสัปดาห์และการสลับรูปแบบเรียนคงตามต้นฉบับ ไม่แปลงเป็นวันสอนโดยอัตโนมัติ',
    noMeetings: 'ทะเบียนไม่แสดงวันและเวลาสำหรับกลุ่มเรียนนี้', fetched: 'ดึงข้อมูลเมื่อ',
    unlinked: 'ยังไม่ได้เชื่อมชั้นเรียนนี้กับรายวิชาในระบบ', unlinkedHelp: 'ให้ผู้ดูแลตรวจสอบการเชื่อมรายวิชาและการมอบหมายงานสอน แล้วตั้งค่าภาคเรียนและกลุ่มเรียนให้ตรงกับข้อมูลด้านบน ข้อมูลทะเบียนเพียงอย่างเดียวไม่ให้สิทธิ์จัดการชั้นเรียน',
    unknown: 'ยังตรวจสอบการเชื่อมชั้นเรียนไม่ได้', unknownHelp: 'กลับสู่ชั้นเรียนของฉันแล้วโหลดใหม่ ไม่ใช้ชื่อวิชาเดาว่าเป็นชั้นเรียนเดียวกัน',
    dates: 'วันสอนที่บันทึกไว้', datesHelp: 'ตารางรายสัปดาห์ไม่ใช่แผนรายวัน เปิดกำหนดการชั้นเรียนเพื่อตรวจสอบวันสอน วันงดเรียน และวันชดเชยที่บันทึกไว้ ไม่สร้างวันหรือหัวข้อขึ้นจากตารางทะเบียน',
    openSchedule: 'เปิดกำหนดการชั้นเรียน', people: 'รายชื่อที่บันทึกไว้', peopleHelp: 'เปิดพื้นที่รายชื่อเดิมเพื่อตรวจสอบสมาชิกและสถานะบัญชี การเปิดหน้านี้ไม่ดึงหรือบันทึกรายชื่อนักศึกษาใหม่', openRoster: 'เปิดรายชื่อชั้นเรียน',
    outline: 'ประมวลรายวิชาเป็นเนื้อหาร่วมของรายวิชา', outlineHelp: 'ยังไม่ได้เชื่อมประมวลรายวิชาในหน้านี้ หากรายวิชาที่เผยแพร่มีเอกสารอยู่แล้ว ให้เปิดอ่านจากรายวิชานั้น ไม่สร้างผลลัพธ์การเรียนรู้ หัวข้อ หรือเกณฑ์คะแนนขึ้นเอง',
    openCourse: 'เปิดรายวิชาที่เผยแพร่แล้ว', notReleased: 'บัญชีนี้ยังเปิดเนื้อหารายวิชาไม่ได้ ไม่ได้หมายความว่าไม่มีประมวลรายวิชา',
  } : {
    back: 'Back to My classes', section: 'Section', title: 'Class workspace', tasks: 'Class tasks',
    source: 'Your actual registrar timetable · Read-only', sourceHelp: 'Records belong to the signed-in account. Opening this page does not create a LearnHouse class, roster or dated sessions.',
    overview: 'Overview', timetable: 'Timetable', plan: 'Teaching plan', roster: 'Roster', syllabus: 'Syllabus', courseCode: 'Course code', term: 'Semester / Academic year', overviewTitle: 'Class details', meetings: 'Registrar meetings', connection: 'Class records', connected: 'Connected to an assigned class', notConnected: 'Not connected to course records yet',
    weekly: 'Registrar meeting times', weeklyHelp: 'These are recurring meetings. Original week and rotation descriptions are preserved, not converted automatically into dated teaching sessions.',
    noMeetings: 'The registrar provides no meeting times for this section.', fetched: 'Fetched',
    unlinked: 'This section is not connected to a LearnHouse class yet', unlinkedHelp: 'Ask an administrator to review the course link and teaching assignment, then set up the matching semester and section shown above. A registrar listing alone does not grant class-management access.',
    unknown: 'The linked class could not be checked', unknownHelp: 'Return to My classes and refresh. Course names are never used to guess a class link.',
    dates: 'Saved teaching dates', datesHelp: 'A weekly pattern is not a dated plan. Open the class schedule to review saved sessions, closures and make-up dates. No dates or topics are generated from the registrar listing.',
    openSchedule: 'Open class schedule', people: 'Saved class roster', peopleHelp: 'Use the existing roster workspace to inspect membership and account matches. Opening this page does not fetch or apply a new student roster.', openRoster: 'Open class roster',
    outline: 'The syllabus belongs to the course', outlineHelp: 'A syllabus is not connected here. Open the released course to consult an existing syllabus if provided. No outcomes, topics or grading policy are invented.',
    openCourse: 'Open released course', notReleased: 'Course content is not available to this account. This does not establish whether a syllabus exists.',
  }
  const missing = <div className={styles.missing}><h3>{linksKnown ? t.unlinked : t.unknown}</h3>{linksKnown ? <SectionConnection context={context} th={th} onChanged={onChanged ?? (() => {})} /> : <p>{t.unknownHelp}</p>}</div>
  return <section className={styles.workspace} aria-labelledby="real-class-title">
    <Button variant="ghost" className="min-h-11" onClick={onClose}><ArrowLeft size={16} aria-hidden="true" />{t.back}</Button>
    <header className={styles.heading}><h1 id="real-class-title" ref={heading} tabIndex={-1}>{c.title}</h1><p>{c.course_code} · {context.semester}/{context.academic_year} · {t.section} {c.section}</p></header>
    <div className={styles.source}><CalendarClock size={18} aria-hidden="true" /><div><strong>{t.source}</strong><p>{t.sourceHelp}</p></div></div>
    <nav className={styles.tasks} aria-label={t.tasks}>{(['overview', 'timetable', 'plan', 'roster', 'syllabus'] as const).map(key => <button type="button" key={key} aria-current={view === key ? 'page' : undefined} onClick={() => setView(key)}>{t[key]}</button>)}</nav>
    {view === 'overview' && <div className={styles.task} role="region" aria-label={t.overview}><h2>{t.overviewTitle}</h2><dl className={styles.facts}><div><dt>{t.courseCode}</dt><dd>{c.course_code}</dd></div><div><dt>{t.term}</dt><dd>{context.semester}/{context.academic_year}</dd></div><div><dt>{t.section}</dt><dd>{c.section}</dd></div><div><dt>{t.meetings}</dt><dd>{c.meetings.length}</dd></div><div><dt>{t.connection}</dt><dd>{linked ? t.connected : t.notConnected}</dd></div></dl>{!linked && missing}</div>}
    {view === 'timetable' && <div className={styles.task} role="region" aria-label={t.timetable}><h2>{t.weekly}</h2><p>{t.weeklyHelp}</p>
      {c.meetings.length === 0 ? <p>{t.noMeetings}</p> : <ul className={styles.meetings}>{c.meetings.map((m, i) => <li key={i}><div className={styles.when}><span className={colors.day} data-weekday={weekdayKey(m.day)}><Clock3 size={14} aria-hidden="true" />{m.day}</span><strong>{m.start_time}–{m.end_time}</strong></div>{m.details && <p className={styles.details}><MapPin size={16} aria-hidden="true" /><span>{m.details}</span></p>}</li>)}</ul>}
    </div>}
    {view === 'plan' && <div className={styles.task} role="region" aria-label={t.plan}><h2>{t.dates}</h2><p>{t.datesHelp}</p>{linked ? <Link className={styles.action} href={`/attendance?class=${linked.id}`}>{t.openSchedule}</Link> : missing}</div>}
    {view === 'roster' && <div className={styles.task} role="region" aria-label={t.roster}><h2>{t.people}</h2><p>{t.peopleHelp}</p>{linked ? <Button className="min-h-11" variant="outline" onClick={onOpenRoster}>{t.openRoster}</Button> : missing}</div>}
    {view === 'syllabus' && <div className={styles.task} role="region" aria-label={t.syllabus}><h2>{t.outline}</h2><p>{t.outlineHelp}</p>{linked ? linked.course_available ? <Link className={styles.action} href={nativeCoursePath(linked.course_uuid)}>{t.openCourse}</Link> : <p>{t.notReleased}</p> : missing}</div>}
    <p className={styles.fetched}>{t.fetched}: <time dateTime={context.fetched_at}>{new Date(context.fetched_at).toLocaleString(th ? 'th-TH' : 'en-GB')}</time></p>
  </section>
}
