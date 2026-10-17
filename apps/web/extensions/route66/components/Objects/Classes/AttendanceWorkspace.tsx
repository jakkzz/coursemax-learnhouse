'use client'

import interior from '@/extensions/route66/components/interior/material.module.css'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Check } from 'lucide-react'
import AttendanceCode from './AttendanceCode'
import { useAttendanceStream } from './useAttendanceStream'
import { attendanceRequest, type AttendanceReceipt, type AttendanceText, type AttendanceError, type Detail, type Session } from './attendance-client'
import attendanceStyles from './attendance.module.css'
export { attendanceRequest } from './attendance-client'
export type { AttendanceReceipt, AttendanceText } from './attendance-client'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { Button } from '@/extensions/route66/adapters/ui'
import { Input } from '@/extensions/route66/adapters/ui'
import { toast } from 'react-hot-toast'
import { attendanceCopy } from './attendance-copy'
import styles from '../Account/subpages/school-identity.module.css'

type Schedule = {class_id:number; course_name:string; section:string; manageable:boolean; sessions:Session[]}

export function attendanceTime(value:string|null, language:string, zone='Asia/Bangkok') {
 if (!value) return '—'
 const formatted=new Intl.DateTimeFormat(language.startsWith('th')?'th-TH':'en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:zone}).format(new Date(value))
 return language.startsWith('th')?formatted.replace(/:/g,'.'):formatted
}
export function attendanceStatus(value:string,t:AttendanceText) { return ({present:t.present,late:t.late,absent:t.absent,upcoming:t.upcoming,unrecorded:t.unrecorded,no_class:t.noClass})[value] || value }
export function Receipt({receipt,t,language,celebrate=false}:{receipt:AttendanceReceipt;t:AttendanceText;language:string;celebrate?:boolean}) {
 return <div className={`${attendanceStyles.receipt} ${celebrate?attendanceStyles.celebrate:''} ${receipt.session_state==='no_class'?attendanceStyles.receiptChanged:''} space-y-4`} role="status">
  <span className={attendanceStyles.check} aria-hidden="true"><Check size={28}/></span>
  <h2 className="text-xl font-semibold">{t.checked}</h2><p className="font-medium">{receipt.session_title}</p>
  <p className="text-sm">{attendanceStatus(receipt.effective_status||receipt.computed_status,t)} · {receipt.kind==='heartbeat'?t.followup:t.entryKind}</p>
  <dl className="text-sm"><dt>{t.timestamp}</dt><dd className="mt-1 tabular-nums">{attendanceTime(receipt.arrived_at,language,receipt.timezone)}</dd></dl>
  {receipt.session_state==='no_class'&&<p className="text-sm">{t.noClassReceipt}</p>}
  <p className="max-w-prose text-sm leading-relaxed">{t.receiptHelp}</p>
  <Link className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href={`/attendance/receipts/${receipt.receipt_id}`}>{t.receiptLink}</Link>
 </div>
}
export function useAttendanceText() {
 const {i18n}=useTranslation();const [mounted,setMounted]=useState(false)
 useEffect(()=>setMounted(true),[])
 const language=mounted?i18n.language:'en'
 return {t:attendanceCopy[language.startsWith('th')?'th':'en'],language,mounted}
}

export default function AttendanceWorkspace({classId}:{classId:number|null}) {
 const {t,language,mounted}=useAttendanceText()
 const [schedule,setSchedule]=useState<Schedule|null>(null),[selected,setSelected]=useState<number|null>(null),[detail,setDetail]=useState<Detail|null>(null)
 const [refresh,setRefresh]=useState(0),[error,setError]=useState(''),[busy,setBusy]=useState(false),[creating,setCreating]=useState(false),[changingState,setChangingState]=useState(false),[reason,setReason]=useState('')
 const [query,setQuery]=useState(''),[filter,setFilter]=useState('all'),[codeKind,setCodeKind]=useState<string|null>(null)
 const seen=useRef<Set<number>|null>(null),[arrivals,setArrivals]=useState<Set<number>>(new Set())
 const [form,setForm]=useState({title:'',starts_at:'',ends_at:'',grace_minutes:'10',late_threshold_minutes:'20'})
 useEffect(()=>{if(!mounted||!classId)return;const abort=new AbortController();const requested=Number(new URLSearchParams(window.location.search).get('session'));const suffix=Number.isInteger(requested)&&requested>0?`?session=${requested}`:'';setError('');attendanceRequest<Schedule>(`/classes/${classId}/sessions${suffix}`,t,undefined,abort.signal).then(setSchedule).catch(e=>{if(!abort.signal.aborted)setError(e.message)});return()=>abort.abort()},[classId,refresh,mounted,t])
 useEffect(()=>{if(!mounted||!schedule)return;const id=Number(new URLSearchParams(window.location.search).get('session'));if(Number.isInteger(id)&&id>0&&schedule.sessions.some(s=>s.id===id))setSelected(id)},[mounted,schedule?.class_id])
 useEffect(()=>{setDetail(null);setCodeKind(null);setChangingState(false);setReason('');seen.current=null;setArrivals(new Set())},[selected,mounted])
 const receive=useCallback((next:Detail)=>{
  const current=new Set((next.students||[]).filter(s=>s.first_arrived_at).map(s=>s.roster_entry_id))
  if(seen.current){const fresh=[...current].filter(id=>!seen.current!.has(id));if(fresh.length)setArrivals(previous=>new Set([...previous,...fresh]))}
  seen.current=current;setDetail(next);setError('')
  if(!next.manageable||next.session.state==='no_class')setCodeKind(null)
 },[])
 const problem=useCallback((issue:AttendanceError)=>{setError(issue.message);if(issue.status&&[401,403,404,409].includes(issue.status))setDetail(null)},[])
 const live=useAttendanceStream(mounted?selected:null,t,receive,problem,refresh)
 async function mutate(path:string,body:unknown,success:string) {setBusy(true);setError('');try{await attendanceRequest(path,t,body);setRefresh(n=>n+1);setCreating(false);setChangingState(false);setReason('');setTimeout(()=>toast.success(success),0)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const arrived=detail?.students?.filter(s=>s.membership==='active'&&s.first_arrived_at).length||0
 const total=detail?.students?.filter(s=>s.membership==='active').length||0
 const students=detail?.students?.filter(s=>`${s.name} ${s.student_number||''}`.toLowerCase().includes(query.toLowerCase())&&(filter==='all'||s.status===filter))||[]
 const start=form.starts_at?new Date(form.starts_at+'+07:00').getTime():NaN,end=form.ends_at?new Date(form.ends_at+'+07:00').getTime():NaN
 const validForm=form.title.trim()&&Number.isFinite(start)&&end>start&&Number(form.late_threshold_minutes)>=Number(form.grace_minutes)
 return <section className={`${interior.scope} ${styles.workspace} space-y-6 px-4 pb-24 pt-8 md:px-8`} aria-labelledby="attendance-title">
  <header className="flex flex-wrap items-start justify-between gap-4"><div><h1 id="attendance-title" className="text-3xl font-semibold">{t.title}</h1><Link className="mt-2 inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/classes">{t.back}</Link>{schedule&&<p className="mt-2 break-words text-sm text-neutral-600">{schedule.course_name} · {schedule.section}</p>}</div>{schedule?.manageable&&!detail&&<Button className="min-h-11" onClick={()=>setCreating(true)}>{t.create}</Button>}</header>
  {error&&<div role="alert" className="space-y-3"><p className="text-sm text-red-800">{error}</p><Button className="min-h-11" variant="outline" disabled={busy} onClick={()=>setRefresh(n=>n+1)}>{t.retry}</Button></div>}
  {!classId?<p>{t.classMissing}</p>:!schedule&&!error?<p role="status">{t.loading}</p>:null}
  {creating&&<form className="max-w-xl space-y-4 rounded-lg border border-neutral-200 bg-white p-5" onSubmit={e=>{e.preventDefault();void mutate(`/classes/${classId}/sessions`,{title:form.title,starts_at:form.starts_at+'+07:00',ends_at:form.ends_at+'+07:00',timezone:'Asia/Bangkok',grace_minutes:Number(form.grace_minutes),late_threshold_minutes:Number(form.late_threshold_minutes)},t.saved)}}>
   <h2 className="text-xl font-semibold">{t.create}</h2><p className="text-sm text-neutral-600">{t.clock}</p>
   <label className="flex flex-col gap-2 text-sm font-medium">{t.titleLabel}<Input className="min-h-11" required maxLength={160} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>
   <div className="grid gap-4 md:grid-cols-2">{(['starts_at','ends_at','grace_minutes','late_threshold_minutes'] as const).map(key=><label key={key} className="flex min-w-0 flex-col gap-2 text-sm font-medium">{({starts_at:t.starts,ends_at:t.ends,grace_minutes:t.grace,late_threshold_minutes:t.cutoff})[key]}<Input className="min-h-11 min-w-0 max-w-full" type={key.endsWith('_at')?'datetime-local':'number'} required min={key.endsWith('_at')?undefined:0} max={key.endsWith('_at')?undefined:1440} value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}/></label>)}</div>
   <p className="text-sm leading-relaxed text-neutral-600">{t.timingHelp}</p><div className="flex gap-3"><Button className="min-h-11" disabled={busy||!validForm}>{t.save}</Button><Button className="min-h-11" type="button" variant="ghost" onClick={()=>setCreating(false)}>{t.cancel}</Button></div>
  </form>}
  {schedule&&selected===null&&<>{schedule.sessions.length===0?<div className="space-y-2 border-t border-neutral-200 pt-6"><h2 className="text-xl font-semibold">{t.noSessions}</h2><p className="text-sm text-neutral-600">{t.noSessionsHelp}</p></div>:<div className="divide-y divide-neutral-200 border-y border-neutral-200">{schedule.sessions.map(session=><article key={session.id} className="flex flex-wrap items-center justify-between gap-4 py-4"><div className="min-w-0"><h2 className="break-words text-lg font-semibold">{session.title}</h2><p className="mt-1 text-sm text-neutral-600">{attendanceTime(session.starts_at,language,session.timezone)} · {session.state==='no_class'?t.noClass:t.scheduled}</p></div><Button className="min-h-11" variant="outline" onClick={()=>{setSelected(session.id);setCreating(false)}}>{t.open}</Button></article>)}</div>}</>}
  {selected!==null&&!detail&&!error&&<p role="status">{t.loading}</p>}
  {detail&&<><div className="flex flex-wrap items-center justify-between gap-3"><Button className="min-h-11" variant="ghost" onClick={()=>setSelected(null)}>{t.sessions}</Button>{!codeKind&&<Button className="min-h-11" variant="outline" disabled={busy} onClick={()=>setRefresh(n=>n+1)}>{t.retry}</Button>}</div>
   <header><h2 className="break-words text-2xl font-semibold">{detail.session.title}</h2><p className="mt-2 text-sm text-neutral-600">{attendanceTime(detail.session.starts_at,language,detail.session.timezone)} — {attendanceTime(detail.session.ends_at,language,detail.session.timezone)}</p><p className={`mt-3 rounded-lg p-3 text-sm font-medium ${detail.session.state==='no_class'?'bg-amber-50 text-amber-950':'bg-blue-50 text-blue-950'}`}>{detail.session.state==='no_class'?t.noClass:t.scheduled}</p></header>
   <p role="status" className="text-sm text-neutral-600">{live?t.live:t.reconnecting}</p>
   {detail.manageable&&<>
   {!codeKind&&<><div className="flex flex-wrap gap-3"><Button className="min-h-11" disabled={busy||detail.session.state==='no_class'} onClick={()=>setCodeKind('entry')}>{t.entry}</Button><Button className="min-h-11" variant="outline" disabled={busy||detail.session.state==='no_class'} onClick={()=>setCodeKind('heartbeat')}>{t.heartbeat}</Button></div><p className="max-w-prose text-sm leading-relaxed text-neutral-600">{t.heartbeatHelp} {t.refreshHelp}</p></>}
   <div className="border-t border-neutral-200 pt-4"><Button className="min-h-11" variant="outline" onClick={()=>setChangingState(!changingState)}>{detail.session.state==='no_class'?t.restore:t.markNoClass}</Button></div>
   {changingState&&<form className="max-w-xl space-y-4" onSubmit={e=>{e.preventDefault();void mutate(`/sessions/${selected}/state`,{expected_version:detail.session.version,state:detail.session.state==='no_class'?'scheduled':'no_class',reason},t.done)}}><p className="text-sm leading-relaxed text-neutral-600">{t.stateHelp}</p><label className="flex flex-col gap-2 text-sm font-medium">{t.reason}<Input className="min-h-11" required minLength={5} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)}/></label><Button className="min-h-11" disabled={busy||reason.trim().length<5}>{t.confirmState}</Button></form>}
   <div className={codeKind?attendanceStyles.liveLayout:''}>
   {codeKind&&<AttendanceCode session={detail.session} kind={codeKind} t={t} arrived={arrived} total={total} live={live} onClose={()=>setCodeKind(null)}/>}
   <div className="space-y-4 border-t border-neutral-200 pt-6"><h3 className="text-xl font-semibold">{t.students}</h3><p role="status" className="text-sm tabular-nums">{arrived} / {total} {t.arrived}</p><div className="flex flex-wrap items-end gap-3"><label className="flex min-w-0 flex-1 flex-col gap-2 text-sm font-medium">{t.search}<Input className="min-h-11" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label={t.status} className="min-h-11 max-w-full rounded-lg border border-neutral-300 bg-white px-3 text-sm" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">{t.filter}</option>{['present','late','unrecorded','absent','no_class'].map(status=><option key={status} value={status}>{attendanceStatus(status,t)}</option>)}</select></div>
   {!detail.students?.length?<p className="text-sm text-neutral-600">{t.noStudents}</p>:!students.length?<p className="text-sm text-neutral-600">{t.noResults}</p>:<div className="divide-y divide-neutral-200">{students.map(student=><article className={`flex flex-wrap items-start justify-between gap-3 py-4 ${arrivals.has(student.roster_entry_id)?attendanceStyles.arrival:''}`} key={student.roster_entry_id}><div className="min-w-0"><h4 className="break-words text-sm font-semibold">{student.name}</h4><p className="mt-1 text-sm text-neutral-600">{student.student_number||'—'}{student.membership==='withdrawn'?` · ${t.withdrawn}`:''}</p><p className="mt-2 text-xs text-neutral-600">{t.first} {attendanceTime(student.first_arrived_at,language,detail.session.timezone)}<br/>{t.last} {attendanceTime(student.last_heartbeat_at,language,detail.session.timezone)}</p></div><p className="text-sm font-medium">{attendanceStatus(student.status,t)}</p></article>)}</div>}</div>
   </div>
   <details className="border-t border-neutral-200 pt-4"><summary className="min-h-11 cursor-pointer text-sm font-medium">{t.recent}</summary><ol className="space-y-3 text-xs text-neutral-600">{detail.events?.map(event=><li key={event.id}><p>{attendanceTime(event.created_at,language)} · {event.kind}</p><pre className="mt-1 whitespace-pre-wrap break-words">{JSON.stringify(event.details,null,2)}</pre></li>)}</ol></details>
   </>}
   {!detail.manageable&&detail.own&&<div className="space-y-4"><h3 className="text-xl font-semibold">{t.own}</h3><p className="text-sm font-medium">{attendanceStatus(detail.own.status,t)}</p>{detail.own.receipts.length?detail.own.receipts.map(receipt=><Receipt key={receipt.receipt_id} receipt={receipt} t={t} language={language}/>):<p className="text-sm text-neutral-600">{t.emptyReceiptHelp}</p>}</div>}
  </>}
 </section>
}
