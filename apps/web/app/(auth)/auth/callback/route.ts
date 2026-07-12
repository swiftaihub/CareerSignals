import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { DEMO_TOKEN_COOKIE } from "@/lib/auth";
import {
  createRecoveryIntent,
  RECOVERY_INTENT_COOKIE_MAX_AGE_SECONDS,
  RECOVERY_INTENT_COOKIE_NAME,
  recoveryRedirectPath,
  trustedSiteOrigin
} from "@/lib/password-recovery";
import {
  clearRecoveryCookies,
  getRecoveryIntentSecret
} from "@/lib/password-recovery-server";
import { exchangeRecoveryCode } from "@/lib/recovery-callback";
import { createWritableRecoveryClient } from "@/lib/supabase/recovery-server";

export async function GET(request: NextRequest) {
  let siteOrigin: string;
  try {
    siteOrigin = trustedSiteOrigin(
      process.env.NEXT_PUBLIC_SITE_URL,
      process.env.NODE_ENV
    );
  } catch {
    return NextResponse.json(
      { error: "Password recovery is not configured." },
      { status: 503, headers: noStoreHeaders() }
    );
  }

  const recoveryClient = await createWritableRecoveryClient();
  const result = await exchangeRecoveryCode(
    request.nextUrl.searchParams.get("code"),
    (code) => recoveryClient.auth.exchangeCodeForSession(code)
  );
  const secret = getRecoveryIntentSecret();
  if (!result.ok || !secret) {
    try {
      await recoveryClient.auth.signOut({ scope: "local" });
    } catch {
      // Explicit cookie cleanup below removes partial recovery state.
    }
    await clearRecoveryCookies();
    return recoveryErrorResponse(siteOrigin);
  }

  const cookieStore = await cookies();
  cookieStore.delete(DEMO_TOKEN_COOKIE);
  cookieStore.set(
    RECOVERY_INTENT_COOKIE_NAME,
    createRecoveryIntent(result.value.identity, secret),
    {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: RECOVERY_INTENT_COOKIE_MAX_AGE_SECONDS
    }
  );

  const destination = recoveryRedirectPath(
    request.nextUrl.searchParams.get("next")
  );
  const response = NextResponse.redirect(new URL(destination, siteOrigin), 303);
  applyNoStoreHeaders(response);
  return response;
}

function recoveryErrorResponse(siteOrigin: string) {
  const destination = new URL("/forgot-password", siteOrigin);
  destination.searchParams.set("recovery_error", "invalid_or_expired");
  const response = NextResponse.redirect(destination, 303);
  applyNoStoreHeaders(response);
  return response;
}

function noStoreHeaders() {
  return {
    "Cache-Control": "private, no-store, max-age=0",
    Pragma: "no-cache",
    "Referrer-Policy": "no-referrer"
  };
}

function applyNoStoreHeaders(response: NextResponse) {
  Object.entries(noStoreHeaders()).forEach(([name, value]) => {
    response.headers.set(name, value);
  });
}
