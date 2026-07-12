import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import {
  RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS,
  RECOVERY_AUTH_COOKIE_NAME
} from "@/lib/password-recovery";

interface RecoveryClientOptions {
  writable?: boolean;
}

/**
 * Uses an isolated cookie namespace so a password-recovery session can never
 * be mistaken for the application's ordinary authenticated session.
 */
export async function createRecoveryClient({ writable = false }: RecoveryClientOptions = {}) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  if (!url || !publishableKey) {
    throw new Error("Supabase server environment variables are not configured.");
  }

  const cookieStore = await cookies();

  return createServerClient(url, publishableKey, {
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
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        const writeCookies = () => {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, {
              ...options,
              httpOnly: true,
              secure: process.env.NODE_ENV === "production",
              sameSite: "lax",
              path: "/",
              // @supabase/ssr 0.7 otherwise persists auth cookies for 400 days.
              maxAge: !value || options.maxAge === 0
                ? 0
                : RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS
            });
          });
        };

        if (writable) {
          writeCookies();
          return;
        }

        try {
          writeCookies();
        } catch {
          // Server Components cannot write cookies. The proxy refreshes the
          // isolated recovery session before rendering the reset page.
        }
      }
    }
  });
}

export function createWritableRecoveryClient() {
  return createRecoveryClient({ writable: true });
}
