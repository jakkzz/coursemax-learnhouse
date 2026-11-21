import { redirect } from 'next/navigation'

/** Retained URL delegate for the retired preview. */
export default function ClassesPreviewPage() {
  redirect('/classes')
}
