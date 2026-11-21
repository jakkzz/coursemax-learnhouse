// Synthetic component contracts, not native auth/provider or academic persistence acceptance.
import React, { useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Button } from '../../components/interior/Button'
import { CopyButton } from '../../components/interior/CopyButton'
import { SegmentedControl } from '../../components/interior/SegmentedControl'
import material from '../../components/interior/material.module.css'

function Fixture() {
  const th = new URLSearchParams(location.search).get('lang') === 'th', t = (en: string, thai: string) => th ? thai : en
  const [pending, setPending] = useState(false), [saved, setSaved] = useState(0), [name, setName] = useState('Synthetic draft')
  const [view, setView] = useState<'details' | 'disabled' | 'roster'>('details'), [showCopy, setShowCopy] = useState(true), [copies, setCopies] = useState(0)
  const button = useRef<HTMLButtonElement>(null)
  return <main className={material.scope} style={{ maxWidth: 850, padding: 24, margin: 'auto' }}>
    <h1>{t('Shared Interior controls', 'ส่วนควบคุม Interior ที่ใช้ร่วมกัน')}</h1>
    <p>{t('Synthetic fixture only. No institutional records.', 'ตัวอย่างทดสอบเท่านั้น ไม่มีข้อมูลของสถานศึกษา')}</p>
    <SegmentedControl label="Fixture views" value={view} onValueChange={setView} options={[{ value: 'details', label: t('Details', 'รายละเอียด') }, { value: 'disabled', label: t('Unavailable', 'ยังไม่เปิด'), disabled: true }, { value: 'roster', label: t('Official roster', 'รายชื่อจากทะเบียน') }]} />
    <p data-testid="view">{view}</p>
    <form onSubmit={async event => { event.preventDefault(); if (pending) return; setPending(true); await new Promise(resolve => setTimeout(resolve, 700)); setSaved(n => n + 1); setPending(false) }}>
      <label style={{ display: 'grid', gap: 8, marginBlock: 20 }}>Draft name<input value={name} onChange={event => setName(event.target.value)} /></label>
      <Button ref={button} loading={pending} loadingLabel={t('Saving…', 'กำลังบันทึก…')} data-testid="save">{t('Save draft', 'บันทึกฉบับร่าง')}</Button>
      <p role="status" data-testid="saved">{saved}</p>
    </form>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBlock: 24 }}>
      {showCopy && <CopyButton data-testid="copy" variant="outline" value={() => 'https://fixture.invalid/attendance/check-in?handoff=' + 'h'.repeat(43)} label={t('Copy link', 'คัดลอกลิงก์')} copiedLabel={t('Link copied', 'คัดลอกแล้ว')} errorLabel={t('Copy failed', 'คัดลอกไม่ได้')} onCopy={() => setCopies(n => n + 1)} />}
      <Button type="button" variant="ghost" onClick={() => setShowCopy(value => !value)}>Toggle copy</Button>
      <Button type="button" variant="outline" onClick={() => button.current?.focus()}>Focus save</Button>
      <Button variant="outline" asChild><a href="#destination">Link action</a></Button>
    </div>
    <p data-testid="copies">{copies}</p>
    <fieldset disabled><legend>Disabled form</legend><Button data-testid="inherited-disabled">Unavailable action</Button><SegmentedControl label="Disabled choices" value="one" onValueChange={() => { throw new Error('Disabled fieldset dispatched') }} options={[{ value: 'one', label: 'One' }, { value: 'two', label: 'Two' }]} /></fieldset>
    <div id="destination" />
  </main>
}
createRoot(document.getElementById('root')!).render(<Fixture />)
