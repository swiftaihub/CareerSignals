import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest, getDashboardSummary } from "@/lib/api-client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("getDashboardSummary", () => {
  it("requests one bounded history window without accepting a tenant override", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({})
    });
    vi.stubGlobal("fetch", fetchMock);

    await getDashboardSummary(30);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/backend/api/dashboard/summary?days=30");
    expect(String(url)).not.toContain("user_uuid");
    expect(options).toMatchObject({ credentials: "same-origin", cache: "no-store" });
  });

  it("prefixes the same-origin BFF when the app has a base path", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/careersignals");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({})
    });
    vi.stubGlobal("fetch", fetchMock);

    await getDashboardSummary(30);

    expect(fetchMock.mock.calls[0]?.[0])
      .toBe("/careersignals/api/backend/api/dashboard/summary?days=30");
  });

  it("redirects auth failures within the base path using a logical next route", async () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/careersignals");
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: {
        pathname: "/careersignals/jobs",
        search: "?page=2",
        hash: "",
        assign
      }
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Sign in required." })
    }));

    await expect(apiRequest("/api/jobs")).rejects.toMatchObject({ status: 401 });

    expect(assign).toHaveBeenCalledWith(
      "/careersignals/login?next=%2Fjobs%3Fpage%3D2"
    );
  });
});
