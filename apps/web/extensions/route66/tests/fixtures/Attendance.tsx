// Real attendance components with synthetic HTTP supplied by the browser harness.
import React from 'react'
import { createRoot } from 'react-dom/client'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import AttendanceWorkspace from '../../components/Objects/Classes/AttendanceWorkspace'
import AttendanceCheckin from '../../components/Objects/Classes/AttendanceCheckin'

const params=new URLSearchParams(location.search)
await i18n.use(initReactI18next).init({lng:params.get('lang')||'en',fallbackLng:'en',resources:{}})

type Listener=(event:{data:string})=>void
const sources=new Set<FixtureEventSource>()
class FixtureEventSource {
 static OPEN=1
 static CLOSED=2
 readyState=FixtureEventSource.OPEN
 onmessage:Listener|null=null
 onerror:(()=>void)|null=null
 listeners=new Map<string,Listener[]>()
 constructor(public url:string) {
  sources.add(this)
  const match=url.match(/\/sessions\/(\d+)\/events/)
  if(match)setTimeout(()=>{void fetch(`/api/v1/attendance/sessions/${match[1]}`,{credentials:'include',cache:'no-store'}).then(response=>response.json()).then(value=>this.onmessage?.({data:JSON.stringify(value)})).catch(()=>this.onerror?.())},0)
 }
 addEventListener(name:string,listener:Listener){this.listeners.set(name,[...(this.listeners.get(name)||[]),listener])}
 close(){this.readyState=FixtureEventSource.CLOSED;sources.delete(this)}
 push(value:unknown){this.onmessage?.({data:JSON.stringify(value)})}
}
;(window as any).EventSource=FixtureEventSource
;(window as any).__attendancePush=(value:unknown)=>sources.forEach(source=>source.push(value))

const surface=params.get('surface')
createRoot(document.getElementById('root')!).render(surface==='receipt'?<AttendanceCheckin receiptId="12345678-1234-4234-8234-123456789012"/>:<AttendanceWorkspace classId={20}/>)
