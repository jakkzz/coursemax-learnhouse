'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { AuthLayout } from '@/extensions/route66/adapters/ui'
import { finishLine } from '@/extensions/route66/services/auth/line'
import { attendanceRetryLogin } from '@/extensions/route66/components/Objects/Classes/attendance-client'

export default function LineCallback() {
  const { t } = useTranslation()
  const started = useRef(false)
  const [error, setError] = useState(false)
  const [linking, setLinking] = useState(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    const params = new URLSearchParams(window.location.search)
    window.history.replaceState(null, '', '/auth/callback/line')
    const saved = sessionStorage.getItem('lh_line_intent')
    sessionStorage.removeItem('lh_line_intent')
    const intent = saved === 'link' ? 'link' : 'signin'
    setLinking(intent === 'link')
    const state = params.get('state')
    if (!state) { setError(true); return }
    fetch('/api/auth/line/complete', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state, intent, code: params.get('code'), provider_error: params.get('error') }),
    }).then(async response => {
      const result = await response.json()
      if (!response.ok) throw new Error()
      finishLine(result)
    }).catch(() => setError(true))
  }, [])
  return <AuthLayout org={null}>
    <main className="m-auto w-full max-w-md space-y-5 p-6">
      <h1 className="text-2xl font-semibold">{t('auth.line_callback_title')}</h1>
      <p role={error ? 'alert' : 'status'} aria-live="polite" className="text-sm leading-relaxed">
        {error ? t('auth.line_callback_retry') : t('auth.line_callback_wait')}
      </p>
      {error && <Link href={linking ? '/auth/link/line' : attendanceRetryLogin()} className="inline-flex rounded-lg border px-4 py-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2">
        {t('auth.line_try_again')}
      </Link>}
    </main>
  </AuthLayout>
}
