import { describe, expect, it } from "vitest";

import { backendPathFromSegments } from "./backend-policy";

describe("backendPathFromSegments", () => {
  it("allows only the application API surface exposed through the BFF", () => {
    expect(backendPathFromSegments(["api", "me"])).toBe("/api/me");
    expect(backendPathFromSegments(["api", "jobs", "job id"])).toBe("/api/jobs/job%20id");
    expect(backendPathFromSegments(["api", "preferences", "preview"])).toBe("/api/preferences/preview");
    expect(backendPathFromSegments(["api", "preferences", "history", "12", "restore"]))
      .toBe("/api/preferences/history/12/restore");
    expect(backendPathFromSegments(["api", "admin", "users"])).toBe("/api/admin/users");
  });

  it("blocks authentication, deprecated operations, and arbitrary paths", () => {
    expect(backendPathFromSegments(["api", "auth", "demo-session"])).toBeNull();
    expect(backendPathFromSegments(["api", "dbt", "run"])).toBeNull();
    expect(backendPathFromSegments(["api", "pipeline", "run"])).toBeNull();
    expect(backendPathFromSegments(["api", "internal", "refresh"])).toBeNull();
  });

  it("rejects ambiguous or unsafe path segments", () => {
    expect(backendPathFromSegments(["api", "jobs", ".."])).toBeNull();
    expect(backendPathFromSegments(["api", "jobs", "nested/id"])).toBeNull();
    expect(backendPathFromSegments(["api", "jobs", "nested\\id"])).toBeNull();
    expect(backendPathFromSegments([])).toBeNull();
  });
});
