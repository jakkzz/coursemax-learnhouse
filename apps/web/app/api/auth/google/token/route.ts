import { NextResponse } from 'next/server'

// Provider codes/tokens never pass through the retired browser-owned bridge.
export function POST() {
  return NextResponse.json({ error: 'Restart Google sign-in from this site' },
    { status: 410, headers: { 'Cache-Control': 'no-store' } })
}
export const GET = POST
