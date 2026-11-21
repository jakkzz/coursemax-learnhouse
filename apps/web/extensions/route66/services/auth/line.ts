export async function startLine(intent: 'signin' | 'link', returnPath: string) {
  const response = await fetch('/api/auth/line/start', {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intent, return_path: returnPath }),
  })
  const result = await response.json()
  if (!response.ok || typeof result.url !== 'string') throw new Error('line_start_failed')
  const target = new URL(result.url)
  if (target.origin !== 'https://access.line.me') throw new Error('line_start_failed')
  sessionStorage.setItem('lh_line_intent', intent)
  window.location.assign(target.toString())
}

export async function googleForLine() {
  const response = await fetch('/api/auth/google/start', {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intent: 'signin', return_path: '/auth/link/line' }),
  })
  const result = await response.json()
  if (!response.ok || typeof result.url !== 'string') throw new Error('google_start_failed')
  const target = new URL(result.url)
  if (target.origin !== 'https://accounts.google.com') throw new Error('google_start_failed')
  sessionStorage.setItem('lh_google_intent', 'signin')
  window.location.assign(target.toString())
}

export function finishLine(result: { mfa_required?: boolean; mfa_token?: string; return_path?: string }) {
  const next = typeof result.return_path === 'string' && /^\/(?!\/)/.test(result.return_path)
    ? result.return_path : '/home'
  if (result.mfa_required && typeof result.mfa_token === 'string') {
    sessionStorage.setItem('lh_provider_mfa', JSON.stringify({ token: result.mfa_token, next }))
    window.location.replace('/login')
  } else window.location.replace(next)
}
