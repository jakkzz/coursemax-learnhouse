import { NextResponse } from 'next/server'

export function POST() {
  return NextResponse.json({ error: 'Google transactions are verified on the server' },
    { status: 410, headers: { 'Cache-Control': 'no-store' } })
}
export const GET = POST
