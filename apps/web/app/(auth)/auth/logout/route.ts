import { NextResponse, type NextRequest } from "next/server";

import { buildAppUrl } from "@/lib/app-path";
import { DEMO_TOKEN_COOKIE } from "@/lib/auth";
import { clearLegacyRootCookie } from "@/lib/cookie-policy";
import { clearAuthenticationSession } from "@/lib/logout";
import { isRecoveryAuthCookieName, RECOVERY_INTENT_COOKIE_NAME } from "@/lib/password-recovery";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function ordinaryAuthCookieBaseName() {
  try {
    const projectRef = new URL(process.env.NEXT_PUBLIC_SUPABASE_URL || "").hostname.split(".")[0];
    return projectRef && /^[A-Za-z0-9_-]+$/.test(projectRef)
      ? `sb-${projectRef}-auth-token`
      : null;
  } catch {
    return null;
  }
}

function isLogoutCookie(name: string, authCookieBaseName: string | null) {
  if (
    name === DEMO_TOKEN_COOKIE
    || name === RECOVERY_INTENT_COOKIE_NAME
    || isRecoveryAuthCookieName(name)
  ) return true;
  if (!authCookieBaseName) return false;
  return name === authCookieBaseName
    || name === `${authCookieBaseName}-code-verifier`
    || new RegExp(`^${authCookieBaseName}(?:-code-verifier)?\\.\\d+$`).test(name);
}

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin) {
    return NextResponse.json(
      { detail: "Cross-origin logout is not allowed.", error_code: "CSRF_CHECK_FAILED" },
      { status: 403 }
    );
  }

  await clearAuthenticationSession();
  const response = NextResponse.redirect(buildAppUrl("/"), 303);
  const authCookieBaseName = ordinaryAuthCookieBaseName();
  request.cookies.getAll().forEach(({ name }) => {
    if (isLogoutCookie(name, authCookieBaseName)) {
      clearLegacyRootCookie(response, name);
    }
  });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  return response;
}
