'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { toast } from 'react-hot-toast'
import { AlertCircle, CheckCircle2, Clock3, Link2 } from 'lucide-react'
import palette from './class-colors.module.css'
import { Button } from '@/extensions/route66/adapters/ui'
import type { RegistrarClassContext } from './real-teaching/model'
import { calendarRequest, type CalendarSummary, type Revision } from './calendar/model'
import CalendarPreview from './calendar/CalendarPreview'

const control = 'min-h-11 min-w-0 max-w-full rounded-lg border border-neutral-300 bg-white px-3 text-sm text-neutral-900'
export async function classRequest(path: string, th: boolean, body?: unknown, signal?: AbortSignal) {
  const r = await fetch('/api/v1/academic-classes' + path, { credentials: 'include', cache: 'no-store', signal,
    method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) })
  // An aborted successful response must not become an empty, apparently valid result.
  const data = r.ok ? await r.json() : await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(th ? r.status === 409 ? 'ข้อมูลเปลี่ยนแล้ว โปรดโหลดข้อมูลใหม่และตรวจสอบชั้นเรียนที่เลือก' : r.status === 401 || r.status === 403 ? 'โปรดตรวจสอบบัญชีและสิทธิ์จัดการรายวิชา แล้วลองอีกครั้ง' : r.status === 503 ? 'ระบบทะเบียนยังไม่พร้อม โปรดลองดึงข้อมูลของชั้นเรียนนี้อีกครั้ง' : 'ดำเนินการไม่ได้ โปรดตรวจสอบชั้นเรียนที่เลือกแล้วลองอีกครั้ง' : typeof data.detail === 'string' ? data.detail : r.status === 503 ? 'The registrar source is temporarily unavailable. Retry source retrieval.' : 'Could not complete this action. Check the selected class and retry.')
  return data
}
const requestId = () => crypto.randomUUID().replaceAll('-', '')

type CalendarAttachment = { revision_id: number; name: string; scope: 'organization' | 'teacher' }
type Connection = { calendar_attachments?: CalendarAttachment[]; id: number; teacher_name: string; registry_course_id: string; registry_class_id?: string; academic_year: number; semester: number; section: string; course_code: string; title: string; status: string }
export type ConnectionCourse = { id: number; name: string; private?: boolean }
type ConnectionPreview = { expected_fingerprint: string; course_name: string; restricts_org_wide_access: boolean; roster_count: number; source_kind?: string; source_url?: string; source_digest?: string; native_access?: string }

type SectionStatus = { request_id?: number | null; calendar_attachments?: CalendarAttachment[]; status: 'ready' | 'requested' | 'connected' | 'needs_course' | 'conflict'; class_id: number | null; can_request: boolean; courses: { id: number; name: string }[] }

