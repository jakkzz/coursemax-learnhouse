import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'

const source = fs.readFileSync(new URL('../server-wrapper.js', import.meta.url), 'utf8')

function run(env) {
  const writes = new Map()
  let started = false
  vm.runInNewContext(source, {
    URL,
    __dirname: '/virtual',
    process: { env: { ...env } },
    require(name) {
      if (name === 'path') return path
      if (name === 'fs') return {
        writeFileSync: (p, text) => writes.set(p, text),
        existsSync: () => true,
      }
      if (name === './server.js') { started = true; return {} }
      throw new Error(`Unexpected import: ${name}`)
    },
  })
  return { writes, started }
}

const publicUrl = 'https://learn.example.com/api/v1/'

test('internal API is server-only; browser retains public API and no secrets', () => {
  const { writes, started } = run({
    NEXT_PUBLIC_LEARNHOUSE_API_URL: publicUrl,
    NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL: 'https://learn.example.com/',
    LEARNHOUSE_INTERNAL_API_URL: 'http://127.0.0.1:9000/api/v1',
    LEARNHOUSE_INTERNAL_BACKEND_URL: 'http://127.0.0.1:9000',
    LEARNHOUSE_AUTH_JWT_SECRET_KEY: 'private-test-secret',
    LEARNHOUSE_GOOGLE_CLIENT_SECRET: 'private-google-secret',
  })
  const server = JSON.parse(writes.get('/virtual/runtime-config.json'))
  const browser = writes.get('/virtual/public/runtime-config.js')
  assert.equal(server.NEXT_PUBLIC_LEARNHOUSE_API_URL, 'http://127.0.0.1:9000/api/v1/')
  assert.equal(server.NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL, 'http://127.0.0.1:9000/')
  assert.ok(browser.includes('https://learn.example.com/'))
  assert.ok(browser.includes(publicUrl))
  assert.ok(!browser.includes('127.0.0.1'))
  assert.ok(!browser.includes('private-'))
  assert.ok(!JSON.stringify(server).includes('private-'))
  assert.equal(started, true)
})

test('without override existing configuration is unchanged', () => {
  const { writes } = run({ NEXT_PUBLIC_LEARNHOUSE_API_URL: publicUrl })
  assert.equal(JSON.parse(writes.get('/virtual/runtime-config.json')).NEXT_PUBLIC_LEARNHOUSE_API_URL, publicUrl)
})

for (const url of [
  'file:///etc/passwd', 'javascript:alert(1)',
  'http://user:pass@api/api/v1/', 'http://api/api/v1/?secret=1',
  'http://api/api/v1/#fragment', 'not-a-url',
]) {
  test(`invalid internal URL rejected: ${url}`, () => {
    assert.throws(() => run({ LEARNHOUSE_INTERNAL_API_URL: url }))
    assert.throws(() => run({ LEARNHOUSE_INTERNAL_BACKEND_URL: url }))
  })
}
