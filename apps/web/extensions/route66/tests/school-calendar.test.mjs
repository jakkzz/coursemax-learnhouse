import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { calendarRequest, formatCalendarDate, hasCalendarDates, localDay, monthDays, moveMonth, suggestedCalendar, teachingPolicyLabel } from '../components/Objects/Classes/calendar/model.ts'
const source = file => fs.readFileSync(new URL('../components/Objects/Classes/' + file, import.meta.url), 'utf8')
test('only one accepted year/semester teaching calendar is suggested; ambiguity and date-only sources stay explicit', () => {
 const full = { id: 1, academic_year: 2569, published_revision_id: 10, planning_options: [{ semester: 1, requires_plan: false }] }
 const dates = { ...full, id: 2, published_revision_id: 20, planning_options: [{ semester: 1, requires_plan: true }] }
 assert.equal(suggestedCalendar([full, dates], 2569, 1), full)
 assert.equal(suggestedCalendar([full, { ...full, id: 3 }], 2569, 1), undefined)
 assert.equal(suggestedCalendar([full], 2570, 1), undefined)
 assert.equal(suggestedCalendar([full], 2569, 2), undefined)
 assert.equal(suggestedCalendar([dates], 2569, 1), undefined)
 const s = source('calendar/ClassSchedule.tsx')
 assert.match(s, /School teaching policy/)
 assert.match(s, /!overriding \? <Button/)
 assert.match(s, /schedule.policy_override \?\? officialPattern/)
 assert.doesNotMatch(s, /First hybrid week|hybridStart|hybrid_start/)
 assert.match(s, /section, .*settings/)
 assert.match(source('calendar/CalendarPreview.tsx'), /week.teaching_dates.map\(day\)/)
})
test('schedule review includes past dates, hides zero-counter noise and does not block missing delivery labels', () => {
 const s = source('calendar/ClassSchedule.tsx')
 assert.match(s, /dated entries, including past dates/)
 assert.match(s, /Schedule notes/)
 assert.match(s, /\{planning && <CourseDatesForm/)
 assert.doesNotMatch(s, /needsRotation|Past dates not added|preview.changes.unchanged|preview.changes.skipped_past/)
 assert.match(source('calendar/ScheduleView.tsx'), /Mode not specified by school/)
 assert.doesNotMatch(source('calendar/ScheduleView.tsx'), /will not be added/)
})
test('month view uses complete Monday-first months, leap days and year boundaries', () => {
 assert.equal(monthDays('2028-02').days.length, 29)
 assert.equal(monthDays('2026-11').offset, 6)
 assert.equal(monthDays('2026-11').days.at(-1), '2026-11-30')
 assert.equal(moveMonth('2026-12', 1), '2027-01')
 assert.equal(moveMonth('2026-01', -1), '2025-12')
 assert.equal(localDay('2026-07-12T18:00:00Z'), '2026-07-13')
})
test('calendar successful response parsing preserves cancellation, not empty replacement data', async () => {
 const original = globalThis.fetch
 try {
  globalThis.fetch = async () => ({ ok: true, json: async () => { throw new DOMException('Aborted', 'AbortError') } })
  await assert.rejects(calendarRequest('', false), { name: 'AbortError' })
 } finally { globalThis.fetch = original }
})
test('calendar coded parsing errors preserve actionable Thai recovery', async () => {
 const original = globalThis.fetch
 try {
  globalThis.fetch = async () => ({ ok: false, json: async () => ({ detail: { code: 'parse_failed', message: 'Provider failed' } }) })
  await assert.rejects(calendarRequest('/revisions/1/parse', true), /ไฟล์ต้นฉบับและฉบับร่างยังคงอยู่/)
 } finally { globalThis.fetch = original }
})
test('calendar scoped text and controls retain AA contrast', () => {
 const luminance = hex => { const rgb = hex.match(/[a-f0-9]{2}/gi).map(x => parseInt(x, 16) / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4); return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722 }
 const contrast = (a, b) => { const values = [luminance(a), luminance(b)].sort((a, b) => b - a); return (values[0] + .05) / (values[1] + .05) }
 for (const [fg, bg] of [['171717','ffffff'],['525252','ffffff'],['404040','f5f5f5'],['1d4ed8','eff6ff'],['1e3a8a','eff6ff'],['166534','f0fdf4'],['92400e','fffbeb'],['991b1b','fef2f2']]) assert(contrast(fg,bg) >= 4.5, `${fg}/${bg}`)
 assert(contrast('737373','ffffff') >= 3)
})
test('calendar upload/review remains separate from publishing or changing classes', () => {
 const s = source('calendar/CalendarLibrary.tsx')
 assert.match(s, /new FormData/)
 assert.match(s, /accept="application\/pdf"/)
 assert.match(s, /expected_version: revision.version, payload/)
 assert.match(s, /reviewed: true, accept_proposals: true, payload, metadata/)
 assert.match(s, /disabled=\{busy \|\| !hasDates \|\| !metadataValid\}/)
 assert.match(s, /\/source`/)
 assert.match(s, /teaching: e.target.checked/)
 assert.match(s, /aria-label=\{t\('Teaching week to inspect'/)
 assert.match(s, /Extracted text below is a reading aid/)
 assert.doesNotMatch(s, /<iframe/)
 assert.doesNotMatch(s, /assignments\/|\/schedules\/apply|localStorage/)
})
test('PDF upload and reopening an empty saved draft read dates automatically without exposing blank validation forms', () => {
 const s = source('calendar/CalendarLibrary.tsx')
 assert.match(s, /setFile\(null\); await openRevision\(value\)/)
 assert.match(s, /value\.state === 'draft' && !hasCalendarDates\(value\.payload\)\) await readPdf\(value\)/)
 assert.match(s, /openRevision\(await calendarRequest<Revision>\(`\/revisions\/\$\{c\.latest_revision_id\}/)
 assert.match(s, /reading \? .*Reading your calendar PDF/)
 assert.match(s, /!hasDates && !manual/)
 assert.match(s, /hasDates && !dirty && Boolean\(revision\.issues/)
 assert.match(s, /Retry reading PDF/)
 assert.match(s, /readFailed && dirty/)
 assert.match(s, /saved\.version !== revision\.version/)
 assert.doesNotMatch(s, /Extract dates from PDF/)
 assert.doesNotMatch(s, /I verified|Corrected and resolved|needsReview|setReviewed/)
 assert.match(s, /!editing && hasDates \? <CalendarPreview/)
 assert.match(s, /PDF reading details/)
 assert.match(s, /<details open=\{term\.weeks\.length === 0\}/)
 assert.match(s, /See all \$\{term\.weeks\.length\} weeks/)
})
test('file selection opens a filled preview; metadata editing and source notes are optional', () => {
 const s = source('calendar/CalendarLibrary.tsx'), preview = source('calendar/CalendarPreview.tsx')
 assert.match(s, /body.append\('file', selected\)/)
 assert.doesNotMatch(s, /Object.entries\(form\)|new Date\(\).getFullYear|New calendar document/)
 assert.match(s, /void upload\(selected\)/)
 assert.match(s, /Edit calendar/)
 assert.match(s, /Accept calendar/)
 assert.match(s, /metadata\.academic_year/)
 assert.match(preview, /Calendar preview/)
 assert.match(preview, /week\.starts_on/)
 assert.match(preview, /closure\.makeup_on/)
 assert.doesNotMatch(preview, /type="checkbox"|<input|question|resolve/i)
})
test('PDF URL uses the same authenticated import and never downloads in the browser', () => {
 const s = source('calendar/CalendarLibrary.tsx')
 assert.match(s, /body.append\('url', url.trim\(\)\)/)
 assert.match(s, /type="url"/)
 assert.match(s, /Use PDF URL/)
 assert.match(s, /onSubmit=.*void importUrl\(\)/)
 assert.match(s, /setUrlEntry\(false\); await openRevision\(value\)/)
 assert.doesNotMatch(s, /fetch\(url|iframe/)
 assert.doesNotMatch(s, /!value.source_kind|Document preview · abridged calendar|Upload full calendar PDF/)
 assert.match(s, /hasDates = hasCalendarDates\(payload\)/)
})
test('academic dates are real calendar content without inventing teaching weeks', () => {
 const event = { semester: 1, program: 'Example program', kind: 'opening', title: 'Opening', starts_on: '2027-01-31', ends_on: '2027-01-31', page: 1 }
 assert.equal(hasCalendarDates({ timezone: 'Asia/Bangkok', terms: [], events: [] }), false)
 assert.equal(hasCalendarDates({ timezone: 'Asia/Bangkok', terms: [], events: [event] }), true)
 assert.equal(formatCalendarDate(event.starts_on, false), '31 Jan 2027')
 assert.match(formatCalendarDate(event.starts_on, true), /2570/)
 const view = source('calendar/CalendarDates.tsx'), lib = source('calendar/CalendarLibrary.tsx')
 assert.match(view, /All programs/)
 assert.match(view, /visible.filter\(\(\{ event \}\) => event.program === name\)/)
 assert.match(view, /onChange \?/)
 assert.match(view, /Academic date to edit/)
 assert.match(lib, /events => \{ setPayload/)
 const schedule = source('calendar/ClassSchedule.tsx')
 assert.doesNotMatch(schedule, /r.has_teaching_weeks !== false/)
 assert.match(schedule, /o.semester === context.semester/)
 assert.match(schedule, /CourseDatesForm/)
 assert.match(schedule, /Create class schedule/)
 assert.match(schedule, /Create or open syllabus draft/)
 assert.match(schedule, /syllabus.editor_url/)
 assert.match(source('calendar/CourseDatesForm.tsx'), /do not alter the school calendar/)
 assert.match(source('calendar/CourseDatesForm.tsx'), /Course holidays and make-ups/)
})
test('school policy is automatic; only an explicit course override reveals a selector, never a first-week control', () => {
 const s = source('calendar/ClassSchedule.tsx')
 assert.match(s, /Override school policy/)
 assert.match(s, /Course-only override/)
 assert.match(s, /Use school policy/)
 assert.match(s, /policy_override: overriding \? pattern \|\| null : null/)
 assert.match(s, /setOverriding\(Boolean\(saved.policy_override\)\)/)
 assert.match(s, /The school timetable and calendar remain unchanged/)
 assert.doesNotMatch(s, /Teaching mode|Choose teaching mode|First hybrid week|first week’s mode|setHybridStart|hybrid_start/)
 for (const th of [false, true]) {
  assert.notEqual(teachingPolicyLabel('even_onsite', th), teachingPolicyLabel('onsite', th))
  assert.notEqual(teachingPolicyLabel('online', th), teachingPolicyLabel(undefined, th))
 }
 assert.match(teachingPolicyLabel(undefined, false), /Not stated/)
 assert.match(teachingPolicyLabel('even_onsite', false), /even school weeks/)
})
test('PDF URL errors offer localized retry or file upload without claiming a source was saved', async () => {
 const original = globalThis.fetch
 try {
  for (const th of [false, true]) {
   globalThis.fetch = async () => ({ ok: false, json: async () => ({ detail: { code: 'url_unavailable', message: 'Server detail' } }) })
   await assert.rejects(calendarRequest('', th), th ? /อัปโหลดไฟล์/ : /upload the file/)
  }
 } finally { globalThis.fetch = original }
})
test('PDF reading errors describe recovery and preserve the uploaded source in both languages', async () => {
 const original = globalThis.fetch
 try {
  for (const th of [false, true]) {
   globalThis.fetch = async () => ({ ok: false, json: async () => ({ detail: { code: 'ai_unavailable', message: 'AI is not enabled for this organization' } }) })
   await assert.rejects(calendarRequest('/revisions/1/parse', th), th ? /ไฟล์ต้นฉบับและฉบับร่างยังคงอยู่/ : /Your PDF and draft are saved/)
  }
 } finally { globalThis.fetch = original }
})
test('calendar selection and preview do not automatically mutate sessions or student membership', () => {
 const s = source('calendar/ClassSchedule.tsx')
 const effect = s.slice(s.indexOf('useEffect('), s.indexOf('async function act'))
 assert.doesNotMatch(effect, /jsonBody|POST|rosterRequest/)
 assert.match(s, /fingerprint: preview.fingerprint, reviewed/)
 assert.match(s, /expected_version: preview.version/)
 assert.match(s, /disabled=\{busy \|\| !reviewed \|\| Boolean\(preview.errors\?\.length\)\}/)
 assert.match(s, /disabled=\{busy \|\| !rosterReviewed\}/)
 assert.match(s, /confirm_changes: rosterReviewed/)
 assert.doesNotMatch(s, /assignment_id|assignment_uuid|due_date/)
})
test('shared calendar and school-only class schedules stay inside native account shell', () => {
 const s = source('ClassesWorkspace.tsx')
 assert.match(s, /CalendarLibrary th=\{th\}/)
 assert.match(s, /ClassSchedule classId=\{studentClass.id\}/)
 assert.match(s, /nativeClasses=data\?\.classes.filter\(c=>c.course_id!==null\)/)
 assert.match(s, /data.classes.filter\(c=>c.course_id===null\|\|!c.manageable\)/)
 assert.match(source('AttendanceWorkspace.tsx'), /schedule.sessions.some\(s=>s.id===id\)/)
 assert.match(source('AttendanceWorkspace.tsx'), /\?session=\$\{requested\}/)
})
test('table and calendar open the same attendance session; cancellation and makeups have text labels', () => {
 const s = source('calendar/ScheduleView.tsx')
 assert.match(s, /href=\{s.attendance_url\}/)
 assert.match(s, /s.makeup_for/)
 assert.match(s, /No class/)
 assert.match(s, /aria-pressed=\{selected === day\}/)
 assert.match(s, /aria-label=\{t\('Selected day'/)
 assert.match(source('calendar/calendar.module.css'), /prefers-reduced-motion/)
 assert.match(source('calendar/calendar.module.css'), /forced-colors/)
})
