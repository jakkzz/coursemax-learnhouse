import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source = name => fs.readFileSync(new URL('../components/Objects/Classes/' + name, import.meta.url), 'utf8')

test('private calendar intake uses per-calendar ownership and never silently shares or applies schedules', () => {
 const lib = source('calendar/CalendarLibrary.tsx')
 assert.match(lib, /catalog\?\.can_upload \?\? catalog\?\.can_edit/)
 assert.match(lib, /value.calendar.can_edit \?\? catalog\?\.can_edit/)
 assert.match(lib, /body.append\('scope', catalog\?\.can_edit \? scope : 'teacher'\)/)
 assert.match(lib, /Accepting keeps this calendar private/)
 assert.match(lib, /Prepare school-wide copy/)
 assert.match(lib, /\/revisions\/\$\{revision.id\}\/share/)
 assert.match(lib, /revision.source_url/)
 assert.doesNotMatch(lib, /\/schedules\/apply|\/connections\/.*\/connect/)
})

test('course proposals attach accepted revisions and reviewers use the same private original', () => {
 const connections = source('ClassConnections.tsx')
 assert.match(connections, /\/requests\/\$\{requestId\}\/calendar/)
 assert.match(connections, /revision_id: Number\(revision\)/)
 assert.match(connections, /r.academic_year === year && r.published_revision_id/)
 assert.match(connections, /CalendarEvidence key=\{selected.id\}/)
 assert.match(connections, /\/revisions\/\$\{value.id\}\/source/)
 assert.match(connections, /Attaching does not approve the course or create a class schedule/)
 assert.match(source('real-teaching/RealTeachingWorkspace.tsx'), /SectionConnection .*onOpenCalendars=\{onOpenCalendars\}/)
})
