import test from 'node:test'
import assert from 'node:assert/strict'
import { weekdayKey } from '../components/Objects/Account/subpages/timetable-colors.ts'

test('weekday categories agree for full Thai and English registrar labels', () => {
  for (const [key, thai, english] of [
    ['monday','จันทร์','Monday'], ['tuesday','อังคาร','Tuesday'], ['wednesday','พุธ','Wednesday'],
    ['thursday','พฤหัสบดี','Thursday'], ['friday','ศุกร์','Friday'], ['saturday','เสาร์','Saturday'], ['sunday','อาทิตย์','Sunday'],
  ]) {
    assert.equal(weekdayKey(thai), key)
    assert.equal(weekdayKey('วัน'+thai), key)
    assert.equal(weekdayKey(english), key)
    assert.equal(weekdayKey(' '+english.toUpperCase()+' '), key)
  }
})
test('common abbreviated labels keep the same category', () => {
  for (const [label, key] of [['จ.','monday'],['อ.','tuesday'],['พ.','wednesday'],['พฤ.','thursday'],['ศ.','friday'],['ส.','saturday'],['อา.','sunday'],['Mon.','monday'],['Thu','thursday']]) assert.equal(weekdayKey(label),key)
})
test('unknown or combined days are neutral rather than guessed; source labels stay unchanged', () => {
  for (const day of ['', 'To be arranged', 'Monday / Tuesday', 'จันทร์–พุธ', 'NotMonday']) assert.equal(weekdayKey(day),'unknown')
  const source='วันพฤหัสบดี';weekdayKey(source);assert.equal(source,'วันพฤหัสบดี')
})
