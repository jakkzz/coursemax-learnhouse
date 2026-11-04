import { attendanceCopy } from './attendance-copy'

export type AttendanceText = typeof attendanceCopy.en
export type AttendanceDecision = { id:number; status:string; reason:string; request_id:string; previous_decision_id:number|null; actor_user_id:number; decided_at:string }
export type AttendanceReceipt = { receipt_id:string; session_id:number; class_id:number; session_title:string; arrived_at:string; kind:string; computed_status:string; effective_status:string; decision:AttendanceDecision|null; session_state:string; starts_at:string; ends_at:string; timezone:string }
export type Session = { id:number; class_id:number; title:string; starts_at:string; ends_at:string; timezone:string; state:string; version:number; grace_minutes:number; late_threshold_minutes:number }
export type Projection = { status:string; effective_status:string; evidence_token:string; decision:AttendanceDecision|null; first_arrived_at:string|null; last_heartbeat_at:string|null; receipts:AttendanceReceipt[] }
export type Student = Projection & { roster_entry_id:number; name:string; student_number:string|null; membership:string }
export type Detail = { session:Session; manageable:boolean; own?:Projection; students?:Student[]; cursor:string; events?:{id:number;kind:string;created_at:string;details:Record<string,unknown>}[] }
export type AttendanceCoverage = { session_count:number; known_denominator:number; unknown_membership:number; uncollected:number; not_eligible:number; no_class:number; incomplete:number; status:'complete'|'partial'|'none' }
export type AttendanceSummary = { total_sessions:number; present:number; late:number; absent:number; excused:number; percent:number|null; at_risk:boolean|null }
export type AttendanceMember = { roster_entry_id:number; student_number:string|null; name:string; membership:string }
export type AttendanceMemberSummary = AttendanceMember & { summary:AttendanceSummary; coverage:AttendanceCoverage; risk:'at_risk'|'not_at_risk'|'unknown' }
export type AttendanceHistoryRow = Projection & { session:Session; membership_at_session:string; collected:boolean; decisions:AttendanceDecision[] }
export type ClassAttendanceSummary = { class_id:number; as_of:string; range:{from:string|null;to:string|null}; coverage_description:string; members:AttendanceMemberSummary[] }
export type AttendanceHistory = { class_id:number; as_of:string; member:AttendanceMember; history:AttendanceHistoryRow[]; next_before:string|null }
export type OwnAttendance = AttendanceHistory & { range:{from:string|null;to:string|null}; coverage_description:string; summary:AttendanceSummary; coverage:AttendanceCoverage; risk:'at_risk'|'not_at_risk'|'unknown' }
export type DecisionResult = { decision:AttendanceDecision; projection:Projection; retried:boolean }
export type AttendanceError = Error & { signin?:boolean; status?:number; code?:string; currentToken?:string }
export type PreparedScan = { handoff:string; expires_at:string; return_path:string }
const pendingKey = 'lh:pending-attendance-code'
const continuationKey = 'lh:attendance-continuation'
const opaque = /^[A-Za-z0-9_-]{43}$/

