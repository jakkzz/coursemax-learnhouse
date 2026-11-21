import { getServerSession } from '@/extensions/route66/adapters/server'
import { redirect } from 'next/navigation'
import { GeneralWrapperStyled } from '@/extensions/route66/adapters/ui'
import AttendanceWorkspace from '@/extensions/route66/components/Objects/Classes/AttendanceWorkspace'

export default async function AttendancePage({searchParams}:{searchParams:Promise<{class?:string}>}) {
 const query=await searchParams
 const classId=query.class&&/^[1-9][0-9]*$/.test(query.class)&&Number.isSafeInteger(Number(query.class))?Number(query.class):null
 if(!await getServerSession()) redirect('/login?next='+encodeURIComponent('/attendance'+(classId?'?class='+classId:'')))
 return <GeneralWrapperStyled><AttendanceWorkspace classId={classId}/></GeneralWrapperStyled>
}
