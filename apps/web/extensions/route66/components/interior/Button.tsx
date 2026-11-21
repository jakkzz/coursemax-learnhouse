'use client'

import { forwardRef, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { NativeButton, type ButtonProps as NativeButtonProps } from '@/extensions/route66/adapters/native-controls'
import styles from './material.module.css'

// Interior loading-button.tsx, 314800833bf01e23e6ae74c2a17fbdaac3688c84, MIT © 2026 ozzy.
// Reserve every label's space; request owners, not presentation, decide pending/success.
export function ButtonLabel({ labels, active }: { labels: readonly ReactNode[]; active: number }) {
  return <span className={styles.faces}>{labels.map((label, index) => <span key={index} className={styles.face} data-active={active === index} aria-hidden={active === index ? undefined : true}>{label}</span>)}</span>
}

export type ButtonProps = NativeButtonProps & { loading?: boolean; loadingLabel?: ReactNode }
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ loading = false, loadingLabel, disabled, asChild, variant, className = '', children, ...props }, ref) {
  return <NativeButton {...props} ref={ref} asChild={asChild} variant={variant} disabled={disabled || loading} aria-busy={loading || props['aria-busy']} data-interior-variant={variant ?? 'default'} className={`${styles.button} ${className}`}>
    {loadingLabel !== undefined && !asChild ? <ButtonLabel active={loading ? 1 : 0} labels={[children, <><LoaderCircle aria-hidden="true" className={loading ? styles.spinner : undefined} />{loadingLabel}</>]} /> : children}
  </NativeButton>
})
