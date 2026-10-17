'use client'

import type { ButtonHTMLAttributes } from 'react'
import interior from '@/extensions/route66/components/interior/material.module.css'

type Provider = 'google' | 'line'

export const providerControlClass = interior.provider

export function ProviderIcon({ provider }: { provider: Provider }) {
  return <img src={`/provider-${provider}.svg`} alt="" aria-hidden="true" width={20} height={20} className="h-5 w-5 shrink-0" />
}

export default function ProviderButton({ provider, primary = false, className = '', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { provider: Provider; primary?: boolean }) {
  return <button type="button" {...props} className={`${providerControlClass} w-full ${primary ? interior.providerPrimary : ''} ${className}`}>
    <ProviderIcon provider={provider} />
    <span>{children}</span>
  </button>
}
