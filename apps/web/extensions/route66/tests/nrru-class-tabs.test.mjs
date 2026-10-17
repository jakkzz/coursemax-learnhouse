import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = file => readFileSync(new URL('../' + file, import.meta.url), 'utf8')

test('NRRU classes owns separate class-list and calendar panels with persistent navigation', () => {
 const workspace = source('components/Objects/Classes/ClassesWorkspace.tsx')
 assert.match(workspace, /NRRU class list/)
 assert.match(workspace, /School calendar/)
 assert.match(workspace, /รายชื่อชั้นเรียน NRRU/)
 assert.match(workspace, /<TabsList[^>]+aria-label=\{th\?'ชั้นเรียน NRRU':'NRRU classes'\}/)
 assert.match(workspace, /<TabsContent value="calendar" forceMount hidden=\{!calendarOpen\}/)
 assert.match(workspace, /<TabsContent value="classes" forceMount hidden=\{calendarOpen\}/)
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
