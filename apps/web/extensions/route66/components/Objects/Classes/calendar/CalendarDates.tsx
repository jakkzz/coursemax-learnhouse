'use client'

import { useState } from 'react'
import { formatCalendarDate, type AcademicDate } from './model'
import styles from './calendar.module.css'
import { SegmentedControl } from '@/extensions/route66/components/interior/SegmentedControl'

export default function CalendarDates({ events, th, onChange }: { events: AcademicDate[]; th: boolean; onChange?: (events: AcademicDate[]) => void }) {
  const [program, setProgram] = useState(''), [selected, setSelected] = useState(0), [view, setView] = useState<'key' | 'other'>('key')
  const t = (en: string, thai: string) => th ? thai : en
  const programs = [...new Set(events.map(event => event.program))]
  const scoped = events.map((event, index) => ({ event, index })).filter(({ event }) => !program || event.program === program)
  const keyCount = scoped.filter(({ event }) => event.kind !== 'other').length, otherCount = scoped.length - keyCount
  const active = keyCount && (view === 'key' || !otherCount) ? 'key' : 'other'
  const visible = scoped.filter(({ event }) => active === 'key' ? event.kind !== 'other' : event.kind === 'other')
  const current = visible.find(row => row.index === selected) ?? visible[0]
  const range = (event: AcademicDate) => event.starts_on === event.ends_on ? formatCalendarDate(event.starts_on, th) : `${formatCalendarDate(event.starts_on, th)} – ${formatCalendarDate(event.ends_on, th)}`
  const change = (field: 'starts_on' | 'ends_on', value: string) => {
    if (onChange && current) onChange(events.map((event, index) => index === current.index ? { ...event, [field]: value, ...(field === 'starts_on' && event.starts_on === event.ends_on ? { ends_on: value } : {}) } : event))
  }
  return <section aria-label={t('Academic dates', 'กำหนดการศึกษา')}>
    <div className={styles.toolbar}><label>{t('Program dates', 'กำหนดการตามรูปแบบการศึกษา')}<select aria-label={t('Program dates', 'กำหนดการตามรูปแบบการศึกษา')} value={program} onChange={e => { setProgram(e.target.value); setSelected(0) }}><option value="">{t('All programs', 'ทุกรูปแบบการศึกษา')}</option>{programs.map(name => <option key={name}>{name}</option>)}</select></label></div>
    {keyCount > 0 && otherCount > 0 && <SegmentedControl className={styles.tabs} label={t('Academic date groups', 'กลุ่มกำหนดการศึกษา')} value={active} onValueChange={value => { setView(value); setSelected(0) }} options={[{ value: 'key', label: `${t('Key dates', 'กำหนดการหลัก')} (${keyCount})` }, { value: 'other', label: `${t('Registration & other dates', 'ลงทะเบียนและกำหนดการอื่น')} (${otherCount})` }]} />}
    {onChange ? <>{current && <><label className="flex flex-col gap-2 my-4">{t('Academic date to edit', 'เลือกกำหนดการที่จะแก้ไข')}<select aria-label={t('Academic date to edit', 'เลือกกำหนดการที่จะแก้ไข')} value={current.index} onChange={e => setSelected(Number(e.target.value))}>{visible.map(({ event, index }) => <option key={index} value={index}>{event.program} · {event.title} · {range(event)}</option>)}</select></label><div className={styles.fields}><label>{t('Starts', 'เริ่ม')}<input type="date" value={current.event.starts_on} onChange={e => change('starts_on', e.target.value)} /></label><label>{t('Ends', 'สิ้นสุด')}<input type="date" value={current.event.ends_on} onChange={e => change('ends_on', e.target.value)} /></label></div><p className={`${styles.muted} mt-3`}>{current.event.program} · {current.event.title}{current.event.page ? ` · ${t('Source page', 'หน้าเอกสาร')} ${current.event.page}` : ''}</p></>}</> : programs.filter(name => visible.some(({ event }) => event.program === name)).map(name => <section key={name} className="mt-6"><h2 className={styles.sectionTitle}>{name}</h2><ul className={styles.previewList}>{visible.filter(({ event }) => event.program === name).map(({ event }, i) => <li key={i} className={styles.previewClosure}><div><strong>{range(event)}</strong><p className={styles.muted}>{t('Semester', 'ภาคเรียนที่')} {event.semester}{event.page ? ` · ${t('Page', 'หน้า')} ${event.page}` : ''}</p></div><div><p>{event.title}</p>{event.uncertain && <small className={styles.muted}>{t('Proposed from source', 'ข้อมูลที่เสนอจากเอกสาร')}</small>}{event.note && <p className={styles.muted}>{event.note}</p>}</div></li>)}</ul></section>)}
  </section>
}
