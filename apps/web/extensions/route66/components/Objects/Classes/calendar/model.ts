export type Rotation = 'odd' | 'even' | 'teaching' | 'midterm' | 'final'
type Evidence = { page?: number | null; uncertain?: boolean }
export type CalendarWeek = Evidence & { number: number; starts_on: string; ends_on: string; rotation: Rotation; teaching: boolean; teaching_dates?: string[] | null; note?: string | null }
export type Closure = Evidence & { affected_on: string; makeup_on: string | null; note: string }
export type CalendarTerm = Evidence & { semester: number; starts_on: string; ends_on: string; weeks: CalendarWeek[]; closures: Closure[] }
export type AcademicDate = Evidence & { semester: number; program: string; kind: 'opening' | 'midterm' | 'final' | 'closing' | 'grades' | 'other'; title: string; starts_on: string; ends_on: string; note?: string | null }
export type CalendarPayload = { timezone: string; terms: CalendarTerm[]; events?: AcademicDate[]; unresolved?: string[] }
export function hasCalendarDates(payload: CalendarPayload) { return payload.terms.length > 0 || Boolean(payload.events?.length) }
export function formatCalendarDate(value: string, th: boolean) {
  const date = new Date(value + 'T00:00:00Z')
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(th ? 'th-TH' : 'en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date)
}
export type CoursePlanning = { program: string; starts_on: string; ends_on: string; closures: Closure[] }
export type PlanningOption = { semester: number; program: string; requires_plan: boolean; starts_on: string; ends_on: string; events: AcademicDate[] }
export type CalendarSummary = { planning_options?: PlanningOption[]; scope?: 'organization' | 'teacher'; can_edit?: boolean; id: number; name: string; academic_year: number; track: string; published_revision_id: number | null; latest_revision_id: number; has_teaching_weeks?: boolean }
export function suggestedCalendar(calendars: CalendarSummary[], year: number, semester: number) {
  const matches = calendars.filter(c => c.published_revision_id && c.academic_year === year && c.planning_options?.some(o => o.semester === semester && !o.requires_plan))
  return matches.length === 1 ? matches[0] : undefined
}
export type Revision = { source_url?: string | null; resolved_url?: string | null; fetched_at?: string | null; derived_from_revision_id?: number | null; id: number; calendar_id: number; version: number; state: 'draft' | 'published'; payload: CalendarPayload; source_name: string; source_hash: string; parse_note: string | null; calendar: CalendarSummary; issues?: string[]; source_pages?: { page: number; text: string }[]; source_truncated?: boolean; source_page_count?: number | null; source_kind?: 'abridged_multi_program' | null }
export type MeetingSession = { id?: number; slot_key: string | null; superseded?: boolean; action?: string; starts_at: string; ends_at: string; title: string; state: 'scheduled' | 'no_class'; week_number: number | null; rotation: Rotation | null; nominal_date: string | null; makeup_for: string | null; mode: string | null; location: string | null; note: string | null; attendance_url?: string | null }
export function teachingPolicyLabel(pattern: string | null | undefined, th: boolean) {
  const labels: Record<string, [string, string]> = {
    onsite: ['On campus', 'ที่มหาวิทยาลัย'],
    online: ['Online', 'ออนไลน์'],
    even_onsite: ['On campus in even school weeks; online in odd school weeks', 'เข้าชั้นเรียนในสัปดาห์คู่และเรียนออนไลน์ในสัปดาห์คี่'],
  }
  return (labels[pattern ?? ''] ?? ['Not stated in the official timetable', 'ทะเบียนยังไม่ได้ระบุรูปแบบเรียน'])[th ? 1 : 0]
}
export type Schedule = { school_pattern?: string | null; policy_override?: string | null; hybrid_start?: 'onsite' | 'online' | null; planning?: CoursePlanning | null; syllabus_available?: boolean; class_id: number | null; version: number; manageable: boolean; revision_id: number | null; calendar_name: string | null; pattern: string; sessions: MeetingSession[]; newer_revision_id?: number | null }
export type SchedulePreview = { fingerprint: string; sessions: MeetingSession[]; warnings: string[]; errors?: string[]; protected_count: number; changes: { added: number; replaced: number; unchanged: number; cancelled?: number; skipped_past?: number }; version: number }

export async function calendarRequest<T>(path: string, th: boolean, options: RequestInit = {}): Promise<T> {
  const response = await fetch('/api/v1/school-calendars' + path, { credentials: 'include', cache: 'no-store', ...options })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : body?.detail?.message
    const issues = body?.detail?.issues as unknown
    const validation = Array.isArray(body?.detail) ? body.detail : body?.detail?.errors
    const fix = Array.isArray(issues) ? issues.filter((x): x is string => typeof x === 'string').join(' · ') : Array.isArray(validation) ? validation.map(e => e.msg).filter(Boolean).join(' · ') : ''
    const thai: Record<string, string> = { invalid_pdf: 'อ่านไฟล์นี้ไม่ได้ โปรดเลือกไฟล์ PDF ต้นฉบับอีกครั้ง', too_large: 'ไฟล์เกิน 10 MB โปรดเลือกไฟล์ที่มีขนาดเล็กกว่า', no_text: 'อ่านตัวอักษรจากไฟล์นี้ไม่ได้ โปรดใช้ไฟล์ต้นฉบับที่เลือกข้อความได้ ไฟล์ที่อัปโหลดยังคงอยู่', ai_unavailable: 'ยังไม่ได้ตั้งค่าระบบอ่านอัตโนมัติสำหรับเอกสารรูปแบบนี้ ไฟล์ต้นฉบับและฉบับร่างยังคงอยู่', parse_failed: 'อ่านวันที่จากเอกสารไม่สำเร็จ โปรดลองอ่านอีกครั้ง ไฟล์ต้นฉบับและฉบับร่างยังคงอยู่' }
    const english: Record<string, string> = { no_text: 'This PDF has no readable text. Try a selectable-text original. Your uploaded file is saved.', ai_unavailable: 'Automatic reading is not configured for this document format. Your PDF and draft are saved.', parse_failed: 'Calendar dates could not be read. Retry reading; your PDF and draft are saved.' }
    const urlErrors: Record<string, string> = th ? { invalid_pdf_url: 'โปรดใช้ลิงก์ HTTPS ของไฟล์ PDF ที่เปิดอ่านได้ทั่วไป', url_unavailable: 'เปิดลิงก์ PDF นี้ไม่ได้ โปรดตรวจสอบลิงก์แล้วลองอีกครั้ง หรือเลือกอัปโหลดไฟล์', url_not_pdf: 'ลิงก์นี้ไม่ได้เปิดเป็นไฟล์ PDF โปรดใช้ลิงก์ตรงไปยังไฟล์ หรือเลือกอัปโหลดไฟล์' } : { invalid_pdf_url: 'Use a public HTTPS link directly to the PDF.', url_unavailable: 'The PDF link could not be downloaded. Check the link and retry, or upload the file.', url_not_pdf: 'This link does not download a PDF. Use a direct PDF link or upload the file.' }
    const localized = urlErrors[body?.detail?.code] || (th ? thai : english)[body?.detail?.code]
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
