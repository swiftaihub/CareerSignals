import { afterEach, describe, expect, it, vi } from "vitest";

import {
  backendPathFromSegments,
  safeBackendRedirectLocation
} from "./backend-policy";

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

describe("safeBackendRedirectLocation", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("rewrites an allowlisted backend redirect through the base-aware BFF", () => {
    vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/careersignals");
    expect(safeBackendRedirectLocation(
      "https://api.example/api/jobs/job-1?page=2",
      "https://api.example"
    )).toBe("/careersignals/api/backend/api/jobs/job-1?page=2");
  });

  it("rejects cross-origin, non-allowlisted, and traversal redirects", () => {
    expect(safeBackendRedirectLocation(
      "https://evil.example/api/jobs/job-1",
      "https://api.example"
    )).toBeNull();
    expect(safeBackendRedirectLocation("/api/auth/login", "https://api.example"))
      .toBeNull();
    expect(safeBackendRedirectLocation("/api/jobs/%2e%2e/admin", "https://api.example"))
      .toBeNull();
  });
});
