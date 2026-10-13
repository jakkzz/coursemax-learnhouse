'use client'

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { startLine } from '@services/auth/line'

export default function LineSignIn() {
  const { t } = useTranslation()
  const [available, setAvailable] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  useEffect(() => {
    let active = true
    fetch('/api/auth/line/capabilities', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (active) setAvailable(data?.line === true) }).catch(() => {})
    return () => { active = false }
  }, [])
  if (!available) return null
  return <div className="space-y-2">
    <button type="button" disabled={busy} onClick={async () => {
      setBusy(true); setError(false)
      try {
        const requested = new URLSearchParams(window.location.search).get('next')
        await startLine('signin', requested && /^\/(?!\/)/.test(requested) ? requested : '/home')
      } catch { setBusy(false); setError(true) }
    }} className="w-full rounded-lg border border-neutral-200 p-3 text-sm font-medium text-black hover:bg-neutral-50 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50">
      {busy ? t('common.loading') : t('auth.line_signin')}
    </button>
    <p className="text-sm leading-relaxed text-neutral-700">{t('auth.line_linked_only')}</p>
    {error && <p role="alert" className="text-sm leading-relaxed">{t('auth.line_retry')}</p>}
  </div>
}
