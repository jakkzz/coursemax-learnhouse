import { getServerSession } from '@/extensions/route66/adapters/server'
import { redirect } from 'next/navigation'
import { GeneralWrapperStyled } from '@/extensions/route66/adapters/ui'
import ClassesWorkspace from '@/extensions/route66/components/Objects/Classes/ClassesWorkspace'

export default async function ClassesPage() {
 if (!await getServerSession()) redirect('/login?next=/classes')
 return <GeneralWrapperStyled><ClassesWorkspace /></GeneralWrapperStyled>
}
