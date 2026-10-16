import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const read = name => fs.readFileSync(new URL(`../components/Objects/Classes/${name}`, import.meta.url), 'utf8')
const connections = read('ClassConnections.tsx')
const workspace = read('ClassesWorkspace.tsx')

test('class connections retrieve NRRU rosters without URL inputs or URL request fields', () => {
  assert.doesNotMatch(connections, /type=["']url["']|roster_url|setUrl|paste|transcrib/i)
  assert.match(connections, /academic_year: context\.academic_year, semester: context\.semester, section: context\.classRow\.section/)
  assert.match(connections, /preview.*course_id: Number\(course\)/s)
  assert.doesNotMatch(connections, /preview.*course_id: Number\(course\),[^}]*roster_url/s)
  assert.match(connections, /roster_count/)
  assert.match(connections, /imports the initial roster|นำเข้ารายชื่อเริ่มต้น/)
})

test('advanced setup keeps internal identifiers server-supplied and preserves correction values', () => {
  assert.doesNotMatch(workspace, /registry_class_id:t\.|\['academic_year',[^\]]*registry_class_id/)
  assert.match(workspace, /registry_course_id:form\.registry_course_id\|\|null,registry_class_id:editing\?\(form\.registry_class_id\|\|null\):null/)
  assert.match(workspace, /registry_course_id:current\.registry_course_id\|\|'',registry_class_id:current\.registry_class_id\|\|''/)
  assert.match(workspace, /Not mapped to the registrar catalog|ยังไม่จับคู่กับแค็ตตาล็อกทะเบียน/)
  assert.match(workspace, /assignmentCourse[^\n]*registry_course_id/)
})
