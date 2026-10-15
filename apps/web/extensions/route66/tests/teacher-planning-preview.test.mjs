import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { buildProposal, demoRoster, applySampleRoster, filterRoster, canPreviewTeaching, topicForWeek, sections } from '../components/Objects/Classes/teaching-preview/model.ts'

test('preview entry relies on strict server-projected staff/manageability, not domain or name',()=>{
 assert.equal(canPreviewTeaching(true,false),true);assert.equal(canPreviewTeaching(false,true),true)
 for(const pair of [[false,false],[null,null],['true',false],[false,1],[{},false]])assert.equal(canPreviewTeaching(...pair),false)
})
test('each fictional section has independent dates, repeated weekly meetings and stable proposal IDs',()=>{
 for(const section of sections){const plan=buildProposal(section.id,true)
 assert.equal(plan.filter(s=>s.state!=='no_class').length,32)
 assert.equal(new Set(plan.map(s=>s.id)).size,plan.length)
 assert.deepEqual(plan,buildProposal(section.id,true))
 assert(plan.every(s=>s.section===section.id&&s.date.startsWith('2027-')))
 for(const row of plan)assert(row.end>row.start)
 }
 assert.notDeepEqual(buildProposal('P1',false).map(s=>s.date),buildProposal('P2',false).map(s=>s.date))
})
test('demo holiday retains closure, links its make-up and does not inflate counted sessions',()=>{
 const plan=buildProposal('P1',true),closed=plan.find(s=>s.state==='no_class'),makeup=plan.find(s=>s.state==='makeup')
 assert(closed);assert(makeup);assert.equal(makeup.replaces,closed.id);assert.equal(closed.date,'2027-06-28');assert.equal(makeup.date,'2027-07-02');assert.equal(makeup.week,closed.week)
 assert.equal(buildProposal('P1',false).length,32);assert.equal(plan.length,33)
 assert.equal(buildProposal('P2',true).filter(s=>s.state==='no_class').length,0)
})
test('topics are shared reusable course data and never inferred from registrar labels',()=>{
 assert.deepEqual(topicForWeek(1),topicForWeek(2));assert.notDeepEqual(topicForWeek(2),topicForWeek(3))
 for(const w of [0,-1,17,NaN,1.5])assert.throws(()=>topicForWeek(w))
 assert.throws(()=>buildProposal('other',true))
})
test('sample roster review preserves manual identities, once-missing active members and withdrawn history',()=>{
 const before=demoRoster('P1'),snapshot=JSON.stringify(before),after=applySampleRoster(before,'P1')
 assert.equal(JSON.stringify(before),snapshot);assert.equal(after.length,8)
 for(const old of before)assert(after.some(s=>s.id===old.id))
 assert.deepEqual(after.find(s=>s.source==='manual'),before.find(s=>s.source==='manual'))
 assert.equal(after.find(s=>s.id==='DEMO-P1-05').missing,1);assert.equal(after.find(s=>s.id==='DEMO-P1-05').status,'active')
 assert.equal(after.find(s=>s.id==='DEMO-P1-06').status,'withdrawn')
 assert.deepEqual(applySampleRoster(after,'P1'),after)
 assert(demoRoster('P2').every(s=>!after.some(p=>p.id===s.id)))
})
test('roster filters recover empty results and include distinct account/membership states',()=>{
 const people=demoRoster('P1')
 assert.equal(filterRoster(people,'DEMO-P1-01','all','all').length,1)
 assert.equal(filterRoster(people,'','withdrawn','all').length,1)
 assert.equal(filterRoster(people,'','all','review').length,1)
 assert.equal(filterRoster(people,'not-found','all','all').length,0)
 assert.deepEqual(filterRoster(people,'  ','all','all'),people)
})
test('dropdowns carry explicit localized accessible labels independently of their option text',()=>{
 const source=fs.readFileSync(new URL('../components/Objects/Classes/teaching-preview/TeacherPlanningPreview.tsx',import.meta.url),'utf8')
 for(const key of ['section','weekSelect','membership','accounts'])assert(source.includes(`<select aria-label={t.${key}}`))
 assert.equal((source.match(/<select\s/g)||[]).length,4)
})
test('preview implementation is memory-only with no academic API, persistence, real student IDs or authoring textarea',()=>{
 const dir=new URL('../components/Objects/Classes/teaching-preview/',import.meta.url)
 for(const file of ['TeacherPlanningPreview.tsx','model.ts','copy.ts']){
 const source=fs.readFileSync(new URL(file,dir),'utf8')
 assert.doesNotMatch(source,/\bfetch\s*\(|\baxios\b|localStorage|sessionStorage|indexedDB|sendBeacon|\/api\/|<textarea|@nrru\.ac\.th/)
 }
})
