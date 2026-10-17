'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { AuthLayout, Button } from '@/extensions/route66/adapters/ui'
import { googleForLine, startLine } from '@/extensions/route66/services/auth/line'

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
        <Button type="button" disabled={busy} loading={busy} loadingLabel={t('common.loading')} onClick={() => run(googleForLine)} className="w-full">
          {t('auth.line_confirm_google')}
        </Button>
      </>}
      {account?.available && account.can_manage && !account.linked && !disconnected && <Button type="button" disabled={busy} loading={busy} loadingLabel={t('common.loading')} onClick={() => run(() => startLine('link', '/account/security'))} className="w-full">
        {t('auth.line_choose_account')}
      </Button>}
      {account?.linked && <>
        <p role="status" className="text-sm font-medium">{t('auth.line_connected')}</p>
        {account.can_manage && !confirm && <Button type="button" variant="outline" onClick={() => setConfirm(true)}>{t('auth.line_disconnect')}</Button>}
        {confirm && <div className="space-y-3 border-t pt-4">
          <p className="text-sm leading-relaxed">{t('auth.line_disconnect_warning')}</p>
          <div className="flex flex-wrap gap-3">
            <Button type="button" variant="destructive" disabled={busy} loading={busy} loadingLabel={t('common.loading')} onClick={() => run(disconnect)}>{t('auth.line_disconnect_confirm')}</Button>
            <Button type="button" variant="outline" disabled={busy} onClick={() => setConfirm(false)}>{t('common.cancel')}</Button>
          </div>
        </div>}
      </>}
      {disconnected && <p role="status" className="text-sm leading-relaxed">{t('auth.line_disconnected')}</p>}
      {error && <p role="alert" className="text-sm leading-relaxed">{t('auth.line_retry')}</p>}
      <Link href="/account/security" className="block text-sm underline underline-offset-4">{t('auth.line_back_security')}</Link>
    </main>
  </AuthLayout>
}
