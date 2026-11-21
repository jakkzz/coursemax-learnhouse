'use client'

import interior from '@/extensions/route66/components/interior/material.module.css'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Check } from 'lucide-react'
import AttendanceCode from './AttendanceCode'
import AttendanceReports from './AttendanceReports'
import { useAttendanceStream } from './useAttendanceStream'
import { attendanceRequest, attendanceSignInPath, type AttendanceDecision, type AttendanceReceipt, type AttendanceText, type AttendanceError, type DecisionResult, type Detail, type Projection, type Session, type Student } from './attendance-client'
import { attendanceStatus, attendanceTime } from './attendance-format'
import attendanceStyles from './attendance.module.css'
export { attendanceRequest } from './attendance-client'
export { attendanceStatus, attendanceTime } from './attendance-format'
export type { AttendanceReceipt, AttendanceText } from './attendance-client'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { Button, Input } from '@/extensions/route66/adapters/ui'
import { toast } from 'react-hot-toast'
import { attendanceCopy } from './attendance-copy'
import styles from '../Account/subpages/school-identity.module.css'

type Schedule = {class_id:number; course_name:string; section:string; manageable:boolean; sessions:Session[]}
type SaveIntent={requestId:string;status:string;reason:string;expectedToken:string}
type StoredIntent=SaveIntent&{reviewedStatus:string}
type CorrectionDraft={entryId:number;status:string;reason:string;reviewedToken:string;reviewedStatus:string;reviewedDecision:AttendanceDecision|null;staleToken:string|null;unresolved:SaveIntent|null}
const correctionStatuses=['present','late','absent','excused','reset']
const filterStatuses=['present','late','absent','excused','unrecorded','unknown','not_eligible','no_class','upcoming']
const correctionIntentKey='lh:attendance-correction-intent:'
function storedCorrectionIntent(sessionId:number,entryId:number):StoredIntent|null {
 try {const value=JSON.parse(sessionStorage.getItem(correctionIntentKey+sessionId+':'+entryId)||'null');return value&&typeof value.requestId==='string'&&correctionStatuses.includes(value.status)&&typeof value.reason==='string'&&/^[0-9a-f]{64}$/.test(value.expectedToken)&&typeof value.reviewedStatus==='string'?value:null}catch{return null}
}
function rememberCorrectionIntent(sessionId:number,entryId:number,intent:SaveIntent,reviewedStatus:string) {try{sessionStorage.setItem(correctionIntentKey+sessionId+':'+entryId,JSON.stringify({...intent,reviewedStatus}))}catch{}}
function forgetCorrectionIntent(sessionId:number,entryId:number) {try{sessionStorage.removeItem(correctionIntentKey+sessionId+':'+entryId)}catch{}}
function recoveryPath(classId:number|null) {
 if(typeof window==='undefined')return classId?`/attendance?class=${classId}`:'/attendance'
 return window.location.pathname.includes('/attendance')?window.location.pathname+window.location.search:classId?`/attendance?class=${classId}`:'/attendance'
}
function AttendanceRecovery({status,classId,t}:{status:number|null;classId:number|null;t:AttendanceText}) {
 if(status===401)return <Link className="inline-flex min-h-11 items-center rounded-lg bg-neutral-900 px-4 text-sm font-medium text-white" href={attendanceSignInPath(recoveryPath(classId),typeof navigator==='undefined'?'':navigator.userAgent)}>{t.signin}</Link>
 if(status===403)return <Link className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/classes">{t.back}</Link>
 return null
}

function DecisionNote({decision,t,language,zone}:{decision:AttendanceDecision|null;t:AttendanceText;language:string;zone:string}) {
 if(!decision)return null
 return <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
  <p className="font-medium">{t.correction}: {attendanceStatus(decision.status,t)}</p>
  <p className="mt-1">{t.correctionReason}: {decision.reason}</p>
  <p className="mt-1 tabular-nums">{t.correctionTime}: {attendanceTime(decision.decided_at,language,zone)}</p>
 </div>
}

