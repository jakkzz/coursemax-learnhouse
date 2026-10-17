'use client'

import { createElement, type ComponentProps } from 'react'
import NativeAuthLayout from '@components/Auth/AuthLayout'
import interior from '@/extensions/route66/components/interior/material.module.css'

// Native shell/control contracts; extension code consumes these, never replaces them.
export { Button } from '@/extensions/route66/components/interior/Button'
export { Input } from '@components/ui/input'
export { Dialog, DialogContent, DialogDescription, DialogTitle } from '@components/ui/dialog'
export { DashTabBar } from '@components/Dashboard/Shared/DashTabBar/DashTabBar'
export { default as useAdminStatus } from '@components/Hooks/useAdminStatus'
export function AuthLayout({ children, ...props }: ComponentProps<typeof NativeAuthLayout>) {
  return createElement(NativeAuthLayout, { ...props, children: createElement('div', { className: `${interior.scope} ${interior.authFrame}` }, children) })
}
export { default as GeneralWrapperStyled } from '@components/Objects/StyledElements/Wrappers/GeneralWrapper'
export { Breadcrumbs } from '@components/Objects/Breadcrumbs/Breadcrumbs'
export { AccountSidebar } from '@components/Objects/Account/AccountSidebar'
export { AccountActionsMobile } from '@components/Objects/Account/AccountActionsMobile'
export { useLHSession } from '@components/Contexts/LHSessionContext'
export { getUriWithOrg } from '@services/config/config'
