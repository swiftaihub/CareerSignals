import { describe, expect, it } from "vitest";

import { safeRedirectPath } from "./navigation";

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
