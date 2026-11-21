'use client'

import type { ReactNode } from 'react'
import { User } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  GeneralWrapperStyled, Breadcrumbs, AccountSidebar, AccountActionsMobile,
  useLHSession, getUriWithOrg,
} from '@/extensions/route66/adapters/ui'
import styles from './classes-account-layout.module.css'

// Compose the same native presentation as AccountClient, without changing its
// subpage router or creating a second account/session/navigation authority.
export default function ClassesAccountLayout({ orgslug, children }: { orgslug: string; children: ReactNode }) {
  const session = useLHSession() as any
  const user = session?.data?.user
  const { t, i18n } = useTranslation()
  const title = i18n.language.startsWith('th') ? 'ชั้นเรียนของฉัน' : 'My classes'
  return <>
    <GeneralWrapperStyled>
      <div className="pb-4">
        <Breadcrumbs items={[
          { label: t('account.title'), href: getUriWithOrg(orgslug, '/account'), icon: <User size={14} /> },
          { label: title },
        ]} />
      </div>
      <div className={`${styles.accountWorkspace} flex flex-col md:flex-row gap-6 pt-2`} data-account-workspace="classes">
        <div className="hidden md:block w-full md:w-72 lg:w-80 flex-shrink-0">
          <div className="sticky top-24"><AccountSidebar orgslug={orgslug} currentSubpage="classes" /></div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="md:hidden mb-4">
            <p className="text-xl font-bold text-gray-900">{user?.first_name} {user?.last_name}</p>
            <p className="mt-1 text-sm text-gray-500">@{user?.username}</p>
          </div>
          {children}
        </div>
      </div>
    </GeneralWrapperStyled>
    <AccountActionsMobile orgslug={orgslug} currentSubpage="classes" />
  </>
}
