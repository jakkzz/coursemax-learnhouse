'use client'

import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, CalendarClock, Clock3, Loader2, MapPin, Search } from 'lucide-react'
import { Button, Input } from '@/extensions/route66/adapters/ui'
import { filterTimetable, readSavedTerm, timetableYears, type RegistrarTerm } from './school-workspace-model'
import { weekdayKey } from './timetable-colors'
import colors from './timetable-colors.module.css'

import { linkedTeachingClass, type AcademicClassLink, type RegistrarTimetable as Timetable, type RegistrarClassContext } from '../../Classes/real-teaching/model'
import school from '../../Classes/school-classes.module.css'

export default function SchoolTimetable({ staffId, teacherName, onOpenClass, schoolMode = false, linkedClasses = [], linksKnown = true }: { staffId: string; teacherName?: string; onOpenClass?: (context: RegistrarClassContext) => void; schoolMode?: boolean; linkedClasses?: AcademicClassLink[]; linksKnown?: boolean }) {
  const { i18n } = useTranslation(), th = i18n.language.startsWith('th')
  const yearId = useId(), semesterId = useId(), searchId = useId(), workspaceId = useId()
  const t = th ? {
    title: 'ตารางสอนจากทะเบียน', note: 'ตารางสอนจากทะเบียนมหาวิทยาลัย แยกจากชั้นเรียนในระบบ การแสดงข้อมูลนี้ไม่มอบหมายรายวิชาและไม่เพิ่มสมาชิกโดยอัตโนมัติ',
    year: 'ปีการศึกษา (พ.ศ.)', term: 'ภาคเรียน', loading: 'กำลังดึงตารางสอน…', error: 'ดึงตารางสอนไม่ได้ โปรดลองอีกครั้ง', retry: 'ลองอีกครั้ง',
    empty: 'ทะเบียนไม่แสดงชั้นเรียนในภาคเรียนนี้', emptyHelp: 'ลองเลือกภาคเรียนหรือปีการศึกษาอื่น ข้อมูลนี้ไม่ได้หมายความว่าคุณไม่มีรายวิชาที่ได้รับมอบหมายในระบบ',
    asof: 'ดึงข้อมูลเมื่อ', section: 'กลุ่มเรียน', readonly: 'ข้อมูลทะเบียน · อ่านอย่างเดียว', teacher: 'ตารางสอนของ',
    search: 'ค้นหาวิชา กลุ่มเรียน วัน หรือห้อง', noMatch: 'ไม่พบชั้นเรียนที่ตรงกับคำค้น', clear: 'ล้างคำค้น', results: 'กลุ่มเรียน', openClass: 'เปิดพื้นที่ชั้นเรียน',
  } : {
    title: 'Registrar timetable', note: 'Your university timetable, separate from LearnHouse classes. These entries do not assign courses or enroll students automatically.',
    year: 'Academic year (Buddhist Era)', term: 'Semester', loading: 'Loading registrar timetable…', error: 'The registrar timetable could not be loaded. Try again.', retry: 'Try again',
    empty: 'No registrar classes for this semester', emptyHelp: 'Try another semester or academic year. This does not describe your LearnHouse teaching assignments.',
    asof: 'Fetched', section: 'Section', readonly: 'Registrar data · Read-only', teacher: 'Timetable for',
    search: 'Search course, section, day or room', noMatch: 'No classes match your search', clear: 'Clear search', results: 'sections', openClass: 'Open class workspace',
  }
  const [data, setData] = useState<Timetable | null>(null), [selection, setSelection] = useState<RegistrarTerm | null>(null)
  const [ready, setReady] = useState(false), [error, setError] = useState(false), [busy, setBusy] = useState(true), [attempt, setAttempt] = useState(0), [query, setQuery] = useState('')
  const currentYear = new Date().getFullYear() + 543, storageKey = `lh:registrar-term:${staffId}`
  useEffect(() => {
    try { setSelection(readSavedTerm(sessionStorage.getItem(storageKey), currentYear)) } catch { setSelection(null) }
    setReady(true)
  }, [storageKey, currentYear])
  useEffect(() => {
    if (!ready) return
    const controller = new AbortController()
    let active = true
    setBusy(true); setError(false); setData(null)
    const timeout = setTimeout(() => { if (active) { setError(true); setBusy(false) }; controller.abort() }, 12000)
    const params = selection ? `?academic_year=${selection.year}&semester=${selection.semester}` : ''
    fetch('/api/v1/school-identity/timetable' + params, { credentials: 'include', cache: 'no-store', signal: controller.signal })
      .then(async r => { if (!r.ok) throw Error(); const value = await r.json(); if (active) setData(value) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { clearTimeout(timeout); if (active) setBusy(false) })
    return () => { active = false; clearTimeout(timeout); controller.abort() }
  }, [staffId, selection, attempt, ready])
  const chosenYear = selection?.year ?? data?.academic_year ?? currentYear, chosenSemester = selection?.semester ?? data?.semester ?? 1
  const visible = filterTimetable(data?.classes ?? [], query)
  const control = 'min-h-11 w-full rounded-lg border border-blue-500 bg-white px-3 text-sm text-blue-950 hover:border-blue-700 disabled:opacity-50'
  function chooseTerm(next: RegistrarTerm) {
    setSelection(next); setQuery('')
    try { sessionStorage.setItem(storageKey, JSON.stringify(next)) } catch { /* Storage is optional, never an access requirement. */ }
  }
  return <section className={schoolMode ? school.index : 'overflow-hidden rounded-xl border border-blue-100 bg-white nice-shadow'} aria-labelledby="registrar-title" aria-busy={busy}>
    {!schoolMode && <p className="flex items-center gap-2 bg-blue-100 px-4 py-2.5 text-xs font-semibold text-blue-900"><CalendarClock size={14} aria-hidden="true" />{t.readonly}</p>}
    <div className={schoolMode ? school.indexContent : 'space-y-5 p-4 sm:p-6'}>
      <header className={schoolMode ? school.indexHeading : `${colors.header} -mx-4 -mt-4 px-4 pb-5 pt-4 sm:-mx-6 sm:-mt-6 sm:px-6 sm:pt-6`}><h2 id="registrar-title" className="text-xl font-semibold tracking-tight text-blue-950">{schoolMode ? (th ? 'ชั้นเรียน NRRU' : 'NRRU classes') : t.title}</h2>
        {teacherName && <p className="mt-2 break-words text-sm text-blue-800">{t.teacher} <strong className="font-medium text-blue-950">{teacherName}</strong></p>}
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-blue-800">{schoolMode ? (th ? 'ชั้นเรียนของคุณจากทะเบียน เลือกกลุ่มเรียนเพื่อดูรายละเอียด ตารางเรียน และรายชื่อ' : 'Your registrar classes. Open a section for details, weekly meetings and official students.') : t.note}</p>
      </header>
      <div className="grid grid-cols-2 gap-3 sm:flex sm:flex-wrap sm:items-end sm:gap-4">
        <div className="flex min-w-0 flex-col gap-2 text-xs font-medium text-neutral-700"><label htmlFor={yearId}>{t.year}</label>
          <select id={yearId} className={`${control} tabular-nums`} value={chosenYear} disabled={!data && !selection} onChange={e => chooseTerm({ year: Number(e.target.value), semester: chosenSemester })}>
            {timetableYears(currentYear, chosenYear).map(year => <option key={year} value={year}>{year}</option>)}
          </select>
        </div>
        <div className="flex min-w-0 flex-col gap-2 text-xs font-medium text-neutral-700"><label htmlFor={semesterId}>{t.term}</label>
          <select id={semesterId} className={`${control} tabular-nums`} value={chosenSemester} disabled={!data && !selection} onChange={e => chooseTerm({ year: chosenYear, semester: Number(e.target.value) })}>
            {[1, 2, 3].map(term => <option key={term} value={term}>{term}</option>)}
          </select>
        </div>
      </div>
      {busy && <p role="status" className="flex items-center gap-2 text-sm text-neutral-600"><Loader2 size={16} className="animate-spin" aria-hidden="true" />{t.loading}</p>}
      {error && <div role="alert" className="space-y-3"><p className="flex items-start gap-2 text-sm font-medium text-red-700"><AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />{t.error}</p><Button variant="outline" className="min-h-11" onClick={() => setAttempt(n => n + 1)}>{t.retry}</Button></div>}
      {data && <>
        {data.classes.length > 0 && <div className="space-y-2"><label htmlFor={searchId} className="flex items-center gap-2 text-sm font-medium text-blue-900"><Search size={16} aria-hidden="true" />{t.search}</label><Input id={searchId} className="min-h-11 border-blue-500 text-blue-950 hover:border-blue-700" value={query} onChange={e => setQuery(e.target.value)} /></div>}
        <p role="status" className="inline-flex rounded-md bg-blue-50 px-2 py-1 text-xs font-medium tabular-nums text-blue-800">{data.semester}/{data.academic_year} · {visible.length} {t.results}</p>
        {data.classes.length === 0 ? <div className="space-y-2 border-t border-neutral-200 py-5"><h3 className="font-semibold">{t.empty}</h3><p className="max-w-prose text-sm leading-relaxed text-neutral-600">{t.emptyHelp}</p></div>
          : visible.length === 0 ? <div className="space-y-2 border-t border-neutral-200 py-5"><h3 className="font-semibold">{t.noMatch}</h3><Button variant="outline" className="min-h-11" onClick={() => setQuery('')}>{t.clear}</Button></div>
          : <ul className={schoolMode ? school.indexRows : '-mx-4 divide-y divide-neutral-200 border-y border-neutral-200 sm:-mx-6'}>{visible.map(c => <li key={`${c.registry_course_id}-${c.section}`} className={schoolMode ? school.indexRow : 'space-y-3 px-4 py-5 sm:px-6'}>
            <div>{schoolMode ? <><h3 className="break-words text-base font-semibold text-blue-950">{c.title}</h3><p className={school.identifiers}>{c.course_code} · {t.section} {c.section}</p><p className={school.match} data-matched={Boolean(linkedTeachingClass({ classRow: c, academic_year: data.academic_year, semester: data.semester, fetched_at: data.fetched_at }, linkedClasses))}>{!linksKnown ? (th ? 'ยังไม่ตรวจสอบการเชื่อม' : 'Match not checked') : linkedTeachingClass({ classRow: c, academic_year: data.academic_year, semester: data.semester, fetched_at: data.fetched_at }, linkedClasses) ? (th ? 'เชื่อมกับ LearnHouse แล้ว' : 'Matched to LearnHouse') : (th ? 'ชั้นเรียนจากทะเบียน' : 'School class')}</p></> : <><p className="inline-flex rounded-md bg-blue-50 px-2 py-1 text-xs font-semibold tabular-nums text-blue-900">{c.course_code} · {t.section} {c.section}</p><h3 className="mt-2 break-words text-base font-semibold text-blue-950">{c.title}</h3></>}</div>
            <ul className={schoolMode ? school.indexMeetings : 'space-y-3'}>{c.meetings.map((m, index) => <li key={index} className="space-y-1.5 text-sm"><p className="flex flex-wrap items-center gap-x-2 gap-y-1 font-medium tabular-nums text-blue-950"><span className={colors.day} data-weekday={weekdayKey(m.day)}><Clock3 size={14} className="shrink-0" aria-hidden="true" /><span className="min-w-0 break-words">{m.day}</span></span><span aria-hidden="true">{' · '}</span><span>{m.start_time}–{m.end_time}</span></p>{m.details && <p className="flex items-start gap-2 leading-relaxed text-neutral-600"><MapPin size={16} className="mt-0.5 shrink-0 text-blue-700" aria-hidden="true" /><span className="min-w-0 break-words">{m.details}</span></p>}</li>)}</ul>
            {onOpenClass && <Button id={`${workspaceId}-${c.registry_course_id}-${encodeURIComponent(c.section)}`} variant="outline" className="min-h-11" aria-label={`${t.openClass}: ${c.course_code} ${c.section}`} onClick={() => onOpenClass({ classRow: c, academic_year: data.academic_year, semester: data.semester, fetched_at: data.fetched_at, teacher_name: teacherName, returnFocusId: `${workspaceId}-${c.registry_course_id}-${encodeURIComponent(c.section)}` })}>{t.openClass}</Button>}
          </li>)}</ul>}
        <p className="text-xs tabular-nums text-neutral-600">{t.asof}: <time dateTime={data.fetched_at}>{new Date(data.fetched_at).toLocaleString(th ? 'th-TH' : 'en-GB')}</time></p>
      </>}
    </div>
  </section>
}
