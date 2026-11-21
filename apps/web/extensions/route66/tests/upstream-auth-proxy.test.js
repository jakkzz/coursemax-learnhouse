// Exercise our retained provider endpoints against the merged native auth proxy.
import { afterAll, beforeEach, expect, mock, test } from 'bun:test'
import { NextRequest } from 'next/server'

mock.module('next/headers', () => ({ cookies: async () => ({ get: () => ({ value: 'synthetic-cookie' }) }) }))
mock.module('@services/config/config', () => ({ getConfig: () => 'http://api.test' }))
const originalFetch = globalThis.fetch
let calls, status
beforeEach(() => { calls = []; status = 200 })
globalThis.fetch = async (url, init) => {
  calls.push({ url, init })
  return new Response(JSON.stringify({ tokens: { access_token: 'synthetic-access', refresh_token: 'synthetic-refresh' } }),
    { status, headers: { 'content-type': 'application/json' } })
}
afterAll(() => { globalThis.fetch = originalFetch })
const { POST } = await import('../../../app/api/auth/[...path]/route.ts')

function request(path, origin = 'https://learn.example.test') {
  return new NextRequest(`https://learn.example.test/api/auth/${path}`, {
    method: 'POST', headers: { host: 'learn.example.test', origin, 'content-type': 'application/json' }, body: '{}',
  })
}

for (const path of ['google/complete', 'line/complete', 'line/liff/session']) {
  test(`${path} keeps origin, sets cookies and hides refresh credentials`, async () => {
    const response = await POST(request(path))
    expect(response.status).toBe(200)
    expect(calls[0].init.headers.Origin).toBe('https://learn.example.test')
    expect(response.headers.get('set-cookie')).toContain('synthetic-refresh')
    expect(response.headers.get('set-cookie')).toContain('HttpOnly')
    expect((await response.json()).tokens.refresh_token).toBeUndefined()
  })
  test(`${path} rejects a foreign origin before contacting the backend`, async () => {
    expect((await POST(request(path, 'https://other.example.test'))).status).toBe(403)
    expect(calls).toHaveLength(0)
  })
}

test('logout does not claim success or clear cookies when revocation fails', async () => {
  status = 503
  const response = await POST(request('logout'))
  expect(response.status).toBe(503)
  expect(response.headers.get('set-cookie')).toBeNull()
  expect(calls).toHaveLength(1)
})
