'use client'
import { useTranslation } from 'react-i18next'

type Profile={student_number:string;full_name_th:string;faculty:string;program:string}
export default function StudentRegistrarDetails({profile,matchStatus}:{profile:Profile|null;matchStatus:string|null}){
 const {i18n}=useTranslation(),th=i18n.language.startsWith('th')
 if(matchStatus==='conflict')return <p role="status" className="max-w-prose text-sm leading-relaxed text-amber-900">{th?'ตัวตนนักศึกษาต้องให้ผู้ดูแลตรวจสอบ โปรดให้ผู้สอนแจ้งตรวจสอบรายชื่อที่มีข้อขัดแย้ง บัญชีและประวัติเดิมจะไม่ถูกย้ายหรือรวมโดยอัตโนมัติ':'Your student identity needs administrator review. Ask your teacher to flag the conflicting roster entry. Existing accounts and history are not transferred or merged automatically.'}</p>
 if(!profile||matchStatus!=='matched')return null
 return <div className="space-y-3"><p role="status" className="text-sm font-medium text-green-800">{th?'จับคู่กับรายชื่อจากทะเบียนแล้ว':'Matched to the official class roster'}</p><dl className="grid gap-4 sm:grid-cols-2">{[[th?'ชื่อและคำนำหน้า':'Name and title',profile.full_name_th],[th?'คณะ':'Faculty',profile.faculty],[th?'สาขาวิชา':'Program',profile.program]].map(([label,value])=><div key={label}><dt className="text-xs font-medium text-neutral-600">{label}</dt><dd className="mt-1 break-words text-sm">{value}</dd></div>)}</dl><p className="max-w-prose text-sm text-neutral-600">{th?'ข้อมูลมาจากรายชื่อชั้นเรียนในทะเบียน โดยไม่เปลี่ยนชื่อที่คุณเลือกใช้ในบัญชี Google หรือชื่อโปรไฟล์ของคุณ':'These details come from the class roster. Your chosen Google and profile names are unchanged.'}</p></div>
}
