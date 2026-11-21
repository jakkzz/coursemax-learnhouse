'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { AuthLayout, Button } from '@/extensions/route66/adapters/ui'
import { CopyButton } from '@/extensions/route66/components/interior/CopyButton'
import { finishLine } from '@/extensions/route66/services/auth/line'
import { useAttendanceText } from '@/extensions/route66/components/Objects/Classes/AttendanceWorkspace'
import { attendanceRequest, attendanceReturn, rememberContinuation, forgetContinuation, pendingScan, reserveScan, type AttendanceError } from '@/extensions/route66/components/Objects/Classes/attendance-client'

type LiffSDK = { init:(options:{liffId:string})=>Promise<void>; isLoggedIn:()=>boolean; login:(options:{redirectUri:string})=>void; getIDToken:()=>string|null; openWindow?:(options:{url:string;external:boolean})=>void }
let sdkPromise:Promise<LiffSDK>|null=null
function loadSDK():Promise<LiffSDK> {
 const existing=(window as Window&{liff?:LiffSDK}).liff
 if(existing)return Promise.resolve(existing)
 if(sdkPromise)return sdkPromise
 sdkPromise=new Promise<LiffSDK>((resolve,reject)=>{
  const script=document.createElement('script')
  const timer=window.setTimeout(()=>{script.remove();reject(new Error())},10000)
  script.src='https://static.line-scdn.net/liff/edge/2/sdk.js';script.referrerPolicy='no-referrer'
  script.onload=()=>{window.clearTimeout(timer);const sdk=(window as Window&{liff?:LiffSDK}).liff;if(sdk)resolve(sdk);else reject(new Error())}
  script.onerror=()=>{window.clearTimeout(timer);script.remove();reject(new Error())}
  document.head.appendChild(script)
 }).catch(error=>{sdkPromise=null;throw error})
 return sdkPromise
}

export default function LineAppPage() {
 const {t}=useTranslation(),{t:copy,mounted}=useAttendanceText()
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[unlinked,setUnlinked]=useState(false),[next,setNext]=useState('/home')
 async function open(destination=next,signal?:AbortSignal) {
  setBusy(true);setError('');setUnlinked(false)
  try {
   const start=await fetch('/api/auth/line/liff/start',{method:'POST',credentials:'include',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({return_path:destination})})
   const challenge=await start.json()
   if(!start.ok||typeof challenge.state!=='string'||typeof challenge.liff_id!=='string')throw new Error()
   const liff=await loadSDK();if(signal?.aborted)return
   await liff.init({liffId:challenge.liff_id});if(signal?.aborted)return
   const redirect='/liff'+(destination==='/home'?'':'?next='+encodeURIComponent(destination))
   if(!liff.isLoggedIn()){liff.login({redirectUri:window.location.origin+redirect});return}
   const token=liff.getIDToken();if(!token)throw new Error()
   const response=await fetch('/api/auth/line/liff/session',{method:'POST',credentials:'include',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({state:challenge.state,id_token:token})})
   const result=await response.json()
   if(!response.ok){setUnlinked(result?.detail?.code==='line_link_required');throw new Error()}
   finishLine(result)
  } catch {if(!signal?.aborted){setBusy(false);setError(copy.lineRecovery)}}
 }
 useEffect(()=>{
  if(!mounted)return
  const abort=new AbortController()
  async function resume() {
   const params=new URLSearchParams(window.location.search)
   let destination=attendanceReturn(params.get('next'))
   try {
    // Reserve before SDK initialization, provider consent, or any sign-in wait.
    if(/^[A-Za-z0-9_-]{43}$/.test(window.location.hash.slice(1))) {
     setBusy(true);setNext('/attendance/check-in')
     destination=(await reserveScan(pendingScan(),copy,abort.signal)).return_path
    }
    if(!destination)return
    setNext(destination);rememberContinuation(destination)
    window.history.replaceState(null,'','/liff?next='+encodeURIComponent(destination))
    const handle=new URL(destination,window.location.origin).searchParams.get('handoff')!
    try {
     const result=await attendanceRequest<{receipt:{receipt_id:string}}>('/check-in/complete',copy,{handoff:handle},abort.signal)
     if(!abort.signal.aborted){forgetContinuation();window.location.replace('/attendance/receipts/'+result.receipt.receipt_id)}
    } catch(error) {
     if(abort.signal.aborted)return
     if((error as AttendanceError).signin)await open(destination,abort.signal)
     else throw error
    }
   } catch(error) {if(!abort.signal.aborted){setBusy(false);setError((error as Error).message)}}
  }
  void resume()
  return()=>abort.abort()
 },[mounted])
 const browser=(next==='/home'?'/login?':'/login?next='+encodeURIComponent(next)+'&')+'openExternalBrowser=1'
 return <AuthLayout org={null}><main className="m-auto w-full max-w-md space-y-5 p-6">
  <h1 className="text-2xl font-semibold">{t('auth.line_app_title')}</h1>
  <p className="text-sm leading-relaxed">{t('auth.line_app_description')}</p>
  {!error&&<Button className="min-h-11 w-full" disabled={busy} loading={busy} loadingLabel={t('common.loading')} onClick={()=>void open()}>{t('auth.line_app_continue')}</Button>}
  {error&&<p role="alert" className="text-sm leading-relaxed">{unlinked?copy.lineUnlinked:error}</p>}
  <a href={browser} onClick={event=>{const sdk=(window as Window&{liff?:LiffSDK}).liff;try{if(sdk?.openWindow){sdk.openWindow({url:new URL(browser,window.location.origin).href,external:true});event.preventDefault()}}catch{/* The ordinary link and copied continuation remain usable. */}}} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">{copy.continueBrowser}</a>
  {unlinked&&<Link href="/auth/link/line" className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">{t('auth.line_link_title')}</Link>}
  {next.includes('?handoff=')&&<CopyButton variant="outline" className="min-h-11" value={()=>window.location.origin+next} label={copy.copyContinuation} copiedLabel={copy.continuationCopied} errorLabel={copy.copyError} onError={()=>setError(copy.copyFailed)} />}
 </main></AuthLayout>
}
