'use client'

import { useCallback, useEffect, useState } from 'react'
import interior from '@/extensions/route66/components/interior/material.module.css'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { Button } from '@/extensions/route66/adapters/ui'
import { ProviderIcon, providerControlClass } from '@/extensions/route66/components/Auth/ProviderButton'

type Method = { provider: 'google' | 'line'; linked: boolean | null; enabled: boolean; manageable: boolean; error: boolean }
const initial: Method[] = ['google', 'line'].map(provider => ({ provider: provider as Method['provider'], linked: null, enabled: false, manageable: false, error: false }))

export default function SignInMethods() {
  const { t } = useTranslation()
  const [methods, setMethods] = useState(initial)
  const [busy, setBusy] = useState(true)
  const load = useCallback(async (signal: AbortSignal) => {
    setBusy(true)
    const results = await Promise.all(initial.map(async method => {
      try {
        const [capResponse, accountResponse] = await Promise.all(['capabilities', 'account'].map(path => fetch(`/api/auth/${method.provider}/${path}`, { credentials: 'include', cache: 'no-store', signal })))
        if (!capResponse.ok || !accountResponse.ok) throw new Error('unavailable')
        const [caps, account] = await Promise.all([capResponse.json(), accountResponse.json()])
        if (typeof account.linked !== 'boolean') throw new Error('invalid_status')
        return { ...method, linked: account.linked, enabled: caps[method.provider] === true, manageable: (method.provider === 'line' ? caps.link : caps.google) === true }
      } catch { return { ...method, error: true } }
    }))
    if (!signal.aborted) { setMethods(results); setBusy(false) }
  }, [])
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    // A hung request must become an actionable error, not perpetual loading.
    const timeout = setTimeout(() => { controller.abort(); setMethods(initial.map(method => ({ ...method, error: true }))); setBusy(false) }, 10000)
    void load(controller.signal).finally(() => clearTimeout(timeout))
    return () => { controller.abort(); clearTimeout(timeout) }
  }, [load, attempt])

  return <section className={interior.scope} aria-labelledby="signin-methods-title">
    <h2 id="signin-methods-title" className="text-lg font-semibold text-neutral-900">{t('auth.methods_title')}</h2>
    <p className="mt-1 max-w-prose text-sm leading-relaxed text-neutral-600">{t('auth.methods_description')}</p>
    <div className="mt-4 divide-y divide-neutral-200" aria-busy={busy}>
      {methods.map(method => <div key={method.provider} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <div className="pt-1"><ProviderIcon provider={method.provider} /></div>
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-neutral-900">{method.provider === 'google' ? 'Google' : 'LINE'}</h3>
            <p role="status" className="mt-1 text-sm text-neutral-700">{t(busy ? 'auth.methods_loading' : method.error ? 'auth.methods_error' : method.linked ? 'auth.methods_connected' : 'auth.methods_not_connected')}</p>
            {!busy && !method.error && <p className="mt-1 max-w-prose text-sm leading-relaxed text-neutral-600">{t(!method.enabled ? 'auth.methods_unavailable' : method.provider === 'line' ? method.linked ? 'auth.line_connected_help' : 'auth.line_linked_only' : method.linked ? 'auth.google_connected_help' : 'auth.google_connect_help')}</p>}
          </div>
        </div>
        {!busy && !method.error && method.manageable && (method.provider === 'line' || !method.linked) && <Link href={`/auth/link/${method.provider}`} className={`${providerControlClass} shrink-0 border-neutral-300 bg-white text-neutral-900 hover:bg-neutral-50 sm:text-sm`}>
          {t(method.provider === 'google' ? 'auth.google_connect' : method.linked ? 'auth.line_manage' : 'auth.line_connect')}
        </Link>}
      </div>)}
    </div>
    {!busy && methods.some(method => method.error) && <Button type="button" variant="outline" onClick={() => setAttempt(value => value + 1)} className="mt-4">{t('auth.methods_retry')}</Button>}
  </section>
}
