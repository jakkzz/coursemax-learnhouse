'use client'

import interior from '@/extensions/route66/components/interior/material.module.css'
import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { Button } from '@/extensions/route66/adapters/ui'
import { Receipt, useAttendanceText } from './AttendanceWorkspace'
import { attendanceRequest, attendanceSignInPath, forgetScan, forgetContinuation, rememberContinuation, handoffHandle, pendingScan, reserveScan, type AttendanceError, type AttendanceReceipt, type Detail } from './attendance-client'
import { useAttendanceStream } from './useAttendanceStream'
import styles from '../Account/subpages/school-identity.module.css'

export default function AttendanceCheckin({receiptId}:{receiptId?:string}) {
 const {t,language,mounted}=useAttendanceText()
 const [receipt,setReceipt]=useState<AttendanceReceipt|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(true),[signin,setSignin]=useState(false),[refresh,setRefresh]=useState(0),[celebrate,setCelebrate]=useState(false)
 const [loginPath,setLoginPath]=useState('/attendance/check-in')
 useEffect(()=>{const changed=()=>{if(/^[A-Za-z0-9_-]{43}$/.test(window.location.hash.slice(1))){setReceipt(null);setCelebrate(false);setRefresh(n=>n+1)}};window.addEventListener('hashchange',changed);return()=>window.removeEventListener('hashchange',changed)},[])
 useEffect(()=>{
  if(!mounted)return
  const abort=new AbortController()
  async function arrive() {
   setBusy(true);setError('');setSignin(false)
   try {
    const savedReceipt=receiptId||(!window.location.hash?new URLSearchParams(window.location.search).get('receipt'):null)
    if(savedReceipt&&/^[a-f0-9-]{36}$/.test(savedReceipt)) {
     setLoginPath('/attendance/receipts/'+savedReceipt)
     setReceipt(await attendanceRequest<AttendanceReceipt>(`/receipts/${encodeURIComponent(savedReceipt)}`,t,undefined,abort.signal))
     return
    }
    let handle=/^[A-Za-z0-9_-]{43}$/.test(window.location.hash.slice(1))?'':handoffHandle(),token=''
    if(!/^[A-Za-z0-9_-]{43}$/.test(handle)) {
     token=pendingScan()
     if(!token)throw new Error(t.invalid)
     try {
      const reserved=await reserveScan(token,t,abort.signal)
      handle=reserved.handoff
      window.history.replaceState(null,'',reserved.return_path)
     } catch(error) {
      if(abort.signal.aborted)throw error
      const issue=error as AttendanceError
      if(issue.status===503||issue.status===410) {
       // A signed-in current scan (or an existing receipt retry) still uses the same writer.
       try {
        const result=await attendanceRequest<{receipt:AttendanceReceipt;created:boolean}>('/check-in',t,{token},abort.signal)
        if(!abort.signal.aborted){forgetScan();forgetContinuation();setReceipt(result.receipt);setCelebrate(result.created);window.history.replaceState(null,'','/attendance/check-in?receipt='+result.receipt.receipt_id)}
        return
       } catch(direct) {
        if((direct as AttendanceError).signin&&issue.status===503){setSignin(true);throw new Error(t.handoffUnavailable)}
        throw issue
       }
      }
      throw issue
     }
    }
    const next='/attendance/check-in?handoff='+handle
    setLoginPath(next);rememberContinuation(next)
    try {
     const result=await attendanceRequest<{receipt:AttendanceReceipt;created:boolean}>('/check-in/complete',t,{handoff:handle},abort.signal)
     if(abort.signal.aborted)return
     setReceipt(result.receipt);setCelebrate(result.created);forgetScan();forgetContinuation()
     window.history.replaceState(null,'','/attendance/check-in?receipt='+result.receipt.receipt_id)
    } catch(error) {
     if((error as AttendanceError).signin&&!abort.signal.aborted){window.location.replace(attendanceSignInPath(next,navigator.userAgent));return}
     throw error
    }
   } catch(error) {
    if(!abort.signal.aborted){const issue=error as AttendanceError;setError(issue.message);if(issue.signin)setSignin(true)}
   } finally {if(!abort.signal.aborted)setBusy(false)}
  }
  void arrive()
  return()=>abort.abort()
 },[mounted,receiptId,refresh,t])
 const receive=useCallback((next:Detail)=>setReceipt(current=>next.own?.receipts.find(value=>value.receipt_id===current?.receipt_id)||current),[])
 const problem=useCallback((issue:AttendanceError)=>{setError(issue.message);setSignin(Boolean(issue.signin))},[])
 const live=useAttendanceStream(receipt?.session_id??null,t,receive,problem,refresh)
 return <section className={`${interior.scope} ${styles.workspace} mx-auto max-w-2xl space-y-6 px-4 pb-24 pt-8 md:px-8`} aria-labelledby="checkin-title">
  <header><h1 className="text-3xl font-semibold" id="checkin-title">{receiptId?t.receipt:t.checkinTitle}</h1><p className="mt-3 text-sm leading-relaxed text-neutral-600">{receiptId?t.receiptHelp:t.checkinHelp}</p></header>
  {error&&<div role="alert" className="space-y-3"><p className="text-sm text-red-800">{error}</p>{signin?<Link className="inline-flex min-h-11 items-center rounded-lg bg-neutral-900 px-4 text-sm font-medium text-white" href={`/login?next=${encodeURIComponent(loginPath)}`}>{t.signin}</Link>:<Button className="min-h-11" variant="outline" onClick={()=>setRefresh(n=>n+1)} disabled={busy}>{t.retry}</Button>}</div>}
  {busy&&<p role="status">{t.waiting}</p>}
  {receipt&&<><Receipt receipt={receipt} t={t} language={language} celebrate={celebrate}/><p role="status" className="text-sm text-neutral-600">{live?t.live:t.reconnecting}</p></>}
  <nav className="flex flex-wrap gap-4" aria-label={t.title}>
   {receipt&&<Link className="inline-flex min-h-11 items-center rounded-lg bg-neutral-900 px-4 text-sm font-medium text-white" href={`/attendance?class=${receipt.class_id}&session=${receipt.session_id}`}>{t.own}</Link>}
   <Link className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/classes">{t.back}</Link>
  </nav>
 </section>
}
