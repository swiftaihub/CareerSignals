import { afterEach, describe, expect, it, vi } from "vitest";

import { getDashboardSummary } from "@/lib/api-client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getDashboardSummary", () => {
  it("requests one bounded history window without accepting a tenant override", async () => {
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
});
