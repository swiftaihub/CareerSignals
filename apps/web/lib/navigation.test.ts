import { describe, expect, it } from "vitest";

import { AUTHENTICATED_NAV_ITEMS, safeRedirectPath } from "./navigation";

describe("authenticated navigation", () => {
  it("does not expose the public home page as a navigation item", () => {
    expect(AUTHENTICATED_NAV_ITEMS.map((item) => item.href)).not.toContain("/");
    expect(AUTHENTICATED_NAV_ITEMS.map((item) => item.label)).not.toContain("Home");
  });

  it("keeps the authenticated product destinations", () => {
    expect(AUTHENTICATED_NAV_ITEMS.map((item) => item.href)).toEqual([
      "/dashboard",
      "/jobs",
      "/top-matches",
      "/skill-gap",
      "/companies",
      "/settings"
    ]);
  });
});

describe("safeRedirectPath", () => {
  it("keeps local paths, queries, and fragments", () => {
    expect(safeRedirectPath("/jobs?page=2#results")).toBe("/jobs?page=2#results");
  });

  it("rejects protocol-relative, absolute, and malformed destinations", () => {
    expect(safeRedirectPath("//evil.example/path")).toBe("/dashboard");
    expect(safeRedirectPath("https://evil.example/path")).toBe("/dashboard");
    expect(safeRedirectPath(undefined)).toBe("/dashboard");
  });
});
