'use client'

import { useEffect, useRef, useState } from 'react'
import { attendanceRequest, type AttendanceError, type AttendanceText, type Detail } from './attendance-client'

export function useAttendanceStream(id:number|null,t:AttendanceText,receive:(value:Detail)=>void,problem:(error:AttendanceError)=>void,restart=0) {
 const [connected,setConnected]=useState(false)
 const callbacks=useRef({receive,problem})
 useEffect(()=>{callbacks.current={receive,problem}},[receive,problem])
 useEffect(()=>{
  setConnected(false)
  if(id===null)return
  let source:EventSource|null=null,stopped=false,fetching=false,lastMessage=0
  const abort=new AbortController()
  function fail(error:AttendanceError) {
   if(stopped||abort.signal.aborted)return
   callbacks.current.problem(error)
   if(error.status&&[401,403,404,409].includes(error.status)){stopped=true;source?.close();setConnected(false)}
  }
  async function recover(reconnect=false) {
   if(stopped||fetching||document.visibilityState==='hidden')return
   fetching=true
   try{const next=await attendanceRequest<Detail>(`/sessions/${id}`,t,undefined,abort.signal);if(!stopped){callbacks.current.receive(next);if(reconnect)open()}}
   catch(error){fail(error as AttendanceError)}finally{fetching=false}
  }
  function open() {
   source?.close();source=null;lastMessage=0;setConnected(false)
   if(stopped||document.visibilityState==='hidden')return
   source=new EventSource(`/api/v1/attendance/sessions/${id}/events`,{withCredentials:true})
   source.onmessage=event=>{
    if(stopped)return
    try{const next=JSON.parse(event.data) as Detail;if(next.session.id!==id)throw new Error();callbacks.current.receive(next);lastMessage=performance.now();setConnected(true)}
    catch{source?.close();setConnected(false);void recover()}
   }
   source.onerror=()=>{lastMessage=0;setConnected(false);void recover()}
   source.addEventListener('access_lost',event=>{
    source?.close();lastMessage=0;setConnected(false)
    // A fresh request may already have the native session's refreshed cookie.
    void recover(true)
   })
  }
  open()
  // Active-page fallback is recovery, not described as server push.
  const timer=setInterval(()=>{
   if(lastMessage&&performance.now()-lastMessage>20000)open()
   if(!lastMessage||!source||source.readyState!==EventSource.OPEN)void recover(source?.readyState===EventSource.CLOSED)
  },3000)
  document.addEventListener('visibilitychange',open)
  return()=>{stopped=true;abort.abort();source?.close();clearInterval(timer);document.removeEventListener('visibilitychange',open)}
 },[id,t,restart])
 return connected
}
