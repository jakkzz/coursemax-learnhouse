import { GeneralWrapperStyled } from '@/extensions/route66/adapters/ui'
import AttendanceCheckin from '@/extensions/route66/components/Objects/Classes/AttendanceCheckin'

export default async function AttendanceReceiptPage({params}:{params:Promise<{receiptId:string}>}) {
 const {receiptId}=await params
 return <GeneralWrapperStyled><AttendanceCheckin receiptId={receiptId}/></GeneralWrapperStyled>
}
