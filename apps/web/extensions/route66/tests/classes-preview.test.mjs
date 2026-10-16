import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { canViewSection, initialState, members, sections, transition, visibleCourses, hasReview } from './fixtures/ClassesPreview/model.ts'
import { copy } from './fixtures/ClassesPreview/copy.ts'

test('teacher sees every section of both assigned courses, not unrelated courses', () => {
  assert.equal(visibleCourses('teacher').length, 2)
  assert.ok(canViewSection('teacher', 'f-a'))
  assert.ok(canViewSection('teacher', 'f-b'))
  assert.ok(canViewSection('teacher', 'f-old'))
  assert.ok(canViewSection('teacher', 'a-a'))
  assert.equal(canViewSection('teacher', 'c-a'), false)
  assert.equal(visibleCourses('admin').length, 3)
  assert.equal(visibleCourses('student').length, 0)
  assert.equal(canViewSection('teacher', 'missing'), false)
})
test('flagging preserves membership and the existing account link', () => {
  const before = initialState()
  const roster = JSON.stringify(members)
  const after = transition(before, { type: 'flag', role: 'teacher', person: 'student-a', section: 'f-a', reason: 'wrong_name' })
  assert.ok(hasReview(after, 'student-a'))
  assert.deepEqual(after.people, before.people)
  assert.equal(JSON.stringify(members), roster)
  assert.equal(after.reviews.at(-1).section, 'f-a')
  assert.equal(after.activity.at(-1).role, 'teacher')
})
test('duplicates and out-of-scope/foreign roster flags are rejected', () => {
  const state = initialState()
  for (const action of [
    { role: 'student', person: 'student-a', section: 'f-a' },
    { role: 'teacher', person: 'student-c', section: 'c-a' },
    { role: 'teacher', person: 'teacher-a', section: 'f-a' },
    { role: 'teacher', person: 'student-c', section: 'f-a' },
  ]) assert.equal(transition(state, { type: 'flag', reason: 'wrong_name', ...action }), state)
  const action = { type: 'flag', role: 'teacher', person: 'student-a', section: 'f-a', reason: 'wrong_name' }
  const flagged = transition(state, action)
  assert.equal(transition(flagged, action), flagged)
})
for (const [role, person] of [['student', 'student-d'], ['teacher', 'teacher-a']]) {
  test(`${role} can request only owned, confirmed school verification`, () => {
    const before = initialState()
    assert.equal(transition(before, { type: 'verify', role, person, confirmed: false }), before)
    assert.equal(transition(before, { type: 'verify', role, person: 'student-b', confirmed: true }), before)
    const pending = transition(before, { type: 'verify', role, person, confirmed: true })
    assert.ok(hasReview(pending, person))
    assert.deepEqual(pending.people, before.people)
    assert.equal(transition(pending, { type: 'verify', role, person, confirmed: true }), pending)
    const id = pending.reviews.at(-1).id
    const after = transition(pending, { type: 'decide', role: 'admin', review: id, decision: 'approve', confirmed: true, reason: 'Synthetic matching record reviewed' })
    assert.ok(after.people.find(p => p.id === person).verified)
    assert.equal(after.people.find(p => p.id === person).account, before.people.find(p => p.id === person).candidate)
    assert.equal(after.activity.at(-1).note, 'Synthetic matching record reviewed')
    assert.equal(after.reviews.at(-1).status, 'approved')
    assert.equal(transition(after, { type: 'decide', role: 'admin', review: id, decision: 'approve', confirmed: true, reason: 'Repeat' }), after)
  })
}
test('admin approval requires confirmation and reason; teacher/student cannot decide', () => {
  const pending = transition(initialState(), { type: 'verify', role: 'student', person: 'student-d', confirmed: true })
  const action = { type: 'decide', role: 'admin', review: pending.reviews.at(-1).id, decision: 'approve', confirmed: true, reason: 'Fixture checked' }
  for (const patch of [{ role: 'teacher' }, { role: 'student' }, { confirmed: false }, { reason: ' ' }]) assert.equal(transition(pending, { ...action, ...patch }), pending)
})
test('conflicting student and teacher evidence cannot be approved', () => {
  const before = initialState()
  for (const review of before.reviews) assert.equal(transition(before, { type: 'decide', role: 'admin', review: review.id, decision: 'approve', confirmed: true, reason: 'Cannot override conflict' }), before)
})
test('more evidence keeps request pending and prevents approval', () => {
  const pending = transition(initialState(), { type: 'verify', role: 'teacher', person: 'teacher-a', confirmed: true })
  const action = { type: 'decide', role: 'admin', review: pending.reviews.at(-1).id, decision: 'more_evidence', confirmed: false, reason: 'Need source confirmation' }
  const after = transition(pending, action)
  assert.equal(after.reviews.at(-1).status, 'more_evidence')
  assert.deepEqual(after.people, pending.people)
  assert.equal(transition(after, { ...action, decision: 'approve', confirmed: true }), after)
})
test('rejecting a request preserves identities and roster membership', () => {
  const before = initialState()
  const after = transition(before, { type: 'decide', role: 'admin', review: before.reviews[0].id, decision: 'reject', confirmed: false, reason: 'Identifiers differ' })
  assert.deepEqual(after.people, before.people)
  assert.equal(after.reviews[0].status, 'rejected')
})
test('reviewing a discrepancy retains original linked identity and verification', () => {
  const before = initialState()
  const flagged = transition(before, { type: 'flag', role: 'teacher', person: 'student-a', section: 'f-a', reason: 'wrong_name' })
  const after = transition(flagged, { type: 'decide', role: 'admin', review: flagged.reviews.at(-1).id, decision: 'approve', confirmed: true, reason: 'Original record confirmed' })
  assert.deepEqual(after.people, before.people)
})
test('manual/withdrawn identities and term-specific sections stay distinct', () => {
  const state = initialState()
  assert.equal(state.people.find(p => p.id === 'manual').number, undefined)
  assert.ok(members.some(m => m.status === 'withdrawn'))
  assert.notEqual(sections.find(s => s.id === 'f-a').id, sections.find(s => s.id === 'f-old').id)
  assert.deepEqual(initialState(), state)
})
test('English and Thai cover the same copy keys', () => {
  assert.deepEqual(Object.keys(copy.en).sort(), Object.keys(copy.th).sort())
  assert.ok(Object.values(copy.th).every(v => v.trim()))
})
test('retired preview is an inert redirect and cannot expose synthetic records', () => {
  const component = fs.readFileSync(new URL('../components/Dashboard/Pages/ClassesPreview/ClassesPreview.tsx', import.meta.url), 'utf8')
  const route = fs.readFileSync(new URL('../app/orgs/[orgslug]/dash/classes-preview/page.tsx', import.meta.url), 'utf8')
  for (const source of [component, route]) {
    assert.match(source, /redirect\('\/classes'\)/)
    assert.doesNotMatch(source, /fetch\s*\(|useReducer|localStorage|sessionStorage|\brole\b|\bview\b|\bquery\b|Demo Student|DEMO101/)
  }
})

test('historical fixture is test-only and production compatibility modules are inert', () => {
  const fixture = fs.readFileSync(new URL('./fixtures/ClassesPreview/model.ts', import.meta.url), 'utf8')
  assert.match(fixture, /Demo Student/)
  const productionRoot = new URL('../', import.meta.url).pathname
  const productionFiles = []
  const walk = dir => { for (const entry of fs.readdirSync(dir, { withFileTypes: true })) { const path = `${dir}/${entry.name}`; if (entry.isDirectory() && entry.name !== 'tests') walk(path); else if (entry.isFile() && /\.(ts|tsx|js|jsx|mjs)$/.test(entry.name)) productionFiles.push(path) } }
  walk(productionRoot)
  for (const path of productionFiles) assert.doesNotMatch(fs.readFileSync(path, 'utf8'), /tests\/fixtures|fixtures\/ClassesPreview/)
  for (const name of ['model.ts', 'copy.ts']) assert.match(fs.readFileSync(new URL(`../components/Dashboard/Pages/ClassesPreview/${name}`, import.meta.url), 'utf8'), /export\s*\{\}/)
  assert.match(fs.readFileSync(new URL('../components/Objects/Classes/ClassesWorkspace.tsx', import.meta.url), 'utf8'), /export|function|class/)
  assert.match(fs.readFileSync(new URL('../components/Objects/Account/subpages/SchoolIdentity.tsx', import.meta.url), 'utf8'), /export|function|const/)
})
