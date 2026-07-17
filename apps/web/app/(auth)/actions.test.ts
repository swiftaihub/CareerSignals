import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const redirect = vi.fn((destination: string): never => {
    throw new Error(`NEXT_REDIRECT:${destination}`);
  });
  const cookieStore = {
    has: vi.fn(() => false),
    set: vi.fn()
  };
  const ordinaryClient = {
    auth: {
      setSession: vi.fn(async () => ({ error: null })),
      signOut: vi.fn(async () => ({ error: null }))
    }
  };
  const recoveryClient = {
    auth: {
      signOut: vi.fn(async () => ({ error: null }))
    }
  };
  return {
    backendFetch: vi.fn(),
    clearRecoveryCookies: vi.fn(async () => undefined),
    cookieStore,
    createClient: vi.fn(async () => ordinaryClient),
    createRecoveryClient: vi.fn(async () => recoveryClient),
    ordinaryClient,
    recoveryClient,
    redirect
  };
});

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => mocks.cookieStore)
}));

vi.mock("next/navigation", () => ({
  redirect: mocks.redirect
}));

vi.mock("@/lib/auth", () => ({
  DEMO_TOKEN_COOKIE: "careersignals-demo-token",
  getCurrentUser: vi.fn()
}));

vi.mock("@/lib/backend", () => ({
  backendFetch: mocks.backendFetch,
  readBackendError: vi.fn()
}));

vi.mock("@/lib/password-recovery-server", () => ({
  clearRecoveryCookies: mocks.clearRecoveryCookies,
  getRecoveryIntentSecret: vi.fn(),
  readRecoverySession: vi.fn()
}));

vi.mock("@/lib/supabase/recovery-server", () => ({
  createWritableRecoveryClient: mocks.createRecoveryClient
}));

vi.mock("@/lib/supabase/server", () => ({
  createWritableClient: mocks.createClient
}));

import { loginAction, logoutAction } from "./actions";

describe("auth server-action redirects", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/careersignals");
    mocks.backendFetch.mockResolvedValue(new Response(JSON.stringify({
      access_token: "access-token",
      refresh_token: "refresh-token"
    }), {
      status: 200,
      headers: { "content-type": "application/json" }
    }));
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("gives Next a logical post-login route when next already includes the base path", async () => {
    const formData = new FormData();
    formData.set("identifier", "career-user");
    formData.set("password", "correct-password");
    formData.set("next", "/careersignals/dashboard");

    await expect(loginAction({}, formData)).rejects.toThrow("NEXT_REDIRECT");

    expect(mocks.redirect).toHaveBeenCalledWith("/dashboard");
  });

  it("gives Next the logical home route after logout", async () => {
    await expect(logoutAction()).rejects.toThrow("NEXT_REDIRECT");

    expect(mocks.redirect).toHaveBeenCalledWith("/");
  });
});
