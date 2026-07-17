import "server-only";

import { cookies } from "next/headers";

import { DEMO_TOKEN_COOKIE } from "@/lib/auth";
import { clearAppCookie } from "@/lib/cookie-policy";
import { RECOVERY_INTENT_COOKIE_NAME } from "@/lib/password-recovery";
import { clearRecoveryCookies } from "@/lib/password-recovery-server";
import { createWritableRecoveryClient } from "@/lib/supabase/recovery-server";
import { createWritableClient } from "@/lib/supabase/server";

/** Clear browser-local authentication state without depending on remote revocation. */
export async function clearAuthenticationSession() {
  try {
    const supabase = await createWritableClient();
    await supabase.auth.signOut({ scope: "local" });
  } catch {
    // Explicit cookie cleanup below still guarantees Demo/recovery logout.
  }
  try {
    const recoveryClient = await createWritableRecoveryClient();
    await recoveryClient.auth.signOut({ scope: "local" });
  } catch {
    // Recovery cookies are also removed explicitly below.
  }
  try {
    await clearRecoveryCookies();
  } catch {
    // Continue clearing the ordinary application-scoped cookies.
  }
  const cookieStore = await cookies();
  clearAppCookie(cookieStore, DEMO_TOKEN_COOKIE);
  clearAppCookie(cookieStore, RECOVERY_INTENT_COOKIE_NAME);
}
