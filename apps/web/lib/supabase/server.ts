import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { getCookiePath } from "@/lib/app-path";
import { secureAppCookieOptions } from "@/lib/cookie-policy";

export async function createClient({ writable = false }: { writable?: boolean } = {}) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  if (!url || !publishableKey) {
    throw new Error("Supabase server environment variables are not configured.");
  }

  const cookieStore = await cookies();

  return createServerClient(url, publishableKey, {
    cookieOptions: {
      ...secureAppCookieOptions(),
      path: getCookiePath()
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
              ...secureAppCookieOptions(),
              path: getCookiePath()
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
          // Server Components cannot always write cookies. middleware.ts performs refresh writes.
        }
      }
    }
  });
}

export function createWritableClient() {
  return createClient({ writable: true });
}