function CalendarEvidence({ attachments, th }: { attachments?: CalendarAttachment[]; th: boolean }) {
  const [value, setValue] = useState<Revision | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState('')
  async function open(id: number) {
    setBusy(true); setError('')
    try { setValue(await calendarRequest<Revision>(`/revisions/${id}`, th)) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  if (!attachments?.length) return null
  return <div className="space-y-3"><p className="text-sm font-medium">{th ? 'ปฏิทินที่แนบแล้ว' : 'Attached calendars'}</p>{attachments.map(a => <div className="flex flex-wrap items-center gap-3 text-sm" key={a.revision_id}><span>{a.name} · {a.scope === 'teacher' ? th ? 'ส่วนตัว' : 'Private' : th ? 'ทั้งสถานศึกษา' : 'School-wide'}</span><Button type="button" variant="outline" className="min-h-11" disabled={busy} onClick={() => void open(a.revision_id)}>{th ? 'ตรวจสอบปฏิทินที่แนบ' : 'Review attached calendar'}</Button></div>)}{value && <div className="space-y-3"><CalendarPreview payload={value.payload} th={th} /><a className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href={`/api/v1/school-calendars/revisions/${value.id}/source`} target="_blank" rel="noopener noreferrer">{th ? 'เปิดไฟล์ต้นฉบับที่แนบ' : 'Open attached original PDF'}</a><Button type="button" variant="ghost" className="min-h-11" onClick={() => setValue(null)}>{th ? 'ปิดปฏิทิน' : 'Close calendar'}</Button></div>}{error && <p role="alert" className="text-sm text-red-800">{error}</p>}</div>
}

function ProposalCalendar({ requestId, year, attachments, th, onChanged, onOpenCalendars }: { requestId: number; year: number; attachments?: CalendarAttachment[]; th: boolean; onChanged: (attachments: CalendarAttachment[]) => void; onOpenCalendars?: () => void }) {
  const [catalog, setCatalog] = useState<CalendarSummary[]>([]), [revision, setRevision] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState(''), [attempt, setAttempt] = useState(0)
  useEffect(() => { const a = new AbortController(); setError(''); calendarRequest<{ calendars: CalendarSummary[] }>('', th, { signal: a.signal }).then(c => setCatalog(c.calendars.filter(r => r.academic_year === year && r.published_revision_id))).catch(e => { if (!a.signal.aborted) setError(e.message) }); return () => a.abort() }, [year, th, attempt])
  async function attach() { setBusy(true); setError(''); try { const result = await classRequest(`/connections/requests/${requestId}/calendar`, th, { revision_id: Number(revision) }); setRevision(''); onChanged(result.calendar_attachments) } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  return <details className="space-y-3 border-t border-neutral-200 pt-3"><summary className="min-h-11 cursor-pointer text-sm font-medium">{th ? 'ปฏิทินสำหรับคำขอนี้' : 'Calendar for this proposal'}</summary><p className="max-w-prose text-sm text-neutral-600">{th ? 'เลือกปฏิทินที่ยืนยันแล้ว หรือเตรียมไฟล์ส่วนตัวก่อน การแนบไม่อนุมัติรายวิชาและไม่สร้างตารางเรียน' : 'Choose an accepted calendar or prepare a private PDF first. Attaching does not approve the course or create a class schedule.'}</p><CalendarEvidence attachments={attachments} th={th}/><label className="flex flex-col gap-2 text-sm">{th ? 'ปฏิทินที่ต้องการแนบ' : 'Calendar to attach'}<select className={control} aria-label={th ? 'ปฏิทินที่ต้องการแนบ' : 'Calendar to attach'} value={revision} disabled={busy} onChange={e => setRevision(e.target.value)}><option value="">{th ? 'เลือกปฏิทินที่ยืนยันแล้ว' : 'Choose an accepted calendar'}</option>{catalog.filter(c => !attachments?.some(a => a.revision_id === c.published_revision_id)).map(c => <option key={c.id} value={c.published_revision_id!}>{c.name} · {c.scope === 'teacher' ? th ? 'ส่วนตัว' : 'Private' : th ? 'ทั้งสถานศึกษา' : 'School-wide'}</option>)}</select></label><div className="flex flex-wrap gap-3"><Button type="button" variant="outline" className="min-h-11" disabled={busy || !revision} onClick={() => void attach()}>{th ? 'แนบปฏิทินกับคำขอ' : 'Attach calendar to proposal'}</Button>{onOpenCalendars && <Button type="button" variant="ghost" className="min-h-11" disabled={busy} onClick={onOpenCalendars}>{th ? 'อัปโหลดหรือตรวจสอบปฏิทิน' : 'Upload or review a calendar'}</Button>}</div>{error && <div role="alert" className="text-sm text-red-800"><p>{error}</p><Button type="button" variant="outline" className="min-h-11" disabled={busy} onClick={() => setAttempt(n => n + 1)}>{th ? 'ลองอีกครั้ง' : 'Try again'}</Button></div>}</details>
}

export function SectionConnection({ context, th, onChanged, onOpenCalendars }: { context: RegistrarClassContext; th: boolean; onChanged: () => void; onOpenCalendars?: () => void }) {
  const [data, setData] = useState<SectionStatus | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [version, setVersion] = useState(0), [course, setCourse] = useState(''), changed = useRef(onChanged)
  changed.current = onChanged
  const { registry_course_id, section } = context.classRow, { academic_year, semester } = context
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined
    setData(null); setError(''); setCourse('')
    async function load() {
      try {
        const query = new URLSearchParams({ registry_course_id, academic_year: String(academic_year), semester: String(semester), section })
        const next: SectionStatus = await classRequest('/connections/section?' + query, th, undefined, controller.signal)
        if (controller.signal.aborted) return
        setData(next); setError(''); setCourse(previous => next.courses.some(c => String(c.id) === previous) ? previous : next.courses.length === 1 ? String(next.courses[0].id) : '')
        if (next.status === 'connected') changed.current()
        else if (next.status === 'requested') timer = setTimeout(() => void load(), 15000)
      } catch (e) { if (!controller.signal.aborted) setError((e as Error).message) }
    }
    void load()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [registry_course_id, academic_year, semester, section, th, version])
  async function submit() {
    if (!data) return
    setBusy(true); setError('')
    try {
      const direct = data.status === 'ready'
      const result = await classRequest(direct ? '/connections/setup' : '/connections/requests', th,
        { registry_course_id, academic_year, semester, section, ...(direct ? { course_id: Number(course) } : {}) })
      setData({ ...data, status: result.status })
      if (result.status === 'connected') changed.current()
      setVersion(v => v + 1)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  const heading = !data ? th ? 'กำลังโหลดชั้นเรียน…' : 'Loading class…' : data.status === 'ready' ? th ? 'พร้อมตั้งค่าชั้นเรียน' : 'Ready to set up this class' : data.status === 'requested' ? th ? 'รอเลือกรายวิชา' : 'Waiting for a course match' : data.status === 'connected' ? th ? 'ชั้นเรียนพร้อมใช้งานแล้ว' : 'Class is ready' : data.status === 'conflict' ? th ? 'ต้องตรวจสอบการเชื่อมรายวิชา' : 'Course connection needs review' : th ? 'ตั้งค่าชั้นเรียนนี้' : 'Set up this class'
  const StatusIcon = data?.status === 'connected' ? CheckCircle2 : data?.status === 'requested' ? Clock3 : data?.status === 'conflict' ? AlertCircle : Link2
  return <div className={`${palette.status} space-y-3`} data-state={data?.status ?? 'loading'} aria-busy={busy} aria-live="polite">
    <h3 className={`${palette.statusHeading} text-base font-semibold`}><StatusIcon size={18} aria-hidden="true" />{heading}</h3>
    {data?.status === 'ready' && <form className="max-w-xl space-y-3" onSubmit={e => { e.preventDefault(); void submit() }}>
      {data.courses.length > 1 ? <label className="flex flex-col gap-2 text-sm">{th ? 'รายวิชาสำหรับชั้นเรียนนี้' : 'Course for this class'}<select required className={control} value={course} onChange={e => setCourse(e.target.value)}><option value="">{th ? 'เลือกรายวิชา' : 'Choose a course'}</option>{data.courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label> : <p className="text-sm">{data.courses[0]?.name}</p>}
      <p className="text-sm text-neutral-600">{th ? 'ตั้งค่ากลุ่มเรียนและโหลดรายชื่อนักศึกษาจากทะเบียน' : 'Set up this section and load its official student roster.'}</p>
      <Button className="min-h-11" disabled={busy || !course} loading={busy} loadingLabel={th ? 'กำลังโหลดรายชื่อ…' : 'Loading roster…'}>{th ? 'ตั้งค่าชั้นเรียนและโหลดรายชื่อ' : 'Set up class and load roster'}</Button>
    </form>}
    {data?.status === 'requested' && <p className="max-w-prose text-sm text-neutral-600">{th ? 'บันทึกคำขอแล้ว ผู้ดูแลกำลังเลือกรายวิชาสำหรับกลุ่มเรียนนี้ หน้านี้จะอัปเดตเมื่อพร้อมใช้งาน' : 'Your request is saved. An administrator needs to select the course for this section. This page updates when it is ready.'}</p>}
    {data?.status === 'needs_course' && <><p className="max-w-prose text-sm text-neutral-600">{th ? 'เลือกรายวิชาที่ใช้กับกลุ่มเรียนนี้ก่อนโหลดรายชื่อนักศึกษา' : 'This section needs a course match before its roster can be loaded.'}</p>{data.can_request ? <Button className="min-h-11" disabled={busy} loading={busy} loadingLabel={th ? 'กำลังส่ง…' : 'Sending…'} onClick={() => void submit()}>{th ? 'ส่งให้เลือกรายวิชา' : 'Request course match'}</Button> : <Link className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/account/school-identity">{th ? 'ตรวจสอบข้อมูลผู้สอน' : 'Review school identity'}</Link>}</>}
    {data?.status === 'requested' && data.request_id && <ProposalCalendar requestId={data.request_id} year={academic_year} attachments={data.calendar_attachments} th={th} onOpenCalendars={onOpenCalendars} onChanged={attachments => setData(previous => previous ? { ...previous, calendar_attachments: attachments } : previous)}/>}
    {data?.status === 'conflict' && <p className="max-w-prose text-sm text-neutral-600">{th ? 'กลุ่มเรียนนี้มีการเชื่อมข้อมูลอยู่แล้ว โปรดตรวจสอบรายวิชาและงานสอนในชั้นเรียนของฉัน' : 'This section already has a connection. Review its course and teaching assignment in My classes.'}</p>}
    {error && <p role="alert" className="text-sm text-red-800">{error}</p>}
    {(error || data?.status === 'requested' || data?.status === 'connected' || data?.status === 'conflict') && <Button variant="outline" className="min-h-11" disabled={busy} onClick={() => { setVersion(v => v + 1); changed.current() }}>{th ? 'ตรวจสอบสถานะอีกครั้ง' : 'Refresh status'}</Button>}
  </div>
}

export function ConnectionsInbox({ th, courses, refresh, onChanged, onOpenClass }: { th: boolean; courses: ConnectionCourse[]; refresh: number; onChanged: () => void; onOpenClass: (id: number) => void }) {
  const [data, setData] = useState<{ requests: Connection[]; can_connect: boolean; repairs?: { class_id: number; course_name: string }[] } | null>(null)
  const [error, setError] = useState(''), [selected, setSelected] = useState<Connection | null>(null), [course, setCourse] = useState('')
  const [preview, setPreview] = useState<ConnectionPreview | null>(null), [reviewed, setReviewed] = useState(false), [busy, setBusy] = useState(false)
  useEffect(() => { const a = new AbortController(); classRequest('/connections/requests', th, undefined, a.signal).then(setData).catch(e => { if (!a.signal.aborted) setError(e.message) }); return () => a.abort() }, [refresh, th])
  useEffect(() => { setPreview(null); setReviewed(false) }, [course, selected])
  const pending = data?.requests.filter(r => r.status !== 'connected') ?? [], available = courses.filter(c => c.private === true)
  async function prepare() { if (!selected) return; setBusy(true); setError(''); try { setPreview(await classRequest(`/connections/requests/${selected.id}/preview`, th, { course_id: Number(course) })) } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  async function connect() { if (!selected || !preview) return; setBusy(true); setError(''); try { const r = await classRequest(`/connections/requests/${selected.id}/connect`, th, { course_id: Number(course), expected_fingerprint: preview.expected_fingerprint, confirm_changes: reviewed, request_id: requestId() }); setSelected(null); onChanged(); onOpenClass(r.class_id) } catch (e) { setError((e as Error).message); setPreview(null); setReviewed(false) } finally { setBusy(false) } }
  if (!pending.length && !data?.repairs?.length && !error) return null
  return <section className="space-y-4 border-y border-neutral-200 py-5" aria-labelledby="connection-queue-title">
    <h2 id="connection-queue-title" className={`${palette.statusHeading} text-xl font-semibold text-amber-900`}><Clock3 size={20} aria-hidden="true" />{th ? data?.can_connect ? 'ชั้นเรียนที่รอเชื่อมข้อมูล' : 'คำขอเชื่อมชั้นเรียนของฉัน' : data?.can_connect ? 'Class connections to review' : 'Your class connection requests'}</h2>
    {data?.repairs?.map(r => <div className="flex flex-wrap items-center justify-between gap-3" key={r.class_id}><p className="text-sm">{r.course_name} · {th ? 'ต้องกู้คืนสิทธิ์เข้ารายวิชา' : 'Course access needs repair'}</p><Button variant="outline" className="min-h-11" onClick={() => onOpenClass(r.class_id)}>{th ? 'ตรวจสอบและแก้ไข' : 'Review and repair'}</Button></div>)}
    <div className="divide-y divide-neutral-200">{pending.map(r => <article className="flex flex-wrap items-center justify-between gap-3 py-3" key={r.id}><div className="min-w-0"><h3 className="break-words text-sm font-semibold">{r.course_code} · {r.title}</h3><p className="mt-1 text-sm text-neutral-600">{r.semester}/{r.academic_year} · {th ? 'กลุ่มเรียน' : 'Section'} {r.section} · {r.teacher_name}</p></div>{data?.can_connect ? <Button variant="outline" className="min-h-11" onClick={() => { setSelected(r); setCourse(''); setError('') }}>{th ? 'เลือกรายวิชาและเชื่อมข้อมูล' : 'Choose course and connect'}</Button> : <span className="text-sm text-neutral-600">{th ? 'รอผู้ดูแลเลือกรายวิชา' : 'Awaiting the administrator’s course selection'}</span>}</article>)}</div>
    {selected && <form className="max-w-2xl space-y-4 rounded-lg border border-neutral-300 bg-white p-4" aria-label={th ? 'เชื่อมชั้นเรียน' : 'Connect class'} onSubmit={e => { e.preventDefault(); void (preview ? connect() : prepare()) }}>
      <h3 className="font-semibold">{selected.course_code} · {selected.title} · {selected.section}</h3>
      <CalendarEvidence key={selected.id} attachments={selected.calendar_attachments} th={th}/>
      {Boolean(selected.calendar_attachments?.length) && <p className="text-sm text-neutral-600">{th ? 'ปฏิทินเป็นเอกสารประกอบเท่านั้น การเชื่อมรายวิชาไม่เผยแพร่ไฟล์ส่วนตัวและไม่เปลี่ยนตารางเรียน' : 'The calendar is supporting evidence only. Connecting the course does not share private files or change class schedules.'}</p>}
      <p className="text-sm text-neutral-600">{th ? 'อนุมัติรายวิชาและงานสอนของผู้ขอ ระบบจะดึงรายชื่อของกลุ่มเรียนนี้อัตโนมัติหลังตรวจสอบ แล้วนำเข้ารายชื่อเริ่มต้นพร้อมเชื่อมสิทธิ์อ่าน ไม่เพิ่มสิทธิ์บัญชีและไม่แก้ไขผลงานเดิม' : 'Approve the requester’s course and teaching assignment. After review, the system retrieves this section’s roster automatically, imports the initial roster and connects reading access. Account roles and existing work stay unchanged.'}</p>
      <label className="flex flex-col gap-2 text-sm font-medium">{th ? 'รายวิชาในระบบที่ตรงกับวิชานี้' : 'Matching LearnHouse course'}<select className={control} required value={course} onChange={e => setCourse(e.target.value)}><option value="">{th ? 'เลือกรายวิชาแบบส่วนตัว' : 'Choose a private course'}</option>{available.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <p className="text-sm text-neutral-600">{th ? 'ไม่มีรายวิชาที่ถูกต้อง? สร้างรายวิชาแบบส่วนตัวในพื้นที่จัดการรายวิชา แล้วกลับมาโหลดใหม่ อย่าเลือกวิชาอื่นเพียงเพราะชื่อคล้ายกัน' : 'No correct course? Create a private course in the course manager, then refresh here. Similar names do not establish course identity.'}</p>
      <div className="flex flex-wrap gap-3"><Link className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/dash/courses" target="_blank" rel="noopener noreferrer">{th ? 'เปิดพื้นที่จัดการรายวิชา' : 'Open course manager'}</Link><Button type="button" variant="ghost" className="min-h-11" onClick={onChanged}>{th ? 'โหลดรายวิชาใหม่' : 'Refresh courses'}</Button></div>

      {preview && <div className="space-y-3" role="region" aria-label={th ? 'ตรวจสอบการเชื่อมข้อมูล' : 'Review connection'}><p className="text-sm font-medium">{preview.course_name} · {selected.teacher_name} · {selected.semester}/{selected.academic_year} · {selected.section}</p>
        <p className="text-sm font-medium">{th ? `ระบบพบรายชื่อนักศึกษา ${preview.roster_count} คนจากแหล่งทางการ` : `The official source found ${preview.roster_count} students for this section.`}</p>
        {preview.source_url && <a className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href={preview.source_url} target="_blank" rel="noopener noreferrer">{th ? 'ดูแหล่งข้อมูลทางการ' : 'Open official source'}</a>}
        {preview.restricts_org_wide_access && <p className="text-sm text-amber-900">{th ? 'การเชื่อมกลุ่มแรกจะจำกัดการอ่านที่เดิมเปิดให้สมาชิกสถานศึกษาทุกคน โปรดตรวจสอบผู้ที่ต้องคงสิทธิ์ และเพิ่มสิทธิ์ด้วยเครื่องมือของรายวิชาก่อนยืนยัน' : 'The first access group restricts the course’s previous organization-wide reading fallback. Review existing readers and preserve any required manual grants in the course manager before confirming.'}</p>}
        <label className="flex min-h-11 items-start gap-3 text-sm"><input type="checkbox" className="mt-1" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />{th ? 'ฉันตรวจสอบรายวิชา ผู้สอน กลุ่มเรียน และผลต่อสิทธิ์อ่านแล้ว' : 'I reviewed the course, teacher, exact section and reading-access effect.'}</label>
      </div>}
      <div className="flex flex-wrap gap-3"><Button className="min-h-11" disabled={busy || !course || (Boolean(preview) && !reviewed)} loading={busy} loadingLabel={preview ? th ? 'กำลังเชื่อมชั้นเรียน…' : 'Connecting class…' : th ? 'กำลังดึงรายชื่อ…' : 'Retrieving roster…'}>{preview ? th ? 'เชื่อมชั้นเรียน' : 'Connect class' : th ? 'ตรวจสอบก่อนเชื่อม' : 'Review connection'}</Button><Button type="button" variant="ghost" className="min-h-11" disabled={busy} onClick={() => setSelected(null)}>{th ? 'ยกเลิก' : 'Cancel'}</Button></div>
    </form>}
    {error && <div role="alert" className="space-y-2 text-sm text-red-800"><p>{error}</p><Button type="button" variant="outline" className="min-h-11" onClick={() => { setError(''); onChanged() }}>{th ? 'โหลดใหม่' : 'Refresh'}</Button></div>}
  </section>
}

type AccessStatus = { status: string; can_configure: boolean }
type AccessPreview = ConnectionPreview & { add_count: number; remove_count: number; waiting_count: number; conflict_count: number }
export function LearningAccessPanel({ classId, th, refresh }: { classId: number; th: boolean; refresh: number }) {
  const [data, setData] = useState<AccessStatus | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [version, setVersion] = useState(0)
  const [preview, setPreview] = useState<AccessPreview | null>(null), [replace, setReplace] = useState(false), [reviewed, setReviewed] = useState(false)
  useEffect(() => { const a = new AbortController(); setData(null); setPreview(null); setError(''); classRequest(`/${classId}/learning-access/status`, th, undefined, a.signal).then(setData).catch(e => { if (!a.signal.aborted) setError(e.message) }); return () => a.abort() }, [classId, refresh, version, th])
  async function prepare(rebuild: boolean) { setBusy(true); setError(''); setReviewed(false); try { setReplace(rebuild); setPreview(await classRequest(`/${classId}/learning-access/preview?enabled=true&replace_group=${rebuild}`, th)) } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  async function apply() { if (!preview) return; setBusy(true); setError(''); try { await classRequest(`/${classId}/learning-access/apply`, th, { enabled: true, replace_group: replace, expected_fingerprint: preview.expected_fingerprint, confirm_changes: reviewed, request_id: requestId(), reason: replace ? 'Reviewed native course access repair' : 'Reviewed roster-based native course reading access' }); setVersion(v => v + 1) } catch (e) { setError((e as Error).message); setPreview(null) } finally { setBusy(false) } }
  async function retry() { setBusy(true); setError(''); try { const result = await classRequest(`/${classId}/learning-access/retry`, th, {}); setTimeout(() => toast.success(result.status === 'requested' ? th ? 'ส่งคำขอสิทธิ์อ่านให้ผู้ดูแลแล้ว' : 'Course-access request sent to the administrator' : result.status === 'ready' ? th ? 'เชื่อมสิทธิ์อ่านแล้ว' : 'Course access restored' : th ? 'บันทึกงานซ่อมให้ผู้ดูแลแล้ว' : 'Access repair task recorded for the administrator'), 0); setVersion(v => v + 1) } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  const ready = data?.status === 'ready', repair = data?.status === 'needs_repair'
  return <section className={`${palette.status} space-y-3`} data-state={error ? 'error' : ready ? 'ready-access' : repair ? 'needs_repair' : data ? 'ready' : 'loading'} aria-label={th ? 'สิทธิ์เข้ารายวิชาตามรายชื่อ' : 'Roster-based course access'}>
    <h3 className={`${palette.statusHeading} text-sm font-semibold`}>{ready ? <CheckCircle2 size={16} aria-hidden="true" /> : repair || error ? <AlertCircle size={16} aria-hidden="true" /> : <Link2 size={16} aria-hidden="true" />}{th ? 'สิทธิ์เข้ารายวิชาตามรายชื่อ' : 'Roster-based course access'}</h3>
    {data && <p role="status" className="max-w-prose text-sm text-neutral-600">{ready ? th ? 'เชื่อมสิทธิ์อ่านแล้ว บัญชีที่ยืนยันและตรงกับรายชื่อจะเข้าถึงเนื้อหาที่เผยแพร่ โดยไม่ลบความก้าวหน้าหรือสิทธิ์ที่เพิ่มเอง' : 'Reading access is connected. Assigned teachers and verified roster matches can read released content; existing progress and manual grants are preserved.' : repair ? th ? 'ต้องซ่อมการเชื่อมสิทธิ์ รายชื่อและการเข้าสู่ระบบยังใช้งานได้ งานซ่อมปรากฏในชั้นเรียนของฉันของผู้ดูแลแล้ว' : 'Course access needs repair. Rosters and sign-in still work; the administrator has a repair task in My classes.' : th ? 'ยังไม่เชื่อมสิทธิ์อ่านตามรายชื่อ ผู้ดูแลเปิดใช้งานได้ที่นี่ โดยไม่เปลี่ยนสิทธิ์บัญชีหรือการเผยแพร่เนื้อหา' : 'Roster reading access is not connected. An administrator can enable it here without changing account roles or content publication.'}</p>}
    <div className="flex flex-wrap gap-3">{data && !ready && <Button variant="outline" className="min-h-11" disabled={busy} onClick={() => void retry()}>{repair ? th ? 'ลองเชื่อมสิทธิ์อีกครั้ง' : 'Retry access' : th ? 'ส่งคำขอสิทธิ์อ่าน' : 'Request course access'}</Button>}{data?.can_configure && !ready && <Button className="min-h-11" disabled={busy} onClick={() => void prepare(repair)}>{repair ? th ? 'ตรวจสอบการซ่อมสิทธิ์' : 'Review access repair' : th ? 'เชื่อมสิทธิ์อ่านตามรายชื่อ' : 'Connect roster reading access'}</Button>}</div>
    {preview && <div className="space-y-3 border-t border-neutral-200 pt-3"><p className="text-sm">{th ? 'เพิ่มสิทธิ์' : 'Add access'}: {preview.add_count} · {th ? 'ถอนเฉพาะสิทธิ์ที่ระบบนี้เพิ่ม' : 'Remove only access added here'}: {preview.remove_count} · {th ? 'รอยืนยันบัญชี' : 'Waiting for verification'}: {preview.waiting_count} · {th ? 'ตัวตนขัดแย้ง' : 'Identity conflicts'}: {preview.conflict_count}</p>
      {preview.restricts_org_wide_access && <p className="text-sm text-amber-900">{th ? 'กลุ่มสิทธิ์แรกจะจำกัดการอ่านที่เดิมเปิดให้สมาชิกสถานศึกษาทุกคน ตรวจสอบและคงสิทธิ์ที่จำเป็นในพื้นที่จัดการรายวิชาก่อนยืนยัน' : 'The first group restricts the previous organization-wide fallback. Review and preserve any required manual readers in the course manager before confirming.'}</p>}
      <label className="flex min-h-11 items-start gap-3 text-sm"><input type="checkbox" className="mt-1" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />{th ? 'ฉันตรวจสอบการเปลี่ยนแปลงสิทธิ์นี้แล้ว ไม่ลบผลงานหรือสิทธิ์ที่เพิ่มเอง' : 'I reviewed these access changes. Existing work and manual grants will be preserved.'}</label>
      <div className="flex gap-3"><Button className="min-h-11" disabled={busy || !reviewed} onClick={() => void apply()}>{th ? 'บันทึกสิทธิ์อ่าน' : 'Apply reading access'}</Button><Button variant="ghost" className="min-h-11" onClick={() => setPreview(null)}>{th ? 'ยกเลิก' : 'Cancel'}</Button></div>
    </div>}
    {error && <p role="alert" className="text-sm text-red-800">{error} <Button variant="link" type="button" onClick={() => setVersion(v => v + 1)}>{th ? 'โหลดใหม่' : 'Refresh'}</Button></p>}
  </section>
}
