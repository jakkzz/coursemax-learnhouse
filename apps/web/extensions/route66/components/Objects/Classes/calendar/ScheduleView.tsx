'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/extensions/route66/adapters/ui'
import { localDay, monthDays, moveMonth, type MeetingSession } from './model'
import styles from './calendar.module.css'
import interior from '@/extensions/route66/components/interior/material.module.css'

export default function ScheduleView({ sessions, th, timezone = 'Asia/Bangkok', preview = false }: { sessions: MeetingSession[]; th: boolean; timezone?: string; preview?: boolean }) {
  const t = (en: string, thai: string) => th ? thai : en
  const [view, setView] = useState<'table' | 'calendar'>('table'), [month, setMonth] = useState(''), [selected, setSelected] = useState('')
  const language = th ? 'th-TH' : 'en-GB'
  const date = (value: string) => new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeZone: timezone }).format(new Date(value))
  const time = (value: string) => new Intl.DateTimeFormat(language, { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: timezone }).format(new Date(value))
  const ordered = useMemo(() => sessions.filter(s => !s.superseded).sort((a, b) => a.starts_at.localeCompare(b.starts_at)), [sessions]), history = sessions.filter(s => s.superseded)
  useEffect(() => {
    if (month) return
    const next = ordered.find(s => s.state === 'scheduled' && new Date(s.ends_at).getTime() >= Date.now()) ?? ordered[0]
    const day = next ? localDay(next.starts_at, timezone) : localDay(new Date().toISOString(), timezone)
    setMonth(day.slice(0, 7)); setSelected(day)
  }, [ordered, month, timezone])
  const byDay = useMemo(() => { const map = new Map<string, MeetingSession[]>(); for (const s of ordered) { const day = localDay(s.starts_at, timezone); map.set(day, [...(map.get(day) ?? []), s]) } return map }, [ordered, timezone])
  const grid = month ? monthDays(month) : { offset: 0, days: [] }
  function records(rows: MeetingSession[]) { return <div className={styles.records}>
    <div className={styles.rowHead} aria-hidden="true"><span>{t('Date / time', 'วัน / เวลา')}</span><span>{t('Teaching week', 'สัปดาห์เรียน')}</span><span>{t('Meeting', 'การเรียน')}</span><span>{t('Attendance', 'เช็กชื่อ')}</span></div>
    {rows.map((s, i) => <article className={styles.row} data-state={s.state} key={s.id ?? `${s.slot_key}-${s.starts_at}-${i}`}>
      <div><p className="font-semibold"><time dateTime={s.starts_at}>{date(s.starts_at)}</time></p><p className={styles.time}>{time(s.starts_at)}–{time(s.ends_at)}</p></div>
      <div><p>{s.week_number ? `${t('Week', 'สัปดาห์')} ${s.week_number}` : t('Additional meeting', 'การเรียนนอกตาราง')}</p><p className={styles.muted}>{({ odd: t('Odd', 'คี่'), even: t('Even', 'คู่'), midterm: t('Midterm', 'กลางภาค'), final: t('Final', 'ปลายภาค'), teaching: '' })[s.rotation ?? 'teaching']}</p></div>
      <div><p className="font-semibold">{s.title}</p>{s.action && <p className={styles.muted}>{({ protected: t('Kept unchanged', 'คงวันเรียนเดิมไว้'), cancelled: t('Will be marked no class', 'จะบันทึกเป็นวันงดเรียน'), replaced: t('Replaces an earlier schedule', 'ปรับเปลี่ยนจากตารางเดิม'), added: t('New meeting', 'เพิ่มวันเรียนใหม่'), unchanged: t('No change', 'ไม่เปลี่ยนแปลง') } as Record<string, string>)[s.action]}</p>}<span className={styles.badge}>{s.state === 'no_class' ? t('No class', 'งดเรียน') : s.makeup_for ? t('Make-up class', 'เรียนชดเชย') : t('Scheduled', 'มีการเรียน')}</span>{s.makeup_for && <p>{t('Replaces', 'ชดเชยวันที่')} {date(s.makeup_for + 'T00:00:00+07:00')}</p>}{s.state !== 'no_class' && <p className={styles.muted}>{s.mode === 'online' ? t('Online', 'ออนไลน์') : s.mode === 'onsite' ? t('On campus', 'ที่มหาวิทยาลัย') : t('Mode not specified by school', 'มหาวิทยาลัยยังไม่ระบุรูปแบบเรียน')}{s.location ? ` · ${s.location}` : ''}</p>}{s.note && <p className={styles.muted}>{s.note}</p>}</div>
      {!preview && s.attendance_url ? <Link href={s.attendance_url}>{t('Open attendance', 'เปิดเช็กชื่อ')}</Link> : <span className={styles.muted}>{preview ? t('Preview', 'ตรวจสอบก่อนบันทึก') : s.state === 'no_class' ? t('Not counted', 'ไม่นับการเข้าเรียน') : ''}</span>}
    </article>)}
  </div> }
  return <div className={styles.workspace}>
    <nav className={`${styles.tabs} ${interior.navigation}`} aria-label={t('Schedule view', 'มุมมองตารางเรียน')}><button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>{t('Table', 'ตาราง')}</button><button type="button" aria-pressed={view === 'calendar'} onClick={() => setView('calendar')}>{t('Calendar', 'ปฏิทิน')}</button></nav>
    {sessions.length === 0 ? <p className={styles.empty}>{t('No dated sessions yet. Select a school calendar and review the schedule to begin.', 'ยังไม่มีวันเรียน เลือกปฏิทินการศึกษาและตรวจสอบตารางเรียนเพื่อเริ่มต้น')}</p> : view === 'table' ? records(ordered) : <div className={styles.month}>
      <div className={styles.toolbar}><Button variant="outline" size="icon" className="min-h-11 min-w-11" aria-label={t('Previous month', 'เดือนก่อนหน้า')} onClick={() => { setMonth(m => moveMonth(m, -1)); setSelected('') }}><ChevronLeft size={18} aria-hidden="true" /></Button><label>{t('Month (Gregorian year)', 'เดือน (ค.ศ.)')}<input type="month" value={month} onChange={e => { if (/^\d{4}-\d{2}$/.test(e.target.value)) { setMonth(e.target.value); setSelected('') } }} /></label><Button variant="outline" size="icon" className="min-h-11 min-w-11" aria-label={t('Next month', 'เดือนถัดไป')} onClick={() => { setMonth(m => moveMonth(m, 1)); setSelected('') }}><ChevronRight size={18} aria-hidden="true" /></Button></div>
      <div className={styles.monthGrid} aria-label={t('Class calendar', 'ปฏิทินชั้นเรียน')}>
        {(th ? ['จ.', 'อ.', 'พ.', 'พฤ.', 'ศ.', 'ส.', 'อา.'] : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']).map(d => <div key={d} className={styles.weekday}>{d}</div>)}
        {Array.from({ length: grid.offset }, (_, i) => <span key={`blank-${i}`} className={styles.blank} aria-hidden="true" />)}
        {grid.days.map(day => { const rows = byDay.get(day) ?? [], cancelled = rows.filter(r => r.state === 'no_class').length; return <button type="button" className={styles.day} key={day} aria-pressed={selected === day} aria-label={`${date(day + 'T00:00:00+07:00')} · ${rows.length} ${t('meetings', 'รายการเรียน')}${cancelled ? ` · ${cancelled} ${t('no class', 'งดเรียน')}` : ''}`} data-meeting={rows.length > 0} onClick={() => setSelected(day)}><span>{Number(day.slice(-2))}</span>{rows.length > 0 && <small>{rows.length} {t('meetings', 'รายการ')}{cancelled ? ` · ${t('No class', 'งดเรียน')}` : ''}</small>}</button> })}
      </div>
      <section className={styles.agenda} aria-live="polite" aria-label={t('Selected day', 'วันที่เลือก')}><h3 className={styles.sectionTitle}>{selected ? date(selected + 'T00:00:00+07:00') : t('Choose a date', 'เลือกวันที่')}</h3>{selected && (byDay.get(selected)?.length ? records(byDay.get(selected)!) : <p className={styles.empty}>{t('No class meetings on this date.', 'ไม่มีการเรียนในวันนี้')}</p>)}</section>
    </div>}
    {history.length > 0 && <details className="mt-5"><summary className="min-h-11 cursor-pointer font-medium">{t('Earlier schedule versions', 'ประวัติวันเรียนที่ปรับเปลี่ยน')} ({history.length})</summary><p className={styles.muted}>{t('Retained for history, not counted as current meetings.', 'เก็บไว้เป็นประวัติ ไม่นับเป็นวันเรียนในตารางปัจจุบัน')}</p>{records(history)}</details>}
  </div>
}
