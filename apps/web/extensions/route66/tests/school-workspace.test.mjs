import test from 'node:test'
import assert from 'node:assert/strict'
import { confirmedStaff, filterTimetable, readSavedTerm, timetableYears } from '../components/Objects/Account/subpages/school-workspace-model.ts'

const directory = { officer_id: 'fixture-1', name_th: 'อาจารย์ตัวอย่าง', name_en: 'Synthetic Teacher' }
test('only server-projected confirmed staff may display their own timetable', () => {
  assert.equal(confirmedStaff({ school_kind: 'staff', directory_identity: directory, needs_google_signin: false }), true)
  for (const status of [null, {}, { school_kind: 'student', directory_identity: directory }, { school_kind: null, directory_identity: directory }, { school_kind: 'staff', directory_identity: null }, { school_kind: 'staff', directory_identity: directory, needs_google_signin: true }]) assert.equal(confirmedStaff(status), false)
})
const classes = [
  { course_code: 'DEMO101', title: 'การบินเบื้องต้น', section: 'P1', meetings: [{ day: 'Monday', details: 'Room A' }] },
  { course_code: 'DEMO202', title: 'Synthetic Planning', section: 'P2', meetings: [{ day: 'Tuesday', details: 'Room B' }] },
]
test('timetable search matches course, section, day or room without changing source records', () => {
  const before = JSON.stringify(classes)
  for (const query of ['DEMO101', 'การบิน', 'p1', 'monday', 'room a']) assert.deepEqual(filterTimetable(classes, query), [classes[0]])
  assert.deepEqual(filterTimetable(classes, '   '), classes)
  assert.deepEqual(filterTimetable(classes, 'missing'), [])
  assert.equal(JSON.stringify(classes), before)
})
test('saved term accepts only current registrar-supported years and semesters', () => {
  assert.deepEqual(readSavedTerm('{"year":2569,"semester":1}', 2569), { year: 2569, semester: 1 })
  for (const raw of [null, '', 'broken', 'null', '[]', '{"year":"2569","semester":1}', '{"year":2567,"semester":1}', '{"year":2569,"semester":4}', '{"year":2569,"semester":1.5}']) assert.equal(readSavedTerm(raw, 2569), null)
})
test('year options include the displayed registrar year in sorted order without duplicates', () => {
  assert.deepEqual(timetableYears(2569, 2569), [2568, 2569, 2570])
  assert.deepEqual(timetableYears(2569, 2567), [2567, 2568, 2569, 2570])
})
