'use client'

// Adapted headless hook from Interior copy-button.tsx at 314800833bf01e23e6ae74c2a17fbdaac3688c84.
// Copyright (c) 2026 ozzy. MIT; see LICENSE. Fallback additionally restores keyboard focus.
import { useCallback, useEffect, useRef, useState } from 'react'

export type CopyStatus = 'idle' | 'copied' | 'error'
export type CopyOptions = { timeout?: number; onCopy?: (value: string) => void; onError?: (reason: unknown) => void }
function writeFallback(text: string) {
  const area = document.createElement('textarea'), focused = document.activeElement
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'; area.style.top = '0'; area.style.left = '0'; area.style.opacity = '0'
  const selection = document.getSelection(), previous = selection?.rangeCount ? selection.getRangeAt(0) : null
  document.body.appendChild(area)
  try { area.select(); return document.execCommand('copy') }
  finally {
    area.remove()
    if (selection && previous) { selection.removeAllRanges(); selection.addRange(previous) }
    if (focused instanceof HTMLElement && focused.isConnected) focused.focus({ preventScroll: true })
  }
}
export function useCopyToClipboard({ timeout = 2000, onCopy, onError }: CopyOptions = {}) {
  const [status, setStatus] = useState<CopyStatus>('idle'), [ticket, setTicket] = useState(0)
  const mounted = useRef(true), copied = useRef(onCopy), failed = useRef(onError)
  copied.current = onCopy; failed.current = onError
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const reset = useCallback(() => { setStatus('idle'); setTicket(0) }, [])
  const copy = useCallback(async (text: string) => {
    if (!text) return false
    let ok = false, reason: unknown = null
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); ok = true }
      else ok = writeFallback(text)
    } catch (error) {
      reason = error
      if (!mounted.current) return false
      try { ok = writeFallback(text) } catch { ok = false }
    }
    if (!mounted.current) return ok
    setStatus(ok ? 'copied' : 'error'); setTicket(t => t + 1)
    if (ok) copied.current?.(text); else failed.current?.(reason)
    return ok
  }, [])
  useEffect(() => {
    if (!ticket || status === 'idle') return
    const timer = setTimeout(() => setStatus('idle'), timeout)
    return () => clearTimeout(timer)
  }, [ticket, status, timeout])
  return { copy, reset, status, copied: status === 'copied' }
}
