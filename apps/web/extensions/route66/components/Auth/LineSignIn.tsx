'use client'

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { startLine } from '@/extensions/route66/services/auth/line'
import ProviderButton from '@/extensions/route66/components/Auth/ProviderButton'

export default function LineSignIn({ disabled = false, onAvailabilityChange, onBusyChange }: { disabled?: boolean; onAvailabilityChange?: (available: boolean) => void; onBusyChange?: (busy: boolean) => void }) {
  const { t } = useTranslation()
  const [available, setAvailable] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  useEffect(() => {
    let active = true
    fetch('/api/auth/line/capabilities', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (active) { setAvailable(data?.line === true); onAvailabilityChange?.(data?.line === true) } }).catch(() => { if (active) onAvailabilityChange?.(false) })
    return () => { active = false }
  }, [onAvailabilityChange])
  if (!available) return null
  return <div className="space-y-2">
    <ProviderButton provider="line" disabled={busy || disabled} loading={busy} loadingLabel={t('common.loading')} aria-busy={busy} onClick={async () => {
      setBusy(true); onBusyChange?.(true); setError(false)
      try {
        const requested = new URLSearchParams(window.location.search).get('next')
        await startLine('signin', requested && /^\/(?!\/)/.test(requested) ? requested : '/home')
      } catch { setBusy(false); onBusyChange?.(false); setError(true) }
    }}>
      {t('auth.line_signin')}
    </ProviderButton>
    <p className="text-sm leading-relaxed text-neutral-700">{t('auth.line_linked_only')}</p>
    {error && <p role="alert" className="text-sm leading-relaxed">{t('auth.line_retry')}</p>}
  </div>
}
