"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { z } from "zod";

import { DEMO_TOKEN_COOKIE } from "@/lib/auth";
import { backendFetch, readBackendError } from "@/lib/backend";
import { safeRedirectPath } from "@/lib/navigation";
import { createClient } from "@/lib/supabase/server";

export interface AuthActionState {
  error?: string;
  errorCode?: string;
}

const loginSchema = z.object({
  identifier: z.string().trim().min(1, "Enter your username or email."),
  password: z.string()
});

const registerSchema = z.object({
  username: z.string().trim().min(3).max(32).regex(/^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,31}$/, "Start with a letter or number; then use letters, numbers, dots, dashes, or underscores."),
  email: z.email(),
  password: z.string().min(10, "Password must be at least 10 characters.")
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
  } catch {
    // Demo authentication is issued and verified by FastAPI, independently of Supabase.
  }
  cookieStore.set(DEMO_TOKEN_COOKIE, payload.demo_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
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
    redirect(safeRedirectPath(formData.get("next")));
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
  (await cookies()).delete(DEMO_TOKEN_COOKIE);
  redirect(safeRedirectPath(formData.get("next")));
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
  redirect("/pending?registered=1");
}

export async function demoAction() {
  const result = await createDemoSession();
  if (result.error) {
    redirect(`/login?error=${encodeURIComponent(result.error.error_code || "DEMO_UNAVAILABLE")}`);
  }
  redirect("/dashboard");
}

export async function logoutAction() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  (await cookies()).delete(DEMO_TOKEN_COOKIE);
  redirect("/");
}
