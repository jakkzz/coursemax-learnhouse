'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { AuthLayout, Button } from '@/extensions/route66/adapters/ui'

export default function LinkGooglePage() {
  const { t } = useTranslation()
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const link = async (event: React.FormEvent) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError(false)
    try {
      const response = await fetch('/api/auth/google/start', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intent: 'link', return_path: '/home', current_password: password }),
      })
      setPassword('')
      const result = await response.json()
      if (!response.ok || typeof result.url !== 'string') throw new Error()
      const target = new URL(result.url)
      if (target.origin !== 'https://accounts.google.com') throw new Error()
      sessionStorage.setItem('lh_google_intent', 'link')
      window.location.assign(target.toString())
    } catch {
      setPassword('')
      setBusy(false)
      setError(true)
    }
  }
  return (
    <AuthLayout org={null}>
      <form onSubmit={link} className="m-auto w-full max-w-md space-y-5 p-6">
        <h1 className="text-2xl font-semibold">{t('auth.google_link_title', { defaultValue: 'Link Google to your account' })}</h1>
        <p className="text-sm leading-relaxed">{t('auth.google_link_description', { defaultValue: 'Sign in to your existing account first. Linking adds Google as a sign-in method without changing your email, role or course access.' })}</p>
        <label className="block space-y-2">
          <span className="text-sm font-medium">{t('auth.google_confirm_password', { defaultValue: 'Confirm your existing password' })}</span>
          <input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)}
            className="w-full rounded-lg border p-3 text-base" disabled={busy} />
        </label>
        {error && <p role="alert" className="text-sm leading-relaxed">{t('auth.google_link_retry', { defaultValue: 'Linking could not start. Sign in again, confirm your password, then retry. Your account has not changed.' })}</p>}
        <Button type="submit" disabled={busy} loading={busy} loadingLabel={t('common.loading')} className="w-full">
          {t('auth.google_link_continue', { defaultValue: 'Choose the Google account to link' })}
        </Button>
        <Link href="/home" className="block text-center text-sm underline underline-offset-4">{t('common.cancel')}</Link>
      </form>
    </AuthLayout>
  )
}
