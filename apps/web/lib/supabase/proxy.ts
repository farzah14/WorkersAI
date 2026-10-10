import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { requiresAuth } from "@/lib/auth/routes";

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });
  const projectRef = process.env.NEXT_PUBLIC_SUPABASE_URL
    ? new URL(process.env.NEXT_PUBLIC_SUPABASE_URL).hostname.match(/^([a-z0-9_-]+)\.supabase\.co$/)?.[1] ?? null
    : null;

  if (projectRef) {
    const expectedPrefix = `sb-${projectRef}-`;
    for (const cookie of request.cookies.getAll()) {
      if (cookie.name.startsWith("sb-") && !cookie.name.startsWith(expectedPrefix)) {
        response.cookies.delete(cookie.name);
      }
    }
  }

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    (process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY)!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          if (projectRef) {
            const expectedPrefix = `sb-${projectRef}-`;
            for (const cookie of request.cookies.getAll()) {
              if (cookie.name.startsWith("sb-") && !cookie.name.startsWith(expectedPrefix)) {
                response.cookies.delete(cookie.name);
              }
            }
          }
          cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    },
  );
  const { data: { user } } = await supabase.auth.getUser();
  if (!user && requiresAuth(request.nextUrl.pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    const redirectResponse = NextResponse.redirect(url);
    response.cookies.getAll().forEach((cookie) => redirectResponse.cookies.set(cookie));
    return redirectResponse;
  }
  return response;
}