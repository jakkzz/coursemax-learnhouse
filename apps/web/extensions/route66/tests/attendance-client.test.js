import { afterEach, beforeEach, expect, test } from 'bun:test'
import { attendanceCopy } from '../components/Objects/Classes/attendance-copy'
import { attendanceEntryPath, attendanceLoginDestination, attendanceRequest, attendanceReturn, attendanceRetryLogin, attendanceSignInPath, forgetContinuation, handoffHandle, pendingScan, rememberContinuation, reserveScan } from '../components/Objects/Classes/attendance-client'

const token='q'.repeat(43),handle='h'.repeat(43),path='/attendance/check-in?handoff='+handle
const originalFetch=globalThis.fetch
let data,location,replaced
beforeEach(()=>{
 data=new Map();replaced='';location={origin:'https://learn.example.com',hash:'',pathname:'/attendance/check-in',search:''}
 Object.assign(globalThis,{window:{location,history:{replaceState:(_a,_b,url)=>{replaced=url;location.hash=''}}},sessionStorage:{getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)}})
})
afterEach(()=>{globalThis.fetch=originalFetch})

test('only the opaque local continuation crosses auth/browser contexts',()=>{
 expect(attendanceReturn(path)).toBe(path)
 expect(attendanceReturn(path+'&state=do-not-copy')).toBe(path)
 for(const unsafe of ['//foreign.example'+path,'https://foreign.example'+path,path+'#'+token,'/login?next='+path,'/attendance/check-in?handoff=bad'])expect(attendanceReturn(unsafe)).toBeNull()
 expect(attendanceReturn(path,'https://server.example.com')).toBe(path)
 expect(attendanceEntryPath('/attendance/check-in')).toBe(true)
 expect(attendanceEntryPath('/orgs/synthetic/attendance/check-in')).toBe(true)
 expect(attendanceEntryPath('/attendance/receipts/private')).toBe(false)
 expect(attendanceEntryPath('/classes')).toBe(false)
 expect(attendanceSignInPath(path,'Mozilla/5.0 Safari')).toBe('/login?next='+encodeURIComponent(path))
 expect(attendanceSignInPath(path,'Mozilla/5.0 Line/15.0.0')).toBe('/liff?next='+encodeURIComponent(path))
 const receipt='/attendance/receipts/12345678-1234-4234-8234-123456789012'
 expect(attendanceLoginDestination(receipt,'https://server.example.com')).toBe(receipt)
 expect(attendanceLoginDestination(path,'https://server.example.com')).toBe(path)
 for(const unsafe of ['//foreign.example'+receipt,receipt+'?next=/home','/classes'])expect(attendanceLoginDestination(unsafe,'https://server.example.com')).toBeNull()
})
test('capture is immediate, removes raw fragment and bounds old storage',()=>{
 location.hash='#'+token
 expect(pendingScan()).toBe(token)
 expect(replaced).toBe('/attendance/check-in')
 expect(pendingScan()).toBe(token)
 data.set('lh:pending-attendance-code',JSON.stringify({token,at:Date.now()-120001}))
 expect(pendingScan()).toBe('')
 data.set('lh:pending-attendance-code',JSON.stringify({token,at:Date.now()+1000}))
 expect(pendingScan()).toBe('')
 data.set('lh:pending-attendance-code',JSON.stringify({token,at:String(Date.now())}))
 expect(pendingScan()).toBe('')
})
test('server reservation sends no client timestamp and retains only safe retry destination',async()=>{
 location.hash='#'+token;pendingScan()
 globalThis.fetch=(async(input,options)=>{
  expect(input).toBe('/api/v1/attendance/check-in/prepare')
  expect(JSON.parse(options.body)).toEqual({token})
  return new Response(JSON.stringify({handoff:handle,return_path:path,expires_at:'2026-10-17T10:10:00Z'}),{status:200})
 })
 await reserveScan(token,attendanceCopy.en)
 expect(data.has('lh:pending-attendance-code')).toBe(false)
 expect(attendanceRetryLogin()).toBe('/login?next='+encodeURIComponent(path))
 expect([...data.values()].join('')).not.toContain(token)
 forgetContinuation();expect(attendanceRetryLogin()).toBe('/login')
})
test('a fresh browser needs the URL handle, not copied native/OAuth storage',()=>{
 location.search='?handoff='+handle
 expect(handoffHandle()).toBe(handle)
 expect(data.size).toBe(0)
 expect(attendanceReturn(location.pathname+location.search)).toBe(path)
 rememberContinuation(path)
 data.set('lh:attendance-continuation',JSON.stringify({path,at:Date.now()-1200001}))
 expect(attendanceRetryLogin()).toBe('/login')
 data.set('lh:attendance-continuation',JSON.stringify({path:'//foreign.example',at:Date.now()}))
 expect(attendanceRetryLogin()).toBe('/login')
})
test('receipt/ended/claim/provider recovery messages stay distinct',async()=>{
 for(const [status,code,message] of [[410,'ended',attendanceCopy.en.ended],[409,'handoff_claimed',attendanceCopy.en.handoffClaimed],[410,'entry_cutoff',attendanceCopy.en.entryCutoff],[503,'handoff_unavailable',attendanceCopy.en.handoffUnavailable],[404,'missing',attendanceCopy.en.receiptMissing]]) {
  globalThis.fetch=(async()=>new Response(JSON.stringify({detail:{code}}),{status}))
  await expect(attendanceRequest('/receipts/synthetic',attendanceCopy.en)).rejects.toThrow(message)
 }
})
test('storage failure cannot prevent capture or native sign-in navigation',()=>{
 Object.assign(globalThis,{sessionStorage:{getItem:()=>{throw new Error()},setItem:()=>{throw new Error()},removeItem:()=>{throw new Error()}}})
 location.hash='#'+token
 expect(pendingScan()).toBe(token)
 expect(()=>rememberContinuation(path)).not.toThrow()
 expect(attendanceRetryLogin()).toBe('/login')
})
