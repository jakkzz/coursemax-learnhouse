'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { Button, Input } from '@/extensions/route66/adapters/ui'
import { attendanceDownload, attendanceRequest, attendanceSignInPath, type AttendanceCoverage, type AttendanceError, type AttendanceHistory, type AttendanceHistoryRow, type AttendanceMemberSummary, type AttendanceSummary, type AttendanceText, type ClassAttendanceSummary, type OwnAttendance } from './attendance-client'
import { attendanceMembership, attendanceStatus, attendanceTime } from './attendance-format'

const reportStatuses=['present','late','absent','excused','unrecorded','unknown','not_eligible','no_class','upcoming']
type Range={from:string;to:string}

function query(range:Range,before?:string) {
 const values=new URLSearchParams()
 if(range.from)values.set('from',range.from)
 if(range.to)values.set('to',range.to)
 if(before)values.set('before',before)
 const suffix=values.toString()
 return suffix?'?'+suffix:''
}
function coverageLabel(value:AttendanceCoverage['status'],t:AttendanceText) { return value==='complete'?t.coverageComplete:value==='partial'?t.coveragePartial:t.coverageNone }
function riskLabel(value:string,t:AttendanceText) { return value==='at_risk'?t.atRisk:value==='not_at_risk'?t.notAtRisk:t.riskUnknown }
function percent(value:number|null) { return value===null?'—':`${value.toFixed(2)}%` }
function reportPath(classId:number) {
 if(typeof window==='undefined')return `/attendance?class=${classId}`
 return window.location.pathname.includes('/attendance')?window.location.pathname+window.location.search:`/attendance?class=${classId}`
}
function ReportRecovery({status,classId,t}:{status:number|null;classId:number;t:AttendanceText}) {
 if(status===401)return <Link className="inline-flex min-h-11 items-center rounded-lg bg-neutral-900 px-4 text-sm font-medium text-white" href={attendanceSignInPath(reportPath(classId),typeof navigator==='undefined'?'':navigator.userAgent)}>{t.signin}</Link>
 if(status===403)return <Link className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/classes">{t.back}</Link>
 return null
}

function RangeFields({range,setRange,apply,error,t,busy=false}:{range:Range;setRange:(value:Range)=>void;apply:()=>void;error:string;t:AttendanceText;busy?:boolean}) {
 return <div className="space-y-3">
  <div className="grid gap-3 sm:grid-cols-2">
   <label className="flex flex-col gap-2 text-sm font-medium">{t.fromDate}<Input className="min-h-11" type="date" value={range.from} onChange={event=>setRange({...range,from:event.target.value})}/></label>
   <label className="flex flex-col gap-2 text-sm font-medium">{t.toDate}<Input className="min-h-11" type="date" value={range.to} onChange={event=>setRange({...range,to:event.target.value})}/></label>
  </div>
  {error&&<p role="alert" className="text-sm text-red-800">{error}</p>}
  <Button variant="outline" className="min-h-11" disabled={busy||Boolean(error)} onClick={apply}>{t.applyRange}</Button>
 </div>
}

function SummaryValues({summary,coverage,risk,t}:{summary:AttendanceSummary;coverage:AttendanceCoverage;risk:string;t:AttendanceText}) {
 const values:Array<[string,string|number]>=[
  [t.totalSessions,summary.total_sessions],[t.knownDenominator,coverage.known_denominator],[t.present,summary.present],[t.late,summary.late],[t.absent,summary.absent],[t.excused,summary.excused],[t.percentage,percent(summary.percent)],[t.coverage,coverageLabel(coverage.status,t)],[t.risk,riskLabel(risk,t)],
 ]
 return <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
  {values.map(([label,value])=><div key={label}><dt className="text-xs font-medium text-neutral-600">{label}</dt><dd className="mt-1 font-semibold tabular-nums">{value}</dd></div>)}
  <div><dt className="text-xs font-medium text-neutral-600">{t.unknownMembership}</dt><dd className="mt-1 tabular-nums">{coverage.unknown_membership}</dd></div>
  <div><dt className="text-xs font-medium text-neutral-600">{t.uncollected}</dt><dd className="mt-1 tabular-nums">{coverage.uncollected}</dd></div>
  <div><dt className="text-xs font-medium text-neutral-600">{t.notEligibleCount}</dt><dd className="mt-1 tabular-nums">{coverage.not_eligible}</dd></div>
  <div><dt className="text-xs font-medium text-neutral-600">{t.noClassCount}</dt><dd className="mt-1 tabular-nums">{coverage.no_class}</dd></div>
  <div><dt className="text-xs font-medium text-neutral-600">{t.incomplete}</dt><dd className="mt-1 tabular-nums">{coverage.incomplete}</dd></div>
 </dl>
}

