'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Beaker, CalendarDays, Check, Clock3, MapPin } from 'lucide-react'
import { Button, Input } from '@/extensions/route66/adapters/ui'
import dayColors from '../../Account/subpages/timetable-colors.module.css'
import { planningCopy } from './copy'
import { applySampleRoster, buildProposal, demoRoster, filterRoster, sections, topicForWeek, weekdays, type SectionId } from './model'
import s from './preview.module.css'

type View = 'overview' | 'timetable' | 'plan' | 'roster' | 'syllabus'
type SyllabusPart = 'about' | 'outcomes' | 'approach' | 'assessment'
const views: View[] = ['overview', 'timetable', 'plan', 'roster', 'syllabus']
const syllabusParts: SyllabusPart[] = ['about', 'outcomes', 'approach', 'assessment']

export default function TeacherPlanningPreview({ th, onClose }: { th: boolean; onClose: () => void }) {
  const t = planningCopy[th ? 'th' : 'en'], language = th ? 'th' : 'en'
  const navLabels = { overview: t.overview, timetable: t.navTimetable, plan: t.plan, roster: t.navRoster, syllabus: t.navSyllabus }
  const [view, setView] = useState<View>('overview'), [section, setSection] = useState<SectionId>('P1')
  const [bothSections, setBothSections] = useState(false), [week, setWeek] = useState('1')
  const [holidays, setHolidays] = useState({ P1: true, P2: true }), [accepted, setAccepted] = useState({ P1: false, P2: false })
  const [planConfirmed, setPlanConfirmed] = useState(false), [showHandoff, setShowHandoff] = useState(false)
  const [rosterApplied, setRosterApplied] = useState({ P1: false, P2: false }), [rosterReview, setRosterReview] = useState(false), [rosterConfirmed, setRosterConfirmed] = useState(false)
  const [query, setQuery] = useState(''), [membership, setMembership] = useState('all'), [account, setAccount] = useState('all')
  const [syllabusPart, setSyllabusPart] = useState<SyllabusPart>('about'), [syllabusConfirmed, setSyllabusConfirmed] = useState(false), [syllabusReviewed, setSyllabusReviewed] = useState(false)
  const title = useRef<HTMLHeadingElement>(null)
  useEffect(() => { title.current?.focus() }, [])
  const proposal = buildProposal(section, holidays[section])
  const initialRoster = demoRoster(section), people = rosterApplied[section] ? applySampleRoster(initialRoster, section) : initialRoster
  const visiblePeople = filterRoster(people, query, membership, account)
  const sessionCount = proposal.filter(p => p.state !== 'no_class').length
  const date = (value: string) => new Intl.DateTimeFormat(th ? 'th-TH' : 'en-GB', { day: 'numeric', month: 'short', timeZone: 'Asia/Bangkok' }).format(new Date(value + 'T12:00:00Z'))
  function chooseSection(id: SectionId) {
    setSection(id); setWeek('1'); setQuery(''); setMembership('all'); setAccount('all')
    setRosterReview(false); setRosterConfirmed(false); setPlanConfirmed(false); setShowHandoff(false)
  }
  function clearFilters() { setQuery(''); setMembership('all'); setAccount('all') }

  return <section className={s.preview} aria-labelledby="teaching-preview-title">
    <Button variant="ghost" className={s.back} onClick={onClose}><ArrowLeft size={16} aria-hidden="true" />{t.back}</Button>
    <header className={s.heading}><h1 id="teaching-preview-title" ref={title} tabIndex={-1}>{t.title}</h1><p>{t.placementHelp}</p></header>
    <aside className={s.disclosure} aria-label={t.demo}><Beaker size={20} aria-hidden="true" /><div><strong>{t.demo}</strong><p>{t.demoHelp}</p></div></aside>
    <div className={s.context}><div><h2>{t.course}</h2><p>{t.courseContext} · {view === 'syllabus' ? t.courseScope : t.classScope}</p></div>
      <label>{t.section}<select aria-label={t.section} value={section} onChange={e => chooseSection(e.target.value as SectionId)}>{sections.map(c => <option key={c.id} value={c.id}>{c.id}</option>)}</select></label>
    </div>
    <nav className={s.navigation} aria-label={t.tasks}>{views.map(v => <button key={v} type="button" aria-label={t[v]} aria-current={view === v ? 'page' : undefined} onClick={() => setView(v)}>{navLabels[v]}</button>)}</nav>
    <div className={s.body}>
      {view === 'overview' && <>
        <section className={s.next} aria-labelledby="preview-next-title"><CalendarDays size={24} aria-hidden="true" /><div><h2 id="preview-next-title">{t.nextTitle}</h2><p>{t.nextHelp}</p><Button onClick={() => setView('plan')}>{t.next}<ArrowRight size={16} aria-hidden="true" /></Button></div></section>
        <section aria-labelledby="preview-sources"><h2 id="preview-sources">{t.sources}</h2><dl className={s.sources}>{([
          ['timetable', t.sourceWeekly, t.sourceWeeklyHelp], ['plan', t.sourcePlan, t.sourcePlanHelp], ['roster', t.sourceRoster, t.sourceRosterHelp], ['syllabus', t.sourceSyllabus, t.sourceSyllabusHelp],
        ] as [View, string, string][]).map(([target, label, help]) => <div key={target}><dt><button type="button" onClick={() => setView(target)}>{label}<ArrowRight size={15} aria-hidden="true" /></button></dt><dd>{help}</dd></div>)}</dl></section>
      </>}
      {view === 'timetable' && <section aria-labelledby="preview-weekly-title">
        <h2 id="preview-weekly-title">{t.weeklyTitle}</h2><p className={s.help}>{t.weeklyHelp}</p>
        <label className={s.check}><input type="checkbox" checked={bothSections} onChange={e => setBothSections(e.target.checked)} />{t.allSections}</label>
        <div className={s.weekGrid}>{weekdays.map((day, dayIndex) => <section className={s.dayColumn} key={day.en} aria-label={day[language]}>
          <h3><span className={dayColors.day} data-weekday={day.en.toLowerCase()}>{day[language]}</span></h3>
          {sections.filter(c => bothSections || c.id === section).flatMap(c => c.meetings.filter(m => m.day === dayIndex).map(m => <div className={s.meeting} key={c.id + m.start}>
            <strong>{c.id}{c.id === section ? ` · ${t.selected}` : ''}</strong><p><Clock3 size={15} aria-hidden="true" />{m.start}–{m.end}</p><p><MapPin size={15} aria-hidden="true" />{m.room}</p>
            {c.id !== section && <button type="button" onClick={() => chooseSection(c.id)}>{t.section} {c.id}<ArrowRight size={14} aria-hidden="true" /></button>}
          </div>))}
          {!sections.some(c => (bothSections || c.id === section) && c.meetings.some(m => m.day === dayIndex)) && <p className={s.noMeeting}>{t.noMeeting}</p>}
        </section>)}</div><Button variant="outline" onClick={() => setView('plan')}>{t.dated}<ArrowRight size={16} aria-hidden="true" /></Button>
      </section>}
      {view === 'plan' && <section aria-labelledby="preview-plan-title">
        <h2 id="preview-plan-title">{t.planTitle}</h2><p className={s.help}>{t.planHelp}</p>
        <div className={s.planControls}><div><label className={s.check}><input type="checkbox" checked={holidays[section]} onChange={e => { setHolidays({ ...holidays, [section]: e.target.checked }); setAccepted({ ...accepted, [section]: false }); setPlanConfirmed(false); setShowHandoff(false) }} />{t.holiday}</label><p className={s.help}>{t.holidayHelp}</p></div>
          <label>{t.weekSelect}<select aria-label={t.weekSelect} value={week} onChange={e => setWeek(e.target.value)}><option value="all">{t.allWeeks}</option>{Array.from({ length: 16 }, (_, i) => <option key={i} value={String(i + 1)}>{t.week} {i + 1}</option>)}</select></label>
        </div>
        <p className={s.summary} role="status"><span className={s.status}>{accepted[section] ? t.accepted : t.proposed}</span>{sessionCount} {t.sessions} · {proposal.filter(p => p.state === 'no_class').length} {t.closures} · {proposal.filter(p => p.state === 'makeup').length} {t.makeupCount}</p>
        <div className={s.plan}>{Array.from({ length: 16 }, (_, i) => i + 1).filter(w => week === 'all' || String(w) === week).map(w => <section className={s.week} key={w} aria-label={`${t.week} ${w}`}>
          <div className={s.weekHeading}><h3>{t.week} {w}</h3><p>{topicForWeek(w)[language]}</p></div>
          <ol>{proposal.filter(p => p.week === w).map(p => <li key={p.id} className={s.session}>
            <div><p className={s.sessionDate}>{date(p.date)}</p><p>{p.start}–{p.end}</p></div>
            <div><strong className={p.state === 'no_class' ? s.warning : s.status}>{p.state === 'no_class' ? t.closed : p.state === 'makeup' ? t.makeup : t.scheduled}</strong>
              <p>{p.state === 'no_class' ? t.closureHelp : p.state === 'makeup' ? t.makeupHelp : t.activity}</p>
              {p.state !== 'no_class' && <p className={s.secondary}>{p.delivery === 'online' ? t.online : `${t.campus} · ${p.room}`}</p>}
            </div>
          </li>)}</ol>
        </section>)}</div>
        <div className={s.reviewBox}>{accepted[section] ? <><p role="status"><Check size={18} aria-hidden="true" />{t.acceptedHelp}</p><Button variant="outline" onClick={() => { setAccepted({ ...accepted, [section]: false }); setPlanConfirmed(false); setShowHandoff(false) }}>{t.regenerate}</Button><Button variant="outline" onClick={() => setShowHandoff(!showHandoff)} aria-expanded={showHandoff}>{t.attendance}</Button>{showHandoff && <p>{t.attendanceHelp}</p>}</> : <><label className={s.check}><input type="checkbox" checked={planConfirmed} onChange={e => setPlanConfirmed(e.target.checked)} />{t.reviewPlan}</label><Button disabled={!planConfirmed} onClick={() => setAccepted({ ...accepted, [section]: true })}>{t.accept}</Button></>}</div>
      </section>}
      {view === 'roster' && <section aria-labelledby="preview-roster-title">
        <div className={s.sectionHeading}><div><h2 id="preview-roster-title">{t.rosterTitle}</h2><p className={s.help}>{t.rosterHelp}</p></div><Button variant="outline" disabled={rosterApplied[section]} onClick={() => { setRosterReview(true); setRosterConfirmed(false) }}>{rosterApplied[section] ? t.rosterReviewed : t.sampleSync}</Button></div>
        {rosterReview && <section className={s.reviewBox} aria-labelledby="preview-roster-review"><h3 id="preview-roster-review">{t.syncTitle}</h3><p>{t.syncHelp}</p><label className={s.check}><input type="checkbox" checked={rosterConfirmed} onChange={e => setRosterConfirmed(e.target.checked)} />{t.confirmRoster}</label><div className={s.actions}><Button disabled={!rosterConfirmed} onClick={() => { setRosterApplied({ ...rosterApplied, [section]: true }); setRosterReview(false) }}>{t.applyRoster}</Button><Button variant="ghost" onClick={() => setRosterReview(false)}>{t.cancel}</Button></div></section>}
        {rosterApplied[section] && <p role="status" className={s.notice}>{t.rosterSaved}</p>}
        <div className={s.filters}><label>{t.search}<Input value={query} onChange={e => setQuery(e.target.value)} /></label><label>{t.membership}<select aria-label={t.membership} value={membership} onChange={e => setMembership(e.target.value)}><option value="all">{t.allMemberships}</option><option value="active">{t.active}</option><option value="withdrawn">{t.withdrawn}</option></select></label><label>{t.accounts}<select aria-label={t.accounts} value={account} onChange={e => setAccount(e.target.value)}><option value="all">{t.allAccounts}</option><option value="linked">{t.linked}</option><option value="unlinked">{t.unlinked}</option><option value="review">{t.review}</option></select></label></div>
        <p className={s.help} role="status">{visiblePeople.length} / {people.length} {t.people}</p>
        {!visiblePeople.length ? <div className={s.empty}><h3>{t.noResults}</h3><Button variant="outline" onClick={clearFilters}>{t.clear}</Button></div> : <table className={s.roster}><caption className="sr-only">{t.rosterTitle}</caption><thead><tr><th scope="col">{t.learner}</th><th scope="col">{t.membership}</th><th scope="col">{t.accounts}</th></tr></thead><tbody>{visiblePeople.map(p => <tr key={p.id}>
          <th scope="row"><strong>{t.learner} {p.ordinal}</strong><p>{p.id}</p><p className={s.secondary}>{p.source === 'manual' ? t.manual : t.registry}</p></th>
          <td><span className={s.mobileLabel} aria-hidden="true">{t.membership}: </span>{p.status === 'active' ? t.active : t.withdrawn}{p.missing === 1 && <p className={s.warning}>{t.missingOnce}</p>}</td>
          <td><span className={s.mobileLabel} aria-hidden="true">{t.accounts}: </span><span className={p.account === 'review' ? s.warning : ''}>{t[p.account]}</span></td>
        </tr>)}</tbody></table>}
      </section>}
      {view === 'syllabus' && <section aria-labelledby="preview-syllabus-title">
        <h2 id="preview-syllabus-title">{t.syllabusTitle}</h2><p className={s.help}>{t.syllabusHelp}</p><p role="status" className={s.notice}>{syllabusReviewed ? t.syllabusReviewed : t.draft}</p>
        <div className={s.syllabus}><nav className={s.syllabusNav} aria-label={t.syllabus}>{syllabusParts.map(part => <button key={part} type="button" aria-current={syllabusPart === part ? 'page' : undefined} onClick={() => setSyllabusPart(part)}>{t[part]}</button>)}</nav>
          <section className={s.prose} aria-labelledby="preview-syllabus-section"><h3 id="preview-syllabus-section">{t[syllabusPart]}</h3>
            {syllabusPart === 'about' && <p>{t.aboutText}</p>}
            {syllabusPart === 'outcomes' && <ul>{[t.outcome1, t.outcome2, t.outcome3].map(text => <li key={text}>{text}</li>)}</ul>}
            {syllabusPart === 'approach' && <p>{t.approachText}</p>}
            {syllabusPart === 'assessment' && <><p>{t.assessmentText}</p><dl className={s.weights}>{([[t.quizzes, 20], [t.homework, 30], [t.capstone, 10], [t.midterm, 15], [t.final, 20], [t.participation, 5]] as [string, number][]).map(([label, weight]) => <div key={label}><dt>{label}</dt><dd>{weight}%</dd></div>)}</dl></>}
          </section>
        </div>
        {!syllabusReviewed && <div className={s.reviewBox}><label className={s.check}><input type="checkbox" checked={syllabusConfirmed} onChange={e => setSyllabusConfirmed(e.target.checked)} />{t.syllabusReview}</label><Button disabled={!syllabusConfirmed} onClick={() => setSyllabusReviewed(true)}>{t.markReviewed}</Button></div>}
      </section>}
    </div>
  </section>
}
