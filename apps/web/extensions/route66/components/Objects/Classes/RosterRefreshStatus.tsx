'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/extensions/route66/adapters/ui'

type Run = { id: number; at: string; origin: string; outcome: string; counts: Record<string, number> | null }
type Status = { class_id: number; class_version: number; control_version: number; paused: boolean; initial_review_required: boolean; status: string; last_attempt_at: string | null; last_accepted_at: string | null; next_check_at: string | null; delayed: boolean; recent: Run[] }

export default function RosterRefreshStatus({ classId, th, onReview, onVersion, refreshKey = 0, disabled = false }: {
  classId: number; th: boolean; refreshKey?: number; disabled?: boolean; onReview: () => Promise<void>; onVersion: (version: number) => void
}) {
  const [data, setData] = useState<Status | null>(null), [error, setError] = useState<'status' | 'action' | 'access' | null>(null), [busy, setBusy] = useState<'check' | 'settings' | 'review' | null>(null), [attempt, setAttempt] = useState(0)
  const controller = useRef<AbortController | null>(null), generation = useRef(0), versionCallback = useRef(onVersion)
  versionCallback.current = onVersion
  useEffect(() => {
    const abort = new AbortController(); controller.current = abort; setBusy(null)
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      const version = generation.current
      try {
        const response = await fetch(`/api/v1/academic-classes/${classId}/roster/refresh`, { credentials: 'include', cache: 'no-store', signal: abort.signal })
        if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'access' : 'status')
        const value: Status = await response.json()
        if (!abort.signal.aborted && version === generation.current && value.class_id === classId) {
          setData(value); setError(previous => previous === 'action' ? previous : null); versionCallback.current(value.class_version)
        }
      } catch (cause) {
        if (!abort.signal.aborted && version === generation.current) {
          if (cause instanceof Error && cause.message === 'access') { setData(null); setError('access') }
          else setError(previous => previous === 'action' ? previous : 'status')
        }
      } finally {
        if (!abort.signal.aborted) timer = setTimeout(poll, 10000)
      }
    }
    void poll()
    return () => { abort.abort(); clearTimeout(timer) }
  }, [classId, attempt, refreshKey])
  const t = th ? {
    access: 'สิทธิ์จัดการชั้นเรียนเปลี่ยนแล้ว โปรดโหลดชั้นเรียนของฉันใหม่หรือตรวจสอบข้อมูลสถานศึกษา', school: 'ตรวจสอบข้อมูลสถานศึกษา',
    checkingShort: 'กำลังตรวจสอบ…', loading: 'กำลังโหลดสถานะการตรวจสอบ…', saveFailed: 'บันทึกคำขอนี้ไม่ได้ โปรดโหลดสถานะแล้วลองอีกครั้ง',
    automatic: 'ตรวจสอบรายชื่อทุก 6 ชั่วโมง', paused: 'พักการตรวจสอบอัตโนมัติ', initial: 'ตรวจสอบและบันทึกรายชื่อครั้งแรกก่อนเริ่มอัปเดตอัตโนมัติ', checking: 'กำลังตรวจสอบรายชื่อ…', queued: 'รอการตรวจสอบ รายชื่อที่บันทึกไว้ยังไม่เปลี่ยน',
    review: 'ตรวจสอบการเปลี่ยนแปลง', large: 'รายชื่อจากทะเบียนลดลงมาก ระบบยังไม่เปลี่ยนสมาชิก โปรดตรวจสอบรายชื่อใหม่', failed: 'ตรวจสอบหรือบันทึกข้อมูลไม่สำเร็จ รายชื่อเดิมยังคงอยู่ ลองตรวจสอบอีกครั้ง', authority: 'การมอบหมายงานสอนหรือข้อมูลสถานศึกษาเปลี่ยนไป โปรดตรวจสอบการเชื่อมชั้นเรียนและข้อมูลสถานศึกษา', delayed: 'การตรวจสอบล่าช้า รายชื่อเดิมยังคงอยู่ ระบบจะลองใหม่เมื่อพร้อม',
    check: 'ตรวจสอบตอนนี้', retry: 'ลองอีกครั้ง', pause: 'พักการตรวจสอบ', resume: 'ตรวจสอบต่อ', saving: 'กำลังบันทึก…', unavailable: 'โหลดสถานะไม่ได้ รายชื่อที่บันทึกไว้ยังคงอยู่ ลองโหลดสถานะอีกครั้ง', reload: 'โหลดสถานะใหม่',
    checked: 'ตรวจสอบล่าสุด', accepted: 'บันทึกรายชื่อล่าสุด', next: 'ตรวจสอบครั้งถัดไป', never: 'ยังไม่มี', recent: 'การตรวจสอบล่าสุด', automaticRun: 'อัตโนมัติ', manualRun: 'ผู้สอนตรวจสอบ', saved: 'บันทึกรายชื่อแล้ว', unchanged: 'เพิ่งบันทึกรายชื่อนี้ ยังไม่นับเป็นการตรวจสอบซ้ำ', held: 'รอตรวจสอบ', retrying: 'จะตรวจสอบใหม่อีกครั้งในไม่ช้า', added: 'เพิ่ม', missing: 'ไม่พบ', withdrawn: 'ถอนสถานะ', reactivated: 'คืนสถานะ', separate: 'สถานะนี้เป็นข้อมูลรายชื่อ ไม่ใช่ผลการให้สิทธิ์เข้าเนื้อหารายวิชา',
  } : {
    access: 'Class access changed. Reload My classes or review School identity.', school: 'Review School identity',
    checkingShort: 'Checking…', loading: 'Loading check status…', saveFailed: 'Could not save that request. Reload status and try again.',
    automatic: 'Roster checked every 6 hours', paused: 'Automatic checks paused', initial: 'Review and save the initial roster to start automatic checks.', checking: 'Checking the roster…', queued: 'Check queued. Saved membership has not changed.',
    review: 'Review changes', large: 'The official roster is much smaller. Membership is unchanged; review a fresh roster.', failed: 'The check could not be completed. Saved membership is unchanged. Try checking again.', authority: 'Teaching authority or school identity changed. Review the class connection and School identity.', delayed: 'Checks are delayed. Saved membership is unchanged; the worker will retry when available.',
    check: 'Check now', retry: 'Try again', pause: 'Pause checks', resume: 'Resume checks', saving: 'Saving…', unavailable: 'Status is unavailable. Saved rows remain visible. Try reloading the status.', reload: 'Reload status',
    checked: 'Last checked', accepted: 'Last accepted', next: 'Next check', never: 'Not yet', recent: 'Recent checks', automaticRun: 'Automatic', manualRun: 'Teacher review', saved: 'Roster saved', unchanged: 'Recently accepted; not another missing observation', held: 'Needs review', retrying: 'Check will retry shortly', added: 'added', missing: 'missing', withdrawn: 'withdrawn', reactivated: 'restored', separate: 'Roster status is separate from course-content access.',
  }
  function date(value: string | null) {
    return value ? new Intl.DateTimeFormat(th ? 'th-TH' : 'en-GB', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' }).format(new Date(value)) : t.never
  }
  async function action(kind: 'check' | 'settings') {
    const abort = controller.current
    if (!data || !abort || busy) return
    generation.current++; setBusy(kind); setError(null)
    try {
      const response = await fetch(`/api/v1/academic-classes/${classId}/roster/refresh/${kind}`, {
        method: 'POST', credentials: 'include', signal: abort.signal, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(kind === 'check' ? {} : { paused: !data.paused, expected_version: data.control_version }),
      })
      if (!response.ok) throw new Error('save')
      const value = await response.json()
      if (!abort.signal.aborted) {
        setData(previous => previous ? { ...previous, ...(kind === 'check' ? { status: value.status } : value) } : previous)
        setAttempt(n => n + 1)
      }
    } catch { if (!abort.signal.aborted) { setError('action'); setAttempt(n => n + 1) } }
    finally { if (!abort.signal.aborted) setBusy(null) }
  }
  async function reviewSource() {
    const abort = controller.current
    if (busy || disabled || !abort) return
    setBusy('review')
    try { await onReview() }
    finally { if (!abort.signal.aborted) setBusy(null) }
  }
  const review = data?.initial_review_required || data?.status === 'needs_review' || data?.status === 'authority_changed' || data?.paused
  const waiting = data?.status === 'queued' || data?.status === 'checking'
  const failure = data?.status === 'source_failed' || data?.status === 'write_failed'
  const message = data?.initial_review_required ? t.initial : data?.paused ? t.paused : data?.status === 'needs_review' ? t.large : data?.status === 'authority_changed' ? t.authority : failure ? t.failed : data?.status === 'stale' || data?.status === 'retrying' ? t.retrying : data?.delayed ? t.delayed : data?.status === 'checking' ? t.checking : data?.status === 'queued' ? t.queued : t.automatic
  const outcome = (value: string) => value === 'applied' ? t.saved : value === 'recently_applied' ? t.unchanged : value === 'needs_review' ? t.held : value === 'authority_changed' ? t.authority : value === 'stale' || value === 'retrying' ? t.retrying : t.failed
  return <section className="space-y-3 border-b border-neutral-200 pb-4 text-sm" aria-label={th ? 'การอัปเดตรายชื่อ' : 'Roster checks'}>
    <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1">{(data || !error) && <p role="status" aria-live="polite">{data ? message : t.loading}</p>}{data?.last_attempt_at && <p className="mt-1 text-neutral-600">{t.checked}: <time dateTime={data.last_attempt_at}>{date(data.last_attempt_at)}</time></p>}</div>
      <div className="flex flex-wrap gap-2">
        {data && <Button variant="outline" className="min-h-11" loading={busy === 'check' || busy === 'review'} loadingLabel={t.checkingShort} disabled={disabled || busy !== null || (!review && waiting)} onClick={() => review ? void reviewSource() : void action('check')}>{review ? t.review : failure ? t.retry : t.check}</Button>}
        {data && !data.initial_review_required && <Button variant="ghost" className="min-h-11" disabled={disabled || busy !== null} loading={busy === 'settings'} loadingLabel={t.saving} onClick={() => void action('settings')}>{data.paused ? t.resume : t.pause}</Button>}
      </div>
    </div>
    {error && <div role="alert"><p>{error === 'access' ? t.access : error === 'action' ? t.saveFailed : t.unavailable}</p>{error === 'access' && <a className="inline-flex min-h-11 items-center underline underline-offset-4" href="/account/school-identity">{t.school}</a>}<Button variant="outline" className="mt-2 min-h-11" onClick={() => { setError(null); setAttempt(n => n + 1) }}>{t.reload}</Button></div>}
    {data && <details><summary className="flex min-h-11 cursor-pointer items-center text-neutral-600">{t.recent}</summary><div className="space-y-3 pt-2 text-neutral-600">
      <p>{t.accepted}: {date(data.last_accepted_at)}{!data.paused && data.next_check_at && <><br />{t.next}: {date(data.next_check_at)}</>}</p>
      <ol className="space-y-3">{data.recent.map(run => <li key={run.id}><p><time dateTime={run.at}>{date(run.at)}</time> · {run.origin === 'scheduled' ? t.automaticRun : t.manualRun}</p><p>{outcome(run.outcome)}</p>{run.counts && <p>{[[t.added, 'added'], [t.missing, 'missing'], [t.withdrawn, 'withdrawn'], [t.reactivated, 'reactivated']].map(([label, key]) => `${run.counts?.[key] ?? 0} ${label}`).join(' · ')}</p>}</li>)}</ol><p>{t.separate}</p>
    </div></details>}
  </section>
}