function DecisionDetails({row,t,language}:{row:AttendanceHistoryRow;t:AttendanceText;language:string}) {
 if(!row.decision)return null
 return <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
  <p className="font-medium">{t.correction}: {attendanceStatus(row.decision.status,t)}</p>
  <p className="mt-1">{t.correctionReason}: {row.decision.reason}</p>
  <p className="mt-1 tabular-nums">{t.correctionTime}: {attendanceTime(row.decision.decided_at,language,row.session.timezone)}</p>
 </div>
}

function HistoryRows({rows,nextBefore,loading,error,retry,loadMore,t,language}:{rows:AttendanceHistoryRow[];nextBefore:string|null;loading:boolean;error:string;retry:()=>void;loadMore:()=>void;t:AttendanceText;language:string}) {
 const [filter,setFilter]=useState('all')
 const visible=rows.filter(row=>filter==='all'||row.effective_status===filter)
 return <div className="space-y-4">
  <label className="flex max-w-sm flex-col gap-2 text-sm font-medium">{t.historyStatus}<select aria-label={t.historyStatus} className="min-h-11 rounded-lg border border-neutral-300 bg-white px-3 text-sm" value={filter} onChange={event=>setFilter(event.target.value)}><option value="all">{t.allHistoryStatuses}</option>{reportStatuses.map(status=><option key={status} value={status}>{attendanceStatus(status,t)}</option>)}</select></label>
  {error&&<div role="alert" className="space-y-3"><p className="text-sm text-red-800">{error}</p><Button variant="outline" className="min-h-11" disabled={loading} onClick={retry}>{t.retry}</Button></div>}
  {!rows.length&&!loading&&!error?<p className="text-sm text-neutral-600">{t.noHistory}</p>:!visible.length&&!loading?<div className="space-y-3"><p className="text-sm text-neutral-600">{t.noHistoryMatches}</p><Button variant="outline" className="min-h-11" onClick={()=>setFilter('all')}>{t.clearFilters}</Button></div>:null}
  <div className="divide-y divide-neutral-200 border-y border-neutral-200">
   {visible.map(row=>{const receipt=row.receipts[0];return <article key={row.session.id} className="space-y-4 py-5" data-history-session={row.session.id}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="font-semibold">{row.session.title}</h4><p className="mt-1 text-sm text-neutral-600 tabular-nums">{attendanceTime(row.session.starts_at,language,row.session.timezone)}</p></div><p className="text-sm font-semibold">{attendanceStatus(row.effective_status,t)}</p></div>
    <dl className="grid gap-3 text-sm sm:grid-cols-3">
     <div><dt className="text-xs font-medium text-neutral-600">{t.currentResult}</dt><dd className="mt-1 font-medium">{attendanceStatus(row.effective_status,t)}</dd></div>
     <div><dt className="text-xs font-medium text-neutral-600">{t.recordedArrival}</dt><dd className="mt-1 tabular-nums">{receipt?attendanceTime(receipt.arrived_at,language,row.session.timezone):t.noRecordedScan}</dd>{receipt&&<dd className="mt-1 text-neutral-600">{attendanceStatus(receipt.computed_status,t)}</dd>}</div>
     <div><dt className="text-xs font-medium text-neutral-600">{t.membershipAtSession}</dt><dd className="mt-1">{attendanceMembership(row.membership_at_session,t)} · {row.collected?t.collected:t.collectionUnknown}</dd></div>
    </dl>
    <DecisionDetails row={row} t={t} language={language}/>
    {row.decisions.length>1&&<details><summary className="min-h-11 cursor-pointer text-sm font-medium">{t.decisionHistory} ({row.decisions.length})</summary><ol className="mt-2 space-y-2 text-sm text-neutral-600">{row.decisions.map(decision=><li key={decision.id}>{attendanceStatus(decision.status,t)} · {decision.reason} · <span className="tabular-nums">{attendanceTime(decision.decided_at,language,row.session.timezone)}</span></li>)}</ol></details>}
   </article>})}
  </div>
  {loading&&<p role="status" className="text-sm text-neutral-600">{t.loadingHistory}</p>}
  {nextBefore&&!error&&<Button variant="outline" className="min-h-11" disabled={loading} onClick={loadMore}>{t.loadMore}</Button>}
 </div>
}

