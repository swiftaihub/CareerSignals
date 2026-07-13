import { describe, expect, it } from "vitest";

import { getBackendBaseUrl } from "./backend";

describe("backend origin configuration", () => {
  it("uses a local default only outside production", () => {
    expect(getBackendBaseUrl(null, "development")).toBe("http://localhost:8000");
    expect(() => getBackendBaseUrl(null, "production")).toThrow(/configured/i);
  });

  it("requires a credential-free HTTPS origin in production", () => {
    expect(getBackendBaseUrl("https://api.example/", "production"))
      .toBe("https://api.example");
    expect(getBackendBaseUrl("http://localhost:8000", "production"))
      .toBe("http://localhost:8000");
    expect(() => getBackendBaseUrl("http://api.example", "production"))
      .toThrow(/HTTPS/i);
    expect(() => getBackendBaseUrl("https://user:pass@api.example", "production"))
      .toThrow();
    expect(() => getBackendBaseUrl("https://api.example/v1", "production"))
      .toThrow(/without credentials or a path/i);
  });
});
