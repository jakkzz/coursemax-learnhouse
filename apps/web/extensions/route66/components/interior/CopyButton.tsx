'use client'

import { Check, Copy, X } from 'lucide-react'
import { Button, ButtonLabel, type ButtonProps } from './Button'
import { useCopyToClipboard, type CopyOptions } from './useCopyToClipboard'

// Interior copy-button.tsx, 314800833bf01e23e6ae74c2a17fbdaac3688c84, MIT © 2026 ozzy.
// Native button + CSS faces retain the source's layout, feedback and fallback contracts.
export function CopyButton({ value, label, copiedLabel, errorLabel, timeout, onCopy, onError, ...props }: Omit<ButtonProps, 'children' | 'onClick' | 'asChild' | 'loading' | 'loadingLabel' | 'value' | 'onCopy' | 'onError'> & CopyOptions & { value: string | (() => string); label: string; copiedLabel: string; errorLabel: string }) {
  const { copy, status } = useCopyToClipboard({ timeout, onCopy, onError })
  return <Button {...props} type="button" aria-label={label} onClick={() => { void copy(typeof value === 'function' ? value() : value) }}>
    <ButtonLabel active={status === 'idle' ? 0 : status === 'copied' ? 1 : 2} labels={[<><Copy aria-hidden="true" />{label}</>, <><Check aria-hidden="true" />{copiedLabel}</>, <><X aria-hidden="true" />{errorLabel}</>]} />
    <span className="sr-only" role="status">{status === 'copied' ? copiedLabel : status === 'error' ? errorLabel : ''}</span>
  </Button>
}
