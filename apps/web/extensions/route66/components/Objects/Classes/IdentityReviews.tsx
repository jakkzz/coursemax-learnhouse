'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { Button, Input } from '@/extensions/route66/adapters/ui'

type Review = {
  id: number; created_at: string; status: 'open' | 'closed'; outcome: 'matched' | 'unchanged' | null
  reason: string; student_number: string | null; match_state: string; decided_at: string | null
  student_name?: string; class_name?: string; section?: string; expected_token?: string; can_match?: boolean
  accounts?: { name: string; owns_record: boolean; has_verified_claim: boolean }[]; decision_reason?: string
}
type List = { cases: Review[]; can_request?: boolean; open_case_id?: number | null }
const copy = {
  en: {
    title: 'Identity reviews', own: 'Review my school identity', teacher: 'Identity review requests',
    intro: 'Review the saved record and current verified account evidence. Membership and previous work stay with their existing records.',
    help: 'Describe what looks wrong. Your verified account and saved roster record are attached automatically.',
    reason: 'Reason for review', note: 'Decision reason (administrator record)', request: 'Request review', send: 'Sending…',
    refresh: 'Refresh', loading: 'Loading review requests…', failed: 'Reviews could not be loaded. Try refreshing.',
    denied: 'Your review access changed. Sign in again or reload My classes.', school: 'School identity',
    pending: 'Waiting for administrator review', matched: 'Closed — verified number matched', unchanged: 'Closed — identity unchanged',
    open: 'Open requests', closed: 'Recent decisions', empty: 'No open identity requests', emptyClosed: 'No decisions yet',
    emptyHelp: 'Teacher flags and student requests appear here. The oldest 100 open requests are shown first.',
    back: 'All review requests', review: 'Review request', noNumber: 'Teacher-added record',
    check: 'Confirm verified match', close: 'Close without changing identity', saving: 'Saving…',
    stale: 'The evidence or decision changed. Your note is kept; reload the request before deciding.',
    saveFailed: 'The decision was not saved. Refresh the request and try again.',
    saved: 'Decision saved', owner: 'Owns the saved record', proof: 'Verified student-number claim',
    accounts: 'Current account evidence', next: 'Open My classes', submitted: 'Request recorded. Your identity and membership are unchanged.',
  },
  th: {
    title: 'ตรวจสอบตัวตน', own: 'ขอตรวจสอบตัวตนของฉัน', teacher: 'คำขอตรวจสอบตัวตน',
    intro: 'ตรวจสอบข้อมูลที่บันทึกไว้และหลักฐานบัญชีที่ยืนยันล่าสุด สมาชิกและผลงานเดิมยังอยู่กับระเบียนเดิม',
    help: 'อธิบายข้อมูลที่ไม่ถูกต้อง ระบบแนบบัญชีที่ยืนยันแล้วและรายชื่อชั้นเรียนให้โดยอัตโนมัติ',
    reason: 'เหตุผลที่ขอตรวจสอบ', note: 'เหตุผลการตัดสินใจ (บันทึกสำหรับผู้ดูแล)', request: 'ส่งคำขอตรวจสอบ', send: 'กำลังส่ง…',
    refresh: 'โหลดใหม่', loading: 'กำลังโหลดคำขอตรวจสอบ…', failed: 'โหลดคำขอตรวจสอบไม่ได้ โปรดลองโหลดใหม่',
    denied: 'สิทธิ์ตรวจสอบเปลี่ยนแล้ว โปรดเข้าสู่ระบบอีกครั้งหรือโหลดชั้นเรียนของฉันใหม่', school: 'ข้อมูลสถานศึกษา',
    pending: 'รอผู้ดูแลตรวจสอบ', matched: 'ปิดคำขอแล้ว — จับคู่รหัสที่ยืนยันแล้ว', unchanged: 'ปิดคำขอแล้ว — ไม่เปลี่ยนตัวตน',
    open: 'คำขอที่ยังเปิดอยู่', closed: 'ผลการตรวจสอบล่าสุด', empty: 'ไม่มีคำขอที่รอตรวจสอบ', emptyClosed: 'ยังไม่มีผลการตรวจสอบ',
    emptyHelp: 'แสดงคำขอจากผู้สอนและนักศึกษา โดยเรียงคำขอที่ยังเปิดอยู่จากเก่าไปใหม่ สูงสุด 100 รายการ',
    back: 'คำขอตรวจสอบทั้งหมด', review: 'ตรวจสอบคำขอ', noNumber: 'รายชื่อที่ผู้สอนเพิ่ม',
    check: 'ยืนยันการจับคู่จากหลักฐาน', close: 'ปิดคำขอโดยไม่เปลี่ยนตัวตน', saving: 'กำลังบันทึก…',
    stale: 'หลักฐานหรือผลการตัดสินใจเปลี่ยนแล้ว ข้อความที่กรอกยังอยู่ โปรดโหลดคำขอใหม่ก่อนตัดสินใจ',
    saveFailed: 'ยังไม่ได้บันทึกผล โปรดโหลดคำขอใหม่แล้วลองอีกครั้ง',
    saved: 'บันทึกผลการตรวจสอบแล้ว', owner: 'เจ้าของระเบียนเดิม', proof: 'ยืนยันรหัสนักศึกษาผ่านบัญชีแล้ว',
    accounts: 'หลักฐานบัญชีปัจจุบัน', next: 'เปิดชั้นเรียนของฉัน', submitted: 'บันทึกคำขอแล้ว โดยไม่เปลี่ยนตัวตนหรือสมาชิกชั้นเรียน',
  },
}
const states: Record<string, [string, string]> = {
  record_missing: ['The saved record is no longer available. Reload the request.', 'ไม่พบระเบียนเดิม โปรดโหลดคำขอใหม่'],
  waiting_for_roster: ['A reviewed official roster is still needed. A manual membership is not official student-number evidence.', 'ต้องมีรายชื่อจากทะเบียนที่ตรวจสอบแล้ว การเพิ่มสมาชิกด้วยตนเองไม่ใช่หลักฐานรหัสนักศึกษาจากทะเบียน'],
  google_signin_needed: ['The student needs to sign in again with their school Google account, then refresh this request.', 'ให้นักศึกษาเข้าสู่ระบบด้วย Google ของมหาวิทยาลัยอีกครั้ง แล้วโหลดคำขอนี้ใหม่'],
  multiple_claims: ['More than one verified account claims this number. Refresh school Google sign-in on the affected accounts; this review cannot choose an owner or merge them.', 'มีบัญชีที่ยืนยันแล้วมากกว่าหนึ่งบัญชีอ้างรหัสนี้ ให้เจ้าของบัญชีเข้าสู่ระบบด้วย Google ของมหาวิทยาลัยอีกครั้ง การตรวจสอบนี้ไม่เลือกเจ้าของหรือรวมบัญชี'],
  ownership_conflict: ['Existing records have different ownership. Use the original linked account; this action cannot transfer records or previous work.', 'ระเบียนเดิมมีเจ้าของต่างกัน ให้ใช้บัญชีเดิมที่เชื่อมไว้ การดำเนินการนี้ไม่ย้ายระเบียนหรือผลงานเดิม'],
  original_account_needed: ['Sign in with the account already linked to this school record. This request does not merge accounts.', 'เข้าสู่ระบบด้วยบัญชีเดิมที่เชื่อมกับระเบียนนี้ คำขอนี้ไม่รวมบัญชีเข้าด้วยกัน'],
  organization_access_needed: ['The verified account is not a member of this organization. Existing organization access must be restored before matching.', 'บัญชีที่ยืนยันแล้วไม่ได้เป็นสมาชิกองค์กรนี้ ต้องคืนสิทธิ์เข้าองค์กรตามขั้นตอนเดิมก่อนจับคู่'],
  ready_to_match: ['One verified student-number claim matches this unlinked record. Confirming uses the existing matching and course-access repair.', 'มีบัญชีที่ยืนยันรหัสนักศึกษาตรงกับระเบียนที่ยังไม่เชื่อมเพียงบัญชีเดียว การยืนยันใช้ขั้นตอนจับคู่และซ่อมสิทธิ์รายวิชาเดิม'],
  matched: ['The verified student number matches the existing owner. Course access still follows the saved class connection.', 'รหัสนักศึกษาที่ยืนยันแล้วตรงกับเจ้าของระเบียนเดิม สิทธิ์รายวิชายังขึ้นกับการเชื่อมชั้นเรียนที่บันทึกไว้'],
}
class ReviewError extends Error { constructor(public status: number) { super(String(status)) } }
async function request(path: string, body?: unknown, signal?: AbortSignal) {
  const response = await fetch('/api/v1/academic-classes' + path, { credentials: 'include', cache: 'no-store', signal,
    method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) throw new ReviewError(response.status)
  return response.json()
}
function useReviews(path: string, refreshKey = 0) {
  const [data, setData] = useState<List | null>(null), [error, setError] = useState(0), [revision, setRevision] = useState(0)
  useEffect(() => {
    const abort = new AbortController(); setError(0)
    request(path, undefined, abort.signal).then(value => { if (!abort.signal.aborted) setData(value) }).catch(e => {
      if (!abort.signal.aborted) { setError(e.status || 500); if ([401, 403, 404].includes(e.status)) setData(null) }
    })
    return () => abort.abort()
  }, [path, revision, refreshKey])
  return { data, error, reload: () => setRevision(n => n + 1) }
}
function stateText(item: Review, th: boolean) { return states[item.match_state]?.[th ? 1 : 0] || copy[th ? 'th' : 'en'].failed }
function statusText(item: Review, th: boolean) {
  const t = copy[th ? 'th' : 'en']; return item.status === 'open' ? t.pending : item.outcome === 'matched' ? t.matched : t.unchanged
}
function Feedback({ error, th, retry }: { error: number; th: boolean; retry: () => void }) {
  const t = copy[th ? 'th' : 'en'], denied = [401, 403, 404].includes(error)
  return <div role="alert" className="space-y-2 text-sm"><p>{denied ? t.denied : t.failed}</p>{denied ? <Link className="inline-flex min-h-11 items-center underline underline-offset-4" href="/account/school-identity">{t.school}</Link> : <Button variant="outline" onClick={retry}>{t.refresh}</Button>}</div>
}
function Receipt({ item, th }: { item: Review; th: boolean }) {
  return <li className="space-y-2 border-t border-neutral-200 py-4 text-sm"><p className="font-semibold">{item.student_name || item.student_number || copy[th ? 'th' : 'en'].noNumber} · {statusText(item, th)}</p><p className="max-w-prose break-words text-neutral-700">{item.reason}</p><p className="max-w-prose text-neutral-600">{stateText(item, th)}</p></li>
}

export function OwnIdentityReview({ th, onRefresh }: { th: boolean; onRefresh?: () => void }) {
  const t = copy[th ? 'th' : 'en'], { data, error, reload } = useReviews('/identity-reviews/own')
  const [reason, setReason] = useState(''), [busy, setBusy] = useState(false), [sendError, setSendError] = useState(0), [sent, setSent] = useState(false)
  const open = data?.cases.find(c => c.id === data.open_case_id), notice = useRef<HTMLParagraphElement>(null)
  useEffect(() => { if (sent) notice.current?.focus() }, [sent])
  async function send() {
    setBusy(true); setSendError(0); setSent(false)
    try { await request('/identity-reviews/own', { reason }); setReason(''); setSent(true); reload() }
    catch (e) { setSendError((e as ReviewError).status || 500); reload() }
    finally { setBusy(false) }
  }
  if (data && !data.can_request && data.cases.length === 0 && !error) return null
  return <section className="space-y-4 border-t border-neutral-200 pt-5" aria-label={t.own}>
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">{t.own}</h2><Button variant="outline" disabled={busy} onClick={() => { reload(); onRefresh?.(); window.dispatchEvent(new Event('lh-school-identity-changed')) }}>{t.refresh}</Button></div>
    {sendError===409 ? <p role="alert" className="max-w-prose text-sm">{th?'มีคำขออยู่แล้วหรือหลักฐานเปลี่ยน ดูสถานะล่าสุดด้านล่าง ข้อความที่กรอกยังอยู่':'A request already exists or your evidence changed. Review the latest status below; your draft is kept.'}</p> : (error || sendError) ? <Feedback error={error || sendError} th={th} retry={() => { setSendError(0); reload() }} /> : null}
    {!data && !error && <p role="status" className="text-sm">{t.loading}</p>}
    {sent && <p ref={notice} tabIndex={-1} role="status" className="text-sm">{t.submitted}</p>}
    {data?.can_request && !open && ![401, 403, 404].includes(error || sendError) && <form className="max-w-xl space-y-3" onSubmit={e => { e.preventDefault(); void send() }}>
      <p className="max-w-prose text-sm text-neutral-600">{t.help}</p><label className="flex flex-col gap-2 text-sm font-medium">{t.reason}<Input value={reason} onChange={e => setReason(e.target.value)} minLength={5} maxLength={500} required disabled={busy} /></label>
      <Button disabled={busy || reason.trim().length < 5} loading={busy} loadingLabel={t.send}>{t.request}</Button>
    </form>}
    <ul>{data?.cases.map(item => <Receipt key={item.id} item={item} th={th} />)}</ul>
    {data?.cases.some(c => c.outcome === 'matched') && <Link className="inline-flex min-h-11 items-center text-sm underline underline-offset-4" href="/classes">{t.next}</Link>}
  </section>
}

export function ClassIdentityReviews({ classId, th, refreshKey }: { classId: number; th: boolean; refreshKey: number }) {
  const t = copy[th ? 'th' : 'en'], { data, error, reload } = useReviews(`/${classId}/identity-reviews`, refreshKey)
  return <details className="border-t border-neutral-200 pt-4"><summary className="min-h-11 cursor-pointer text-sm font-medium">{t.teacher}{data ? ` (${data.cases.length})` : ''}</summary>
    <Button variant="outline" onClick={reload}>{t.refresh}</Button>
    {error ? <Feedback error={error} th={th} retry={reload} /> : !data ? <p role="status">{t.loading}</p> : data.cases.length ? <ul>{data.cases.map(item => <Receipt key={item.id} item={item} th={th} />)}</ul> : <p className="py-3 text-sm text-neutral-600">{t.empty}</p>}
  </details>
}

export function IdentityReviewInbox({ th, onChanged }: { th: boolean; onChanged: () => void }) {
  const t = copy[th ? 'th' : 'en'], [filter, setFilter] = useState<'open' | 'closed'>('open')
  const { data, error, reload } = useReviews('/identity-reviews?status=' + filter)
  const [selected, setSelected] = useState<number | null>(null), [item, setItem] = useState<Review | null>(null), [revision, setRevision] = useState(0)
  const [drafts, setDrafts] = useState<Record<number, string>>({}), [busy, setBusy] = useState<'recheck' | 'close' | null>(null), [failure, setFailure] = useState(0), [saved, setSaved] = useState(false)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    setItem(null); setFailure(0); setSaved(false)
    if (selected === null) return
    const abort = new AbortController()
    request(`/identity-reviews/${selected}`, undefined, abort.signal).then(value => {
      if (!abort.signal.aborted) { setItem(value); heading.current?.focus() }
    }).catch(e => { if (!abort.signal.aborted) setFailure(e.status || 500) })
    return () => abort.abort()
  }, [selected, revision])
  async function decide(action: 'recheck' | 'close') {
    if (!item) return
    setBusy(action); setFailure(0); setSaved(false)
    try {
      const value = await request(`/identity-reviews/${item.id}/decision`, { action, reason: drafts[item.id] || '', expected_token: item.expected_token })
      setItem(value); setSaved(true); reload(); onChanged()
    } catch (e) { const status = (e as ReviewError).status || 500; setFailure(status); if ([401, 403, 404].includes(status)) setItem(null) }
    finally { setBusy(null) }
  }
  return <section className="space-y-5" aria-label={t.title}>
    {selected === null ? <>
      <div className="flex flex-wrap items-end justify-between gap-3"><h2 className="text-xl font-semibold">{t.title}</h2><div className="flex flex-wrap items-center gap-3"><label className="flex flex-col gap-1 text-sm"><span>{t.title}</span><select className="min-h-11 rounded-lg border border-neutral-300 bg-white px-3" value={filter} onChange={e => setFilter(e.target.value as 'open' | 'closed')}><option value="open">{t.open}</option><option value="closed">{t.closed}</option></select></label><Button variant="outline" onClick={reload}>{t.refresh}</Button></div></div>
      <p className="max-w-prose text-sm text-neutral-600">{t.intro}</p>
      {error ? <Feedback error={error} th={th} retry={reload} /> : !data ? <p role="status">{t.loading}</p> : data.cases.length === 0 ? <div className="space-y-2 py-4"><h3 className="font-semibold">{filter === 'open' ? t.empty : t.emptyClosed}</h3><p className="max-w-prose text-sm text-neutral-600">{t.emptyHelp}</p></div> : <ul className="divide-y divide-neutral-200 border-y border-neutral-200">{data.cases.map(c => <li key={c.id} className="flex flex-wrap items-center justify-between gap-4 py-4"><div className="min-w-0 space-y-1"><h3 className="break-words font-semibold">{c.student_name || c.student_number || t.noNumber}</h3><p className="text-sm text-neutral-600">{c.student_number} {c.class_name ? `· ${c.class_name} · ${c.section}` : ''}</p><p className="text-sm">{statusText(c, th)}</p></div><Button variant="outline" onClick={() => setSelected(c.id)}>{t.review}</Button></li>)}</ul>}
    </> : <>
      <Button variant="ghost" disabled={busy !== null} onClick={() => setSelected(null)}>{t.back}</Button>
      <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">{item?.student_name || t.review}</h2>
      {failure ? failure === 409 ? <div role="alert" className="space-y-3 text-sm"><p>{t.stale}</p><Button variant="outline" disabled={busy !== null} onClick={() => setRevision(n => n + 1)}>{t.refresh}</Button></div> : <Feedback error={failure} th={th} retry={() => setRevision(n => n + 1)} /> : null}
      {!item && !failure && <p role="status">{t.loading}</p>}
      {item && <>
        <p className="text-sm">{item.student_number || t.noNumber}{item.class_name ? ` · ${item.class_name} · ${item.section}` : ''}</p>
        <p className="max-w-prose break-words text-sm text-neutral-700">{item.reason}</p>
        <p className="max-w-prose text-sm">{stateText(item, th)}</p>
        {Boolean(item.accounts?.length) && <div className="space-y-2"><h3 className="text-sm font-semibold">{t.accounts}</h3><ul className="space-y-2 text-sm">{item.accounts!.map((account, i) => <li key={i} className="break-words">{account.name} — {[account.owns_record ? t.owner : '', account.has_verified_claim ? t.proof : ''].filter(Boolean).join(' · ')}</li>)}</ul></div>}
        {saved && <p role="status" className="text-sm font-semibold">{t.saved}</p>}
        {item.status === 'closed' ? <div className="space-y-2 border-t border-neutral-200 pt-4"><p className="font-semibold">{statusText(item, th)}</p><p className="max-w-prose break-words text-sm">{item.decision_reason}</p></div> : <div className="max-w-xl space-y-4 border-t border-neutral-200 pt-5">
          <label className="flex flex-col gap-2 text-sm font-medium">{t.note}<Input value={drafts[item.id] || ''} maxLength={500} minLength={5} onChange={e => setDrafts(values => ({ ...values, [item.id]: e.target.value }))} disabled={busy !== null} /></label>
          <div className="flex flex-wrap gap-3"><Button disabled={busy !== null || Boolean(failure) || !item.can_match || (drafts[item.id] || '').trim().length < 5} loading={busy === 'recheck'} loadingLabel={t.saving} onClick={() => void decide('recheck')}>{t.check}</Button><Button variant="outline" disabled={busy !== null || Boolean(failure) || (drafts[item.id] || '').trim().length < 5} loading={busy === 'close'} loadingLabel={t.saving} onClick={() => void decide('close')}>{t.close}</Button></div>
        </div>}
      </>}
    </>}
  </section>
}
