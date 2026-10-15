import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
test('Classes reserves the same mobile footer clearance as native account pages, without a core edit',()=>{
 const css=fs.readFileSync(new URL('../components/Objects/Classes/classes-account-layout.module.css',import.meta.url),'utf8')
 assert.match(css,/@media \(width < 48rem\)/)
 assert.match(css,/:global\(\.lh-org-font-root\):has\(\.accountWorkspace\)/)
 assert.match(css,/padding-bottom: calc\(6rem \+ env\(safe-area-inset-bottom\)\)/)
 const layout=fs.readFileSync(new URL('../components/Objects/Classes/ClassesAccountLayout.tsx',import.meta.url),'utf8')
 assert.match(layout,/styles\.accountWorkspace/)
 assert.doesNotMatch(layout,/document\.|createPortal|setAttribute|style\.padding/)
})
