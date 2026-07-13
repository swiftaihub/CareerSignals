import { describe, expect, it } from "vitest";

import { safeExternalHttpUrl } from "./external-url";

describe("external job URLs", () => {
  it("allows explicit HTTP(S) destinations", () => {
    expect(safeExternalHttpUrl("https://jobs.example/role?id=1"))
      .toBe("https://jobs.example/role?id=1");
    expect(safeExternalHttpUrl("http://jobs.example/role"))
      .toBe("http://jobs.example/role");
  });

  it("rejects executable, relative, credentialed, and malformed URLs", () => {
    expect(safeExternalHttpUrl("javascript:alert(1)")).toBeNull();
    expect(safeExternalHttpUrl("data:text/html,unsafe")).toBeNull();
    expect(safeExternalHttpUrl("/internal/path")).toBeNull();
    expect(safeExternalHttpUrl("https://user:pass@jobs.example/role")).toBeNull();
    expect(safeExternalHttpUrl("https:\\evil.example")).toBeNull();
  });
});
