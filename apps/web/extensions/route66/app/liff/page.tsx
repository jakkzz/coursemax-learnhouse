'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { AuthLayout } from '@/extensions/route66/adapters/ui'
import { finishLine } from '@/extensions/route66/services/auth/line'

type LiffSDK = {
  init: (options: { liffId: string }) => Promise<void>
  isLoggedIn: () => boolean
  login: (options: { redirectUri: string }) => void
  getIDToken: () => string | null
}
let sdkPromise: Promise<LiffSDK> | null = null
function loadSDK(): Promise<LiffSDK> {
  const existing = (window as Window & { liff?: LiffSDK }).liff
  if (existing) return Promise.resolve(existing)
  if (sdkPromise) return sdkPromise
  sdkPromise = new Promise<LiffSDK>((resolve, reject) => {
    const script = document.createElement('script')
    const timer = window.setTimeout(() => { script.remove(); reject(new Error()) }, 10000)
    script.src = 'https://static.line-scdn.net/liff/edge/2/sdk.js'
    script.referrerPolicy = 'no-referrer'
    script.onload = () => {
      window.clearTimeout(timer)
      const sdk = (window as Window & { liff?: LiffSDK }).liff
      if (sdk) resolve(sdk); else reject(new Error())
    }
    script.onerror = () => { window.clearTimeout(timer); script.remove(); reject(new Error()) }
    document.head.appendChild(script)
  }).catch(error => { sdkPromise = null; throw error })
  return sdkPromise
}

export default function LineAppPage() {
  const { t } = useTranslation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const open = async () => {
    if (busy) return
    setBusy(true); setError(false)
    try {
      const start = await fetch('/api/auth/line/liff/start', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: '{}',
      })
      const challenge = await start.json()
      if (!start.ok || typeof challenge.state !== 'string' || typeof challenge.liff_id !== 'string') throw new Error()
      const liff = await loadSDK()
      await liff.init({ liffId: challenge.liff_id })
      if (!liff.isLoggedIn()) { liff.login({ redirectUri: window.location.origin + '/liff' }); return }
      const token = liff.getIDToken()
      if (!token) throw new Error()
      const response = await fetch('/api/auth/line/liff/session', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: challenge.state, id_token: token }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error()
      window.history.replaceState(null, '', '/liff')
      finishLine(result)
    } catch { setBusy(false); setError(true) }
  }
  return <AuthLayout org={null}>
    <main className="m-auto w-full max-w-md space-y-5 p-6">
      <h1 className="text-2xl font-semibold">{t('auth.line_app_title')}</h1>
      <p className="text-sm leading-relaxed">{t('auth.line_app_description')}</p>
      <button type="button" disabled={busy} onClick={open} className="w-full rounded-lg bg-black p-3 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50">
        {busy ? t('common.loading') : t('auth.line_app_continue')}
      </button>
      {error && <p role="alert" className="text-sm leading-relaxed">{t('auth.line_app_retry')}</p>}
      <Link href="/auth/link/line" className="block text-sm underline underline-offset-4">{t('auth.line_link_title')}</Link>
      <Link href="/login" className="block text-sm underline underline-offset-4">{t('auth.line_use_google')}</Link>
    </main>
  </AuthLayout>
}
