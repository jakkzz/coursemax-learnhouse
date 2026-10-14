'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Button } from '@components/ui/button'
import { Receipt, AttendanceReceipt, attendanceRequest, useAttendanceText } from './AttendanceWorkspace'
import styles from '../Account/subpages/school-identity.module.css'

const pendingKey='lh:pending-attendance-code'
export default function AttendanceCheckin({receiptId}:{receiptId?:string}) {
 const {t,language,mounted}=useAttendanceText()
 const [token,setToken]=useState(''),[receipt,setReceipt]=useState<AttendanceReceipt|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[signin,setSignin]=useState(false),[refresh,setRefresh]=useState(0)
 useEffect(()=>{
  if(!mounted||receiptId)return
  function readCode() {
   const raw=window.location.hash.slice(1)
   if(/^[A-Za-z0-9_-]{43}$/.test(raw)) {
    setToken(raw);setReceipt(null);setError('');setSignin(false)
    try{sessionStorage.setItem(pendingKey,JSON.stringify({token:raw,at:Date.now()}))}catch{}
    window.history.replaceState(null,'',window.location.pathname+window.location.search)
   } else {
    try{const pending=JSON.parse(sessionStorage.getItem(pendingKey)||'null');if(pending&&/^[A-Za-z0-9_-]{43}$/.test(pending.token)&&Date.now()-pending.at<120000&&Date.now()>=pending.at)setToken(pending.token);else sessionStorage.removeItem(pendingKey)}catch{}
   }
  }
  readCode()
  window.addEventListener('hashchange',readCode)
  return()=>window.removeEventListener('hashchange',readCode)
 },[mounted,receiptId])
 useEffect(()=>{
  if(!mounted||!receiptId)return
  const abort=new AbortController();setError('');setBusy(true)
  attendanceRequest<AttendanceReceipt>(`/receipts/${encodeURIComponent(receiptId)}`,t,undefined,abort.signal).then(setReceipt).catch(e=>{if(!abort.signal.aborted){setError(e.message);setSignin(Boolean(e.signin))}}).finally(()=>{if(!abort.signal.aborted)setBusy(false)})
  return()=>abort.abort()
 },[mounted,receiptId,refresh,t])
 async function checkin() {
  setBusy(true);setError('');setSignin(false)
  try{const result=await attendanceRequest<{receipt:AttendanceReceipt}>('/check-in',t,{token});setReceipt(result.receipt);setToken('');try{sessionStorage.removeItem(pendingKey)}catch{}}
  catch(e){const problem=e as Error&{signin?:boolean};setError(problem.message);setSignin(Boolean(problem.signin))}
  finally{setBusy(false)}
 }
 return <section className={`${styles.workspace} mx-auto max-w-2xl space-y-6 px-4 pb-24 pt-8 md:px-8`} aria-labelledby="checkin-title">
  <header><h1 className="text-3xl font-semibold" id="checkin-title">{receiptId?t.receipt:t.checkinTitle}</h1><p className="mt-3 text-sm leading-relaxed text-neutral-600">{receiptId?t.receiptHelp:t.checkinHelp}</p></header>
  {error&&<div role="alert" className="space-y-3"><p className="text-sm text-red-800">{error}</p>{signin?<Link className="inline-flex min-h-11 items-center rounded-lg bg-neutral-900 px-4 text-sm font-medium text-white" href={`/login?next=${encodeURIComponent(receiptId?'/attendance/receipts/'+receiptId:'/attendance/check-in')}`}>{t.signin}</Link>:receiptId?<Button className="min-h-11" variant="outline" onClick={()=>setRefresh(n=>n+1)} disabled={busy}>{t.retry}</Button>:null}</div>}
  {busy&&<p role="status">{t.waiting}</p>}
  {receipt?<Receipt receipt={receipt} t={t} language={language}/>:receiptId?null:token?<Button className="min-h-11" disabled={busy} onClick={()=>void checkin()}>{t.scan}</Button>:mounted?<p role="status" className="text-sm text-neutral-600">{t.invalid}</p>:null}
  <nav className="flex flex-wrap gap-4" aria-label={t.title}>
   {receipt&&<Link className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href={`/attendance?class=${receipt.class_id}`}>{t.own}</Link>}
   <Link className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/classes">{t.back}</Link>
  </nav>
 </section>
}
