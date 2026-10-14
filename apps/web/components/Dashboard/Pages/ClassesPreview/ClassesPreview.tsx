'use client'

import React, { useEffect, useReducer, useRef, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, ArrowRight, BookOpen, CheckCircle2, ChevronRight, Flag, GraduationCap, Search, ShieldCheck, XCircle } from 'lucide-react'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@components/ui/dialog'
import { DashTabBar } from '@components/Dashboard/Shared/DashTabBar/DashTabBar'
import useAdminStatus from '@components/Hooks/useAdminStatus'
import { copy, type CopyKey } from './copy'
import { canViewSection, courses, hasReview, initialState, isPending, ownPerson, rosterFor, sections, transition, visibleCourses, type DemoRole, type Locale, type Person, type Review } from './model'
import styles from './preview.module.css'

const control = 'min-h-11 rounded-lg'
function Mark({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'green' | 'amber' }) {
  const tones = { neutral: 'bg-gray-100 text-gray-700', green: 'bg-green-50 text-green-800', amber: 'bg-amber-50 text-amber-900' }
  return <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ${tones[tone]}`}>{children}</span>
}
function Choice({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode }) {
  const id = React.useId()
  return <div className="flex min-w-0 flex-col gap-1.5 text-xs font-medium text-gray-600"><label htmlFor={id}>{label}</label><select id={id} value={value} onChange={e => onChange(e.target.value)} className="min-h-11 min-w-0 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900">{children}</select></div>
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="min-w-0"><dt className="text-xs font-medium text-gray-600">{label}</dt><dd className="mt-1 break-words text-sm font-medium text-gray-900">{children}</dd></div>
}

export default function ClassesPreview() {
  const { canManageOrg, loading } = useAdminStatus()
  const { t } = useTranslation()
  if (loading) return <div className="p-6" role="status">{t('common.loading')}</div>
  if (!canManageOrg) return <div className="p-6"><h1 className="text-xl font-semibold">{t('classes_preview.admin_only')}</h1><p className="mt-2 text-sm text-gray-600">{t('classes_preview.admin_only_help')}</p></div>
  return <PreviewScene />
}

function PreviewScene() {
  const params = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()
  const { i18n } = useTranslation()
  const [locale, setLocale] = useState<Locale>(i18n.language.startsWith('th') ? 'th' : 'en')
  const text = (key: CopyKey) => copy[locale][key]
  const role: DemoRole = params.get('role') === 'admin' ? 'admin' : params.get('role') === 'student' ? 'student' : 'teacher'
  const rawView = params.get('view') || 'classes'
  const requestedView = ['classes', 'roster', 'student', 'identity', 'queue', 'case'].includes(rawView) ? rawView : 'classes'
  const view = role === 'student' ? 'identity' : requestedView === 'queue' || requestedView === 'case' ? (role === 'admin' ? requestedView : 'classes') : requestedView === 'identity' && role === 'admin' ? 'classes' : requestedView
  const sectionId = params.get('section') || ''
  const personId = params.get('person') || ''
  const reviewId = params.get('case') || ''
  const [state, dispatch] = useReducer(transition, undefined, initialState)
  const [term, setTerm] = useState('current')
  const [query, setQuery] = useState('')
  const [attention, setAttention] = useState(false)
  const [membership, setMembership] = useState('active')
  const [linkFilter, setLinkFilter] = useState('all')
  const [reviewKind, setReviewKind] = useState('all')
  const [reviewStatus, setReviewStatus] = useState('pending')
  const [previewState, setPreviewState] = useState('ready')
  const [notice, setNotice] = useState('')
  const [flagReason, setFlagReason] = useState<Review['reason']>('wrong_account')
  const [flagging, setFlagging] = useState(false)
  const [ownStep, setOwnStep] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [decisionConfirmed, setDecisionConfirmed] = useState(false)
  const [decisionReason, setDecisionReason] = useState('')
  const [resetting, setResetting] = useState(false)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const routeKey = params.toString()
  useEffect(() => {
    headingRef.current?.focus()
    setNotice(''); setConfirmed(false); setOwnStep(false); setDecisionConfirmed(false); setDecisionReason(''); setQuery(''); setFlagging(false)
  }, [routeKey])
  const url = (nextView: string, extras: Record<string, string> = {}, nextRole = role) => {
    const next = new URLSearchParams({ role: nextRole, view: nextView, ...extras })
    return `${pathname}?${next}`
  }
  const person = state.people.find(p => p.id === personId)
  const section = sections.find(s => s.id === sectionId)
  const course = courses.find(c => c.id === section?.course)
  const reviewCase = state.reviews.find(r => r.id === reviewId)
  const casePerson = state.people.find(p => p.id === reviewCase?.person)
  const owned = state.people.find(p => p.id === ownPerson(role))!
  const ownedReview = state.reviews.find(r => r.person === owned.id && isPending(r))
  const scopedSections = sections.filter(s => s.term === term && visibleCourses(role).some(c => c.id === s.course))
  const filteredSections = scopedSections.filter(s => {
    const c = courses.find(c => c.id === s.course)!
    const search = `${c.code} ${c.name.en} ${c.name.th} ${s.label}`.toLowerCase()
    return search.includes(query.toLowerCase()) && (!attention || rosterFor(s.id).some(m => m.status === 'active' && (!state.people.find(p => p.id === m.person)?.account || hasReview(state, m.person))))
  })
  const rows = rosterFor(sectionId).filter(m => {
    const p = state.people.find(p => p.id === m.person)!
    return (membership === 'all' || m.status === membership) && (linkFilter === 'all' || (linkFilter === 'review' ? hasReview(state, p.id) : linkFilter === 'linked' ? !!p.account : !p.account)) && `${p.name.en} ${p.name.th} ${p.number || ''}`.toLowerCase().includes(query.toLowerCase())
  })
  const reviews = state.reviews.filter(r => {
    const p = state.people.find(p => p.id === r.person)!
    return (reviewKind === 'all' || p.kind === reviewKind) && (reviewStatus === 'all' || isPending(r)) && `${p.name.en} ${p.name.th} ${p.number || ''}`.toLowerCase().includes(query.toLowerCase())
  })
  const title = view === 'identity' ? text('identity') : view === 'queue' || view === 'case' ? text('queue') : view === 'student' ? text('details') : view === 'roster' ? text('students') : role === 'admin' ? text('classes') : text('myClasses')
  const searchField = (label: string) => <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-xs font-medium text-gray-600"><span>{label}</span><div className="relative"><Search aria-hidden="true" size={17} className="pointer-events-none absolute left-3 top-3.5 text-gray-500" /><Input value={query} onChange={e => setQuery(e.target.value)} placeholder={label} className={`${control} pl-10`} /></div></label>
  const empty = (titleKey: CopyKey = 'empty', helpKey: CopyKey = 'emptyHelp') => <div className="py-12 text-center"><Search size={24} aria-hidden="true" className="mx-auto text-gray-500" /><h2 className="mt-3 text-base font-semibold">{text(titleKey)}</h2><p className="mx-auto mt-2 max-w-md text-sm text-gray-600">{text(helpKey)}</p><Button variant="outline" className={`mt-5 ${control}`} onClick={() => { setQuery(''); setAttention(false); setMembership('all'); setLinkFilter('all'); setReviewKind('all'); setReviewStatus('all') }}>{text('clear')}</Button></div>
  const personFields = (p: Person) => <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2"><Field label={text('officialName')}>{p.name[locale]}</Field><Field label={text(p.kind === 'teacher' ? 'staffNumber' : 'number')}>{p.number || text('noNumber')}</Field><Field label={text('identityKind')}>{text(p.kind)}</Field><Field label={text('institution')}>{text('institution')}</Field><Field label={text('currentLink')}>{p.account || text('noAccount')}</Field>{p.candidate && <Field label={text('candidate')}>{p.candidate}</Field>}</dl>
  const activityFor = (id: string) => <section className="mt-8 border-t border-gray-200 pt-6"><h2 className="text-base font-semibold">{text('history')}</h2>{state.activity.filter(a => a.person === id).length === 0 ? <p className="mt-3 text-sm text-gray-600">{text('noHistory')}</p> : <ol className="mt-3 space-y-3">{state.activity.filter(a => a.person === id).map((a, i) => <li key={i} className="text-sm text-gray-700"><span className="font-medium">{text(a.action === 'flagged' ? 'flaggedAction' : a.action === 'requested' ? 'requestedAction' : a.action === 'approved' ? 'approvedAction' : a.action === 'rejected' ? 'rejectedAction' : 'evidenceAction')}</span><span className="ml-2 text-gray-600">· {text(a.role)}</span>{a.note && <p className="mt-1 break-words text-gray-600">{a.note}</p>}</li>)}</ol>}</section>
  const rosterContext = section && course && <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600"><span className="font-medium text-gray-900">{course.name[locale]} · {course.code}</span><span>{text('section')} {section.label}</span><span>{text(section.term)}</span></div>
  const clearFilters = () => { setQuery(''); setMembership('all'); setLinkFilter('all'); setAttention(false) }
  function decide(decision: 'approve' | 'reject' | 'more_evidence') {
    if (!reviewCase) return
    dispatch({ type: 'decide', role, review: reviewCase.id, decision, confirmed: decisionConfirmed, reason: decisionReason })
    setNotice(text('decisionSaved'))
  }

  return <main className={`${styles.preview} min-w-0 text-gray-900`}>
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-4 sm:px-10">
      <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-center">
        <div className="max-w-xl"><p className="text-sm font-semibold text-amber-950">{text('boundary')}</p><p className="mt-1 text-xs leading-relaxed text-amber-900">{text('boundaryHelp')}</p></div>
        <div className="grid grid-cols-2 gap-3"><Choice label={text('role')} value={role} onChange={value => router.push(url(value === 'student' ? 'identity' : 'classes', {}, value as DemoRole))}>{(['teacher', 'student', 'admin'] as const).map(r => <option key={r} value={r}>{text(r)}</option>)}</Choice><Choice label={text('language')} value={locale} onChange={value => setLocale(value as Locale)}><option value="en">English</option><option value="th">ไทย</option></Choice></div>
      </div>
    </div>
    <header className="border-b border-gray-200 bg-white px-4 pt-6 sm:px-10">
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1.5 text-xs text-gray-600"><Link href={url(role === 'student' ? 'identity' : 'classes')} className="inline-flex min-h-11 items-center gap-1.5 rounded hover:text-gray-900"><BookOpen size={14} aria-hidden="true" />{text('preview')}</Link>{view !== 'classes' && <><ChevronRight size={14} aria-hidden="true" /><span>{title}</span></>}</nav>
      <h1 ref={headingRef} tabIndex={-1} className="mt-2 text-3xl font-bold tracking-tight">{title}</h1>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-gray-600">{view === 'identity' ? text('identityHelp') : view === 'queue' || view === 'case' ? text('queueHelp') : view === 'classes' ? text(role === 'admin' ? 'adminHelp' : 'classesHelp') : text('readonlyHelp')}</p>
      {rosterContext && (view === 'roster' || view === 'student') && rosterContext}
      <div className="mt-5"><DashTabBar tabs={[
        ...(role !== 'student' ? [{ key: 'classes', label: text('classes'), icon: <BookOpen size={16} />, href: url('classes'), active: view === 'classes' || view === 'roster' || view === 'student' }] : []),
        ...(role !== 'admin' ? [{ key: 'identity', label: text('identity'), icon: <GraduationCap size={16} />, href: url('identity'), active: view === 'identity' }] : []),
        ...(role === 'admin' ? [{ key: 'queue', label: text('queue'), icon: <ShieldCheck size={16} />, href: url('queue'), active: view === 'queue' || view === 'case' }] : []),
      ]} /></div>
    </header>
    <div className="px-4 py-6 sm:px-10 sm:py-8">
      {notice && <p role="status" className="mb-5 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{notice}</p>}
      {view === 'classes' && <>
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end">{searchField(text('searchClasses'))}<Choice label={text('term')} value={term} onChange={setTerm}><option value="current">{text('current')}</option><option value="previous">{text('previous')}</option></Choice></div>
        <label className="mb-5 inline-flex min-h-11 cursor-pointer items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={attention} onChange={e => setAttention(e.target.checked)} className="h-4 w-4 accent-gray-900" />{text('attention')}</label>
        {previewState === 'loading' ? <div role="status" className="space-y-4"><p className="text-sm text-gray-600">{text('loadingLabel')}</p>{[0, 1, 2].map(i => <div key={i} className="h-24 rounded-xl border border-gray-200 bg-gray-100" aria-hidden="true" />)}</div> : previewState === 'error' ? <div role="alert" className="rounded-xl border border-gray-200 bg-white p-6"><h2 className="font-semibold">{text('unavailable')}</h2><p className="mt-2 text-sm text-gray-600">{text('unavailableHelp')}</p><Button onClick={() => setPreviewState('ready')} className={`mt-5 ${control}`}>{text('retry')}</Button></div> : filteredSections.length === 0 ? empty() : <div className="space-y-8">{visibleCourses(role).filter(c => filteredSections.some(s => s.course === c.id)).map(c => <section key={c.id}>
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2"><h2 className="text-lg font-semibold">{c.name[locale]} <span className="ml-2 text-sm font-normal text-gray-600">{c.code}</span></h2><span className="text-xs text-gray-600">{text('teacherAssignment')}</span></div>
          <ul className="divide-y divide-gray-200 overflow-hidden rounded-xl border border-gray-200 bg-white">{filteredSections.filter(s => s.course === c.id).map(s => {
            const roster = rosterFor(s.id).filter(m => m.status === 'active')
            const pending = roster.filter(m => hasReview(state, m.person)).length
            const missing = roster.filter(m => !state.people.find(p => p.id === m.person)?.account).length
            return <li key={s.id} className="grid gap-4 p-5 md:grid-cols-[1fr_1.5fr_1fr_auto] md:items-center"><div><p className="font-semibold">{text('section')} {s.label}</p><p className="mt-1 text-xs text-gray-600">{text(s.term)}</p></div><div className="text-sm text-gray-700"><p>{s.schedule[locale]}</p><p className="mt-1 text-xs text-gray-600">{s.room}</p></div><div className="flex flex-wrap items-center gap-2 md:block"><p className="text-sm"><span className="font-semibold tabular-nums">{roster.length}</span> <span className="text-gray-600">{text('activeStudents')}</span></p><p className="mt-1 text-xs text-gray-600">{pending > 0 && <span className="font-medium text-amber-900">{pending} {text('review')} · </span>}{missing} {text('unlinked')}</p></div><Button variant="outline" className={control} asChild><Link href={url('roster', { section: s.id })}>{text('viewStudents')}<ArrowRight aria-hidden="true" /></Link></Button></li>
          })}</ul>
        </section>)}</div>}
        <p className="mt-6 text-xs text-gray-600">{role === 'teacher' ? text('scope') : text('scopeSchool')}</p>
      </>}
      {(view === 'roster' || view === 'student') && (!section || !canViewSection(role, sectionId)) && empty('notFound', 'noClassesHelp')}
      {view === 'roster' && section && canViewSection(role, sectionId) && <>
        <div className="mb-6 grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto_auto]">{searchField(text('searchStudents'))}<Choice label={text('membership')} value={membership} onChange={setMembership}>{(['active', 'all', 'withdrawn'] as const).map(s => <option key={s} value={s}>{text(s)}</option>)}</Choice><Choice label={text('accountLink')} value={linkFilter} onChange={setLinkFilter}>{(['all', 'linked', 'unlinked', 'review'] as const).map(s => <option key={s} value={s}>{text(s)}</option>)}</Choice></div>
        <div className="mb-3 flex items-center justify-between gap-3 text-sm text-gray-600"><p><span className="tabular-nums">{rows.length}</span> {text('rowCount')}</p>{(query || membership !== 'active' || linkFilter !== 'all') && <Button variant="ghost" className={control} onClick={clearFilters}>{text('clear')}</Button>}</div>
        {rows.length === 0 ? empty() : <div className="overflow-hidden rounded-xl border border-gray-200 bg-white"><table className={styles.rosterTable}><caption className="sr-only">{course?.name[locale]} · {text('section')} {section.label} · {text(section.term)}</caption><thead><tr><th>{text('officialIdentity')}</th><th>{text('membership')}</th><th>{text('accountLink')}</th><th><span className="sr-only">{text('details')}</span></th></tr></thead><tbody>{rows.map(m => {
          const p = state.people.find(p => p.id === m.person)!
          return <tr key={p.id}><td><p className="font-semibold">{p.name[locale]}</p><p className="mt-1 text-xs tabular-nums text-gray-600">{p.number || text('manual')}</p></td><td><Mark>{text(m.status)}</Mark><p className="mt-1.5 text-xs text-gray-600">{text(m.source === 'manual' ? 'manual' : 'registrar')}</p></td><td><Mark tone={p.account ? 'green' : 'neutral'}>{p.account && <CheckCircle2 size={13} aria-hidden="true" />}{text(p.account ? 'linked' : 'unlinked')}</Mark>{hasReview(state, p.id) && <p className="mt-1.5 text-xs font-medium text-amber-900">{text('review')}</p>}</td><td><Button variant="ghost" className={`${control} w-full whitespace-normal`} asChild><Link aria-label={`${text('details')}: ${p.name[locale]}`} href={url('student', { section: sectionId, person: p.id })}>{text('details')}<ChevronRight aria-hidden="true" /></Link></Button></td></tr>
        })}</tbody></table></div>}
        <p className="mt-5 flex items-center gap-2 text-xs text-gray-600"><ShieldCheck size={15} aria-hidden="true" />{text('readonly')}</p>
      </>}
      {view === 'student' && section && canViewSection(role, sectionId) && person && rosterFor(sectionId).some(m => m.person === person.id) && <section className="max-w-3xl rounded-xl border border-gray-200 bg-white p-5 sm:p-7">
        <Button variant="ghost" asChild className={`${control} mb-5 -ml-3`}><Link href={url('roster', { section: sectionId })}><ArrowLeft aria-hidden="true" />{text('returnRoster')}</Link></Button>
        <h2 className="mb-6 text-xl font-semibold">{person.name[locale]}</h2>{personFields(person)}
        <div className="mt-6 border-t border-gray-200 pt-5"><p className="text-sm text-gray-600">{person.number ? text('protected') : text('manualHelp')}</p>{hasReview(state, person.id) ? <div className="mt-4"><Mark tone="amber">{text('pending')}</Mark>{role === 'admin' && <Button className={`ml-3 ${control}`} asChild><Link href={url('case', { case: state.reviews.find(r => r.person === person.id && isPending(r))!.id })}>{text('resolve')}</Link></Button>}</div> : role === 'teacher' && <Button className={`mt-4 ${control}`} variant="outline" onClick={() => setFlagging(true)}><Flag aria-hidden="true" />{text('flag')}</Button>}
          {flagging && <form className="mt-5 space-y-4" onSubmit={e => { e.preventDefault(); dispatch({ type: 'flag', role, person: person.id, section: sectionId, reason: flagReason }); setFlagging(false); setNotice(text('flagged')) }}><Choice label={text('reason')} value={flagReason} onChange={v => setFlagReason(v as Review['reason'])}>{(['wrong_account', 'wrong_name', 'wrong_number'] as const).map(r => <option key={r} value={r}>{text(r)}</option>)}</Choice><div className="flex flex-wrap gap-3"><Button type="submit" className={control}>{text('submitFlag')}</Button><Button type="button" variant="ghost" className={control} onClick={() => setFlagging(false)}>{text('cancel')}</Button></div></form>}
        </div>{activityFor(person.id)}
      </section>}
      {view === 'student' && section && canViewSection(role, sectionId) && (!person || !rosterFor(sectionId).some(m => m.person === person.id)) && empty('notFound', 'emptyHelp')}
      {view === 'identity' && role !== 'admin' && <section className="max-w-3xl rounded-xl border border-gray-200 bg-white p-5 sm:p-7">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">{owned.name[locale]}</h2><Mark tone={ownedReview ? 'amber' : owned.verified ? 'green' : 'neutral'}>{ownedReview ? text(ownedReview.status === 'more_evidence' ? 'needsEvidence' : 'pending') : text(owned.verified ? 'verified' : 'notVerified')}</Mark></div>
        {personFields(owned)}<p className="mt-6 max-w-prose text-sm leading-relaxed text-gray-600">{text('stillUse')}</p>
        <div className="mt-6 border-t border-gray-200 pt-6"><p className="max-w-prose text-xs leading-relaxed text-gray-600">{text('schoolMethod')}</p>{!owned.verified && !ownedReview && !ownStep && <Button className={`mt-4 ${control}`} onClick={() => setOwnStep(true)}>{text('tryVerify')}<ArrowRight aria-hidden="true" /></Button>}
          {ownStep && !ownedReview && <form onSubmit={e => { e.preventDefault(); if (!confirmed) return; dispatch({ type: 'verify', role, person: owned.id, confirmed }); setOwnStep(false); setNotice(text('submitted')) }} className="mt-5 space-y-5"><p className="rounded-lg bg-gray-50 p-4 text-sm text-gray-700">{text('proofBoundary')}</p><label className="flex min-h-11 cursor-pointer items-start gap-3 text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-gray-900" />{text('confirmOwn')}</label><Button type="submit" disabled={!confirmed} className={control}>{text('requestReview')}</Button></form>}
          {ownedReview && <p className="mt-4 text-sm text-amber-900">{text('pending')}</p>}
        </div>{activityFor(owned.id)}
      </section>}
      {view === 'queue' && role === 'admin' && <>
        <div className="mb-6 grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto_auto]">{searchField(text('searchReview'))}<Choice label={text('identityKind')} value={reviewKind} onChange={setReviewKind}><option value="all">{text('reviewAll')}</option><option value="student">{text('reviewStudents')}</option><option value="teacher">{text('reviewTeachers')}</option></Choice><Choice label={text('status')} value={reviewStatus} onChange={setReviewStatus}><option value="pending">{text('pendingTab')}</option><option value="all">{text('decisions')}</option></Choice></div>
        {reviews.length === 0 ? empty('noPending', 'noPendingHelp') : <ul className="divide-y divide-gray-200 overflow-hidden rounded-xl border border-gray-200 bg-white">{reviews.map(r => { const p = state.people.find(p => p.id === r.person)!; return <li key={r.id} className="flex flex-col justify-between gap-4 p-5 sm:flex-row sm:items-center"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h2 className="text-base font-semibold">{p.name[locale]}</h2><Mark>{text(p.kind)}</Mark><Mark tone={isPending(r) ? 'amber' : 'neutral'}>{text(r.status)}</Mark></div><p className="mt-2 text-sm text-gray-600">{p.number} · {text(r.reason)}</p></div><Button variant="outline" className={`${control} shrink-0`} asChild><Link href={url('case', { case: r.id })}>{text('resolve')}<ArrowRight aria-hidden="true" /></Link></Button></li> })}</ul>}
      </>}
      {view === 'case' && role === 'admin' && reviewCase && casePerson && <section className="max-w-3xl rounded-xl border border-gray-200 bg-white p-5 sm:p-7">
        <Button variant="ghost" className={`${control} mb-5 -ml-3`} asChild><Link href={url('queue')}><ArrowLeft aria-hidden="true" />{text('back')}</Link></Button>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">{casePerson.name[locale]}</h2><Mark tone={isPending(reviewCase) ? 'amber' : 'neutral'}>{text(reviewCase.status)}</Mark></div>{personFields(casePerson)}
        {reviewCase.section && <p className="mt-5 text-sm"><span className="text-gray-600">{text('associatedClass')}: </span><Link className="underline underline-offset-4" href={url('roster', { section: reviewCase.section })}>{courses.find(c => c.id === sections.find(s => s.id === reviewCase.section)?.course)?.name[locale]} · {text('section')} {sections.find(s => s.id === reviewCase.section)?.label}</Link></p>}
        <div className="mt-6 border-t border-gray-200 pt-6"><h3 className="font-semibold">{text('proof')}</h3><p className="mt-2 text-sm text-gray-600">{text(reviewCase.reason)}</p><p className={`mt-4 flex items-start gap-2 rounded-lg p-4 text-sm ${reviewCase.eligible ? 'bg-green-50 text-green-900' : 'bg-amber-50 text-amber-950'}`}>{reviewCase.eligible ? <CheckCircle2 className="mt-0.5 shrink-0" size={18} aria-hidden="true" /> : <XCircle className="mt-0.5 shrink-0" size={18} aria-hidden="true" />}{text(reviewCase.eligible ? 'matches' : 'conflict')}</p><p className="mt-4 text-sm leading-relaxed text-gray-600">{text(reviewCase.type === 'discrepancy' ? 'retainConsequence' : 'consequence')}</p></div>
        {isPending(reviewCase) ? <div className="mt-6 space-y-5"><label className="flex flex-col gap-2 text-sm font-medium">{text('decisionReason')}<Input value={decisionReason} onChange={e => setDecisionReason(e.target.value)} maxLength={160} placeholder={text('decisionPlaceholder')} className={control} /></label>{reviewCase.eligible && reviewCase.status !== 'more_evidence' && <label className="flex min-h-11 cursor-pointer items-start gap-3 text-sm"><input type="checkbox" checked={decisionConfirmed} onChange={e => setDecisionConfirmed(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-gray-900" />{text('confirmDecision')}</label>}<div className="flex flex-wrap gap-3"><Button className={`${control} whitespace-normal`} disabled={!reviewCase.eligible || reviewCase.status === 'more_evidence' || !decisionConfirmed || !decisionReason.trim()} onClick={() => decide('approve')}>{text(reviewCase.type === 'discrepancy' ? 'keepLink' : 'approve')}</Button><Button variant="outline" className={`${control} whitespace-normal`} disabled={!decisionReason.trim() || reviewCase.status === 'more_evidence'} onClick={() => decide('more_evidence')}>{text('askEvidence')}</Button><Button variant="ghost" className={control} disabled={!decisionReason.trim()} onClick={() => decide('reject')}>{text('reject')}</Button></div></div> : <p className="mt-6 text-sm text-gray-600">{text('caseResolved')}</p>}{activityFor(casePerson.id)}
      </section>}
      {view === 'case' && role === 'admin' && (!reviewCase || !casePerson) && empty('empty', 'emptyHelp')}
      <details className="mt-10 border-t border-gray-200 pt-5"><summary className="min-h-11 cursor-pointer text-sm font-medium text-gray-600">{text('controls')}</summary><div className="mt-4 flex flex-wrap items-end gap-4"><Choice label={text('state')} value={previewState} onChange={value => { setPreviewState(value); router.push(url('classes')) }}>{(['ready', 'loading', 'error'] as const).map(s => <option key={s} value={s}>{text(s)}</option>)}</Choice><Button variant="outline" className={control} onClick={() => setResetting(true)}>{text('reset')}</Button></div></details>
    </div>
    <Dialog open={resetting} onOpenChange={setResetting}><DialogContent className="w-[calc(100%_-_2rem)] p-6"><DialogTitle>{text('confirmReset')}</DialogTitle><DialogDescription className="mt-3 pr-4">{text('resetHelp')}</DialogDescription><div className="mt-6 flex flex-wrap justify-end gap-3"><Button variant="outline" className={control} onClick={() => setResetting(false)}>{text('cancel')}</Button><Button className={control} onClick={() => window.location.reload()}>{text('reset')}</Button></div></DialogContent></Dialog>
  </main>
}
