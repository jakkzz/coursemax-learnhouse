import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../components/Objects/Classes/ClassesWorkspace.tsx', import.meta.url), 'utf8')

test('opening a class automatically reads its saved roster with cancellation', () => {
  assert.match(source, /useEffect\(\(\)=>\{setRoster\(null\).*?new AbortController\(\);request\(`\/\$\{selected\}\/roster`,undefined,abort.signal\)\.then\(setRoster\).*?return\(\)=>abort.abort\(\)\},\[selected,refresh,mounted,t.failed\]\)/s)
  assert.match(source, /!roster&&!error&&<p role="status">\{t.loadingRoster\}/)
})

test('registrar refresh uses an accessible icon rather than an initial-load action', () => {
  assert.match(source, /<Button variant="outline" size="icon" className="min-h-11 min-w-11" aria-label=\{t.refreshRoster\} title=\{t.refreshRoster\} aria-busy=\{busy\} disabled=\{busy\} onClick=\{\(\)=>void loadPreview\(\)\}><RefreshCw size=\{18\} aria-hidden="true" \/><\/Button>/)
  assert.match(source, /refreshRoster:'Refresh roster'/)
  assert.match(source, /refreshRoster:'อัปเดตรายชื่อ'/)
  assert.doesNotMatch(source, /Load official roster|t\.loadRoster/)
})

test('refresh retains the existing preview and explicit apply path', () => {
  assert.match(source, /async function loadPreview\(\).*?setPreview\(await request\(`\/\$\{selected\}\/roster\/preview`,\{\}\)\)/s)
  assert.match(source, /disabled=\{busy\|\|!reviewed\}.*?roster\/apply/s)
})
