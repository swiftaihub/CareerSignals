import "server-only";

import { cookies } from "next/headers";

import { backendFetch } from "@/lib/backend";
import { DEMO_TOKEN_COOKIE } from "@/lib/demo-cookie";
import { createClient } from "@/lib/supabase/server";
import type { CurrentUser } from "@/lib/types";

export { DEMO_TOKEN_COOKIE } from "@/lib/demo-cookie";

export async function getServerAuthorization(): Promise<string | null> {
  const cookieStore = await cookies();
  const demoToken = cookieStore.get(DEMO_TOKEN_COOKIE)?.value;
  if (demoToken) {
    return `Demo ${demoToken}`;
  }

  const supabase = await createClient();
  const {
    data: { session }
  } = await supabase.auth.getSession();

  if (session?.access_token) {
    const { error } = await supabase.auth.getUser();
    if (!error) {
      return `Bearer ${session.access_token}`;
    }
  }

  return null;
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const authorization = await getServerAuthorization();
  if (!authorization) {
    return null;
  }

  try {
    const response = await backendFetch("/api/me", {
      headers: { Authorization: authorization }
    });
    if (!response.ok) {
      return null;
    }
    return response.json() as Promise<CurrentUser>;
  } catch {
    return null;
  }
}
