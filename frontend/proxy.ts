import { NextResponse } from "next/server";

/**
 * Edge proxy (Next.js 16 successor to `middleware.ts`).
 *
 * Phase 7 will gate `/dashboard/**` on the Supabase Auth session and
 * redirect unauthenticated visitors to `/login`. Until then it is a
 * pass-through so routing behaviour is stable from day one.
 */
export function proxy() {
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
