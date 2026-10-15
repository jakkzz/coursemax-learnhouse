export type SectionId = 'P1' | 'P2'
export type Localized = { en: string; th: string }
export const sections = [
  { id: 'P1' as const, meetings: [{ day: 0, start: '09:00', end: '11:00', room: 'Demo A' }, { day: 2, start: '13:00', end: '15:00', room: 'Demo Lab' }] },
  { id: 'P2' as const, meetings: [{ day: 1, start: '09:00', end: '11:00', room: 'Demo B' }, { day: 3, start: '13:00', end: '15:00', room: 'Demo Lab' }] },
]
export const weekdays = [
  { en: 'Monday', th: 'จันทร์' }, { en: 'Tuesday', th: 'อังคาร' }, { en: 'Wednesday', th: 'พุธ' },
  { en: 'Thursday', th: 'พฤหัสบดี' }, { en: 'Friday', th: 'ศุกร์' },
]
export const topics: Localized[] = [
  { en: 'Understand a learning problem', th: 'สำรวจโจทย์การเรียนรู้' },
  { en: 'Observe and gather evidence', th: 'สังเกตและรวบรวมหลักฐาน' },
  { en: 'Define learning outcomes', th: 'กำหนดผลลัพธ์การเรียนรู้' },
  { en: 'Design a learning activity', th: 'ออกแบบกิจกรรมการเรียนรู้' },
  { en: 'Build a small prototype', th: 'สร้างต้นแบบขนาดเล็ก' },
  { en: 'Test and collect feedback', th: 'ทดลองและรับข้อเสนอแนะ' },
  { en: 'Improve the activity', th: 'ปรับปรุงกิจกรรม' },
  { en: 'Present and reflect', th: 'นำเสนอและสะท้อนการเรียนรู้' },
]
export function canPreviewTeaching(staff: unknown, manageable: unknown) { return staff === true || manageable === true }
export function topicForWeek(week: number): Localized {
  if (!Number.isInteger(week) || week < 1 || week > 16) throw new Error('Invalid example week')
  return topics[Math.floor((week - 1) / 2)]
}
export type ProposalSession = {
  id: string; section: SectionId; week: number; date: string; start: string; end: string; room: string
  state: 'scheduled' | 'no_class' | 'makeup'; replaces?: string; delivery: 'campus' | 'online'
}
export function buildProposal(sectionId: SectionId, includeHoliday: boolean): ProposalSession[] {
  const section = sections.find(s => s.id === sectionId)
  if (!section) throw new Error('Invalid example section')
  const sessions: ProposalSession[] = []
  for (let week = 1; week <= 16; week++) for (const [index, slot] of section.meetings.entries()) {
    const date = new Date(Date.UTC(2027, 5, 7 + (week - 1) * 7 + slot.day)).toISOString().slice(0, 10)
    const id = `demo-${sectionId}-${week}-${index}`
    const closed = includeHoliday && date === '2027-06-28'
    const row: ProposalSession = { ...slot, id, section: sectionId, week, date, state: closed ? 'no_class' : 'scheduled', delivery: week % 2 === 0 ? 'online' : 'campus' }
    sessions.push(row)
    if (closed) sessions.push({ ...row, id: `${id}-makeup`, date: '2027-07-02', state: 'makeup', replaces: id })
  }
  return sessions.sort((a, b) => `${a.date} ${a.start}`.localeCompare(`${b.date} ${b.start}`))
}
export type DemoPerson = {
  id: string; ordinal: number; source: 'registry' | 'manual'; status: 'active' | 'withdrawn'
  account: 'linked' | 'unlinked' | 'review'; missing: number
}
export function demoRoster(section: SectionId): DemoPerson[] {
  return Array.from({ length: 6 }, (_, i) => ({
    id: `DEMO-${section}-${String(i + 1).padStart(2, '0')}`, ordinal: i + 1,
    source: i === 3 ? 'manual' : 'registry', status: i === 5 ? 'withdrawn' : 'active',
    account: i === 2 ? 'review' : i % 2 === 0 || i === 3 ? 'linked' : 'unlinked', missing: 0,
  }))
}
export function applySampleRoster(people: DemoPerson[], section: SectionId): DemoPerson[] {
  if (people.some(p => p.id === `DEMO-${section}-07`)) return people.map(p => ({ ...p }))
  return [
    ...people.map(p => p.id === `DEMO-${section}-05` ? { ...p, missing: 1 } : { ...p }),
    ...[7, 8].map(ordinal => ({ id: `DEMO-${section}-0${ordinal}`, ordinal, source: 'registry' as const, status: 'active' as const, account: 'unlinked' as const, missing: 0 })),
  ]
}
export function filterRoster(people: DemoPerson[], query: string, membership: string, account: string) {
  const q = query.trim().toLowerCase()
  return people.filter(p => p.id.toLowerCase().includes(q) && (membership === 'all' || p.status === membership) && (account === 'all' || p.account === account))
}
