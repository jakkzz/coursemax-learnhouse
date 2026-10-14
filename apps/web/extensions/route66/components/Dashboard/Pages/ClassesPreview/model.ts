export type Locale = 'en' | 'th'
export type DemoRole = 'teacher' | 'admin' | 'student'
export type Name = Record<Locale, string>
export type Person = {
  id: string; name: Name; kind: 'student' | 'teacher'; number?: string
  account?: string; candidate?: string; verified: boolean
}
export type Course = { id: string; code: string; name: Name; teacher: string }
export type Section = {
  id: string; course: string; label: string; term: 'current' | 'previous'
  schedule: Name; room: string
}
export type Member = { section: string; person: string; status: 'active' | 'withdrawn'; source: 'registrar' | 'manual' }
export type Review = {
  id: string; person: string; section?: string; type: 'verification' | 'discrepancy'
  reason: 'ownership' | 'wrong_account' | 'wrong_name' | 'wrong_number'
  eligible: boolean; status: 'open' | 'more_evidence' | 'approved' | 'rejected'
}
export type DemoState = { people: Person[]; reviews: Review[]; activity: { person: string; action: string; role: DemoRole; note?: string }[] }
const name = (en: string, th: string): Name => ({ en, th })
export const courses: Course[] = [
  { id: 'foundations', code: 'DEMO101', name: name('Transport foundations', 'พื้นฐานการขนส่ง'), teacher: 'teacher-a' },
  { id: 'analysis', code: 'DEMO202', name: name('Logistics analysis', 'การวิเคราะห์โลจิสติกส์'), teacher: 'teacher-a' },
  { id: 'communication', code: 'DEMO303', name: name('Professional communication', 'การสื่อสารในวิชาชีพ'), teacher: 'teacher-b' },
]
export const sections: Section[] = [
  { id: 'f-a', course: 'foundations', label: 'A', term: 'current', schedule: name('Monday · 09:00–12:00', 'จันทร์ · 09:00–12:00'), room: 'DEMO-201' },
  { id: 'f-b', course: 'foundations', label: 'B', term: 'current', schedule: name('Wednesday · 13:00–16:00', 'พุธ · 13:00–16:00'), room: 'DEMO-202' },
  { id: 'a-a', course: 'analysis', label: 'A', term: 'current', schedule: name('Friday · 09:00–12:00', 'ศุกร์ · 09:00–12:00'), room: 'DEMO-301' },
  { id: 'c-a', course: 'communication', label: 'A', term: 'current', schedule: name('Tuesday · 09:00–12:00', 'อังคาร · 09:00–12:00'), room: 'DEMO-401' },
  { id: 'f-old', course: 'foundations', label: 'A', term: 'previous', schedule: name('Monday · 13:00–16:00', 'จันทร์ · 13:00–16:00'), room: 'DEMO-201' },
]
export const members: Member[] = [
  { section: 'f-a', person: 'student-a', status: 'active', source: 'registrar' },
  { section: 'f-a', person: 'student-b', status: 'active', source: 'registrar' },
  { section: 'f-a', person: 'student-c', status: 'active', source: 'registrar' },
  { section: 'f-a', person: 'student-d', status: 'active', source: 'registrar' },
  { section: 'f-a', person: 'manual', status: 'active', source: 'manual' },
  { section: 'f-a', person: 'student-e', status: 'withdrawn', source: 'registrar' },
  { section: 'f-b', person: 'student-b', status: 'active', source: 'registrar' },
  { section: 'f-b', person: 'student-d', status: 'active', source: 'registrar' },
  { section: 'a-a', person: 'student-a', status: 'active', source: 'registrar' },
  { section: 'a-a', person: 'student-e', status: 'withdrawn', source: 'registrar' },
  { section: 'c-a', person: 'student-c', status: 'active', source: 'registrar' },
  { section: 'f-old', person: 'student-e', status: 'active', source: 'registrar' },
]
export const initialState = (): DemoState => ({
  people: [
    { id: 'student-a', name: name('Demo Student A', 'นักศึกษาตัวอย่าง ก'), kind: 'student', number: '9999000001', account: 'Demo learner A', verified: true },
    { id: 'student-b', name: name('Demo Student B', 'นักศึกษาตัวอย่าง ข'), kind: 'student', number: '9999000002', candidate: 'Demo learner B', verified: false },
    { id: 'student-c', name: name('Demo Student C', 'นักศึกษาตัวอย่าง ค'), kind: 'student', number: '9999000003', candidate: 'Demo conflicting account', verified: false },
    { id: 'student-d', name: name('Demo Student D', 'นักศึกษาตัวอย่าง ง'), kind: 'student', number: '9999000004', candidate: 'Demo learner D', verified: false },
    { id: 'student-e', name: name('Demo Student E', 'นักศึกษาตัวอย่าง จ'), kind: 'student', number: '9999000005', account: 'Demo learner E', verified: true },
    { id: 'manual', name: name('Demo manual member', 'สมาชิกที่เพิ่มเองตัวอย่าง'), kind: 'student', account: 'Demo manual account', verified: false },
    { id: 'teacher-a', name: name('Demo Teacher A', 'ผู้สอนตัวอย่าง ก'), kind: 'teacher', number: 'DEMO-T01', candidate: 'Demo teacher account A', verified: false },
    { id: 'teacher-b', name: name('Demo Teacher B', 'ผู้สอนตัวอย่าง ข'), kind: 'teacher', number: 'DEMO-T02', candidate: 'Demo teacher account B', verified: false },
  ],
  reviews: [
    { id: 'initial-student-conflict', person: 'student-c', type: 'verification', reason: 'wrong_number', eligible: false, status: 'open', section: 'f-a' },
    { id: 'initial-teacher-conflict', person: 'teacher-b', type: 'verification', reason: 'wrong_name', eligible: false, status: 'open' },
  ],
  activity: [],
})
export const isPending = (review: Review) => review.status === 'open' || review.status === 'more_evidence'
export const hasReview = (state: DemoState, person: string) => state.reviews.some(r => r.person === person && isPending(r))
export const ownPerson = (role: DemoRole) => role === 'student' ? 'student-d' : 'teacher-a'
export const visibleCourses = (role: DemoRole) => role === 'student' ? [] : courses.filter(c => role === 'admin' || c.teacher === 'teacher-a')
export const canViewSection = (role: DemoRole, sectionId: string) => sections.some(s => s.id === sectionId && visibleCourses(role).some(c => c.id === s.course))
export const rosterFor = (sectionId: string) => members.filter(m => m.section === sectionId)
export type DemoAction =
  | { type: 'flag'; role: DemoRole; person: string; section: string; reason: Review['reason'] }
  | { type: 'verify'; role: DemoRole; person: string; confirmed: boolean }
  | { type: 'decide'; role: DemoRole; review: string; decision: 'approve' | 'reject' | 'more_evidence'; confirmed: boolean; reason: string }
