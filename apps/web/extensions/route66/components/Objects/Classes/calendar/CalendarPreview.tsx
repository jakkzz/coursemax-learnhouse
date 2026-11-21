'use client'

import { useState } from 'react'
import { formatCalendarDate, type CalendarPayload, type Rotation } from './model'
import CalendarDates from './CalendarDates'
import styles from './calendar.module.css'
import { SegmentedControl } from '@/extensions/route66/components/interior/SegmentedControl'

export default function CalendarPreview({ payload, th }: { payload: CalendarPayload; th: boolean }) {
  const [semester, setSemester] = useState(0), [view, setView] = useState<'weeks' | 'closures'>('weeks')
  const t = (en: string, thai: string) => th ? thai : en
  const term = payload.terms[semester] ?? payload.terms[0]
  const day = (value: string) => formatCalendarDate(value, th)
  const rotation = (value: Rotation) => ({ odd: t('Odd', 'คี่'), even: t('Even', 'คู่'), teaching: t('Teaching', 'เรียนปกติ'), midterm: t('Midterm', 'กลางภาค'), final: t('Final', 'ปลายภาค') })[value]
  if (!term) return payload.events?.length ? <section aria-label={t('Calendar preview', 'ตัวอย่างปฏิทิน')}><CalendarDates events={payload.events} th={th} /></section> : null
  return <section aria-label={t('Calendar preview', 'ตัวอย่างปฏิทิน')}>
    {Boolean(payload.events?.length) && <CalendarDates events={payload.events!} th={th} />}
    {payload.terms.length > 1 && <label className={styles.toolbar}>{t('Semester', 'ภาคเรียน')}<select value={semester} onChange={e => setSemester(Number(e.target.value))}>{payload.terms.map((item, i) => <option key={i} value={i}>{item.semester}</option>)}</select></label>}
    <h2 className={styles.sectionTitle}>{t('Semester', 'ภาคเรียนที่')} {term.semester}</h2>
    <p className={styles.muted}>{day(term.starts_on)} – {day(term.ends_on)}</p>
    <SegmentedControl className={styles.tabs} label={t('Preview sections', 'ส่วนของตัวอย่างปฏิทิน')} value={view} onValueChange={setView} options={[{ value: 'weeks', label: `${t('Teaching weeks', 'สัปดาห์เรียน')} (${term.weeks.length})` }, { value: 'closures', label: `${t('Holidays & make-ups', 'วันหยุดและวันชดเชย')} (${term.closures.length})` }]} />
    {view === 'weeks' ? <ol className={styles.previewList}>{term.weeks.map((week, i) => <li key={i} className={styles.previewWeek}>
      <strong>{t('Week', 'สัปดาห์')} {week.number}</strong>
      <div><p>{week.teaching_dates?.length ? week.teaching_dates.map(day).join(' · ') : `${day(week.starts_on)} – ${day(week.ends_on)}`}</p>{week.uncertain && <small className={styles.muted}>{t('Proposed from source', 'ข้อมูลที่เสนอจากเอกสาร')}</small>}</div>
      <div><p>{rotation(week.rotation)}</p>{!week.teaching ? <small>{t('No regular classes', 'งดเรียนตามตารางปกติ')}</small> : (week.rotation === 'midterm' || week.rotation === 'final') && <small>{t('Regular classes kept', 'คงการเรียนตามตาราง')}</small>}</div>
    </li>)}</ol> : <ul className={styles.previewList}>{term.closures.length === 0 && <li className={styles.empty}>{t('No holidays or closures in this calendar.', 'ปฏิทินนี้ไม่มีวันหยุดหรือวันงดเรียน')}</li>}{term.closures.map((closure, i) => <li key={i} className={styles.previewClosure}>
      <div><strong>{day(closure.affected_on)}</strong><p className={styles.muted}>{closure.makeup_on ? `${t('Make-up', 'ชดเชย')} ${day(closure.makeup_on)}` : t('No make-up stated', 'ไม่ระบุวันชดเชย')}</p></div><p>{closure.note}</p>
    </li>)}</ul>}
  </section>
}
