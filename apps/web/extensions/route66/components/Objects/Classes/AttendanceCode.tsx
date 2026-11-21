'use client'

import { useEffect, useRef, useState } from 'react'
import { Button, Dialog, DialogContent, DialogDescription, DialogTitle } from '@/extensions/route66/adapters/ui'
import interior from '@/extensions/route66/components/interior/material.module.css'
import { CopyButton } from '@/extensions/route66/components/interior/CopyButton'
import { attendanceRequest, type AttendanceError, type AttendanceText, type Session } from './attendance-client'
import styles from './attendance.module.css'

type Challenge = { checkin_url:string; expires_at:string; server_now:string; session_id:number; session_version:number }
type Display = Challenge & { image:string; validUntil:number }

export default function AttendanceCode({session,kind,t,arrived,total,live,onClose}:{session:Session;kind:string;t:AttendanceText;arrived:number;total:number;live:boolean;onClose:()=>void}) {
 const [display,setDisplay]=useState<Display|null>(null),[clock,setClock]=useState(0),[renewing,setRenewing]=useState(false),[error,setError]=useState(''),[large,setLarge]=useState(false)
 const renew=useRef<()=>void>(()=>{})
 useEffect(()=>{
  let active=true,pending=false,timer:ReturnType<typeof setTimeout>
  const abort=new AbortController()
  setDisplay(null);setError('')
  async function next() {
   if(!active||pending)return
   clearTimeout(timer);pending=true;setRenewing(true)
   try {
    const sent=performance.now()
    const code=await attendanceRequest<Challenge>(`/sessions/${session.id}/open`,t,{kind},abort.signal)
    const qr=await import('qrcode')
    const image=await qr.toDataURL(code.checkin_url,{width:768,margin:4,errorCorrectionLevel:'M'})
    const decoded=new Image();decoded.src=image;await decoded.decode()
    if(!active)return
    if(code.session_id!==session.id||code.session_version!==session.version)throw new Error(t.conflict)
    // Server-relative, conservative lifetime also works with a mis-set projector clock.
    const validUntil=sent+Math.min(new Date(code.expires_at).getTime(),new Date(session.ends_at).getTime())-new Date(code.server_now).getTime()
    if(!Number.isFinite(validUntil))throw new Error(t.failed)
    setClock(performance.now());setDisplay({...code,image,validUntil});setError('')
    timer=setTimeout(()=>void next(),Math.max(1000,Math.min(60000,validUntil-performance.now()-30000)))
   } catch(error) {
    if(!active||abort.signal.aborted)return
    const issue=error as AttendanceError
    setError(issue.message)
    if(!issue.status||issue.status>=500||issue.status===429)timer=setTimeout(()=>void next(),5000)
   } finally {pending=false;if(active)setRenewing(false)}
  }
  renew.current=()=>void next()
  void next()
  const tick=setInterval(()=>setClock(performance.now()),250)
  return()=>{active=false;abort.abort();clearTimeout(timer);clearInterval(tick)}
 },[session.id,session.version,kind,t])
 const seconds=display?Math.max(0,Math.floor((display.validUntil-clock)/1000)):0
 const stage=(projector=false)=><div className={`${styles.stage} ${projector?styles.projectorStage:''}`} aria-busy={!display&&renewing}>
  {display&&seconds>0?<img src={display.image} width={768} height={768} alt={t.scan} className={styles.qr}/>:<p role="status">{renewing?t.loading:error||t.codeExpired}</p>}
 </div>
 const summary=<p role="status" className="text-sm tabular-nums">{arrived} / {total} {t.arrived} · {live?t.live:t.reconnecting}</p>
 return <>
  <div className="space-y-4 text-center">
   <h3 className="text-xl font-semibold">{kind==='entry'?t.entry:t.heartbeat}</h3>
   {stage()}
   <p className="text-sm tabular-nums">{seconds>0?`${seconds} ${t.remaining}`:t.codeExpired} · {renewing?t.renewing:t.automaticRenewal}</p>
   {error&&<p role="alert" className="text-sm text-red-800">{error}</p>}
   <p className="mx-auto max-w-prose text-sm leading-relaxed text-neutral-600">{t.scanHelp}</p>
   {summary}
   <div className="flex flex-wrap justify-center gap-3">
    <Button className="min-h-11" onClick={()=>setLarge(true)}>{t.projector}</Button>
    <CopyButton className="min-h-11" variant="outline" disabled={!seconds} value={display?.checkin_url??''} label={t.copy} copiedLabel={t.continuationCopied} errorLabel={t.copyError} onCopy={()=>setError('')} onError={()=>setError(t.copyFailed)} />
    <Button className="min-h-11" variant="ghost" disabled={renewing} onClick={()=>renew.current()}>{t.renew}</Button>
    <Button className="min-h-11" variant="ghost" onClick={onClose}>{t.closeCode}</Button>
   </div>
  </div>
  <Dialog open={large} onOpenChange={setLarge}>
   <DialogContent className={`${interior.scope} ${styles.projector}`}>
    <DialogTitle>{session.title}</DialogTitle>
    <DialogDescription>{t.scanHelp}</DialogDescription>
    {stage(true)}
    {summary}
    <p role="status" className="text-sm">{error||(!seconds?t.codeExpired:renewing?t.renewing:t.automaticRenewal)}</p>
    <Button className="min-h-11 justify-self-center" variant="outline" onClick={()=>setLarge(false)}>{t.exitProjector}</Button>
   </DialogContent>
  </Dialog>
 </>
}
