'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Clock3, MapPin } from 'lucide-react'
import { Button } from '@/extensions/route66/adapters/ui'
import { nativeCoursePath, type AcademicClassLink, type RegistrarClassContext } from './model'
import { SectionConnection } from '../ClassConnections'
import { weekdayKey } from '../../Account/subpages/timetable-colors'
import colors from '../../Account/subpages/timetable-colors.module.css'
import styles from './workspace.module.css'

type View = 'overview' | 'timetable' | 'roster'
export default function RealTeachingWorkspace({ context, linked, linksKnown, th, onClose, onOpenRoster, onChanged }: {
  context: RegistrarClassContext; linked: AcademicClassLink | null; linksKnown: boolean; th: boolean
  onClose: () => void; onOpenRoster: () => void; onChanged?: () => void
}) {
  const [view, setView] = useState<View>('overview'), heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { window.scrollTo(0, 0); heading.current?.focus({ preventScroll: true }) }, [])
  const c = context.classRow
  const t = th ? {
    back: 'กลับสู่ชั้นเรียนของฉัน', section: 'กลุ่มเรียน', tasks: 'งานของชั้นเรียน',
    overview: 'ภาพรวม', timetable: 'ตารางสอน', roster: 'รายชื่อ',
    ready: 'ชั้นเรียนพร้อมใช้งาน', openRoster: 'เปิดรายชื่อชั้นเรียน',
    weekly: 'วันและเวลาตามทะเบียน', noMeetings: 'ทะเบียนยังไม่ระบุวันและเวลาของกลุ่มเรียนนี้',
    source: 'ตารางสอนจากทะเบียน', updated: 'อัปเดต', recurring: 'ตารางประจำสัปดาห์',
    openSchedule: 'เปิดวันเรียนและเช็กชื่อ', openCourse: 'เปิดรายวิชา', loading: 'กำลังตรวจสอบชั้นเรียน…',
  } : {
    back: 'Back to My classes', section: 'Section', tasks: 'Class tasks',
    overview: 'Overview', timetable: 'Timetable', roster: 'Roster',
    ready: 'Your class is ready', openRoster: 'Open class roster',
    weekly: 'Registrar meeting times', noMeetings: 'The registrar has not listed meeting times for this section.',
    source: 'Registrar timetable', updated: 'Updated', recurring: 'Weekly schedule',
    openSchedule: 'Open sessions and attendance', openCourse: 'Open course', loading: 'Checking class…',
  }
  const setup = <SectionConnection context={context} th={th} onChanged={onChanged ?? (() => {})} />
  return <section className={styles.workspace} aria-labelledby="real-class-title">
    <Button variant="ghost" className="min-h-11" onClick={onClose}><ArrowLeft size={16} aria-hidden="true" />{t.back}</Button>
    <header className={styles.heading}><h1 id="real-class-title" ref={heading} tabIndex={-1}>{c.title}</h1><p>{c.course_code} · {context.semester}/{context.academic_year} · {t.section} {c.section}</p></header>
    <nav className={styles.tasks} aria-label={t.tasks}>{(['overview', 'timetable', 'roster'] as const).map(key => <button type="button" key={key} aria-current={view === key ? 'page' : undefined} onClick={() => setView(key)}>{t[key]}</button>)}</nav>
    {view === 'overview' && <div className={styles.task} role="region" aria-label={t.overview}>
      {linked ? <><h2>{t.ready}</h2><div className="mt-4 flex flex-wrap items-center gap-3"><Button className="min-h-11" onClick={onOpenRoster}>{t.openRoster}</Button><Link className={styles.action} href={`/attendance?class=${linked.id}`}>{t.openSchedule}</Link>{linked.course_available && <Link className={styles.action} href={nativeCoursePath(linked.course_uuid)}>{t.openCourse}</Link>}</div></> : setup}
      {!linksKnown && <p role="status">{t.loading}</p>}
    </div>}
    {view === 'timetable' && <div className={styles.task} role="region" aria-label={t.timetable}><h2>{t.weekly}</h2><p>{t.recurring}</p>
      {c.meetings.length === 0 ? <p>{t.noMeetings}</p> : <ul className={styles.meetings}>{c.meetings.map((m, i) => <li key={i}><div className={styles.when}><span className={colors.day} data-weekday={weekdayKey(m.day)}><Clock3 size={14} aria-hidden="true" />{m.day}</span><strong>{m.start_time}–{m.end_time}</strong></div>{m.details && <p className={styles.details}><MapPin size={16} aria-hidden="true" /><span>{m.details}</span></p>}</li>)}</ul>}
    </div>}
    {view === 'roster' && <div className={styles.task} role="region" aria-label={t.roster}>{linked ? <><h2>{t.roster}</h2><Button className="mt-4 min-h-11" onClick={onOpenRoster}>{t.openRoster}</Button></> : setup}</div>}
    <p className={styles.fetched}>{t.source} · {t.updated}: <time dateTime={context.fetched_at}>{new Date(context.fetched_at).toLocaleString(th ? 'th-TH' : 'en-GB')}</time></p>
  </section>
}
