"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { z } from "zod";

import { buildAppUrl, buildAuthCallbackUrl, getCookiePath } from "@/lib/app-path";
import { DEMO_TOKEN_COOKIE, getCurrentUser } from "@/lib/auth";
import { backendFetch, readBackendError } from "@/lib/backend";
import {
  clearAppCookie,
  secureAppCookieOptions
} from "@/lib/cookie-policy";
import { safeRedirectPath } from "@/lib/navigation";
import { clearAuthenticationSession } from "@/lib/logout";
import {
  requestPasswordReset,
  updateAuthenticatedPassword,
  updateRecoveryPassword
} from "@/lib/password-management";
import {
  changePasswordSchema,
  DEMO_PASSWORD_CHANGE_MESSAGE,
  passwordSchema,
  resetPasswordSchema,
  resetRequestSchema
} from "@/lib/password-policy";
import { RECOVERY_INTENT_COOKIE_NAME } from "@/lib/password-recovery";
import {
  clearRecoveryCookies,
  getRecoveryIntentSecret,
  readRecoverySession
} from "@/lib/password-recovery-server";
import { createWritableRecoveryClient } from "@/lib/supabase/recovery-server";
import { createWritableClient as createClient } from "@/lib/supabase/server";

export interface AuthActionState {
  error?: string;
  errorCode?: string;
  success?: string;
  cooldownUntil?: number;
}

const loginSchema = z.object({
  identifier: z.string().trim().min(1, "Enter your username or email."),
  password: z.string()
});

const registerSchema = z.object({
  username: z.string().trim().min(3).max(32).regex(/^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,31}$/, "Start with a letter or number; then use letters, numbers, dots, dashes, or underscores."),
  email: z.email(),
  password: passwordSchema
});

async function createDemoSession() {
  const response = await backendFetch("/api/auth/demo-session", { method: "POST" });
  if (!response.ok) {
    return { error: await readBackendError(response) };
  }
  const payload = await response.json() as { demo_token: string; expires_at: string };
  const expiresAt = new Date(payload.expires_at);
  const cookieStore = await cookies();
  try {
    // Demo is a deliberate lower-privilege mode. Clear any local Supabase session
    // so an existing authenticated cookie cannot shadow the signed Demo identity.
    const supabase = await createClient();
    await supabase.auth.signOut({ scope: "local" });
    const recoveryClient = await createWritableRecoveryClient();
    await recoveryClient.auth.signOut({ scope: "local" });
    await clearRecoveryCookies();
  } catch {
    // Demo authentication is issued and verified by FastAPI, independently of Supabase.
  }
  cookieStore.set(DEMO_TOKEN_COOKIE, payload.demo_token, {
    ...secureAppCookieOptions(),
    path: getCookiePath(),
    expires: Number.isNaN(expiresAt.getTime()) ? undefined : expiresAt
  });
  return { error: null };
}

export async function loginAction(_state: AuthActionState, formData: FormData): Promise<AuthActionState> {
  const parsed = loginSchema.safeParse({
    identifier: formData.get("identifier"),
    password: formData.get("password")
  });
  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message || "Check your login details." };
  }

  // "demo" is a reserved, lower-privilege identity. Password managers may
  // autofill the password field, but that must not route Demo through the
  // normal Supabase username/password flow.
  if (parsed.data.identifier.toLowerCase() === "demo") {
    const result = await createDemoSession();
    if (result.error) {
      return { error: result.error.detail, errorCode: result.error.error_code };
    }
    redirect(buildAppUrl(safeRedirectPath(formData.get("next"))));
  }

  let response: Response;
  try {
    response = await backendFetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data)
    });
  } catch {
    return { error: "The CareerSignals service is temporarily unavailable.", errorCode: "API_UNREACHABLE" };
  }
  if (!response.ok) {
    const error = await readBackendError(response);
    return { error: error.detail, errorCode: error.error_code };
  }

  const payload = await response.json() as {
    access_token?: string;
    refresh_token?: string;
    session?: { access_token?: string; refresh_token?: string };
  };
  const accessToken = payload.access_token || payload.session?.access_token;
  const refreshToken = payload.refresh_token || payload.session?.refresh_token;
  if (!accessToken || !refreshToken) {
    return { error: "The login response did not include a valid session.", errorCode: "INVALID_SESSION" };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.setSession({ access_token: accessToken, refresh_token: refreshToken });
  if (error) {
    return { error: "Your session could not be established.", errorCode: "INVALID_SESSION" };
  }
  clearAppCookie(await cookies(), DEMO_TOKEN_COOKIE);
  redirect(buildAppUrl(safeRedirectPath(formData.get("next"))));
}