function ProjectionEvidence({projection,t,language,zone}:{projection:Projection;t:AttendanceText;language:string;zone:string}) {
 const receipt=projection.receipts[0]
 return <div className="space-y-3">
  <dl className="grid gap-3 text-sm sm:grid-cols-2">
   <div><dt className="text-xs font-medium text-neutral-600">{t.currentResult}</dt><dd className="mt-1 font-semibold">{attendanceStatus(projection.effective_status,t)}</dd></div>
   <div><dt className="text-xs font-medium text-neutral-600">{t.recordedArrival}</dt><dd className="mt-1 tabular-nums">{receipt?attendanceTime(receipt.arrived_at,language,zone):t.noRecordedScan}</dd>{receipt&&<dd className="mt-1 text-neutral-600">{attendanceStatus(receipt.computed_status,t)}</dd>}</div>
  </dl>
  <DecisionNote decision={projection.decision} t={t} language={language} zone={zone}/>
 </div>
}

export function Receipt({receipt,t,language,celebrate=false}:{receipt:AttendanceReceipt;t:AttendanceText;language:string;celebrate?:boolean}) {
 const changed=receipt.session_state==='no_class'||Boolean(receipt.decision)||receipt.effective_status!==receipt.computed_status
 return <div className={`${attendanceStyles.receipt} ${celebrate?attendanceStyles.celebrate:''} ${changed?attendanceStyles.receiptChanged:''} space-y-4`} role="status">
  <span className={attendanceStyles.check} aria-hidden="true"><Check size={28}/></span>
  <h2 className="text-xl font-semibold">{t.checked}</h2><p className="font-medium">{receipt.session_title}</p>
  <dl className="grid gap-4 text-sm sm:grid-cols-2">
   <div><dt>{t.currentResult}</dt><dd className="mt-1 font-semibold">{attendanceStatus(receipt.effective_status,t)}</dd></div>
   <div><dt>{t.recordedStatus}</dt><dd className="mt-1">{attendanceStatus(receipt.computed_status,t)} · {receipt.kind==='heartbeat'?t.followup:t.entryKind}</dd></div>
   <div><dt>{t.recordedArrival}</dt><dd className="mt-1 tabular-nums">{attendanceTime(receipt.arrived_at,language,receipt.timezone)}</dd></div>
  </dl>
  <DecisionNote decision={receipt.decision} t={t} language={language} zone={receipt.timezone}/>
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
 const [schedule,setSchedule]=useState<Schedule|null>(null),[selected,setSelected]=useState<number|null>(null),[detail,setDetail]=useState<Detail|null>(null),[view,setView]=useState<'sessions'|'report'>('sessions')
 const [refresh,setRefresh]=useState(0),[error,setError]=useState(''),[busy,setBusy]=useState(false),[creating,setCreating]=useState(false),[changingState,setChangingState]=useState(false),[reason,setReason]=useState('')
 const [query,setQuery]=useState(''),[filter,setFilter]=useState('all'),[codeKind,setCodeKind]=useState<string|null>(null)
 const [correction,setCorrection]=useState<CorrectionDraft|null>(null),[correctionBusy,setCorrectionBusy]=useState(false),[correctionError,setCorrectionError]=useState(''),[correctionErrorStatus,setCorrectionErrorStatus]=useState<number|null>(null),[focusedResult,setFocusedResult]=useState<number|null>(null)
 const correctionTrigger=useRef<HTMLButtonElement|null>(null)
 const seen=useRef<Set<number>|null>(null),[arrivals,setArrivals]=useState<Set<number>>(new Set())
 const [form,setForm]=useState({title:'',starts_at:'',ends_at:'',grace_minutes:'10',late_threshold_minutes:'20'})
 useEffect(()=>{if(!mounted||!classId)return;const abort=new AbortController();const requested=Number(new URLSearchParams(window.location.search).get('session'));const suffix=Number.isInteger(requested)&&requested>0?`?session=${requested}`:'';setError('');attendanceRequest<Schedule>(`/classes/${classId}/sessions${suffix}`,t,undefined,abort.signal).then(setSchedule).catch(e=>{if(!abort.signal.aborted)setError(e.message)});return()=>abort.abort()},[classId,refresh,mounted,t])
 useEffect(()=>{if(!mounted||!schedule)return;const id=Number(new URLSearchParams(window.location.search).get('session'));if(Number.isInteger(id)&&id>0&&schedule.sessions.some(s=>s.id===id))setSelected(id)},[mounted,schedule?.class_id])
 useEffect(()=>{setDetail(null);setCodeKind(null);setChangingState(false);setReason('');setCorrection(null);setCorrectionError('');setCorrectionErrorStatus(null);setCorrectionBusy(false);setFocusedResult(null);seen.current=null;setArrivals(new Set())},[selected,mounted])
 const receive=useCallback((next:Detail)=>{
  const current=new Set((next.students||[]).filter(s=>s.first_arrived_at).map(s=>s.roster_entry_id))
  if(seen.current){const fresh=[...current].filter(id=>!seen.current!.has(id));if(fresh.length)setArrivals(previous=>new Set([...previous,...fresh]))}
  seen.current=current;setDetail(next);setError('')
  if(!next.manageable||next.session.state==='no_class')setCodeKind(null)
 },[])
 const problem=useCallback((issue:AttendanceError)=>{setError(issue.message);if(issue.status&&[401,403,404,409].includes(issue.status))setDetail(null)},[])
 const live=useAttendanceStream(mounted?selected:null,t,receive,problem,refresh)
 async function mutate(path:string,body:unknown,success:string) {setBusy(true);setError('');try{await attendanceRequest(path,t,body);setRefresh(n=>n+1);setCreating(false);setChangingState(false);setReason('');setTimeout(()=>toast.success(success),0)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 function openCorrection(student:Student,trigger:HTMLButtonElement) {
  const unresolved=selected===null?null:storedCorrectionIntent(selected,student.roster_entry_id)
  correctionTrigger.current=trigger;setFocusedResult(null);setCorrectionError('');setCorrectionErrorStatus(null);setCorrection({entryId:student.roster_entry_id,status:unresolved?.status||(correctionStatuses.includes(student.effective_status)?student.effective_status:'present'),reason:unresolved?.reason||'',reviewedToken:unresolved?.expectedToken||student.evidence_token,reviewedStatus:unresolved?.reviewedStatus||student.effective_status,reviewedDecision:unresolved?null:student.decision,staleToken:null,unresolved})
  requestAnimationFrame(()=>document.getElementById('attendance-correction-reason')?.focus())
 }
 function closeCorrection() {setCorrection(null);setCorrectionError('');setCorrectionErrorStatus(null);requestAnimationFrame(()=>correctionTrigger.current?.focus())}
 async function persistCorrection(intent:SaveIntent) {
  if(selected===null||!correction)return
  const retryingUnresolved=correction.unresolved?.requestId===intent.requestId
  setCorrectionBusy(true);setCorrectionError('');setCorrectionErrorStatus(null)
  try {
   const result=await attendanceRequest<DecisionResult>(`/sessions/${selected}/decisions`,t,{roster_entry_id:correction.entryId,status:intent.status,reason:intent.reason,expected_token:intent.expectedToken,request_id:intent.requestId})
   setDetail(current=>current?{...current,students:current.students?.map(student=>student.roster_entry_id===correction.entryId&&(student.evidence_token===intent.expectedToken||student.evidence_token===result.projection.evidence_token)?{...student,...result.projection}:student)}:current)
   const id=correction.entryId;forgetCorrectionIntent(selected,id);setFocusedResult(id);setCorrection(null);setTimeout(()=>toast.success(t.correctionSaved),0);requestAnimationFrame(()=>document.getElementById(`attendance-result-${id}`)?.focus())
  } catch(error) {
   const issue=error as AttendanceError,authFailure=issue.status===401||issue.status===403
   if(!issue.status||issue.status>=500||(retryingUnresolved&&authFailure)){rememberCorrectionIntent(selected,correction.entryId,intent,correction.reviewedStatus);setCorrection(current=>current?{...current,unresolved:intent}:current)}
   else {if(retryingUnresolved)forgetCorrectionIntent(selected,correction.entryId);if(issue.code==='stale_evidence')setCorrection(current=>current?{...current,staleToken:issue.currentToken||'changed',unresolved:null}:current);else setCorrection(current=>current?{...current,unresolved:null}:current)}
   setCorrectionErrorStatus(authFailure?issue.status!:null)
   setCorrectionError(!issue.status||issue.status>=500?t.saveUncertain:issue.status===403?t.accessLost:issue.message)
  } finally {setCorrectionBusy(false)}
 }
 async function saveCorrection() {
  if(!correction)return
  await persistCorrection({requestId:crypto.randomUUID(),status:correction.status,reason:correction.reason.trim(),expectedToken:correction.reviewedToken})
 }
 async function reloadCorrection() {
  if(selected===null||!correction)return
  setCorrectionBusy(true);setCorrectionError('');setCorrectionErrorStatus(null)
  try {
   const next=await attendanceRequest<Detail>(`/sessions/${selected}`,t),student=next.students?.find(value=>value.roster_entry_id===correction.entryId)
   if(!student)throw new Error(t.denied)
   receive(next);setCorrection(current=>current?{...current,reviewedToken:student.evidence_token,reviewedStatus:student.effective_status,reviewedDecision:student.decision,staleToken:null}:current)
   requestAnimationFrame(()=>document.getElementById('attendance-correction-reason')?.focus())
  } catch(error){const issue=error as AttendanceError;setCorrectionErrorStatus(issue.status===401||issue.status===403?issue.status:null);setCorrectionError(issue.status===403?t.accessLost:issue.message)}finally{setCorrectionBusy(false)}
 }
 const arrived=detail?.students?.filter(s=>s.membership==='active'&&s.first_arrived_at).length||0
 const total=detail?.students?.filter(s=>s.membership==='active').length||0
 const students=detail?.students?.filter(s=>{const matches=`${s.name} ${s.student_number||''}`.toLowerCase().includes(query.toLowerCase())&&(filter==='all'||s.effective_status===filter);return matches||s.roster_entry_id===correction?.entryId||s.roster_entry_id===focusedResult})||[]
 const start=form.starts_at?new Date(form.starts_at+'+07:00').getTime():NaN,end=form.ends_at?new Date(form.ends_at+'+07:00').getTime():NaN
 const validForm=form.title.trim()&&Number.isFinite(start)&&end>start&&Number(form.late_threshold_minutes)>=Number(form.grace_minutes)
 const correctionStudent=detail?.students?.find(student=>student.roster_entry_id===correction?.entryId)
 const correctionStale=Boolean(correction&&(correction.staleToken||correctionStudent?.evidence_token!==correction.reviewedToken))
 const unresolvedChanged=Boolean(correction?.unresolved&&(correction.status!==correction.unresolved.status||correction.reason.trim()!==correction.unresolved.reason))
 const unresolved=Boolean(correction?.unresolved)
 return <section className={`${interior.scope} ${styles.workspace} space-y-6 px-4 pb-24 pt-8 md:px-8`} aria-labelledby="attendance-title">
  <header className="flex flex-wrap items-start justify-between gap-4"><div><h1 id="attendance-title" className="text-3xl font-semibold">{t.title}</h1><Link className="mt-2 inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/classes">{t.back}</Link>{schedule&&<p className="mt-2 break-words text-sm text-neutral-600">{schedule.course_name} · {schedule.section}</p>}</div>{schedule?.manageable&&!detail&&view==='sessions'&&<Button className="min-h-11" onClick={()=>setCreating(true)}>{t.create}</Button>}</header>
  {error&&<div role="alert" className="space-y-3"><p className="text-sm text-red-800">{error}</p><Button className="min-h-11" variant="outline" disabled={busy} onClick={()=>setRefresh(n=>n+1)}>{t.retry}</Button></div>}
  {!classId?<p>{t.classMissing}</p>:!schedule&&!error?<p role="status">{t.loading}</p>:null}
  {schedule&&<nav className={interior.navigation} aria-label={t.title}><Button variant="ghost" aria-pressed={view==='sessions'} onClick={()=>setView('sessions')}>{t.sessionsView}</Button><Button variant="ghost" aria-pressed={view==='report'} onClick={()=>setView('report')}>{schedule.manageable?t.reportView:t.myAttendance}</Button></nav>}
  {schedule&&classId&&<div hidden={view!=='report'}><AttendanceReports classId={classId} manageable={schedule.manageable} active={view==='report'} t={t} language={language}/></div>}
  <div hidden={view!=='sessions'} className="space-y-6">
  {creating&&<form className="max-w-xl space-y-4 rounded-lg border border-neutral-200 bg-white p-5" onSubmit={e=>{e.preventDefault();void mutate(`/classes/${classId}/sessions`,{title:form.title,starts_at:form.starts_at+'+07:00',ends_at:form.ends_at+'+07:00',timezone:'Asia/Bangkok',grace_minutes:Number(form.grace_minutes),late_threshold_minutes:Number(form.late_threshold_minutes)},t.saved)}}>
   <h2 className="text-xl font-semibold">{t.create}</h2><p className="text-sm text-neutral-600">{t.clock}</p>
   <label className="flex flex-col gap-2 text-sm font-medium">{t.titleLabel}<Input className="min-h-11" required maxLength={160} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>
   <div className="grid gap-4 md:grid-cols-2">{(['starts_at','ends_at','grace_minutes','late_threshold_minutes'] as const).map(key=><label key={key} className="flex min-w-0 flex-col gap-2 text-sm font-medium">{({starts_at:t.starts,ends_at:t.ends,grace_minutes:t.grace,late_threshold_minutes:t.cutoff})[key]}<Input className="min-h-11 min-w-0 max-w-full" type={key.endsWith('_at')?'datetime-local':'number'} required min={key.endsWith('_at')?undefined:0} max={key.endsWith('_at')?undefined:1440} value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}/></label>)}</div>
   <p className="text-sm leading-relaxed text-neutral-600">{t.timingHelp}</p><div className="flex gap-3"><Button className="min-h-11" disabled={busy||!validForm}>{t.save}</Button><Button className="min-h-11" type="button" variant="ghost" onClick={()=>setCreating(false)}>{t.cancel}</Button></div>
  </form>}
  {schedule&&selected===null&&<>{schedule.sessions.length===0?<div className="space-y-2 border-t border-neutral-200 pt-6"><h2 className="text-xl font-semibold">{t.noSessions}</h2><p className="text-sm text-neutral-600">{t.noSessionsHelp}</p></div>:<div className="divide-y divide-neutral-200 border-y border-neutral-200">{schedule.sessions.map(session=><article key={session.id} className="flex flex-wrap items-center justify-between gap-4 py-4"><div className="min-w-0"><h2 className="break-words text-lg font-semibold">{session.title}</h2><p className="mt-1 text-sm text-neutral-600">{attendanceTime(session.starts_at,language,session.timezone)} · {session.state==='no_class'?t.noClass:t.scheduled}</p></div><Button className="min-h-11" variant="outline" onClick={()=>{setSelected(session.id);setCreating(false)}}>{t.open}</Button></article>)}</div>}</>}
  {selected!==null&&!detail&&!error&&<p role="status">{t.loading}</p>}
  {detail&&<><div className="flex flex-wrap items-center justify-between gap-3"><Button className="min-h-11" variant="ghost" disabled={correctionBusy||unresolved} onClick={()=>setSelected(null)}>{t.sessions}</Button>{!codeKind&&<Button className="min-h-11" variant="outline" disabled={busy} onClick={()=>setRefresh(n=>n+1)}>{t.retry}</Button>}</div>
   <header><h2 className="break-words text-2xl font-semibold">{detail.session.title}</h2><p className="mt-2 text-sm text-neutral-600">{attendanceTime(detail.session.starts_at,language,detail.session.timezone)} — {attendanceTime(detail.session.ends_at,language,detail.session.timezone)}</p><p className={`mt-3 rounded-lg p-3 text-sm font-medium ${detail.session.state==='no_class'?'bg-amber-50 text-amber-950':'bg-blue-50 text-blue-950'}`}>{detail.session.state==='no_class'?t.noClass:t.scheduled}</p></header>
   <p role="status" className="text-sm text-neutral-600">{live?t.live:t.reconnecting}</p>
   {detail.manageable&&<>
   {!codeKind&&<><div className="flex flex-wrap gap-3"><Button className="min-h-11" disabled={busy||detail.session.state==='no_class'} onClick={()=>setCodeKind('entry')}>{t.entry}</Button><Button className="min-h-11" variant="outline" disabled={busy||detail.session.state==='no_class'} onClick={()=>setCodeKind('heartbeat')}>{t.heartbeat}</Button></div><p className="max-w-prose text-sm leading-relaxed text-neutral-600">{t.heartbeatHelp} {t.refreshHelp}</p></>}
   <div className="border-t border-neutral-200 pt-4"><Button className="min-h-11" variant="outline" onClick={()=>setChangingState(!changingState)}>{detail.session.state==='no_class'?t.restore:t.markNoClass}</Button></div>
   {changingState&&<form className="max-w-xl space-y-4" onSubmit={e=>{e.preventDefault();void mutate(`/sessions/${selected}/state`,{expected_version:detail.session.version,state:detail.session.state==='no_class'?'scheduled':'no_class',reason},t.done)}}><p className="text-sm leading-relaxed text-neutral-600">{t.stateHelp}</p><label className="flex flex-col gap-2 text-sm font-medium">{t.reason}<Input className="min-h-11" required minLength={5} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)}/></label><Button className="min-h-11" disabled={busy||reason.trim().length<5}>{t.confirmState}</Button></form>}
   <div className={codeKind?attendanceStyles.liveLayout:''}>
   {codeKind&&<AttendanceCode session={detail.session} kind={codeKind} t={t} arrived={arrived} total={total} live={live} onClose={()=>setCodeKind(null)}/>}
   <div className="space-y-4 border-t border-neutral-200 pt-6"><h3 className="text-xl font-semibold">{t.students}</h3><p role="status" className="text-sm tabular-nums">{arrived} / {total} {t.arrived}</p><div className="flex flex-wrap items-end gap-3"><label className="flex min-w-0 flex-1 flex-col gap-2 text-sm font-medium">{t.search}<Input className="min-h-11" value={query} onChange={e=>{setFocusedResult(null);setQuery(e.target.value)}}/></label><select aria-label={t.status} className="min-h-11 max-w-full rounded-lg border border-neutral-300 bg-white px-3 text-sm" value={filter} onChange={e=>{setFocusedResult(null);setFilter(e.target.value)}}><option value="all">{t.filter}</option>{filterStatuses.map(status=><option key={status} value={status}>{attendanceStatus(status,t)}</option>)}</select></div>
   {!detail.students?.length?<p className="text-sm text-neutral-600">{t.noStudents}</p>:!students.length?<div className="space-y-3"><p className="text-sm text-neutral-600">{t.noResults}</p><Button variant="outline" className="min-h-11" onClick={()=>{setFocusedResult(null);setQuery('');setFilter('all')}}>{t.clearFilters}</Button></div>:<div className="divide-y divide-neutral-200">{students.map(student=>{const editing=correction?.entryId===student.roster_entry_id;return <article className={`space-y-4 py-4 ${arrivals.has(student.roster_entry_id)?attendanceStyles.arrival:''}`} key={student.roster_entry_id} data-roster-entry={student.roster_entry_id}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h4 className="break-words text-sm font-semibold">{student.name}</h4><p className="mt-1 text-sm text-neutral-600">{student.student_number||'—'}{student.membership==='withdrawn'?` · ${t.withdrawn}`:''}</p></div><div className="flex flex-wrap items-center justify-end gap-3"><p id={`attendance-result-${student.roster_entry_id}`} tabIndex={-1} className={`${attendanceStyles.result} text-sm font-medium`}>{attendanceStatus(student.effective_status,t)}</p><Button variant="outline" className="min-h-11" aria-expanded={editing} aria-controls={editing?'attendance-correction-editor':undefined} disabled={detail.session.state==='no_class'||Boolean(correction&&!editing)||correctionBusy} onClick={event=>openCorrection(student,event.currentTarget)}>{t.correctAttendance}</Button></div></div>
    <ProjectionEvidence projection={student} t={t} language={language} zone={detail.session.timezone}/>
    {editing&&correction&&<form id="attendance-correction-editor" className="max-w-2xl space-y-4 rounded-lg border border-neutral-300 bg-white p-4" onSubmit={event=>{event.preventDefault();void saveCorrection()}}><h5 className="font-semibold">{t.correctAttendance}: {student.name}</h5><p className="max-w-prose text-sm text-neutral-600">{t.correctionHelp}</p><p className="text-sm">{t.reviewedEvidence}: <strong>{attendanceStatus(correction.reviewedStatus,t)}</strong></p>{correction.reviewedDecision&&<p className="text-sm text-neutral-600">{correction.reviewedDecision.reason} · {attendanceTime(correction.reviewedDecision.decided_at,language,detail.session.timezone)}</p>}
     <label className="flex max-w-sm flex-col gap-2 text-sm font-medium">{t.correctionStatus}<select aria-label={t.correctionStatus} className="min-h-11 rounded-lg border border-neutral-300 bg-white px-3 text-sm" disabled={correctionBusy} value={correction.status} onChange={event=>setCorrection(current=>current?{...current,status:event.target.value}:current)}>{correctionStatuses.map(status=><option key={status} value={status}>{attendanceStatus(status,t)}</option>)}</select></label>
     <label className="flex flex-col gap-2 text-sm font-medium">{t.reason}<Input id="attendance-correction-reason" className="min-h-11" required minLength={5} maxLength={500} disabled={correctionBusy} value={correction.reason} onChange={event=>setCorrection(current=>current?{...current,reason:event.target.value}:current)}/></label>
     {correctionStale&&<div role="status" className="space-y-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-950"><p>{t.staleEvidence}</p>{correctionError&&<p role="alert" className="text-red-800">{correctionError}</p>}<div className="flex flex-wrap gap-3"><Button type="button" variant="outline" className="min-h-11" disabled={correctionBusy||unresolved} onClick={()=>void reloadCorrection()}>{t.reloadReview}</Button><AttendanceRecovery status={correctionErrorStatus} classId={classId} t={t}/></div></div>}
     {correction.unresolved&&<div role="alert" className="space-y-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-950"><p>{t.saveUncertain}</p>{correctionErrorStatus&&<p className="text-red-800">{correctionError}</p>}<p><strong>{t.previousIntent}:</strong> {attendanceStatus(correction.unresolved.status,t)} · {correction.unresolved.reason}</p>{unresolvedChanged&&<p>{t.changedIntent}</p>}<div className="flex flex-wrap gap-3"><Button type="button" variant="outline" className="min-h-11" disabled={correctionBusy} onClick={()=>void persistCorrection(correction.unresolved!)}>{t.retryPrevious}</Button><AttendanceRecovery status={correctionErrorStatus} classId={classId} t={t}/></div></div>}
     {correctionError&&!correctionStale&&!correction.unresolved&&<div role="alert" className="space-y-3"><p className="text-sm text-red-800">{correctionError}</p><AttendanceRecovery status={correctionErrorStatus} classId={classId} t={t}/></div>}
     <div className="flex flex-wrap gap-3"><Button className="min-h-11" loading={correctionBusy} loadingLabel={t.loading} disabled={correctionBusy||correctionStale||unresolved||correction.reason.trim().length<5}>{t.saveCorrection}</Button><Button type="button" variant="ghost" className="min-h-11" disabled={correctionBusy||unresolved} onClick={closeCorrection}>{t.close}</Button></div>
    </form>}
   </article>})}</div>}</div>
   </div>
   <details className="border-t border-neutral-200 pt-4"><summary className="min-h-11 cursor-pointer text-sm font-medium">{t.recent}</summary><ol className="space-y-3 text-xs text-neutral-600">{detail.events?.map(event=><li key={event.id}><p>{attendanceTime(event.created_at,language)} · {event.kind}</p><pre className="mt-1 whitespace-pre-wrap break-words">{JSON.stringify(event.details,null,2)}</pre></li>)}</ol></details>
   </>}
   {!detail.manageable&&detail.own&&<div className="space-y-4"><h3 className="text-xl font-semibold">{t.own}</h3><ProjectionEvidence projection={detail.own} t={t} language={language} zone={detail.session.timezone}/>{detail.own.receipts.length?detail.own.receipts.map(receipt=><Receipt key={receipt.receipt_id} receipt={receipt} t={t} language={language}/>):<p className="text-sm text-neutral-600">{t.emptyReceiptHelp}</p>}</div>}
  </>}
  </div>
 </section>
}
