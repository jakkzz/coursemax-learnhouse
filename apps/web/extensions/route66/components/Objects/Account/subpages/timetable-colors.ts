export type WeekdayKey = 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday' | 'unknown'

const weekdays: Readonly<Record<string, WeekdayKey>> = {
  monday: 'monday', mon: 'monday', 'จันทร์': 'monday', 'จ': 'monday',
  tuesday: 'tuesday', tue: 'tuesday', tues: 'tuesday', 'อังคาร': 'tuesday', 'อ': 'tuesday',
  wednesday: 'wednesday', wed: 'wednesday', 'พุธ': 'wednesday', 'พ': 'wednesday',
  thursday: 'thursday', thu: 'thursday', thurs: 'thursday', 'พฤหัสบดี': 'thursday', 'พฤ': 'thursday',
  friday: 'friday', fri: 'friday', 'ศุกร์': 'friday', 'ศ': 'friday',
  saturday: 'saturday', sat: 'saturday', 'เสาร์': 'saturday', 'ส': 'saturday',
  sunday: 'sunday', sun: 'sunday', 'อาทิตย์': 'sunday', 'อา': 'sunday',
}

// Presentation category only; never rewrite the authoritative meeting label.
export function weekdayKey(day: string): WeekdayKey {
  const key = day.trim().toLocaleLowerCase().replace(/^วัน/, '').replace(/\.$/, '')
  return Object.hasOwn(weekdays, key) ? weekdays[key] : 'unknown'
}
