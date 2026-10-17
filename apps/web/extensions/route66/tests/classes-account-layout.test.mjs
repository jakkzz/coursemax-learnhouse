import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const read=p=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
test('Classes composes native account presentation, without another identity/navigation authority',()=>{
 const source=read('../components/Objects/Classes/ClassesAccountLayout.tsx')
 for(const name of ['GeneralWrapperStyled','Breadcrumbs','AccountSidebar','AccountActionsMobile','useLHSession','getUriWithOrg'])assert.match(source,new RegExp(name))
 assert.match(source,/currentSubpage="classes"/)
 assert.doesNotMatch(source,/fetch\(|localStorage|sessionStorage|NAV_ITEMS|is_superadmin|directory_identity/)
 assert.match(source,/md:w-72 lg:w-80/)
 assert.match(source,/sticky top-24/)
 assert.match(source,/flex-1 min-w-0/)
 assert.match(source,/md:hidden mb-4/)
})
test('Authenticated class route supplies org context; native delegates stay untouched',()=>{
 const page=read('../app/orgs/[orgslug]/(withmenu)/classes/page.tsx')
 assert.match(page,/getServerSession\(\)/)
 assert.match(page,/redirect\('\/login\?next=\/classes'\)/)
 assert.match(page,/await params/)
 assert.match(page,/<ClassesAccountLayout orgslug=/)
 assert.doesNotMatch(page,/GeneralWrapperStyled/)
 const workspace=read('../components/Objects/Classes/ClassesWorkspace.tsx')
 assert.doesNotMatch(workspace,/space-y-6 px-4 pb-24 pt-8 md:px-8/)
 assert.doesNotMatch(workspace,/SchoolWorkspaceNav/)
 assert.match(workspace, /Class workspace/)
})
