import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = path => readFileSync(new URL('../' + path, import.meta.url), 'utf8')
const css = source('components/interior/material.module.css')

test('Interior controls are shared, attributed and preserve native behavior', () => {
  assert.doesNotMatch(css, /:root|font-family|linear-gradient/)
  for (const value of ['#131313', '#454545', '#6e6e6e', '#4568ff', 'inset 0 1px 2px', 'prefers-reduced-motion', 'forced-colors', 'focus-visible', '::selection', 'caret-color', 'scrollbar-color']) assert(css.includes(value), value)
  assert.match(source('components/interior/LICENSE'), /Copyright \(c\) 2026 ozzy/)
  const adapter = source('adapters/ui.ts')
  assert.match(adapter, /export \{ Button \} from '@\/extensions\/route66\/components\/interior\/Button'/)
  assert.match(source('adapters/native-controls.ts'), /Button as NativeButton/)
  assert.match(source('components/interior/Button.tsx'), /<NativeButton/)
  assert.doesNotMatch(source('components/interior/Button.tsx'), /fetch\(|setTimeout|useAsyncAction/)
  assert.match(adapter, /export \{ Input \} from '@components\/ui\/input'/)
  assert.match(source('adapters/tabs.ts'), /export \{ Tabs, TabsList, TabsTrigger, TabsContent \}/)
  assert.doesNotMatch(adapter, /fetch\(|useEffect|useState|onClick|setTimeout/)
})

test('active custom roots share Interior without retheming the native account shell', () => {
  for (const path of ['Objects/Classes/ClassesWorkspace.tsx', 'Objects/Classes/AttendanceWorkspace.tsx', 'Objects/Classes/AttendanceCheckin.tsx', 'Objects/Classes/calendar/CalendarLibrary.tsx', 'Objects/Account/subpages/SchoolIdentity.tsx', 'Objects/Account/subpages/SignInMethods.tsx']) assert.match(source('components/' + path), /interior\.scope/)
  assert.match(source('components/Auth/ProviderButton.tsx'), /interior\.providerPrimary/)
  assert.match(source('adapters/ui.ts'), /interior\.authFrame/)
  assert.doesNotMatch(source('components/Objects/Classes/ClassesAccountLayout.tsx'), /interior/)
})

test('button variants and hidden navigation retain distinct treatments', () => {
  assert.match(css, /\.scope\.scope button\[class~='bg-primary'\]/)
  assert.match(css, /:not\(\[data-meeting\]\)/)
  assert.match(css, /\[data-state=active\]/)
  assert.match(css, /\[aria-pressed=true\]/)
  assert.doesNotMatch(css, /\[hidden\].*display/)
  assert.match(css, /prefers-reduced-motion:[\s\S]*\.scope button:not\(\[role=tab\]\):not\(\[data-meeting\]\):active:not\(:disabled\)[^{]*\{ transform: none/)
  assert.match(css, /\.navigation\.navigation > :is\(button,a\):is\(\[aria-pressed=true\],\[aria-current\],\[aria-checked=true\]\)/)
})