export async function registerAction(_state: AuthActionState, formData: FormData): Promise<AuthActionState> {
  const parsed = registerSchema.safeParse({
    username: formData.get("username"),
    email: formData.get("email"),
    password: formData.get("password")
  });
  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message || "Check your registration details." };
  }

  let response: Response;
  try {
    response = await backendFetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data)
    });
  } catch {
    return { error: "The CareerSignals service is temporarily unavailable.", errorCode: "API_UNREACHABLE" };
  }
  if (!response.ok) {
    const error = await readBackendError(response);
    return { error: error.detail, errorCode: error.error_code };
  }
  redirect(buildAppUrl("/pending?registered=1"));
}

export async function forgotPasswordAction(
  _state: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  const parsed = resetRequestSchema.safeParse({ email: formData.get("email") });
  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message || "Enter a valid email address." };
  }

  let callbackUrl: string;
  try {
    callbackUrl = buildAuthCallbackUrl("/reset-password");
  } catch {
    return { error: "Password recovery is temporarily unavailable." };
  }

  if (!getRecoveryIntentSecret()) {
    return { error: "Password recovery is temporarily unavailable." };
  }

  let recoveryClient: Awaited<ReturnType<typeof createWritableRecoveryClient>>;
  try {
    recoveryClient = await createWritableRecoveryClient();
  } catch {
    return { error: "Password recovery is temporarily unavailable." };
  }
  try {
    await recoveryClient.auth.signOut({ scope: "local" });
  } catch {
    // Stale isolated state is also removed explicitly below.
  }
  await clearRecoveryCookies();

  const result = await requestPasswordReset({
    email: parsed.data.email,
    redirectTo: callbackUrl,
    send: (email, options) => recoveryClient.auth.resetPasswordForEmail(email, options)
  });
  return result.success
    ? { ...result, cooldownUntil: Date.now() + 30_000 }
    : result;
}

export async function resetPasswordAction(
  _state: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  const parsed = resetPasswordSchema.safeParse({
    newPassword: formData.get("newPassword"),
    confirmPassword: formData.get("confirmPassword")
  });
  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message || "Check your new password." };
  }

  let recoveryClient: Awaited<ReturnType<typeof createWritableRecoveryClient>>;
  try {
    recoveryClient = await createWritableRecoveryClient();
  } catch {
    return {
      error: "This password reset session is unavailable. Request a new reset email."
    };
  }
  const recoveryState = await readRecoverySession(recoveryClient);
  if (!recoveryState.valid) {
    try {
      await recoveryClient.auth.signOut({ scope: "local" });
    } catch {
      // Explicit cookie cleanup below is the final local guard.
    }
    await clearRecoveryCookies();
    return {
      error: "This password reset link is invalid or has expired. Request a new reset email."
    };
  }

  const result = await updateRecoveryPassword(parsed.data.newPassword, {
    update: (attributes) => recoveryClient.auth.updateUser(attributes),
    signOutGlobally: async () => {
      const { error } = await recoveryClient.auth.signOut({ scope: "global" });
      if (error) throw error;
    },
    clearLocalState: clearRecoveryCookies
  });
  if (result.error) {
    if (result.error.includes("invalid or has expired")) {
      await clearRecoveryCookies();
    }
    return result;
  }

  await clearRecoveryCookies();
  const cookieStore = await cookies();
  clearAppCookie(cookieStore, DEMO_TOKEN_COOKIE);
  clearAppCookie(cookieStore, RECOVERY_INTENT_COOKIE_NAME);
  try {
    const normalClient = await createClient();
    await normalClient.auth.signOut({ scope: "local" });
  } catch {
    // The isolated recovery credentials are already cleared. This only removes
    // a pre-existing ordinary session from the current browser when present.
  }
  redirect(buildAppUrl("/login?password_reset=success"));
}

