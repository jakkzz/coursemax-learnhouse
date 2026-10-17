'use client'

import { Button } from '@/extensions/route66/adapters/ui'
import { type CoursePlanning, type PlanningOption } from './model'
import CalendarDates from './CalendarDates'
import styles from './calendar.module.css'

export default function CourseDatesForm({ value, options, th, onChange }: { value: CoursePlanning; options: PlanningOption[]; th: boolean; onChange: (value: CoursePlanning) => void }) {
  const t = (en: string, thai: string) => th ? thai : en
  const selected = options.find(o => o.program === value.program)
  function exception(index: number, changes: Partial<CoursePlanning['closures'][number]>) {
    onChange({ ...value, closures: value.closures.map((row, i) => i === index ? { ...row, ...changes } : row) })
  }
  return <section className="mt-4" aria-label={t('Course teaching dates', 'วันสอนของรายวิชา')}>
    <p className={styles.muted}>{t('This published calendar is available. It lists academic dates rather than teaching weeks. Review the proposed course period below; these course-only weeks do not alter the school calendar.', 'ใช้ปฏิทินที่เผยแพร่นี้ได้ เอกสารระบุกำหนดการศึกษาแต่ไม่ได้ระบุสัปดาห์สอน โปรดตรวจสอบช่วงวันสอนที่เสนอด้านล่าง สัปดาห์ที่วางแผนสำหรับรายวิชานี้ไม่เปลี่ยนปฏิทินส่วนกลาง')}</p>
    <div className={`${styles.fields} mt-4`}>
      <label>{t('Semester program', 'รูปแบบการศึกษาของภาคเรียน')}<select aria-label={t('Semester program', 'รูปแบบการศึกษาของภาคเรียน')} value={value.program} onChange={e => { const o = options.find(o => o.program === e.target.value); onChange({ ...value, program: e.target.value, starts_on: o?.starts_on ?? '', ends_on: o?.ends_on ?? '', closures: [] }) }}><option value="">{t('Choose your program', 'เลือกรูปแบบการศึกษา')}</option>{value.program && !selected && <option>{value.program}</option>}{options.map(o => <option key={o.program}>{o.program}</option>)}</select></label>
      <label>{t('First course week starts', 'วันเริ่มสัปดาห์แรกของรายวิชา')}<input type="date" value={value.starts_on} onChange={e => onChange({ ...value, starts_on: e.target.value })} /></label>
      <label>{t('Last teaching date', 'วันสอนสุดท้าย')}<input type="date" value={value.ends_on} onChange={e => onChange({ ...value, ends_on: e.target.value })} /></label>
    </div>
    <p className={`${styles.muted} mt-3`}>{t('The suggested end is before the first final-exam or closing date for this program. Adjust it for your course. Weeks count from your chosen start; no odd/even rotation or unlisted holiday is assumed.', 'วันสิ้นสุดที่เสนออยู่ก่อนวันเริ่มสอบปลายภาคหรือวันปิดภาคของรูปแบบการศึกษาที่เลือก โปรดปรับให้ตรงกับรายวิชา นับสัปดาห์จากวันเริ่มที่เลือก โดยไม่สมมติสัปดาห์คู่คี่หรือวันหยุดที่เอกสารไม่ได้ระบุ')}</p>
    {selected && <details className="mt-4"><summary className="min-h-11 cursor-pointer">{t('Review published semester dates', 'ดูกำหนดการศึกษาที่เผยแพร่')}</summary><CalendarDates events={selected.events} th={th} /></details>}
    <details className="mt-4"><summary className="min-h-11 cursor-pointer">{t('Course holidays and make-ups', 'วันงดสอนและวันชดเชยของรายวิชา')} ({value.closures.length})</summary>
      <p className={styles.muted}>{t('Add only dates you have checked. These exceptions affect this class, not other courses.', 'เพิ่มเฉพาะวันที่ตรวจสอบแล้ว ข้อยกเว้นเหล่านี้ใช้กับกลุ่มเรียนนี้ ไม่เปลี่ยนรายวิชาอื่น')}</p>
      {value.closures.map((row, i) => <fieldset key={i} className="mt-4 border-t border-neutral-200 pt-4"><legend>{t('Exception', 'ข้อยกเว้น')} {i + 1}</legend><div className={styles.fields}>
        <label>{t('No-class date', 'วันงดสอน')}<input type="date" value={row.affected_on} onChange={e => exception(i, { affected_on: e.target.value })} /></label>
        <label>{t('Make-up date (optional)', 'วันชดเชย ถ้ามี')}<input type="date" value={row.makeup_on ?? ''} onChange={e => exception(i, { makeup_on: e.target.value || null })} /></label>
        <label>{t('Reason', 'เหตุผล')}<input maxLength={500} value={row.note} onChange={e => exception(i, { note: e.target.value })} /></label>
      </div><Button variant="ghost" className="min-h-11 mt-2" onClick={() => onChange({ ...value, closures: value.closures.filter((_, n) => n !== i) })}>{t('Remove exception', 'นำข้อยกเว้นออก')} {i + 1}</Button></fieldset>)}
      <Button variant="outline" className="min-h-11 mt-3" onClick={() => onChange({ ...value, closures: [...value.closures, { affected_on: '', makeup_on: null, note: '' }] })}>{t('Add course exception', 'เพิ่มวันงดสอนของรายวิชา')}</Button>
    </details>
  </section>
}
