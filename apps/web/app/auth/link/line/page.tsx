'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import AuthLayout from '@components/Auth/AuthLayout'
import { googleForLine, startLine } from '@services/auth/line'

type Connection = { linked: boolean; can_manage: boolean; identity_id?: number; available: boolean }

export default function LinkLinePage() {
  const { t } = useTranslation()
  const [account, setAccount] = useState<Connection | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [disconnected, setDisconnected] = useState(false)
  useEffect(() => {
    let active = true
    fetch('/api/auth/line/capabilities', { cache: 'no-store' }).then(async response => {
      const capabilities = await response.json()
      if (!response.ok || !capabilities.link) {
        if (active) setAccount({ linked: false, can_manage: false, available: false })
        return
      }
      const status = await fetch('/api/auth/line/account', { credentials: 'include', cache: 'no-store' })
      const data = status.ok ? await status.json() : { linked: false, can_manage: false }
      if (active) setAccount({ ...data, available: true })
    }).catch(() => { if (active) setError(true) })
    return () => { active = false }
  }, [])
  const run = async (action: () => Promise<void>) => {
    if (busy) return
    setBusy(true); setError(false)
    try { await action() } catch { setError(true) } finally { setBusy(false) }
  }
  const disconnect = async () => {
    const response = await fetch('/api/auth/line/unlink', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expected_identity_id: account?.identity_id, confirm_remove: true }),
    })
    if (!response.ok) throw new Error()
    setAccount(value => value ? { ...value, linked: false } : value)
    setConfirm(false); setDisconnected(true)
  }
  return <AuthLayout org={null}>
    <main className="m-auto w-full max-w-md space-y-5 p-6">
      <h1 className="text-2xl font-semibold">{t('auth.line_link_title')}</h1>
      <p className="text-sm leading-relaxed">{t('auth.line_link_description')}</p>
      {!account && !error && <p role="status">{t('common.loading')}</p>}
      {account && !account.available && <p role="status" className="text-sm leading-relaxed">{t('auth.line_disabled')}</p>}
      {account?.available && !account.can_manage && <>
        <p className="text-sm leading-relaxed">{t('auth.line_google_required')}</p>
        <button type="button" disabled={busy} onClick={() => run(googleForLine)} className="w-full rounded-lg bg-black p-3 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50">
          {busy ? t('common.loading') : t('auth.line_confirm_google')}
        </button>
      </>}
      {account?.available && account.can_manage && !account.linked && !disconnected && <button type="button" disabled={busy} onClick={() => run(() => startLine('link', '/account/security'))}
        className="w-full rounded-lg bg-black p-3 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50">
        {busy ? t('common.loading') : t('auth.line_choose_account')}
      </button>}
      {account?.linked && <>
        <p role="status" className="text-sm font-medium">{t('auth.line_connected')}</p>
        {account.can_manage && !confirm && <button type="button" onClick={() => setConfirm(true)} className="rounded-lg border px-4 py-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2">{t('auth.line_disconnect')}</button>}
        {confirm && <div className="space-y-3 border-t pt-4">
          <p className="text-sm leading-relaxed">{t('auth.line_disconnect_warning')}</p>
          <div className="flex flex-wrap gap-3">
            <button type="button" disabled={busy} onClick={() => run(disconnect)} className="rounded-lg border border-red-700 px-4 py-3 text-sm font-medium text-red-800 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50">{busy ? t('common.loading') : t('auth.line_disconnect_confirm')}</button>
            <button type="button" disabled={busy} onClick={() => setConfirm(false)} className="rounded-lg border px-4 py-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2">{t('common.cancel')}</button>
          </div>
        </div>}
      </>}
      {disconnected && <p role="status" className="text-sm leading-relaxed">{t('auth.line_disconnected')}</p>}
      {error && <p role="alert" className="text-sm leading-relaxed">{t('auth.line_retry')}</p>}
      <Link href="/account/security" className="block text-sm underline underline-offset-4">{t('auth.line_back_security')}</Link>
    </main>
  </AuthLayout>
}
