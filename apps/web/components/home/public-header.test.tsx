// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/app/(auth)/actions", () => ({
  demoAction: vi.fn()
}));

import { PublicHeader } from "./public-header";

const originalBasePath = process.env.NEXT_PUBLIC_BASE_PATH;

beforeEach(() => {
  process.env.NEXT_PUBLIC_BASE_PATH = "/careersignals";
});

afterEach(() => {
  cleanup();
  if (originalBasePath === undefined) delete process.env.NEXT_PUBLIC_BASE_PATH;
  else process.env.NEXT_PUBLIC_BASE_PATH = originalBasePath;
});

describe("public header navigation", () => {
  it("links pricing-page controls to the base-path home page", () => {
    render(<PublicHeader />);

    expect(screen.getByRole("link", { name: "CareerSignals home" }))
      .toHaveAttribute("href", "/careersignals");
    expect(screen.getByRole("link", { name: "How it works" }))
      .toHaveAttribute("href", "/careersignals#how-it-works");
  });
});
