import { getServerSession } from '@/extensions/route66/adapters/server'
import { redirect } from 'next/navigation'
import ClassesAccountLayout from '@/extensions/route66/components/Objects/Classes/ClassesAccountLayout'
import ClassesWorkspace from '@/extensions/route66/components/Objects/Classes/ClassesWorkspace'

export default async function ClassesPage({ params }: { params: Promise<{ orgslug: string }> }) {
 if (!await getServerSession()) redirect('/login?next=/classes')
 const { orgslug } = await params
 return <ClassesAccountLayout orgslug={orgslug}><ClassesWorkspace /></ClassesAccountLayout>
}
