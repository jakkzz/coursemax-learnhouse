'use client'

import { useEffect, useId, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Button, Input } from '@/extensions/route66/adapters/ui'
import type { RegistrarClassContext } from './model'
import styles from './workspace.module.css'
import interior from '@/extensions/route66/components/interior/material.module.css'

type Student = { student_number: string; full_name_th: string; faculty: string; program: string; registry_status_code: string | null; display_position: number }
type OfficialRosterData = { students: Student[]; fetched_at: string; source_url: string }
export default function OfficialRoster({ context, th }: { context: RegistrarClassContext; th: boolean }) {
  const [data, setData] = useState<OfficialRosterData | null>(null), [busy, setBusy] = useState(true), [error, setError] = useState(''), [attempt, setAttempt] = useState(0), [query, setQuery] = useState('')
  const searchId = useId()
  const { academic_year, semester, classRow: { registry_course_id, section } } = context
  useEffect(() => {
    const controller = new AbortController(); let active = true
    setBusy(true); setError('')
    const timeout = setTimeout(() => controller.abort(), 22000)
    const params = new URLSearchParams({ registry_course_id, academic_year: String(academic_year), semester: String(semester), section })
    fetch('/api/v1/academic-classes/connections/official-roster?' + params, { credentials: 'include', cache: 'no-store', signal: controller.signal })
      .then(async r => { if (!r.ok) throw new Error(r.status === 403 || r.status === 401 ? 'identity' : 'source'); const value = await r.json(); if (active) setData(value) })
      .catch(e => { if (active) { setError(e.message === 'identity' ? 'identity' : 'source'); if (e.message === 'identity') setData(null) } })
      .finally(() => { clearTimeout(timeout); if (active) setBusy(false) })
    return () => { active = false; clearTimeout(timeout); controller.abort() }
  }, [registry_course_id, academic_year, semester, section, attempt])
  const t = th ? {
    title: 'รายชื่อจากทะเบียน', help: 'รายชื่อของกลุ่มเรียนนี้จาก NRRU แยกจากสมาชิกและการจับคู่บัญชีใน LearnHouse', refresh: 'อัปเดตรายชื่อจากทะเบียน', loading: 'กำลังดึงรายชื่อจากทะเบียน…',
    failed: 'ดึงรายชื่อจากทะเบียนไม่ได้ ลองอัปเดตอีกครั้ง รายชื่อที่เปิดไว้ยังคงอยู่', identity: 'โปรดตรวจสอบข้อมูลสถานศึกษาและเข้าสู่ระบบด้วย Google ของมหาวิทยาลัยอีกครั้ง',
    search: 'ค้นหาชื่อ รหัสนักศึกษา หรือสาขาวิชา', number: 'รหัสนักศึกษา', name: 'ชื่อจากทะเบียน', program: 'คณะ / สาขาวิชา', status: 'รหัสสถานภาพจากทะเบียน', count: 'คน', empty: 'ไม่พบรายชื่อที่ตรงกับคำค้น', source: 'แหล่งข้อมูลทะเบียน', updated: 'ดึงข้อมูลเมื่อ',
  } : {
    title: 'Official roster', help: 'Students registered for this NRRU section, separate from LearnHouse membership and account matching.', refresh: 'Refresh official roster', loading: 'Loading official roster…',
    failed: 'The registrar roster could not be retrieved. Try refreshing; any loaded students remain visible.', identity: 'Review your school identity and sign in again with your university Google account.',
    search: 'Search name, student number or program', number: 'Student number', name: 'Registrar name', program: 'Faculty / program', status: 'Registrar status code', count: 'students', empty: 'No students match your search', source: 'Registrar source', updated: 'Fetched',
  }
  const people = data?.students.filter(p => `${p.student_number} ${p.full_name_th} ${p.faculty ?? ''} ${p.program ?? ''}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())) ?? []
  return <section className={styles.task} aria-labelledby="official-roster-title" aria-busy={busy}>
    <header className={styles.rosterHeading}><div><h2 id="official-roster-title">{t.title}</h2><p>{t.help}</p></div><Button size="icon" variant="outline" className="min-h-11 min-w-11" aria-label={t.refresh} title={t.refresh} disabled={busy} onClick={() => setAttempt(n => n + 1)}><RefreshCw size={18} aria-hidden="true" /></Button></header>
    {busy && <p role="status">{t.loading}</p>}
    {error && <div role="alert" className={styles.rosterError}><p>{error === 'identity' ? t.identity : t.failed}</p>{error === 'identity' && <a href="/account/school-identity" className={styles.action}>{th ? 'ตรวจสอบข้อมูลสถานศึกษา' : 'Review school identity'}</a>}</div>}
    {data && <><div className={`${styles.rosterSearch} ${interior.well}`}><label htmlFor={searchId}>{t.search}</label><Input id={searchId} className="min-h-11" value={query} onChange={e => setQuery(e.target.value)} /><p role="status">{people.length} / {data.students.length} {t.count}</p></div>
      <div className={styles.officialStudents}>{people.length === 0 ? <p>{t.empty}</p> : people.map(p => <article key={p.student_number} className={styles.officialStudent}><div><p className={styles.studentNumber}>{p.student_number}</p><h3>{p.full_name_th}</h3></div><p className={styles.studentProgram}>{p.faculty} {p.program}</p>{p.registry_status_code && <p className={styles.studentStatus}>{t.status}: {p.registry_status_code}</p>}</article>)}</div>
      <p className={styles.fetched}>{t.updated}: <time dateTime={data.fetched_at}>{new Date(data.fetched_at).toLocaleString(th ? 'th-TH' : 'en-GB')}</time> · <a href={data.source_url} target="_blank" rel="noopener noreferrer">{t.source}</a></p>
    </>}
  </section>
}