export async function cancelPasswordRecoveryAction() {
  try {
    const recoveryClient = await createWritableRecoveryClient();
    await recoveryClient.auth.signOut({ scope: "local" });
  } catch {
    // Continue with explicit cookie cleanup.
  }
  await clearRecoveryCookies();
  const cookieStore = await cookies();
  clearAppCookie(cookieStore, DEMO_TOKEN_COOKIE);
  try {
    const normalClient = await createClient();
    await normalClient.auth.signOut({ scope: "local" });
  } catch {
    // Returning to sign in must still work when Supabase is unavailable.
  }
  redirect(buildAppUrl("/login"));
}

export async function changePasswordAction(
  _state: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  const parsed = changePasswordSchema.safeParse({
    currentPassword: formData.get("currentPassword"),
    newPassword: formData.get("newPassword"),
    confirmPassword: formData.get("confirmPassword")
  });
  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message || "Check your password details." };
  }

  const cookieStore = await cookies();
  if (cookieStore.has(DEMO_TOKEN_COOKIE)) {
    return { error: DEMO_PASSWORD_CHANGE_MESSAGE };
  }
  if (cookieStore.has(RECOVERY_INTENT_COOKIE_NAME)) {
    return { error: "Finish or cancel password recovery before changing your password." };
  }

  let account: Awaited<ReturnType<typeof getCurrentUser>>;
  try {
    account = await getCurrentUser();
  } catch {
    return { error: "Password changes are temporarily unavailable." };
  }
  if (!account) return { error: "Your session has expired. Please sign in again." };
  if (account.is_demo) return { error: DEMO_PASSWORD_CHANGE_MESSAGE };
  if (account.account_status !== "active") {
    return { error: "Password changes are available only for active accounts." };
  }

  let supabase: Awaited<ReturnType<typeof createClient>>;
  try {
    supabase = await createClient();
  } catch {
    return { error: "Password changes are temporarily unavailable." };
  }
  const {
    data: { user },
    error: userError
  } = await supabase.auth.getUser();
  if (userError || !user) {
    return { error: "Your session has expired. Please sign in again." };
  }

  const result = await updateAuthenticatedPassword(
    parsed.data.currentPassword,
    parsed.data.newPassword,
    {
      update: (attributes) => supabase.auth.updateUser(attributes),
      signOutGlobally: async () => {
        const { error } = await supabase.auth.signOut({ scope: "global" });
        if (error) throw error;
      },
      clearLocalState: clearRecoveryCookies,
      isDemo: account.is_demo
    }
  );
  if (!result.success) return result;

  try {
    // Guarantee that this browser loses its ordinary session even if remote
    // global revocation returned an error after the password was updated.
    await supabase.auth.signOut({ scope: "local" });
  } catch {
    // The server-side auth cookie adapter normally clears local state as part
    // of global sign-out; recovery/demo cookies are still removed explicitly.
  }
  clearAppCookie(cookieStore, DEMO_TOKEN_COOKIE);
  await clearRecoveryCookies();
  redirect(buildAppUrl("/login?password_changed=success"));
}

export async function demoAction() {
  const result = await createDemoSession();
  if (result.error) {
    redirect(buildAppUrl(`/login?error=${encodeURIComponent(result.error.error_code || "DEMO_UNAVAILABLE")}`));
  }
  redirect(buildAppUrl("/dashboard"));
}

export async function logoutAction() {
  await clearAuthenticationSession();
  redirect(buildAppUrl("/"));
}
