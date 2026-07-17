import { NextResponse, type NextRequest } from "next/server";

import { buildAppUrl } from "@/lib/app-path";
import { clearAppCookie, clearLegacyRootCookie } from "@/lib/cookie-policy";
import { DEMO_TOKEN_COOKIE_NAMES } from "@/lib/demo-cookie";
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
    DEMO_TOKEN_COOKIE_NAMES.includes(name as typeof DEMO_TOKEN_COOKIE_NAMES[number])
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
  const cookieNames = new Set<string>([
    ...DEMO_TOKEN_COOKIE_NAMES,
    RECOVERY_INTENT_COOKIE_NAME
  ]);
  request.cookies.getAll().forEach(({ name }) => {
    if (isLogoutCookie(name, authCookieBaseName)) {
      cookieNames.add(name);
    }
  });
  cookieNames.forEach((name) => clearAppCookie(response.cookies, name));
  cookieNames.forEach((name) => clearLegacyRootCookie(response, name));
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  return response;
}
