import type { AttendanceText } from './attendance-client'

export function attendanceTime(value:string|null, language:string, zone='Asia/Bangkok') {
 if (!value) return '—'
 const formatted=new Intl.DateTimeFormat(language.startsWith('th')?'th-TH':'en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:zone}).format(new Date(value))
 return language.startsWith('th')?formatted.replace(/:/g,'.'):formatted
}

export function attendanceStatus(value:string,t:AttendanceText) {
 const labels:Record<string,string>={present:t.present,late:t.late,absent:t.absent,excused:t.excused,upcoming:t.upcoming,unrecorded:t.unrecorded,unknown:t.unknown,not_eligible:t.notEligible,no_class:t.noClass,reset:t.reset}
 return labels[value] || value
}

export function attendanceMembership(value:string,t:AttendanceText) {
 return value==='active'?t.active:value==='withdrawn'?t.withdrawn:value
}
