export type Rotation = 'odd' | 'even' | 'teaching' | 'midterm' | 'final'
type Evidence = { page?: number | null; uncertain?: boolean }
export type CalendarWeek = Evidence & { number: number; starts_on: string; ends_on: string; rotation: Rotation; teaching: boolean; note?: string | null }
export type Closure = Evidence & { affected_on: string; makeup_on: string | null; note: string }
export type CalendarTerm = Evidence & { semester: number; starts_on: string; ends_on: string; weeks: CalendarWeek[]; closures: Closure[] }
export type CalendarPayload = { timezone: string; terms: CalendarTerm[]; unresolved?: string[] }
export type CalendarSummary = { id: number; name: string; academic_year: number; track: string; published_revision_id: number | null; latest_revision_id: number }
export type Revision = { id: number; calendar_id: number; version: number; state: 'draft' | 'published'; payload: CalendarPayload; source_name: string; source_hash: string; parse_note: string | null; calendar: CalendarSummary; issues?: string[]; source_pages?: { page: number; text: string }[]; source_truncated?: boolean; source_page_count?: number | null }
export type MeetingSession = { id?: number; slot_key: string | null; superseded?: boolean; action?: string; starts_at: string; ends_at: string; title: string; state: 'scheduled' | 'no_class'; week_number: number | null; rotation: Rotation | null; nominal_date: string | null; makeup_for: string | null; mode: string | null; location: string | null; note: string | null; attendance_url?: string | null }
export type Schedule = { class_id: number | null; version: number; manageable: boolean; revision_id: number | null; calendar_name: string | null; pattern: string; sessions: MeetingSession[]; newer_revision_id?: number | null }
export type SchedulePreview = { fingerprint: string; sessions: MeetingSession[]; warnings: string[]; errors?: string[]; protected_count: number; changes: { added: number; replaced: number; unchanged: number; cancelled?: number; skipped_past?: number }; version: number }

export async function calendarRequest<T>(path: string, th: boolean, options: RequestInit = {}): Promise<T> {
  const response = await fetch('/api/v1/school-calendars' + path, { credentials: 'include', cache: 'no-store', ...options })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : body?.detail?.message
    const issues = body?.detail?.issues as unknown
    const validation = Array.isArray(body?.detail) ? body.detail : body?.detail?.errors
    const fix = Array.isArray(issues) ? issues.filter((x): x is string => typeof x === 'string').join(' · ') : Array.isArray(validation) ? validation.map(e => e.msg).filter(Boolean).join(' · ') : ''
    const thai: Record<string, string> = { invalid_pdf: 'ไฟล์นี้อ่านเป็น PDF ไม่ได้ โปรดเลือกไฟล์ต้นฉบับอีกครั้ง', too_large: 'ไฟล์เกิน 10 MB โปรดเลือกไฟล์ที่มีขนาดเล็กกว่า', no_text: 'เอกสารไม่มีข้อความที่ดึงได้ โปรดเปิดต้นฉบับและกรอกวันที่เอง ระบบเก็บไฟล์ไว้แล้ว', ai_unavailable: 'ยังใช้ระบบดึงวันที่ไม่ได้ โปรดกรอกวันที่เอง ไฟล์ต้นฉบับและฉบับร่างยังคงอยู่', parse_failed: 'ดึงวันที่จากเอกสารไม่สำเร็จ ลองอีกครั้งหรือกรอกข้อมูลเองได้ ไฟล์ต้นฉบับและฉบับร่างยังคงอยู่' }
    const localized = th ? thai[body?.detail?.code] : undefined
    throw new Error(localized || detail || fix || (th ? 'ดำเนินการไม่ได้ โปรดลองอีกครั้ง ข้อมูลที่บันทึกไว้ยังคงอยู่' : 'This action could not be completed. Retry; saved records are unchanged.'))
  }
  return response.json()
}
export function jsonBody(body: unknown): RequestInit { return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } }
export function localDay(iso: string, zone = 'Asia/Bangkok') {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(iso))
  const part = (type: string) => parts.find(p => p.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}`
}
export function monthDays(month: string) {
  const [year, m] = month.split('-').map(Number)
  const first = new Date(Date.UTC(year, m - 1, 1)), count = new Date(Date.UTC(year, m, 0)).getUTCDate()
  return { offset: (first.getUTCDay() + 6) % 7, days: Array.from({ length: count }, (_, i) => `${month}-${String(i + 1).padStart(2, '0')}`) }
}
export function moveMonth(month: string, delta: number) { const [y, m] = month.split('-').map(Number); return new Date(Date.UTC(y, m - 1 + delta, 1)).toISOString().slice(0, 7) }
