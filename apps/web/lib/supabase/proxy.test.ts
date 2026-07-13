import { createServerClient } from "@supabase/ssr";
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createRecoveryIntent,
  RECOVERY_AUTH_COOKIE_NAME,
  RECOVERY_INTENT_COOKIE_NAME
} from "../password-recovery";
import { updateSession } from "./proxy";

vi.mock("@supabase/ssr", () => ({
  createServerClient: vi.fn()
}));

const SECRET = "proxy-recovery-secret-with-at-least-32-bytes";
const identity = { userId: "user-123", sessionId: "session-123" };
const accessToken = [
  Buffer.from(JSON.stringify({ alg: "none" })).toString("base64url"),
  Buffer.from(JSON.stringify({ session_id: identity.sessionId })).toString("base64url"),
  "signature"
].join(".");

function recoveryAuth() {
  return {
    getSession: vi.fn().mockResolvedValue({
      data: { session: { access_token: accessToken } },
      error: null
    }),
    getUser: vi.fn().mockResolvedValue({
      data: { user: { id: identity.userId } },
      error: null
    }),
    signOut: vi.fn().mockResolvedValue({ error: null })
  };
}

async function request(pathname: string, includeIntent = true) {
  const cookies = [`${RECOVERY_AUTH_COOKIE_NAME}=serialized-session`];
  if (includeIntent) {
    cookies.push(
      `${RECOVERY_INTENT_COOKIE_NAME}=${await createRecoveryIntent(identity, SECRET)}`
    );
  }
  return new NextRequest(`https://app.example/careersignals${pathname}`, {
    headers: { cookie: cookies.join("; ") }
  });
}

beforeEach(() => {
  process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  process.env.NEXT_PUBLIC_SITE_ORIGIN = "https://app.example";
  process.env.NEXT_PUBLIC_BASE_PATH = "/careersignals";
  process.env.PASSWORD_RECOVERY_COOKIE_SECRET = SECRET;
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("recovery session proxy isolation", () => {
  it("writes refreshed ordinary sessions at the app path and expires a legacy root copy", async () => {
    vi.mocked(createServerClient).mockImplementation(((
      _url: string,
      _key: string,
      options: {
        cookies: {
          setAll: (values: Array<{
            name: string;
            value: string;
            options: { path: string; maxAge: number };
          }>) => void;
        };
      }
    ) => ({
      auth: {
        getUser: vi.fn().mockImplementation(async () => {
          options.cookies.setAll([{
            name: "sb-project-auth-token",
            value: "fresh-session",
            options: { path: "/", maxAge: 3600 }
          }]);
          return { data: { user: { id: identity.userId } }, error: null };
        })
      }
    })) as never);
    const ordinaryRequest = new NextRequest("https://app.example/careersignals/dashboard", {
      headers: { cookie: "sb-project-auth-token=legacy-session" }
    });

    const response = await updateSession(ordinaryRequest);
    const setCookies = response.headers.getSetCookie();

    expect(setCookies.some((cookie) => (
      cookie.includes("sb-project-auth-token=fresh-session")
      && cookie.includes("Path=/careersignals")
      && cookie.includes("HttpOnly")
    ))).toBe(true);
    expect(setCookies.some((cookie) => (
      cookie.includes("sb-project-auth-token=")
      && cookie.includes("Path=/;")
      && cookie.includes("Max-Age=0")
    ))).toBe(true);
  });

  it("allows reset routes but redirects Dashboard access to password reset", async () => {
    vi.mocked(createServerClient).mockReturnValue({ auth: recoveryAuth() } as never);

    const allowed = await updateSession(await request("/reset-password"));
    const blocked = await updateSession(await request("/dashboard"));

    expect(allowed.status).toBe(200);
    expect(allowed.headers.get("cache-control")).toContain("no-store");
    expect(blocked.status).toBe(303);
    expect(blocked.headers.get("location"))
      .toBe("https://app.example/careersignals/reset-password");
  });

  it("fails closed and clears recovery auth when intent is missing", async () => {
    const auth = recoveryAuth();
    vi.mocked(createServerClient).mockReturnValue({ auth } as never);

    const response = await updateSession(await request("/reset-password", false));

    expect(response.status).toBe(303);
    expect(response.headers.get("location"))
      .toBe("https://app.example/careersignals/forgot-password?recovery_error=invalid_or_expired");
    expect(auth.signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(response.headers.get("set-cookie")).toContain(`${RECOVERY_AUTH_COOKIE_NAME}=`);
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
    expect(response.headers.get("set-cookie")).toContain("Path=/careersignals");
    expect(response.headers.getSetCookie().some((cookie) => (
      cookie.includes(`Path=/;`)
      && cookie.includes(`${RECOVERY_AUTH_COOKIE_NAME}=`)
      && cookie.includes("Max-Age=0")
    ))).toBe(true);
  });

  it("fails closed when Supabase configuration is unavailable", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;

    const response = await updateSession(await request("/dashboard"));

    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toContain("no-store");
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
    expect(createServerClient).not.toHaveBeenCalled();
  });
});
