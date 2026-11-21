import { redirect } from 'next/navigation'

/**
 * Compatibility entry point for the retired preview. The institutional classes
 * workspace is the only supported surface; legacy URL state is deliberately ignored.
 */
export default function ClassesPreview() {
  redirect('/classes')
}
