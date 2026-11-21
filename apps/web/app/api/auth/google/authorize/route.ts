import { NextResponse } from 'next/server'

export function POST() {
  return NextResponse.json({ error: 'Use the server-owned Google start endpoint' },
    { status: 410, headers: { 'Cache-Control': 'no-store' } })
}
export const GET = POST
