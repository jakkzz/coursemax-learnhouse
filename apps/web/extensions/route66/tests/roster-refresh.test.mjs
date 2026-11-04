import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../components/Objects/Classes/ClassesWorkspace.tsx', import.meta.url), 'utf8')

test('opening a class automatically reads its saved roster with cancellation', () => {
  assert.match(source, /useEffect\(\(\)=>\{setRoster\(null\).*?new AbortController\(\);request\(`\/\$\{selected\}\/roster`,undefined,abort.signal\)\.then\(setRoster\).*?return\(\)=>abort.abort\(\)\},\[selected,refresh,mounted,t.failed\]\)/s)
  assert.match(source, /!roster&&!error&&<p role="status">\{t.loadingRoster\}/)
})

test('saved roster delegates checking and review to the shared refresh control', () => {
  assert.match(source, /sourceView==='learnhouse'&&<RosterRefreshStatus/)
  assert.match(source, /disabled=\{busy\} onReview=\{loadPreview\}/)
  const status = readFileSync(new URL('../components/Objects/Classes/RosterRefreshStatus.tsx', import.meta.url), 'utf8')
  assert.match(status, /review \? t.review : failure \? t.retry : t.check/)
  assert.match(status, /aria-live="polite"/)
  assert.match(status, /review: 'ตรวจสอบการเปลี่ยนแปลง'/)
  assert.doesNotMatch(source, /Load official roster|t\.loadRoster/)
})

test('refresh retains the existing preview and explicit apply path', () => {
  assert.match(source, /async function loadPreview\(\).*?const value=await request\(`\/\$\{id\}\/roster\/preview`,\{\}\).*?selectedRef.current===id.*?setPreview\(value\)/s)
  assert.match(source, /disabled=\{busy\|\|!reviewed\|\|previewStale\}.*?roster\/apply/s)
  assert.match(source, /confirm_large_drop:preview.requires_large_drop_review===true&&reviewed/)
})
