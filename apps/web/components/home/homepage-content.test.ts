import { describe, expect, it } from "vitest";

import {
  DEMO_PREVIEW_LABEL,
  HOME_ROUTES,
  HOW_IT_WORKS_STEPS,
  PRODUCT_CAPABILITIES,
  TRUST_INDICATORS
} from "./home-content";

describe("public homepage content contracts", () => {
  it("preserves the public authentication and product routes", () => {
    expect(HOME_ROUTES).toEqual({
      home: "/",
      howItWorks: "/#how-it-works",
      register: "/register",
      login: "/login",
      pricing: "/pricing",
      dashboard: "/dashboard"
    });
  });

  it("labels all static product metrics as illustrative demo data", () => {
    expect(DEMO_PREVIEW_LABEL.toLowerCase()).toContain("illustrative");
    expect(DEMO_PREVIEW_LABEL.toLowerCase()).toContain("demo");
  });

  it("keeps the four-step story and daily-decision capabilities concise", () => {
    expect(HOW_IT_WORKS_STEPS).toHaveLength(4);
    expect(PRODUCT_CAPABILITIES).toHaveLength(4);
    expect(TRUST_INDICATORS).toContain("Read-only demo environment");
  });

  it("uses the CareerSignals product name consistently in public copy", () => {
    const publicCopy = JSON.stringify({ HOW_IT_WORKS_STEPS, PRODUCT_CAPABILITIES });
    expect(publicCopy).not.toMatch(/CareerSignal(?!s)/);
  });
});
