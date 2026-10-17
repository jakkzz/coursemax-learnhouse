'use client'

import React, { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { Loader2, AlertTriangle } from 'lucide-react'
import AuthLayout from '@components/Auth/AuthLayout'
import { attendanceRetryLogin } from '@/extensions/route66/components/Objects/Classes/attendance-client'

export default function GoogleCallbackPage() {
  const { t } = useTranslation()
  const started = useRef(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (started.current) return
    started.current = true
    const params = new URLSearchParams(window.location.search)
    const state = params.get('state')
    const code = params.get('code')
    const providerError = params.get('error')
    const intent = sessionStorage.getItem('lh_google_intent')
    sessionStorage.removeItem('lh_google_intent')
    // Scrub the callback immediately. Never forward codes across hosts or keep
    // Google access/refresh tokens in browser storage (the server owns exchange).
    window.history.replaceState(null, '', window.location.pathname)
    const run = async () => {
      if (!state || params.getAll('state').length !== 1 || params.getAll('code').length > 1 ||
          !['signin', 'register', 'link'].includes(intent ?? '')) throw new Error('restart')
      const response = await fetch('/api/auth/google/complete', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intent, state, code, provider_error: providerError }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'restart')
      const next = new URL(typeof result.return_path === 'string' ? result.return_path : '/home', window.location.origin)
      if (next.origin !== window.location.origin) throw new Error('restart')
      if (result.mfa_required && typeof result.mfa_token === 'string') {
        sessionStorage.setItem('lh_google_mfa', JSON.stringify({ token: result.mfa_token, next: next.pathname + next.search }))
        window.location.replace('/login')
        return
      }
      window.location.replace(next.pathname + next.search)
    }
    run().catch((reason: Error) => {
      const conflict = reason.message.includes('already uses this email') || reason.message.includes('not linked')
      setError(conflict
        ? t('auth.google_link_existing', { defaultValue: 'Sign in using your existing method, then link Google from your account. Your accounts will not be merged automatically.' })
        : t('auth.google_restart', { defaultValue: 'Google sign-in could not be completed. Please try again.' }))
    })
  }, [t])

  return (
    <AuthLayout org={null}>
      <div className="m-auto w-full max-w-md space-y-4 p-6 text-center" role={error ? 'alert' : 'status'}>
        {error ? <AlertTriangle className="mx-auto" size={24} /> : <Loader2 className="mx-auto animate-spin" size={24} />}
        <h1 className="text-xl font-semibold">{t('auth.google_continue')}</h1>
        <p className="text-sm leading-relaxed">{error ?? t('auth.google_completing', { defaultValue: 'Completing secure sign-in…' })}</p>
        {error && <Link className="inline-block rounded-lg border px-4 py-3 text-sm font-medium" href={attendanceRetryLogin()}>{t('auth.google_back_to_login', { defaultValue: 'Back to sign in' })}</Link>}
      </div>
    </AuthLayout>
  )
}
