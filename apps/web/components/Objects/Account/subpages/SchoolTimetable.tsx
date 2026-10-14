'use client'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@components/ui/button'

type Timetable = { academic_year:number;semester:number;fetched_at:string;classes:{registry_course_id:string;course_code:string;title:string;section:string;meetings:{day:string;start_time:string;end_time:string;details:string}[]}[] }
export default function SchoolTimetable({ staffId }: { staffId:string }) {
 const {i18n}=useTranslation();const th=i18n.language.startsWith('th')
 const t=th?{title:'ชั้นเรียนตามทะเบียนมหาวิทยาลัย',note:'อ่านข้อมูลจากทะเบียนเท่านั้น ยังไม่ใช่รายวิชาที่มอบหมายในระบบนี้ การจับคู่รายวิชาจะไม่เกิดขึ้นโดยอัตโนมัติ',year:'ปีการศึกษา',term:'ภาคเรียน',loading:'กำลังดึงตารางสอน…',error:'ดึงตารางสอนไม่ได้ โปรดลองอีกครั้ง',retry:'ลองอีกครั้ง',empty:'ทะเบียนไม่แสดงชั้นเรียนในภาคเรียนที่เลือก',asof:'ดึงข้อมูลเมื่อ',section:'กลุ่มเรียน'}:{title:'NRRU registrar classes',note:'Read-only registrar data, not courses assigned in LearnHouse. Course matching never happens automatically.',year:'Academic year (Buddhist Era)',term:'Semester',loading:'Loading registrar timetable…',error:'The registrar timetable could not be loaded. Try again.',retry:'Try again',empty:'No classes returned by the registrar for this semester',asof:'Fetched',section:'Section'}
 const [data,setData]=useState<Timetable|null>(null),[selection,setSelection]=useState<{year:number;semester:number}|null>(null),[error,setError]=useState(false),[busy,setBusy]=useState(true),[attempt,setAttempt]=useState(0)
 useEffect(()=>{const c=new AbortController();let active=true;setBusy(true);setError(false);setData(null)
  const timeout=setTimeout(()=>{if(active){setError(true);setBusy(false)}c.abort()},12000)
  const query=selection?`?academic_year=${selection.year}&semester=${selection.semester}`:''
  fetch('/api/v1/school-identity/timetable'+query,{credentials:'include',cache:'no-store',signal:c.signal}).then(async r=>{if(!r.ok)throw Error();const value=await r.json();if(active)setData(value)}).catch(()=>{if(active)setError(true)}).finally(()=>{clearTimeout(timeout);if(active)setBusy(false)})
  return()=>{active=false;clearTimeout(timeout);c.abort()}
 },[staffId,selection,attempt])
 const currentYear=new Date().getFullYear()+543
 const chosenYear=selection?.year??data?.academic_year??currentYear, chosenSemester=selection?.semester??data?.semester??1
 return <section className="space-y-4 border-t border-neutral-200 pt-6" aria-labelledby="registrar-title">
  <div><h2 id="registrar-title" className="text-lg font-semibold">{t.title}</h2><p className="mt-2 max-w-prose text-sm leading-relaxed text-neutral-600">{t.note}</p></div>
  {(data||selection)&&<div className="flex flex-wrap gap-4"><label className="flex flex-col gap-1 text-xs font-medium">{t.year}<select className="min-h-11 rounded-lg border border-neutral-200 bg-white px-3 text-sm" value={chosenYear} onChange={e=>setSelection({year:Number(e.target.value),semester:chosenSemester})}>{[currentYear-1,currentYear,currentYear+1].map(year=><option key={year} value={year}>{year}</option>)}</select></label><label className="flex flex-col gap-1 text-xs font-medium">{t.term}<select className="min-h-11 rounded-lg border border-neutral-200 bg-white px-3 text-sm" value={chosenSemester} onChange={e=>setSelection({year:chosenYear,semester:Number(e.target.value)})}>{[1,2,3].map(term=><option key={term} value={term}>{term}</option>)}</select></label></div>}
  {busy&&<p role="status" className="text-sm">{t.loading}</p>}
  {error&&<div role="alert" className="space-y-3"><p className="text-sm text-red-800">{t.error}</p><Button variant="outline" className="min-h-11" onClick={()=>setAttempt(n=>n+1)}>{t.retry}</Button></div>}
  {data&&<><p className="text-sm font-medium">{data.semester}/{data.academic_year}</p>{data.classes.length===0?<p className="text-sm text-neutral-600">{t.empty}</p>:<ul className="divide-y divide-neutral-200 rounded-lg border border-neutral-200 bg-white">{data.classes.map(c=><li key={`${c.registry_course_id}-${c.section}`} className="space-y-3 p-4"><div><p className="text-xs text-neutral-600">{c.course_code} · {t.section} {c.section}</p><h3 className="mt-1 break-words text-base font-semibold">{c.title}</h3></div><ul className="space-y-3">{c.meetings.map((m,i)=><li key={i} className="text-sm"><p className="font-medium">{m.day} · {m.start_time}–{m.end_time}</p><p className="mt-1 break-words leading-relaxed text-neutral-600">{m.details}</p></li>)}</ul></li>)}</ul>}<p className="text-xs text-neutral-600">{t.asof}: <time dateTime={data.fetched_at}>{new Date(data.fetched_at).toLocaleString(th?'th-TH':'en-GB')}</time></p></>}
 </section>
}
