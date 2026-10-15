import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { linkedTeachingClass, nativeCoursePath } from '../components/Objects/Classes/real-teaching/model.ts'

test('native course handoff strips exactly one API prefix and encodes one route segment',()=>{
 assert.equal(nativeCoursePath('course_abc-123'),'/course/abc-123')
 assert.equal(nativeCoursePath('course_synthetic_fixture'),'/course/synthetic_fixture')
 assert.equal(nativeCoursePath('course_a/b?c#d'),'/course/a%2Fb%3Fc%23d')
 const native=fs.readFileSync(new URL('../../../services/courses/courses.ts',import.meta.url),'utf8')
 assert.match(native,/courses\/course_\$\{course_uuid\}\/meta/)
 for(const file of ['ClassesWorkspace.tsx','real-teaching/RealTeachingWorkspace.tsx']){
  const source=fs.readFileSync(new URL('../components/Objects/Classes/'+file,import.meta.url),'utf8')
  assert.match(source,/href=\{nativeCoursePath\(/)
  assert.doesNotMatch(source,/href=\{`\/course\/\$\{/)
 }
})

const context={academic_year:2569,semester:1,fetched_at:'2026-10-15T00:00:00Z',classRow:{registry_course_id:'501',course_code:'TEST501',title:'Synthetic test fixture only',section:'S1',meetings:[{day:'Wednesday',start_time:'09:00',end_time:'12:00',details:'Original rotation description'}]}}
const row={id:21,registry_course_id:'501',academic_year:2569,semester:1,section:'S1',manageable:true,course_uuid:'course_fixture',course_available:false}
test('real workspace links only exact authorized course/year/term/section, never names or codes',()=>{
 assert.equal(linkedTeachingClass(context,[row]),row)
 for(const patch of [{registry_course_id:'502'},{registry_course_id:null},{academic_year:2570},{semester:2},{section:'S2'},{manageable:false},{manageable:'true'},{id:0},{id:1.5}])assert.equal(linkedTeachingClass(context,[{...row,...patch}]),null)
 assert.equal(linkedTeachingClass(context,[]),null)
 assert.equal(linkedTeachingClass(context,[row,{...row,id:22}]),null)
 assert.equal(linkedTeachingClass(context,[row,{...row,id:22,manageable:false}]),null)
 assert.equal(linkedTeachingClass(context,[row,{...row,id:0}]),null)
 assert.equal(linkedTeachingClass(context,[{...row,registry_course_id:null,course_code:'TEST501',course_name:context.classRow.title}]),null)
})
test('link lookup is immutable and does not manufacture classes, dates or institutional identity',()=>{
 const before=JSON.stringify({context,row});linkedTeachingClass(context,[row]);assert.equal(JSON.stringify({context,row}),before)
 const source=fs.readFileSync(new URL('../components/Objects/Classes/real-teaching/model.ts',import.meta.url),'utf8')
 assert.doesNotMatch(source,/new Date|fetch\s*\(|POST|@nrru|course_code\s*===|title\s*===/)
})
test('active classes use actual timetable context, with no fictional preview entry or module',()=>{
 const source=fs.readFileSync(new URL('../components/Objects/Classes/ClassesWorkspace.tsx',import.meta.url),'utf8')
 assert.doesNotMatch(source,/teaching-preview|TeacherPlanningPreview|planningPreview|canPreviewTeaching|teaching-preview-entry|fictional/)
 assert.match(source,/RealTeachingWorkspace/)
 assert.match(source,/onOpenClass=\{setWorkspaceClass\}/)
 assert.match(source,/hidden=\{Boolean\(workspaceClass\)\}/)
})
test('production demonstration data and its simulator have been removed, not relabelled',()=>{
 for(const file of ['TeacherPlanningPreview.tsx','model.ts','copy.ts','preview.module.css'])assert.equal(fs.existsSync(new URL('../components/Objects/Classes/teaching-preview/'+file,import.meta.url)),false)
 const source=fs.readFileSync(new URL('../components/Objects/Classes/real-teaching/RealTeachingWorkspace.tsx',import.meta.url),'utf8')
 assert.doesNotMatch(source,/\b(example|sample|fictional|demo|test)\b/i)
 assert.match(source,/overview: 'Overview'/)
 assert.match(source,/timetable: 'Timetable'/)
 assert.match(source,/syllabus: 'Syllabus'/)
 assert.match(source,/useState<View>\('overview'\)/)
})
test('real workspace offers read-only facts and canonical handoffs, no fake academic writers or prose',()=>{
 const source=fs.readFileSync(new URL('../components/Objects/Classes/real-teaching/RealTeachingWorkspace.tsx',import.meta.url),'utf8')
 assert.doesNotMatch(source,/\bfetch\s*\(|localStorage|sessionStorage|<textarea|DEMO|Sample|fictional|buildProposal|demoRoster/)
 assert.match(source,/\/attendance\?class=/)
 assert.match(source,/onOpenRoster/)
 assert.match(source,/course_available/)
 assert.match(source,/not set up|not connected/)
})
