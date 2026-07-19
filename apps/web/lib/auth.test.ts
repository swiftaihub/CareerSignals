import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  cookieGet: vi.fn(),
  getSession: vi.fn(async () => ({ data: { session: null } }))
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: mocks.cookieGet }))
}));

vi.mock("@/lib/supabase/server", () => ({
  createClient: vi.fn(async () => ({
    auth: {
      getSession: mocks.getSession,
      getUser: vi.fn()
    }
  }))
}));

vi.mock("@/lib/backend", () => ({
  backendFetch: vi.fn()
}));

import { getServerAuthorization } from "./auth";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getSession.mockResolvedValue({ data: { session: null } });
});

describe("demo authorization cookie migration", () => {
  it("authorizes the current demo cookie", async () => {
    mocks.cookieGet.mockImplementation((name: string) => (
      name === "careersignals-demo-token-v2" ? { value: "current-token" } : undefined
    ));

    await expect(getServerAuthorization()).resolves.toBe("Demo current-token");
  });

  it("ignores the retired demo cookie so a stale demo session cannot persist", async () => {
    mocks.cookieGet.mockImplementation((name: string) => (
      name === "careersignals-demo-token" ? { value: "retired-token" } : undefined
    ));

    await expect(getServerAuthorization()).resolves.toBeNull();
    expect(mocks.getSession).toHaveBeenCalledOnce();
  });
});
