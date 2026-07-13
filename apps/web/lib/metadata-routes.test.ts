import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import manifest from "@/app/manifest";
import robots from "@/app/robots";
import sitemap from "@/app/sitemap";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_SITE_ORIGIN", "https://jobs.swiftaihub.com");
  vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/careersignals");
});

afterEach(() => vi.unstubAllEnvs());

describe("base-aware metadata routes", () => {
  it("emits canonical sitemap URLs under the application mount", () => {
    expect(sitemap().map((entry) => entry.url)).toEqual([
      "https://jobs.swiftaihub.com/careersignals",
      "https://jobs.swiftaihub.com/careersignals/pricing"
    ]);
  });

  it("keeps crawler rules and the manifest inside the base path", () => {
    const robotRules = robots();
    expect(robotRules.sitemap)
      .toBe("https://jobs.swiftaihub.com/careersignals/sitemap.xml");
    expect(robotRules.rules).toMatchObject({
      allow: "/careersignals",
      disallow: expect.arrayContaining([
        "/careersignals/api",
        "/careersignals/dashboard"
      ])
    });
    expect(manifest()).toMatchObject({
      id: "/careersignals",
      start_url: "/careersignals",
      scope: "/careersignals/"
    });
  });
});