function errorMessage(path:string,response:Response,code:string|undefined,t:AttendanceText) {
 return code==='handoff_claimed'?t.handoffClaimed:code==='entry_cutoff'?t.entryCutoff:code==='handoff_unavailable'?t.handoffUnavailable:code==='no_class'?t.noClassClosed:code==='not_open'?t.notOpen:code==='ended'?t.ended:code==='stale_evidence'?t.staleEvidence:code==='request_id_collision'?t.requestCollision:code==='future_session'?t.futureCorrection:response.status===401||response.status===403?t.denied:response.status===410?t.expired:response.status===409?t.conflict:response.status===404?(path.startsWith('/receipts/')?t.receiptMissing:t.invalid):t.failed
}
async function attendanceResponse(path:string,t:AttendanceText,body?:unknown,signal?:AbortSignal) {
 const response=await fetch('/api/v1/attendance'+path,{credentials:'include',cache:'no-store',signal,method:body===undefined?'GET':'POST',headers:body===undefined?undefined:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)})
 if (!response.ok) {
  const data=await response.json().catch(()=>null),code=data?.detail?.code
  throw Object.assign(new Error(errorMessage(path,response,code,t)),{signin:response.status===401,status:response.status,code,currentToken:data?.detail?.current_token})
 }
 return response
}
export async function attendanceRequest<T>(path:string,t:AttendanceText,body?:unknown,signal?:AbortSignal):Promise<T> {
 return (await attendanceResponse(path,t,body,signal)).json()
}
export async function attendanceDownload(path:string,t:AttendanceText,signal?:AbortSignal) {
 return (await attendanceResponse(path,t,undefined,signal)).blob()
}

// Only a same-origin continuation crosses browser contexts, never OAuth state/cookies.
export function attendanceEntryPath(path:string|null) { return /^\/(?:orgs\/[^/]+\/)?attendance\/check-in\/?$/.test(path||'') }
export function attendanceReturn(value:string|null,origin=window.location.origin) {
 if (!value) return null
 try {
  const url=new URL(value,origin)
  const handle=url.searchParams.get('handoff')
  if(url.origin===origin&&url.pathname==='/attendance/check-in'&&handle&&opaque.test(handle)&&!url.hash)
   return '/attendance/check-in?handoff='+handle
 } catch {}
 return null
}

export function attendanceSignInPath(path:string,userAgent:string) {
 return (/\bLine\//i.test(userAgent)?'/liff':'/login')+'?next='+encodeURIComponent(path)
}

export function attendanceLoginDestination(value:string|null,origin:string) {
 return attendanceReturn(value,origin)||(/^\/attendance\/receipts\/[a-f0-9-]{36}$/.test(value||'')?value:null)
}

export function rememberContinuation(path:string) {
 if(!attendanceReturn(path))return
 try{sessionStorage.setItem(continuationKey,JSON.stringify({path,at:Date.now()}))}catch{}
}
export function forgetContinuation() { try{sessionStorage.removeItem(continuationKey)}catch{} }
export function attendanceRetryLogin() {
 if(typeof window==='undefined')return '/login'
 try {
  const saved=JSON.parse(sessionStorage.getItem(continuationKey)||'null')
  const path=attendanceReturn(saved?.path)
  if(path&&Date.now()>=saved.at&&Date.now()-saved.at<1200000)return '/login?next='+encodeURIComponent(path)
 }catch{}
 return '/login'
}

export function pendingScan() {
 const raw=window.location.hash.slice(1)
 if(opaque.test(raw)) {
  try{sessionStorage.setItem(pendingKey,JSON.stringify({token:raw,at:Date.now()}))}catch{}
  window.history.replaceState(null,'',window.location.pathname+window.location.search)
  return raw
 }
 try {
  const pending=JSON.parse(sessionStorage.getItem(pendingKey)||'null')
  if(pending&&typeof pending.token==='string'&&typeof pending.at==='number'&&opaque.test(pending.token)&&Date.now()-pending.at<120000&&Date.now()>=pending.at)return pending.token as string
  sessionStorage.removeItem(pendingKey)
 } catch {}
 return ''
}
export function forgetScan() { try{sessionStorage.removeItem(pendingKey)}catch{} }
export function handoffHandle() { return new URLSearchParams(window.location.search).get('handoff') || '' }
export async function reserveScan(token:string,t:AttendanceText,signal?:AbortSignal) {
 const result=await attendanceRequest<PreparedScan>('/check-in/prepare',t,{token},signal)
 if(!opaque.test(result.handoff)||attendanceReturn(result.return_path)!==result.return_path)throw new Error(t.failed)
 forgetScan();rememberContinuation(result.return_path)
 return result
}
