import { describe, expect, it } from "vitest";

import {
  buildAppUrl,
  buildAuthCallbackUrl,
  getAppUrl,
  getBasePath,
  getCookiePath,
  getSiteOrigin,
  sanitizeInternalRedirect,
  stripBasePath,
  withBasePath
} from "./app-path";

describe("application URL configuration", () => {
  it("separates the trusted origin from the optional base path", () => {
    expect(getSiteOrigin(" https://jobs.swiftaihub.com ", "production"))
      .toBe("https://jobs.swiftaihub.com");
    expect(getSiteOrigin("http://localhost:3000", "production"))
      .toBe("http://localhost:3000");
    expect(getBasePath(" /careersignals ")).toBe("/careersignals");
    expect(getBasePath("/")).toBe("");
    expect(getAppUrl("https://jobs.swiftaihub.com", "/careersignals"))
      .toBe("https://jobs.swiftaihub.com/careersignals");
  });

  it("rejects ambiguous origins and base paths", () => {
    expect(() => getSiteOrigin("https://jobs.swiftaihub.com/careersignals", "production"))
      .toThrow(/must not contain a path/i);
    expect(() => getSiteOrigin("http://jobs.swiftaihub.com", "production"))
      .toThrow(/HTTPS in production/i);
    expect(() => getSiteOrigin("https://user:pass@jobs.swiftaihub.com", "production"))
      .toThrow(/credentials/i);
    expect(() => getBasePath("careersignals")).toThrow();
    expect(() => getBasePath("/careersignals/")).toThrow();
    expect(() => getBasePath("//careersignals")).toThrow();
    expect(() => getBasePath("/careersignals/../admin")).toThrow();
  });
});

describe("base-path helpers", () => {
  it("prefixes native URLs exactly once and supports an empty base path", () => {
    expect(withBasePath("/api/backend/api/me", "/careersignals"))
      .toBe("/careersignals/api/backend/api/me");
    expect(withBasePath("/careersignals/api/backend/api/me", "/careersignals"))
      .toBe("/careersignals/api/backend/api/me");
    expect(withBasePath("/", "/careersignals")).toBe("/careersignals");
    expect(withBasePath("/jobs?page=2#results", ""))
      .toBe("/jobs?page=2#results");
  });

  it("strips only a complete configured prefix", () => {
    expect(stripBasePath("/careersignals/jobs?page=2", "/careersignals"))
      .toBe("/jobs?page=2");
    expect(stripBasePath("/careersignals", "/careersignals")).toBe("/");
    expect(stripBasePath("/careersignals-other/jobs", "/careersignals"))
      .toBe("/careersignals-other/jobs");
  });

  it("scopes cookies to the application mount", () => {
    expect(getCookiePath("/careersignals")).toBe("/careersignals");
    expect(getCookiePath("")).toBe("/");
  });
});

describe("internal redirects", () => {
  it("builds an absolute application URL with exactly one base path", () => {
    expect(buildAppUrl(
      "/careersignals/dashboard?from=login",
      "https://jobs.swiftaihub.com",
      "/careersignals"
    )).toBe("https://jobs.swiftaihub.com/careersignals/dashboard?from=login");
    expect(buildAppUrl(
      "/",
      "https://jobs.swiftaihub.com",
      "/careersignals"
    )).toBe("https://jobs.swiftaihub.com/careersignals");
  });

  it("normalizes logical and base-prefixed inputs without double-prefixing", () => {
    expect(sanitizeInternalRedirect("/jobs?page=2#results", "/dashboard", "/careersignals"))
      .toBe("/jobs?page=2#results");
    expect(sanitizeInternalRedirect("/careersignals/jobs?page=2", "/dashboard", "/careersignals"))
      .toBe("/jobs?page=2");
  });

  it("rejects external, protocol-relative, and backslash redirects", () => {
    expect(sanitizeInternalRedirect("https://evil.example", "/dashboard", "/careersignals"))
      .toBe("/dashboard");
    expect(sanitizeInternalRedirect("//evil.example", "/dashboard", "/careersignals"))
      .toBe("/dashboard");
    expect(sanitizeInternalRedirect("/\\evil.example", "/dashboard", "/careersignals"))
      .toBe("/dashboard");
  });

  it("builds a trusted base-aware auth callback with a logical next route", () => {
    expect(buildAuthCallbackUrl(
      "/careersignals/reset-password",
      "https://jobs.swiftaihub.com",
      "/careersignals"
    )).toBe(
      "https://jobs.swiftaihub.com/careersignals/auth/callback?next=%2Freset-password"
    );
  });
});
