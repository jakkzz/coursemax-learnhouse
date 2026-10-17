export type RegistrarClass = {
  registry_course_id: string
  course_code: string
  title: string
  section: string
  teaching_pattern?: 'even_onsite'
  credits?: string
  meetings: { day: string; start_time: string; end_time: string; details: string }[]
}
export type RegistrarTimetable = { academic_year: number; semester: number; fetched_at: string; classes: RegistrarClass[] }
export type RegistrarClassContext = Omit<RegistrarTimetable, 'classes'> & { classRow: RegistrarClass; returnFocusId?: string; teacher_name?: string }
export type AcademicClassLink = {
  id: number; registry_course_id: string | null; academic_year: number; semester: number; section: string
  manageable: boolean; course_uuid: string; course_available: boolean
}

// Native course routes take the unprefixed UUID; getCourseMetadata adds course_.
// Encode a single route segment, never infer native identity from a course name.
export function nativeCoursePath(uuid: string): string {
  return `/course/${encodeURIComponent(uuid.replace(/^course_/, ''))}`
}

// Navigation only. The destination's native REST authorization remains authoritative.
export function linkedTeachingClass(context: RegistrarClassContext, classes: AcademicClassLink[]): AcademicClassLink | null {
  const matches = classes.filter(c => Boolean(c.course_uuid) && typeof c.registry_course_id === 'string' && c.registry_course_id !== '' &&
    c.registry_course_id === context.classRow.registry_course_id && c.academic_year === context.academic_year &&
    c.semester === context.semester && c.section === context.classRow.section)
  const match = matches.length === 1 ? matches[0] : null
  return match && Number.isInteger(match.id) && match.id > 0 && match.manageable === true ? match : null
}