function TeacherReports({classId,active,t,language}:{classId:number;active:boolean;t:AttendanceText;language:string}) {
 const [range,setRange]=useState<Range>({from:'',to:''}),[applied,setApplied]=useState<Range>({from:'',to:''})
 const [summary,setSummary]=useState<ClassAttendanceSummary|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState(''),[reload,setReload]=useState(0),[accessStatus,setAccessStatus]=useState<number|null>(null)
 const [search,setSearch]=useState(''),[member,setMember]=useState<AttendanceMemberSummary|null>(null),[history,setHistory]=useState<AttendanceHistoryRow[]>([]),[nextBefore,setNextBefore]=useState<string|null>(null),[historyError,setHistoryError]=useState(''),[historyLoading,setHistoryLoading]=useState(false),[historyRetry,setHistoryRetry]=useState<string|undefined>()
 const [downloadError,setDownloadError]=useState(''),[downloading,setDownloading]=useState(false),historySequence=useRef(0)
 const rangeError=range.from&&range.to&&range.from>range.to?t.rangeInvalid:''
 function clearPrivileged() {historySequence.current++;setSummary(null);setMember(null);setHistory([]);setNextBefore(null);setHistoryError('');setHistoryRetry(undefined);setHistoryLoading(false);setDownloadError('')}
 function failure(issue:unknown,fallback:string) {const problem=issue as AttendanceError;if(problem.status===401||problem.status===403){clearPrivileged();setAccessStatus(problem.status);return problem.status===403?t.accessLost:problem.message||fallback}return problem.message||fallback}
 useEffect(()=>{if(!active)return;const abort=new AbortController();setLoading(true);setError('');setAccessStatus(null);attendanceRequest<ClassAttendanceSummary>(`/classes/${classId}/summary${query(applied)}`,t,undefined,abort.signal).then(value=>{setSummary(value);setAccessStatus(null)}).catch(issue=>{if(!abort.signal.aborted)setError(failure(issue,t.summaryFailed))}).finally(()=>{if(!abort.signal.aborted)setLoading(false)});return()=>abort.abort()},[active,applied,classId,reload,t])
 useEffect(()=>()=>{historySequence.current++},[active,classId])
 async function loadHistory(target:AttendanceMemberSummary,before?:string) {
  const sequence=++historySequence.current;setMember(target);setHistoryLoading(true);setHistoryError('');setHistoryRetry(before);setAccessStatus(null);if(!before){setHistory([]);setNextBefore(null)}
  try {const suffix=new URLSearchParams({roster_entry_id:String(target.roster_entry_id)});if(before)suffix.set('before',before);const result=await attendanceRequest<AttendanceHistory>(`/classes/${classId}/history?${suffix}`,t);if(sequence!==historySequence.current)return;setHistory(previous=>before?[...previous,...result.history]:result.history);setNextBefore(result.next_before)}
  catch(issue){if(sequence!==historySequence.current)return;const problem=issue as AttendanceError,message=failure(problem,t.historyFailed);if(problem.status===401||problem.status===403)setError(message);else setHistoryError(message)}finally{if(sequence===historySequence.current)setHistoryLoading(false)}
 }
 async function download() {
  setDownloading(true);setDownloadError('');setAccessStatus(null)
  try {const blob=await attendanceDownload(`/classes/${classId}/summary.csv${query(applied)}`,t),url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download='attendance-summary.csv';document.body.append(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),0)}
  catch(issue){const problem=issue as AttendanceError;if(problem.status===401||problem.status===403)setError(failure(problem,t.downloadFailed));else setDownloadError(t.downloadFailed)}finally{setDownloading(false)}
 }
 const members=summary?.members.filter(value=>`${value.name} ${value.student_number||''}`.toLowerCase().includes(search.trim().toLowerCase()))||[]
 return <section className="space-y-6" aria-labelledby="attendance-summary-title">
  <header><h2 id="attendance-summary-title" className="text-2xl font-semibold">{t.summaryTitle}</h2><p className="mt-2 max-w-prose text-sm text-neutral-600">{t.classReportHelp}</p></header>
  <RangeFields range={range} setRange={setRange} apply={()=>setApplied({...range})} error={rangeError} t={t} busy={loading}/>
  <div className="flex flex-wrap gap-3"><Button className="min-h-11" disabled={downloading||loading||!summary} loading={downloading} loadingLabel={t.loading} onClick={()=>void download()}>{t.downloadCsv}</Button>{downloadError&&<Button variant="outline" className="min-h-11" disabled={downloading} onClick={()=>void download()}>{t.retryDownload}</Button>}</div>
  {downloadError&&<p role="alert" className="text-sm text-red-800">{downloadError}</p>}
  {error&&<div role="alert" className="space-y-3"><p className="text-sm text-red-800">{error}</p><div className="flex flex-wrap gap-3"><Button variant="outline" className="min-h-11" disabled={loading} onClick={()=>setReload(value=>value+1)}>{t.retry}</Button><ReportRecovery status={accessStatus} classId={classId} t={t}/></div></div>}
  {loading&&!summary&&<p role="status">{t.loadingSummary}</p>}
  {summary&&<><p className="max-w-prose text-sm text-neutral-600">{t.coverageHelp}</p><p className="text-xs text-neutral-600 tabular-nums">{t.asOf}: {attendanceTime(summary.as_of,language)}</p>
   <label className="flex max-w-lg flex-col gap-2 text-sm font-medium">{t.memberSearch}<Input className="min-h-11" value={search} onChange={event=>setSearch(event.target.value)}/></label>
   {!summary.members.length?<p className="text-sm text-neutral-600">{t.noSummaryMembers}</p>:!members.length?<div className="space-y-3"><p className="text-sm text-neutral-600">{t.noSummaryMatches}</p><Button variant="outline" className="min-h-11" onClick={()=>setSearch('')}>{t.clearFilters}</Button></div>:<div className="divide-y divide-neutral-200 border-y border-neutral-200" data-summary-members>
    {members.map(value=><article key={value.roster_entry_id} className="space-y-4 py-5" data-summary-member={value.roster_entry_id}><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">{value.name}</h3><p className="mt-1 text-sm text-neutral-600">{value.student_number||'—'} · {attendanceMembership(value.membership,t)}</p></div><Button variant="outline" className="min-h-11" aria-pressed={member?.roster_entry_id===value.roster_entry_id} onClick={()=>void loadHistory(value)}>{t.viewHistory}</Button></div><SummaryValues summary={value.summary} coverage={value.coverage} risk={value.risk} t={t}/></article>)}
   </div>}
  </>}
  {member&&<section className="space-y-4 border-t border-neutral-300 pt-6" aria-labelledby="member-history-title"><header><h3 id="member-history-title" className="text-xl font-semibold">{t.memberHistory}: {member.name}</h3><p className="mt-1 text-sm text-neutral-600">{member.student_number||'—'} · {attendanceMembership(member.membership,t)}</p></header><HistoryRows rows={history} nextBefore={nextBefore} loading={historyLoading} error={historyError} retry={()=>void loadHistory(member,historyRetry)} loadMore={()=>void loadHistory(member,nextBefore||undefined)} t={t} language={language}/></section>}
 </section>
}

function OwnReports({classId,active,t,language}:{classId:number;active:boolean;t:AttendanceText;language:string}) {
 const [range,setRange]=useState<Range>({from:'',to:''}),[applied,setApplied]=useState<Range>({from:'',to:''})
 const [report,setReport]=useState<OwnAttendance|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState(''),[retryBefore,setRetryBefore]=useState<string|undefined>(),[accessStatus,setAccessStatus]=useState<number|null>(null)
 const rangeError=range.from&&range.to&&range.from>range.to?t.rangeInvalid:''
 async function load(before?:string,signal?:AbortSignal) {
  setLoading(true);setError('');setRetryBefore(before);setAccessStatus(null)
  try {const result=await attendanceRequest<OwnAttendance>(`/classes/${classId}/own${query(applied,before)}`,t,undefined,signal);setReport(previous=>before&&previous?{...result,history:[...previous.history,...result.history]}:result);setRetryBefore(undefined)}
  catch(issue){if(!signal?.aborted){const problem=issue as AttendanceError;if(problem.status===401||problem.status===403){setReport(null);setAccessStatus(problem.status)}setError(problem.status===403?t.accessLost:problem.message||t.historyFailed)}}finally{if(!signal?.aborted)setLoading(false)}
 }
 useEffect(()=>{if(!active)return;const abort=new AbortController();void load(undefined,abort.signal);return()=>abort.abort()},[active,applied,classId,t])
 function apply(){setRetryBefore(undefined);setApplied({...range})}
 function loadMore(){if(report?.next_before)void load(report.next_before)}
 return <section className="space-y-6" aria-label={t.myAttendance}>
  <header><h2 id="own-attendance-title" className="text-2xl font-semibold">{t.ownSummaryTitle}</h2><p className="mt-2 max-w-prose text-sm text-neutral-600">{t.reportHelp}</p></header>
  <RangeFields range={range} setRange={setRange} apply={apply} error={rangeError} t={t} busy={loading}/>
  {error&&<div role="alert" className="space-y-3"><p className="text-sm text-red-800">{error}</p><div className="flex flex-wrap gap-3"><Button variant="outline" className="min-h-11" disabled={loading} onClick={()=>void load(retryBefore)}>{t.retry}</Button><ReportRecovery status={accessStatus} classId={classId} t={t}/></div></div>}
  {loading&&!report&&<p role="status">{t.loadingSummary}</p>}
  {report&&<><section className="space-y-4 rounded-lg border border-neutral-200 bg-white p-4" aria-label={t.ownSummaryTitle}><div><h3 className="font-semibold">{report.member.name}</h3><p className="mt-1 text-sm text-neutral-600">{report.member.student_number||'—'} · {attendanceMembership(report.member.membership,t)}</p></div><SummaryValues summary={report.summary} coverage={report.coverage} risk={report.risk} t={t}/><p className="max-w-prose text-sm text-neutral-600">{t.coverageHelp}</p><p className="text-xs text-neutral-600 tabular-nums">{t.asOf}: {attendanceTime(report.as_of,language)}</p></section>
   <section className="space-y-4" aria-labelledby="own-history-title"><h3 id="own-history-title" className="text-xl font-semibold">{t.history}</h3><HistoryRows rows={report.history} nextBefore={report.next_before} loading={loading} error="" retry={()=>void load(retryBefore)} loadMore={loadMore} t={t} language={language}/></section>
  </>}
 </section>
}

export default function AttendanceReports({classId,manageable,active,t,language}:{classId:number;manageable:boolean;active:boolean;t:AttendanceText;language:string}) {
 return manageable?<TeacherReports classId={classId} active={active} t={t} language={language}/>:<OwnReports classId={classId} active={active} t={t} language={language}/>
}
