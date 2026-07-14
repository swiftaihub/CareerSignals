import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getServerAuthorization } from "@/lib/auth";
import { GET } from "@/app/api/backend/[...path]/route";

vi.mock("@/lib/auth", () => ({
  getServerAuthorization: vi.fn()
}));

beforeEach(() => {
  vi.stubEnv("API_BASE_URL", "https://api.example");
  vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/careersignals");
  vi.mocked(getServerAuthorization).mockResolvedValue("Bearer test-token");
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

function request() {
  return new NextRequest(
    "https://jobs.example/careersignals/api/backend/api/jobs?page=2"
  );
}

const context = { params: Promise.resolve({ path: ["api", "jobs"] }) };

describe("authenticated BFF response policy", () => {
  it("forwards allowlisted requests but never relays backend cookies", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", {
      status: 200,
      headers: {
        "content-type": "application/json",
        "set-cookie": "backend-session=unsafe; Path=/"
      }
    })));

    const response = await GET(request(), context);

    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(fetch).toHaveBeenCalledWith(
      new URL("https://api.example/api/jobs?page=2"),
      expect.objectContaining({ redirect: "manual" })
    );
  });

  it("rewrites safe backend redirects through the base-aware BFF", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, {
      status: 307,
      headers: { location: "https://api.example/api/jobs/job-1" }
    })));

    const response = await GET(request(), context);

    expect(response.status).toBe(307);
    expect(response.headers.get("location"))
      .toBe("/careersignals/api/backend/api/jobs/job-1");
  });

  it("fails closed on an external backend redirect", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, {
      status: 302,
      headers: { location: "https://evil.example/collect" }
    })));

    const response = await GET(request(), context);

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toMatchObject({
      error_code: "UPSTREAM_REDIRECT_REJECTED"
    });
  });
});
