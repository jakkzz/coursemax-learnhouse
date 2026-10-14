import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// Exercise the actual dropdown predicate rather than a duplicated policy.
const source = readFileSync(new URL('../../../components/Dashboard/Pages/Users/OrgUsers/OrgUsers.tsx', import.meta.url), 'utf8')
const expression = source.match(/disabled=\{([^\n]+is_superadmin[^\n]+)\}/)?.[1]
assert.ok(expression, 'Member role dropdown has an explicit superadmin self-edit exception')
const disabled = new Function('roles', 'canManageOrg', 'user', 'session', `return (${expression})`)
const actor = (id, is_superadmin) => ({ data: { user: { id, is_superadmin } } })
const member = { user: { id: 4 } }

test('platform superadmin can edit own organization role', () => {
  assert.equal(disabled([], true, member, actor(4, true)), false)
})
test('ordinary org manager cannot edit own role', () => {
  assert.equal(disabled([], true, member, actor(4, false)), true)
})
test('org manager can edit another member', () => {
  assert.equal(disabled([], true, member, actor(1, false)), false)
})
test('missing or non-boolean superadmin evidence cannot unlock self-edit', () => {
  for (const flag of [undefined, null, false, 'true', 1]) {
    assert.equal(disabled([], true, member, actor(4, flag)), true)
  }
})
test('loading roles and missing org management authority remain disabled', () => {
  assert.equal(disabled(undefined, true, member, actor(4, true)), true)
  assert.equal(disabled([], false, member, actor(4, true)), true)
})
