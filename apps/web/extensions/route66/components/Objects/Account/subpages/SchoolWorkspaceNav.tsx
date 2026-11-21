'use client'

import Link from 'next/link'
import interior from '@/extensions/route66/components/interior/material.module.css'
import { BookOpen, GraduationCap } from 'lucide-react'

export default function SchoolWorkspaceNav({ active, th }: { active: 'classes' | 'identity'; th: boolean }) {
  const pages = [
    { id: 'classes', href: '/classes', label: th ? 'ชั้นเรียนของฉัน' : 'My classes', Icon: BookOpen },
    { id: 'identity', href: '/account/school-identity', label: th ? 'ข้อมูลสถานศึกษา' : 'School identity', Icon: GraduationCap },
  ] as const
  return <nav aria-label={th ? 'หน้าข้อมูลสถานศึกษา' : 'School pages'} className={interior.navigation}>
    {pages.map(({ id, href, label, Icon }) => <Link key={id} href={href} aria-current={active === id ? 'page' : undefined}
      className={"inline-flex min-h-11 items-center gap-2 px-3 text-sm font-medium"}>
      <Icon size={18} aria-hidden="true" />{label}
    </Link>)}
  </nav>
}
