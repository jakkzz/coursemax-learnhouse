'use client'

import { useRef, type HTMLAttributes, type KeyboardEvent } from 'react'
import styles from './material.module.css'

// Controlled keyboard/selection adaptation of Interior segmented-control.tsx.
// 314800833bf01e23e6ae74c2a17fbdaac3688c84, MIT © 2026 ozzy. No duplicate panel/request state.
export function SegmentedControl<Value extends string>({ options, value, onValueChange, label, className = '', ...props }: Omit<HTMLAttributes<HTMLDivElement>, 'onChange'> & { options: readonly { value: Value; label: string; disabled?: boolean }[]; value: Value; onValueChange: (value: Value) => void; label: string }) {
  const buttons = useRef<(HTMLButtonElement | null)[]>([])
  const selected = options.findIndex(option => option.value === value && !option.disabled)
  const focusable = selected < 0 ? options.findIndex(option => !option.disabled) : selected
  function go(index: number) {
    const option = options[index]
    if (!option || option.disabled) return
    buttons.current[index]?.focus()
    if (option.value !== value) onValueChange(option.value)
  }
  function seek(from: number, direction: number) {
    let index = from
    for (let count = 0; count < options.length; count++) {
      index = (index + direction + options.length) % options.length
      if (!options[index].disabled) return index
    }
    return from
  }
  function keyDown(event: KeyboardEvent, index: number) {
    const key = event.key
    if (!['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'].includes(key)) return
    event.preventDefault()
    go(key === 'Home' ? seek(options.length - 1, 1) : key === 'End' ? seek(0, -1) : seek(index, key === 'ArrowRight' || key === 'ArrowDown' ? 1 : -1))
  }
  return <div {...props} role="radiogroup" aria-label={label} className={`${styles.scope} ${styles.navigation} ${className}`}>
    {options.map((option, index) => <button key={option.value} ref={node => { buttons.current[index] = node }} type="button" role="radio" aria-checked={option.value === value} disabled={option.disabled} tabIndex={index === focusable ? 0 : -1} onClick={() => go(index)} onKeyDown={event => keyDown(event, index)}>{option.label}</button>)}
  </div>
}