export function transition(state: DemoState, action: DemoAction): DemoState {
  if (action.type === 'flag') {
    if (action.role !== 'teacher' || !canViewSection(action.role, action.section) || !rosterFor(action.section).some(m => m.person === action.person) || hasReview(state, action.person)) return state
    return { ...state, reviews: [...state.reviews, { id: `flag-${action.person}-${state.reviews.length}`, person: action.person, section: action.section, type: 'discrepancy', reason: action.reason, eligible: true, status: 'open' }], activity: [...state.activity, { person: action.person, action: 'flagged', role: action.role }] }
  }
  if (action.type === 'verify') {
    const person = state.people.find(p => p.id === action.person)
    if (action.role === 'admin' || action.person !== ownPerson(action.role) || !person?.number || person.verified || !action.confirmed || hasReview(state, action.person)) return state
    return { ...state, reviews: [...state.reviews, { id: `verify-${action.person}-${state.reviews.length}`, person: action.person, type: 'verification', reason: 'ownership', eligible: true, status: 'open' }], activity: [...state.activity, { person: action.person, action: 'requested', role: action.role }] }
  }
  const review = state.reviews.find(r => r.id === action.review)
  if (action.role !== 'admin' || !review || !isPending(review) || !action.reason.trim() || (action.decision === 'approve' && (!review.eligible || review.status === 'more_evidence' || !action.confirmed))) return state
  const status = action.decision === 'approve' ? 'approved' : action.decision === 'reject' ? 'rejected' : 'more_evidence'
  return {
    people: state.people.map(p => p.id === review.person && status === 'approved' && review.type === 'verification' ? { ...p, verified: true, account: p.candidate } : p),
    reviews: state.reviews.map(r => r.id === review.id ? { ...r, status } : r),
    activity: [...state.activity, { person: review.person, action: status, role: action.role, note: action.reason.trim() }],
  }
}
