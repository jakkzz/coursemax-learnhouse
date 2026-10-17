import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { calendarRequest, localDay, monthDays, moveMonth } from '../components/Objects/Classes/calendar/model.ts'
const source = file => fs.readFileSync(new URL('../components/Objects/Classes/' + file, import.meta.url), 'utf8')
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
 assert.match(s, /disabled=\{busy \|\| dirty \|\| !reviewed \|\| !hasDates \|\| needsReview\}/)
 assert.match(s, /\/source`/)
 assert.match(s, /teaching: e.target.checked/)
 assert.match(s, /aria-label=\{t\('Teaching week to inspect'/)
 assert.match(s, /Extracted text below is a reading aid/)
 assert.doesNotMatch(s, /<iframe/)
 assert.doesNotMatch(s, /assignments\/|\/schedules\/apply|localStorage/)
})
test('PDF upload and reopening an empty saved draft read dates automatically without exposing blank validation forms', () => {
 const s = source('calendar/CalendarLibrary.tsx')
 assert.match(s, /setUploading\(false\); setFile\(null\); await openRevision\(value\)/)
 assert.match(s, /value\.state === 'draft' && value\.payload\.terms\.length === 0\) await readPdf\(value\)/)
 assert.match(s, /openRevision\(await calendarRequest<Revision>\(`\/revisions\/\$\{c\.latest_revision_id\}/)
 assert.match(s, /reading \? .*Reading your calendar PDF/)
 assert.match(s, /!hasDates && !manual/)
 assert.match(s, /hasDates && !dirty && Boolean\(revision\.issues/)
 assert.match(s, /Retry reading PDF/)
 assert.match(s, /readFailed && dirty/)
 assert.match(s, /saved\.version !== revision\.version/)
 assert.doesNotMatch(s, /Extract dates from PDF/)
 assert.match(s, /Dates or teaching status to check/)
 assert.match(s, /setTermIndex\(check\.ti\); setTab\(check\.tab\)/)
 assert.match(s, /setWeekIndex\(check\.index\)/)
 assert.match(s, /checks\.length > 0 \|\| Boolean\(payload\.unresolved/)
 assert.match(s, /PDF reading details/)
 assert.match(s, /<details open=\{term\.weeks\.length === 0\}/)
 assert.match(s, /See all \$\{term\.weeks\.length\} weeks/)
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
