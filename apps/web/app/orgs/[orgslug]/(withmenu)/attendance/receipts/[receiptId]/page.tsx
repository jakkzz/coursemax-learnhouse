import GeneralWrapperStyled from '@components/Objects/StyledElements/Wrappers/GeneralWrapper'
import AttendanceCheckin from '@components/Objects/Classes/AttendanceCheckin'

export default async function AttendanceReceiptPage({params}:{params:Promise<{receiptId:string}>}) {
 const {receiptId}=await params
 return <GeneralWrapperStyled><AttendanceCheckin receiptId={receiptId}/></GeneralWrapperStyled>
}
