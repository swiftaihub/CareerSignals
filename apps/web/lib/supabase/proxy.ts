import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import {
  extractSessionId,
  isRecoveryAuthCookieName,
  isRecoveryAuthSessionCookieName,
  isRecoveryIntentSecretConfigured,
  isRecoveryRouteAllowed,
  RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS,
  RECOVERY_AUTH_COOKIE_NAME,
  RECOVERY_INTENT_COOKIE_NAME,
  trustedSiteOrigin,
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
    return NextResponse.next({ request });
  }

  if (hasRecoverySession || hasRecoveryIntent) {
    return updateRecoverySession(request, url, publishableKey);
  }

  let response = NextResponse.next({ request });
  const supabase = createServerClient(url, publishableKey, {
    cookieOptions: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/"
    },
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, options);
        });
      }
    }
  });

  // Validate and refresh the ordinary session before layouts inspect it.
  await supabase.auth.getUser();
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
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
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
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: "lax",
            path: "/",
            maxAge: !value || options.maxAge === 0
              ? 0
              : RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS
          });
        });
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
  const validIntent = Boolean(
    !userError
    && user
    && session
    && sessionId
    && intent
    && validSecret
    && verifyRecoveryIntent(
      intent,
      { userId: user.id, sessionId },
      secret!
    )
  );

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
  if (isRecoveryRouteAllowed(request.nextUrl.pathname)) return response;
  return recoveryRedirectResponse(response, "/reset-password");
}

function clearRecoveryResponseCookies(request: NextRequest, response: NextResponse) {
  request.cookies.getAll().forEach(({ name }) => {
    if (
      isRecoveryAuthCookieName(name)
      || name === RECOVERY_INTENT_COOKIE_NAME
    ) {
      response.cookies.set(name, "", {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 0
      });
    }
  });
}

function recoveryRedirectResponse(
  cookieSource: NextResponse,
  pathname: string
) {
  let origin: string;
  try {
    origin = trustedSiteOrigin(
      process.env.NEXT_PUBLIC_SITE_URL,
      process.env.NODE_ENV
    );
  } catch {
    const unavailable = NextResponse.json(
      { error: "Password recovery is not configured." },
      { status: 503 }
    );
    copyResponseCookies(cookieSource, unavailable);
    setNoStoreHeaders(unavailable);
    return unavailable;
  }

  const redirect = NextResponse.redirect(new URL(pathname, origin), 303);
  copyResponseCookies(cookieSource, redirect);
  setNoStoreHeaders(redirect);
  return redirect;
}

function copyResponseCookies(source: NextResponse, destination: NextResponse) {
  source.cookies.getAll().forEach((cookie) => destination.cookies.set(cookie));
}

function setNoStoreHeaders(response: NextResponse) {
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("Referrer-Policy", "no-referrer");
}
