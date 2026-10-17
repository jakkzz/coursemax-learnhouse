import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = file => readFileSync(new URL('../' + file, import.meta.url), 'utf8')

test('one workspace rail owns separate mounted school, LearnHouse and calendar panels', () => {
 const workspace = source('components/Objects/Classes/ClassesWorkspace.tsx')
 assert.equal((workspace.match(/<TabsList /g) ?? []).length, 1)
 assert.equal((workspace.match(/<TabsTrigger /g) ?? []).length, 3)
 assert.doesNotMatch(workspace, /SchoolWorkspaceNav|school\.sources|NRRU class list|workspace\.intro/)
 assert.match(workspace, /<TabsList[^>]+aria-label=\{th\?'พื้นที่ชั้นเรียน':'Class workspace'\}/)
 assert.match(workspace, /<TabsContent value="calendar" forceMount hidden=\{sourceView!=='school'\|\|!calendarOpen\}/)
 assert.match(workspace, /<TabsContent value="classes" forceMount hidden=\{sourceView!=='school'\|\|calendarOpen\}/)
 assert.match(workspace, /<TabsContent value="learnhouse" forceMount hidden=\{sourceView!=='learnhouse'\}/)
 assert.match(workspace, /calendarVisited&&<CalendarLibrary th=\{th\} embedded/)
 assert.match(workspace, /onOpenCalendars=\{openCalendars\}/)
 assert.match(workspace, /function openCalendars\(\)\{setSourceView\('school'\);setCalendarVisited\(true\);setCalendarOpen\(true\)\}/)
 assert.match(workspace, /function closeCalendars\(\)\{setCalendarOpen\(false\);setCalendarRefresh/)
 assert.doesNotMatch(workspace, /CalendarDays|\{calendarOpen&&<CalendarLibrary/)
})

test('calendar tab keeps native keyboard semantics and revision back/unsaved-edit checks', () => {
 assert.match(source('adapters/tabs.ts'), /export \{ Tabs, TabsList, TabsTrigger, TabsContent \} from '@components\/ui\/tabs'/)
 const library = source('components/Objects/Classes/calendar/CalendarLibrary.tsx')
 assert.match(library, /const Heading = embedded \? 'h2' : 'h1'/)
 assert.match(library, /\(revision \|\| !embedded\) && <Button/)
 assert.match(library, /onClick=\{\(\) => revision \? leave\(\) : onClose\(\)\}/)
 assert.match(library, /if \(dirty && !window.confirm/)
})
