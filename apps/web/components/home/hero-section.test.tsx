// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/app/(auth)/actions", () => ({
  demoAction: vi.fn()
}));

vi.mock("next/image", () => ({
  default: () => <div />
}));

import { HeroSection } from "./hero-section";

afterEach(cleanup);

describe("homepage hero", () => {
  it("offers a small scroll cue to the next homepage section", () => {
    render(<HeroSection />);

    expect(screen.getByRole("link", { name: "Scroll to explore more" }))
      .toHaveAttribute("href", "#why-careersignals");
  });
});
