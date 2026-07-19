import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { getCookiePath, getSiteOrigin, withBasePath } from "@/lib/app-path";
import {
  clearAppCookie,
  clearLegacyRootCookie,
  secureAppCookieOptions
} from "@/lib/cookie-policy";
import { DEMO_TOKEN_COOKIE_NAMES } from "@/lib/demo-cookie";
import {
  extractSessionId,
  isRecoveryAuthCookieName,
  isRecoveryAuthSessionCookieName,
  isRecoveryIntentSecretConfigured,
  isRecoveryRouteAllowed,
  RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS,
  RECOVERY_AUTH_COOKIE_NAME,
  RECOVERY_INTENT_COOKIE_NAME,
  verifyRecoveryIntent
} from "@/lib/password-recovery";

export async function updateSession(request: NextRequest) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  const hasRecoverySession = request.cookies.getAll().some(({ name }) =>
    isRecoveryAuthSessionCookieName(name)
  );
  const hasRecoveryIntent = request.cookies.has(RECOVERY_INTENT_COOKIE_NAME);
  if (!url || !publishableKey) {
    if (hasRecoverySession || hasRecoveryIntent) {
      const unavailable = NextResponse.json(
        { error: "Password recovery is not configured." },
        { status: 503 }
      );
      clearRecoveryResponseCookies(request, unavailable);
      setNoStoreHeaders(unavailable);
      return unavailable;
    }
    const response = NextResponse.next({ request });
    clearLegacyApplicationCookies(request, response);
    return response;
  }

  if (hasRecoverySession || hasRecoveryIntent) {
    return updateRecoverySession(request, url, publishableKey);
  }

  let response = NextResponse.next({ request });
  const supabase = createServerClient(url, publishableKey, {
    cookieOptions: {
      ...secureAppCookieOptions(),
      path: getCookiePath()
    },
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, {
            ...options,
            ...secureAppCookieOptions(),
            path: getCookiePath()
          });
        });
        cookiesToSet.forEach(({ name }) => clearLegacyRootCookie(response, name));
      }
    }
  });

  // Validate and refresh the ordinary session before layouts inspect it.
  await supabase.auth.getUser();
  clearLegacySupabaseCookies(request, response, url);
  clearLegacyApplicationCookies(request, response);
  return response;
}

async function updateRecoverySession(
  request: NextRequest,
  supabaseUrl: string,
  publishableKey: string
) {
  let response = NextResponse.next({ request });
  const recoveryClient = createServerClient(supabaseUrl, publishableKey, {
    cookieOptions: {
      name: RECOVERY_AUTH_COOKIE_NAME,
      ...secureAppCookieOptions(),
      path: getCookiePath(),
      maxAge: RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS
    },
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, {
            ...options,
            ...secureAppCookieOptions(),
            path: getCookiePath(),
            maxAge: !value || options.maxAge === 0
              ? 0
              : RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS
          });
        });
        cookiesToSet.forEach(({ name }) => clearLegacyRootCookie(response, name));
      }
    }
  });

  const { data: userData, error: userError } = await recoveryClient.auth.getUser();
  const { data: sessionData } = await recoveryClient.auth.getSession();
  const session = sessionData.session;
  const user = userData.user;
  const sessionId = extractSessionId(session?.access_token);
  const intent = request.cookies.get(RECOVERY_INTENT_COOKIE_NAME)?.value;
  const secret = process.env.PASSWORD_RECOVERY_COOKIE_SECRET;
  const validSecret = isRecoveryIntentSecretConfigured(secret);
  let validIntent = false;
  if (
    !userError
    && user
    && session
    && sessionId
    && intent
    && validSecret
  ) {
    validIntent = await verifyRecoveryIntent(
      intent,
      { userId: user.id, sessionId },
      secret
    );
  }

  if (!validIntent) {
    try {
      await recoveryClient.auth.signOut({ scope: "local" });
    } catch {
      // Cookie removal below remains fail-closed.
    }
    clearRecoveryResponseCookies(request, response);
    return recoveryRedirectResponse(response, "/forgot-password?recovery_error=invalid_or_expired");
  }

  setNoStoreHeaders(response);
  clearLegacyApplicationCookies(request, response);
  if (isRecoveryRouteAllowed(request.nextUrl.pathname)) return response;
  return recoveryRedirectResponse(response, "/reset-password");
}

function clearRecoveryResponseCookies(request: NextRequest, response: NextResponse) {
  const names = new Set<string>();
  request.cookies.getAll().forEach(({ name }) => {
    if (
      isRecoveryAuthCookieName(name)
      || name === RECOVERY_INTENT_COOKIE_NAME
    ) {
      names.add(name);
    }
  });
  names.forEach((name) => clearAppCookie(response.cookies, name));
  names.forEach((name) => clearLegacyRootCookie(response, name));
}

function recoveryRedirectResponse(
  cookieSource: NextResponse,
  pathname: string
) {
  let destination: URL;
  try {
    destination = new URL(withBasePath(pathname), getSiteOrigin());
  } catch {
    const unavailable = NextResponse.json(
      { error: "Password recovery is not configured." },
      { status: 503 }
    );
    copyResponseCookies(cookieSource, unavailable);
    setNoStoreHeaders(unavailable);
    return unavailable;
  }

  const redirect = NextResponse.redirect(destination, 303);
  copyResponseCookies(cookieSource, redirect);
  setNoStoreHeaders(redirect);
  return redirect;
}

function clearLegacySupabaseCookies(
  request: NextRequest,
  response: NextResponse,
  supabaseUrl: string
) {
  if (getCookiePath() === "/") return;
  let projectRef: string;
  try {
    projectRef = new URL(supabaseUrl).hostname.split(".")[0] ?? "";
  } catch {
    return;
  }
  if (!projectRef || !/^[A-Za-z0-9_-]+$/.test(projectRef)) return;
  const baseName = `sb-${projectRef}-auth-token`;
  request.cookies.getAll().forEach(({ name }) => {
    if (
      name === baseName
      || name === `${baseName}-code-verifier`
      || new RegExp(`^${baseName}(?:-code-verifier)?\\.\\d+$`).test(name)
    ) {
      clearLegacyRootCookie(response, name);
    }
  });
}

function copyResponseCookies(source: NextResponse, destination: NextResponse) {
  source.headers.getSetCookie().forEach((cookie) => {
    destination.headers.append("Set-Cookie", cookie);
  });
}

function clearLegacyApplicationCookies(request: NextRequest, response: NextResponse) {
  if (getCookiePath() === "/") return;
  request.cookies.getAll().forEach(({ name }) => {
    if (
      DEMO_TOKEN_COOKIE_NAMES.includes(name as typeof DEMO_TOKEN_COOKIE_NAMES[number])
      || name === RECOVERY_INTENT_COOKIE_NAME
      || isRecoveryAuthCookieName(name)
    ) {
      clearLegacyRootCookie(response, name);
    }
  });
}

function setNoStoreHeaders(response: NextResponse) {
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("Referrer-Policy", "no-referrer");
}
