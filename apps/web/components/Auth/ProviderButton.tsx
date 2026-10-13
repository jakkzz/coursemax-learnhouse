'use client'

import type { ButtonHTMLAttributes } from 'react'

type Provider = 'google' | 'line'

export const providerControlClass = 'inline-flex min-h-12 items-center justify-center gap-3 rounded-lg border px-4 py-2.5 text-base font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-neutral-900! focus-visible:outline-offset-2 disabled:cursor-wait disabled:opacity-60'

export function ProviderIcon({ provider }: { provider: Provider }) {
  return <img src={`/provider-${provider}.svg`} alt="" aria-hidden="true" width={20} height={20} className="h-5 w-5 shrink-0" />
}

export default function ProviderButton({ provider, primary = false, className = '', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { provider: Provider; primary?: boolean }) {
  return <button type="button" {...props} className={`${providerControlClass} w-full ${primary ? 'border-neutral-900 bg-neutral-900 text-white hover:bg-neutral-800' : 'border-neutral-300 bg-white text-neutral-900 hover:bg-neutral-50'} ${className}`}>
    <ProviderIcon provider={provider} />
    <span>{children}</span>
  </button>
}
