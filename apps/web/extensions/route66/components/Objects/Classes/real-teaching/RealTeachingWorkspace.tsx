'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, CheckCircle2, Clock3, MapPin } from 'lucide-react'
import { Button } from '@/extensions/route66/adapters/ui'
import { nativeCoursePath, type AcademicClassLink, type RegistrarClassContext } from './model'
import { SectionConnection } from '../ClassConnections'
import OfficialRoster from './OfficialRoster'
import ClassSchedule from '../calendar/ClassSchedule'
import { weekdayKey } from '../../Account/subpages/timetable-colors'
import colors from '../../Account/subpages/timetable-colors.module.css'
import styles from './workspace.module.css'
import { SegmentedControl } from '@/extensions/route66/components/interior/SegmentedControl'
import palette from '../class-colors.module.css'

type View = 'overview' | 'timetable' | 'roster'
export default function RealTeachingWorkspace({ context, linked, linksKnown, th, onClose, onOpenRoster, onChanged, onOpenCalendars, calendarRefresh }: {
  context: RegistrarClassContext; linked: AcademicClassLink | null; linksKnown: boolean; th: boolean
  onClose: () => void; onOpenRoster: () => void; onChanged?: () => void; onOpenCalendars?: () => void; calendarRefresh?: number
}) {
  const [view, setView] = useState<View>('overview'), [connecting, setConnecting] = useState(false), heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { window.scrollTo(0, 0); heading.current?.focus({ preventScroll: true }) }, [])
  const c = context.classRow
  const t = th ? {
    back: 'ชั้นเรียน NRRU ทั้งหมด', section: 'กลุ่มเรียน', tasks: 'ข้อมูลชั้นเรียน', overview: 'รายละเอียด', timetable: 'ตารางเรียน', roster: 'รายชื่อจากทะเบียน',
    code: 'รหัสวิชา', term: 'ภาคเรียน / ปีการศึกษา', teacher: 'ผู้สอน', school: 'NRRU', source: 'ข้อมูลจากทะเบียน NRRU', updated: 'ดึงข้อมูลเมื่อ',
    weekly: 'ตารางประจำสัปดาห์', noMeetings: 'ทะเบียนยังไม่ระบุวันและเวลาของกลุ่มเรียนนี้', scheduleHelp: 'วัน เวลา และห้องตามทะเบียน ไม่ใช่ปฏิทินวันเรียนหรือวันชดเชย',
    learning: 'ชั้นเรียน LearnHouse', matched: 'เชื่อมกับชั้นเรียน LearnHouse แล้ว', separate: 'ยังไม่เชื่อมกับ LearnHouse', separateHelp: 'ดูรายละเอียด ตารางเรียน และรายชื่อจากทะเบียนได้โดยไม่ต้องเชื่อมชั้นเรียน',
    connect: 'เชื่อมกับ LearnHouse', openRoster: 'จัดการสมาชิก LearnHouse', openSchedule: 'เปิดวันเรียนและเช็กชื่อ', openCourse: 'เปิดเนื้อหารายวิชา', loading: 'ยังตรวจสอบการเชื่อมกับ LearnHouse ไม่ได้', retry: 'ตรวจสอบอีกครั้ง',
  } : {
    back: 'All NRRU classes', section: 'Section', tasks: 'Class information', overview: 'Details', timetable: 'Schedule', roster: 'Official roster',
    code: 'Course code', term: 'Semester / academic year', teacher: 'Teacher', school: 'NRRU', source: 'NRRU registrar data', updated: 'Fetched',
    weekly: 'Weekly meeting times', noMeetings: 'The registrar has not listed meeting times for this section.', scheduleHelp: 'Registrar days, times and rooms—not a dated calendar or make-up schedule.',
    learning: 'LearnHouse class', matched: 'Matched to a LearnHouse class', separate: 'Not matched to LearnHouse', separateHelp: 'Official details, weekly meetings and students are available without connecting a learning workspace.',
    connect: 'Connect to LearnHouse', openRoster: 'Manage LearnHouse members', openSchedule: 'Open sessions and attendance', openCourse: 'Open course content', loading: 'The LearnHouse connection has not been checked yet.', retry: 'Check again',
  }
  return <section className={`${styles.workspace} ${palette.workspace}`} aria-labelledby="real-class-title">
    <Button variant="ghost" className="min-h-11" onClick={onClose}><ArrowLeft size={16} aria-hidden="true" />{t.back}</Button>
    <header className={styles.heading}><h1 id="real-class-title" ref={heading} tabIndex={-1}>{c.title}</h1><p>{c.course_code} · {context.semester}/{context.academic_year} · {t.section} {c.section}</p></header>
    <SegmentedControl className={styles.tasks} label={t.tasks} value={view} onValueChange={setView} options={(['overview', 'timetable', 'roster'] as const).map(key => ({ value: key, label: t[key] }))} />
    {view === 'overview' && <div className={styles.task} role="region" aria-label={t.overview}>
      <h2>{t.overview}</h2><dl className={styles.facts}>{[[t.code, c.course_code], [t.section, c.section], [t.term, `${context.semester}/${context.academic_year}`], ...(context.teacher_name ? [[t.teacher, context.teacher_name]] : [])].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <section className={styles.learningLink} aria-labelledby="learning-class-title"><h2 id="learning-class-title">{t.learning}</h2>
        {!linksKnown ? <><p role="status">{t.loading}</p><Button variant="outline" className="mt-3 min-h-11" onClick={onChanged}>{t.retry}</Button></> : linked ? <><p className={styles.matched}><CheckCircle2 size={16} aria-hidden="true" />{t.matched}</p><div className={styles.handoffs}><Button variant="outline" className="min-h-11" onClick={onOpenRoster}>{t.openRoster}</Button><Link className={styles.action} href={`/attendance?class=${linked.id}`}>{t.openSchedule}</Link>{linked.course_available && <Link className={styles.action} href={nativeCoursePath(linked.course_uuid)}>{t.openCourse}</Link>}</div></> : <><p>{t.separate}</p><p>{t.separateHelp}</p><details onToggle={e => setConnecting(e.currentTarget.open)}><summary>{t.connect}</summary>{connecting && <SectionConnection context={context} th={th} onChanged={onChanged ?? (() => {})} onOpenCalendars={onOpenCalendars} />}</details></>}
      </section>
    </div>}
    {view === 'timetable' && <div className={styles.task} role="region" aria-label={t.timetable}><ClassSchedule context={context} th={th} onOpenCalendars={onOpenCalendars} refreshKey={calendarRefresh} onSaved={onChanged}/><h2 className="mt-8">{t.weekly}</h2><p>{t.scheduleHelp}</p>
      {c.meetings.length === 0 ? <p>{t.noMeetings}</p> : <ul className={styles.meetings}>{c.meetings.map((m, i) => <li key={i}><div className={styles.when}><span className={colors.day} data-weekday={weekdayKey(m.day)}><Clock3 size={14} aria-hidden="true" />{m.day}</span><strong>{m.start_time}–{m.end_time}</strong></div>{m.details && <p className={styles.details}><MapPin size={16} aria-hidden="true" /><span>{m.details}</span></p>}</li>)}</ul>}
    </div>}
    {view === 'roster' && <OfficialRoster key={`${c.registry_course_id}/${context.academic_year}/${context.semester}/${c.section}`} context={context} th={th} />}
    {view !== 'roster' && <p className={styles.fetched}>{t.source} · {t.updated}: <time dateTime={context.fetched_at}>{new Date(context.fetched_at).toLocaleString(th ? 'th-TH' : 'en-GB')}</time></p>}
  </section>
}
