'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { Button } from '@/extensions/route66/adapters/ui'
import SchoolTimetable from '../Account/subpages/SchoolTimetable'
import { confirmedStaff, type StaffProjection } from '../Account/subpages/school-workspace-model'

import type { RegistrarClassContext } from './real-teaching/model'

export default function TeacherTimetable({ th, collapsed = false, onStaffStatus, onOpenClass }: { th: boolean; collapsed?: boolean; onStaffStatus?: (staff: boolean) => void; onOpenClass?: (context: RegistrarClassContext) => void }) {
  const [expanded, setExpanded] = useState(!collapsed)
  const [status, setStatus] = useState<StaffProjection | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setStatus(null); setFailed(false)
    const timeout = setTimeout(() => { if (active) setFailed(true); controller.abort() }, 12000)
    fetch('/api/v1/school-identity/me', { credentials: 'include', cache: 'no-store', signal: controller.signal })
      .then(async r => { if (!r.ok) throw Error(); const value = await r.json(); if (active) { setStatus(value); onStaffStatus?.(value.school_kind === 'staff') } })
      .catch(() => { if (active) setFailed(true) })
      .finally(() => clearTimeout(timeout))
    return () => { active = false; clearTimeout(timeout); controller.abort() }
  }, [attempt, onStaffStatus])
  if (failed) return <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg bg-amber-50 p-4 text-sm text-amber-900">
    <AlertTriangle size={18} aria-hidden="true" />
    <p className="min-w-0 flex-1">{th ? 'ตรวจสอบตารางสอนของคุณไม่ได้ ชั้นเรียนในระบบยังแสดงแยกด้านล่าง' : 'Your timetable could not be checked. LearnHouse classes are shown separately below.'}</p>
    <Button variant="outline" className="min-h-11" onClick={() => setAttempt(n => n + 1)}>{th ? 'ลองอีกครั้ง' : 'Try again'}</Button>
  </div>
  if (!status) return <p role="status" className="flex items-center gap-2 text-sm text-neutral-600"><Loader2 size={16} className="animate-spin" aria-hidden="true" />{th ? 'กำลังตรวจสอบตารางสอนของคุณ…' : 'Checking your teaching timetable…'}</p>
  if (confirmedStaff(status) && status.directory_identity) {
    const timetable = <SchoolTimetable staffId={status.directory_identity.officer_id} teacherName={status.directory_identity.name_th} onOpenClass={onOpenClass} />
    return collapsed ? <details className="border-t border-neutral-200 pt-4" onToggle={event => setExpanded(event.currentTarget.open)}><summary className="min-h-11 cursor-pointer text-sm font-medium">{th ? 'ตารางสอนจากทะเบียน (อ่านอย่างเดียว)' : 'Registrar timetable (read-only)'}</summary>{expanded && timetable}</details> : timetable
  }
  if (status.school_kind !== 'staff') return null
  return <p className="text-sm leading-relaxed text-neutral-600">{th ? 'ยืนยันข้อมูลสถานศึกษาเพื่อดูตารางสอนจากทะเบียน' : 'Confirm your school identity to view your registrar timetable.'}{' '}<Link href="/account/school-identity" className="inline-flex min-h-11 items-center font-medium text-blue-700 underline underline-offset-4">{th ? 'ตรวจสอบข้อมูลสถานศึกษา' : 'Review school identity'}</Link></p>
}
