import "server-only";

import type { Session, SupabaseClient, User } from "@supabase/supabase-js";
import { cookies } from "next/headers";

import { clearAppCookie } from "@/lib/cookie-policy";
import {
  extractSessionId,
  isRecoveryIntentSecretConfigured,
  isRecoveryAuthCookieName,
  RECOVERY_INTENT_COOKIE_NAME,
  type RecoveryIntentIdentity,
  verifyRecoveryIntent
} from "@/lib/password-recovery";
import { createRecoveryClient } from "@/lib/supabase/recovery-server";

export interface ValidRecoverySession {
  valid: true;
  client: SupabaseClient;
  identity: RecoveryIntentIdentity;
  session: Session;
  user: User;
}

export interface InvalidRecoverySession {
  valid: false;
  reason: "configuration" | "intent" | "session";
}

export type RecoverySessionState = ValidRecoverySession | InvalidRecoverySession;

export function getRecoveryIntentSecret() {
  const secret = process.env.PASSWORD_RECOVERY_COOKIE_SECRET;
  return isRecoveryIntentSecretConfigured(secret) ? secret : null;
}

export async function readRecoverySession(
  client: SupabaseClient | null = null
): Promise<RecoverySessionState> {
  const secret = getRecoveryIntentSecret();
  if (!secret) return { valid: false, reason: "configuration" };

  const cookieStore = await cookies();
  const intent = cookieStore.get(RECOVERY_INTENT_COOKIE_NAME)?.value;
  if (!intent) return { valid: false, reason: "intent" };

  const recoveryClient = client ?? await createRecoveryClient();
  const {
    data: { session },
    error: sessionError
  } = await recoveryClient.auth.getSession();
  if (sessionError || !session) return { valid: false, reason: "session" };

  const {
    data: { user },
    error: userError
  } = await recoveryClient.auth.getUser();
  const sessionId = extractSessionId(session.access_token);
  if (userError || !user || !sessionId) return { valid: false, reason: "session" };

  const identity = { userId: user.id, sessionId };
  if (!await verifyRecoveryIntent(intent, identity, secret)) {
    return { valid: false, reason: "intent" };
  }

  return { valid: true, client: recoveryClient, identity, session, user };
}

export async function clearRecoveryCookies() {
  const cookieStore = await cookies();
  clearAppCookie(cookieStore, RECOVERY_INTENT_COOKIE_NAME);
  cookieStore.getAll().forEach(({ name }) => {
    if (isRecoveryAuthCookieName(name)) clearAppCookie(cookieStore, name);
  });
}
