export type RegistrarTerm = { year: number; semester: number }
export type StaffProjection = {
  school_kind?: string | null
  needs_google_signin?: boolean
  directory_identity?: { officer_id: string; name_th: string; name_en: string } | null
}

// Discovery only. The own-only timetable API remains the authorization authority.
export function confirmedStaff(status: StaffProjection | null): boolean {
  return status?.school_kind === 'staff' && !!status.directory_identity && !status.needs_google_signin
}

export function readSavedTerm(raw: string | null, currentYear: number): RegistrarTerm | null {
  if (!raw) return null
  try {
    const value = JSON.parse(raw)
    return value && Number.isInteger(value.year) && Math.abs(value.year - currentYear) <= 1
      && Number.isInteger(value.semester) && [1, 2, 3].includes(value.semester)
      ? { year: value.year, semester: value.semester } : null
  } catch { return null }
}

export function timetableYears(currentYear: number, displayedYear: number): number[] {
  return [...new Set([currentYear - 1, currentYear, currentYear + 1, displayedYear])].sort((a, b) => a - b)
}

export function filterTimetable<T extends { course_code: string; title: string; section: string; meetings: { day: string; details: string }[] }>(classes: T[], query: string): T[] {
  const needle = query.trim().toLocaleLowerCase()
  return classes.filter(c => [c.course_code, c.title, c.section, ...c.meetings.flatMap(m => [m.day, m.details])].join(' ').toLocaleLowerCase().includes(needle))
}
