import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = file => readFileSync(new URL('../components/Objects/' + file, import.meta.url), 'utf8')

test('official school classes are the default and native classes remain a separate source', () => {
  const source = read('Classes/ClassesWorkspace.tsx')
  assert.match(source, /useState<'school'\|'learnhouse'>\('school'\)/)
  assert.match(source, /aria-label=\{th\?'พื้นที่ชั้นเรียน':'Class workspace'\}/)
  assert.match(source, /value="learnhouse" forceMount hidden=\{sourceView!=='learnhouse'\}/)
  assert.match(source, /value="classes" forceMount hidden=\{sourceView!=='school'\|\|calendarOpen\}/)
  assert.equal((source.match(/<TeacherTimetable /g) ?? []).length, 1)
})

test('official details and students do not require a LearnHouse connection', () => {
  const source = read('Classes/real-teaching/RealTeachingWorkspace.tsx')
  assert.match(source, /view === 'roster' && <OfficialRoster/)
  assert.match(source, /<dl className=\{styles.facts\}/)
  assert.match(source, /connecting && <SectionConnection/)
  assert.match(source, /not a dated calendar or make-up schedule/)
})

test('official roster auto-reads the selected tuple and never imports or edits membership', () => {
  const source = read('Classes/real-teaching/OfficialRoster.tsx')
  assert.match(source, /connections\/official-roster\?/)
  assert.match(source, /credentials: 'include', cache: 'no-store', signal: controller.signal/)
  assert.match(source, /\[registry_course_id, academic_year, semester, section, attempt\]/)
  assert.match(source, /active = false; clearTimeout\(timeout\); controller.abort\(\)/)
  assert.doesNotMatch(source, /method: 'POST'|roster\/apply|roster\/manual|localStorage|@nrru/)
})

test('school index reuses term selection and exact authorized LearnHouse matching', () => {
  const source = read('Account/subpages/SchoolTimetable.tsx')
  assert.match(source, /schoolMode \? school.indexRows/)
  assert.match(source, /linkedTeachingClass\(/)
  assert.match(source, /readSavedTerm/)
  assert.match(source, /teacher_name: teacherName/)
})
