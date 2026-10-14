import { getServerSession } from '@/lib/auth/server'
import { redirect } from 'next/navigation'
import GeneralWrapperStyled from '@components/Objects/StyledElements/Wrappers/GeneralWrapper'
import SchoolIdentity from '@components/Objects/Account/subpages/SchoolIdentity'

export default async function ClassesPage() {
 if (!await getServerSession()) redirect('/login?next=/classes')
 return <GeneralWrapperStyled><div className="py-6"><SchoolIdentity classes /></div></GeneralWrapperStyled>
}
