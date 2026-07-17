import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  clearAuthenticationSession: vi.fn(async () => undefined)
}));

vi.mock("@/lib/logout", () => ({
  clearAuthenticationSession: mocks.clearAuthenticationSession
}));

import { POST } from "./route";

describe("stable logout route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/careersignals");
    vi.stubEnv("NEXT_PUBLIC_SITE_ORIGIN", "https://jobs.swiftaihub.com");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://jmgodcrpsfmzpctstnjp.supabase.co");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("clears local auth state and redirects to the application home", async () => {
    const request = new NextRequest("https://jobs.swiftaihub.com/careersignals/auth/logout", {
      method: "POST",
      headers: {
        cookie: [
          "sb-jmgodcrpsfmzpctstnjp-auth-token=legacy",
          "careersignals-demo-token-v2=current-demo",
          "careersignals-demo-token=legacy-demo"
        ].join("; "),
        origin: "https://jobs.swiftaihub.com"
      }
    });

    const response = await POST(request);

    expect(mocks.clearAuthenticationSession).toHaveBeenCalledOnce();
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe(
      "https://jobs.swiftaihub.com/careersignals"
    );
    expect(response.headers.get("cache-control")).toBe("private, no-store, max-age=0");
    const setCookies = response.headers.getSetCookie().join("\n");
    expect(setCookies).toContain(
      "sb-jmgodcrpsfmzpctstnjp-auth-token=; Path=/;"
    );
    expect(setCookies).toContain(
      "careersignals-demo-token-v2=; Path=/careersignals;"
    );
    expect(setCookies).toContain(
      "careersignals-demo-token-v2=; Path=/;"
    );
    expect(setCookies).toContain(
      "careersignals-demo-token=; Path=/careersignals;"
    );
    expect(setCookies).toContain(
      "careersignals-demo-token=; Path=/;"
    );
  });

  it("rejects a cross-origin logout submission", async () => {
    const request = new NextRequest("https://jobs.swiftaihub.com/careersignals/auth/logout", {
      method: "POST",
      headers: { origin: "https://attacker.invalid" }
    });

    const response = await POST(request);

    expect(response.status).toBe(403);
    expect(mocks.clearAuthenticationSession).not.toHaveBeenCalled();
  });
});
